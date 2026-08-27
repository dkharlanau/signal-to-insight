#!/usr/bin/env python3
"""Run deterministic precision-oriented prior-knowledge retrieval benchmarks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from graph_context import rank, words

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "retrieval-benchmark.json"
DEFAULT_FEEDBACK = ROOT / "data" / "retrieval-negative-feedback.json"
BUNDLES = ROOT / "data" / "research-bundles"


class BenchmarkError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_feedback(path: Path = DEFAULT_FEEDBACK) -> list[dict]:
    data = load(path)
    records = data.get("records")
    if not isinstance(records, list):
        raise BenchmarkError("retrieval feedback records must be a list")

    seen: set[str] = set()
    validated: list[dict] = []
    for index, record in enumerate(records):
        where = f"feedback[{index}]"
        record_id = record.get("id")
        intake_id = record.get("intake_id")
        query = record.get("query")
        rejected = record.get("rejected_concepts")
        if not isinstance(record_id, str) or not record_id:
            raise BenchmarkError(f"{where}.id must be non-empty")
        if record_id in seen:
            raise BenchmarkError(f"duplicate feedback id: {record_id}")
        seen.add(record_id)
        if not isinstance(intake_id, str) or not intake_id:
            raise BenchmarkError(f"{where}.intake_id must be non-empty")
        if not isinstance(query, str) or not query.strip():
            raise BenchmarkError(f"{where}.query must be non-empty")
        if not isinstance(rejected, list) or not rejected or not all(isinstance(item, str) and item for item in rejected):
            raise BenchmarkError(f"{where}.rejected_concepts must be a non-empty string list")
        if len(set(rejected)) != len(rejected):
            raise BenchmarkError(f"{where}.rejected_concepts contains duplicates")

        bundle_path = BUNDLES / f"{intake_id}.json"
        if not bundle_path.exists():
            raise BenchmarkError(f"{where}: research bundle not found: {bundle_path.relative_to(ROOT)}")
        bundle = load(bundle_path)
        prior = bundle.get("prior_knowledge") or {}
        if prior.get("query") != query:
            raise BenchmarkError(f"{where}: feedback query differs from captured research-bundle query")
        match_by_id = {
            item.get("concept_id"): item
            for item in prior.get("matches", [])
            if isinstance(item, dict) and item.get("concept_id")
        }
        for concept_id in rejected:
            match = match_by_id.get(concept_id)
            if match is None:
                raise BenchmarkError(
                    f"{where}: rejected concept '{concept_id}' is absent from captured prior snapshot"
                )
            if match.get("relationship_to_source") != "not_relevant":
                raise BenchmarkError(
                    f"{where}: rejected concept '{concept_id}' is not classified not_relevant"
                )
        validated.append({
            **record,
            "query_terms": sorted(words(query)),
        })
    return validated


def feedback_suppression(query: str, records: list[dict]) -> tuple[set[str], list[dict]]:
    """Return rejected concepts from sufficiently similar historical source-time queries.

    This is intentionally conservative and experimental. It requires at least three shared
    searchable terms and 40% overlap relative to the smaller query. Exact historical queries
    therefore activate their evidence-backed negatives, while unrelated domains do not inherit
    a global blacklist.
    """
    query_terms = words(query)
    suppressed: set[str] = set()
    activations: list[dict] = []
    if not query_terms:
        return suppressed, activations

    for record in records:
        historical_terms = set(record.get("query_terms", []))
        if not historical_terms:
            continue
        overlap = query_terms & historical_terms
        denominator = max(1, min(len(query_terms), len(historical_terms)))
        coverage = len(overlap) / denominator
        if len(overlap) < 3 or coverage < 0.4:
            continue
        rejected = set(record.get("rejected_concepts", []))
        suppressed.update(rejected)
        activations.append({
            "feedback_id": record["id"],
            "overlap_terms": sorted(overlap),
            "coverage": round(coverage, 3),
            "rejected_concepts": sorted(rejected),
        })
    return suppressed, activations


def evaluate_case(
    case: dict,
    feedback_records: list[dict] | None = None,
) -> dict:
    suppressed: set[str] = set()
    activations: list[dict] = []
    if feedback_records is not None:
        suppressed, activations = feedback_suppression(case["query"], feedback_records)

    result = rank(
        case["query"],
        int(case.get("limit", 5)),
        suppressed_concepts=suppressed,
    )
    returned = [item["concept_id"] for item in result.get("matches", [])]
    required = set(case.get("required", []))
    acceptable = set(case.get("acceptable", []))
    forbidden = set(case.get("forbidden", []))
    relevant = required | acceptable

    required_found = required & set(returned)
    forbidden_found = forbidden & set(returned)
    relevant_returned = [concept_id for concept_id in returned if concept_id in relevant]
    precision = len(relevant_returned) / len(returned) if returned else 0.0
    recall = len(required_found) / len(required) if required else 1.0

    trace_failures: list[str] = []
    traces: list[dict] = []
    for match in result.get("matches", []):
        if match.get("match_type") == "lexical":
            explanation = {"type": "lexical", "matched_terms": match.get("matched_terms", [])}
            if not explanation["matched_terms"]:
                trace_failures.append(f"{match['concept_id']}: lexical result has no matched_terms")
        else:
            explanation = {"type": "graph_neighbor", "via": match.get("via", [])}
            if not explanation["via"]:
                trace_failures.append(f"{match['concept_id']}: graph neighbor has no via path")
        traces.append({"concept_id": match["concept_id"], **explanation})

    min_precision = float(case.get("min_precision", 0.0))
    failures: list[str] = []
    missing = sorted(required - required_found)
    if missing:
        failures.append(f"missing required concepts: {missing}")
    if forbidden_found:
        failures.append(f"forbidden concepts returned: {sorted(forbidden_found)}")
    if precision < min_precision:
        failures.append(f"precision {precision:.3f} < required {min_precision:.3f}")
    failures.extend(trace_failures)

    return {
        "id": case["id"],
        "classification_probe": case.get("classification_probe"),
        "query": case["query"],
        "returned": returned,
        "required_recall": round(recall, 3),
        "precision_proxy": round(precision, 3),
        "forbidden_found": sorted(forbidden_found),
        "suppressed_concepts": sorted(suppressed),
        "feedback_activations": activations,
        "traces": traces,
        "passed": not failures,
        "failures": failures,
    }


def run_benchmark(
    fixture: Path = DEFAULT_FIXTURE,
    feedback_records: list[dict] | None = None,
) -> dict:
    data = load(fixture)
    cases = data.get("cases", [])
    results = [evaluate_case(case, feedback_records=feedback_records) for case in cases]
    if results:
        macro_precision = sum(item["precision_proxy"] for item in results) / len(results)
        macro_recall = sum(item["required_recall"] for item in results) / len(results)
    else:
        macro_precision = 0.0
        macro_recall = 0.0
    return {
        "version": data.get("version"),
        "cases": results,
        "summary": {
            "case_count": len(results),
            "passed": sum(item["passed"] for item in results),
            "failed": sum(not item["passed"] for item in results),
            "forbidden_hits": sum(len(item["forbidden_found"]) for item in results),
            "feedback_activations": sum(bool(item["feedback_activations"]) for item in results),
            "macro_precision_proxy": round(macro_precision, 3),
            "macro_required_recall": round(macro_recall, 3),
        },
    }


def compare_benchmarks(fixture: Path, feedback_path: Path) -> dict:
    feedback = load_feedback(feedback_path)
    baseline = run_benchmark(fixture, feedback_records=None)
    candidate = run_benchmark(fixture, feedback_records=feedback)
    baseline_by_id = {item["id"]: item for item in baseline["cases"]}
    candidate_by_id = {item["id"]: item for item in candidate["cases"]}

    recall_regressions = [
        case_id
        for case_id, item in candidate_by_id.items()
        if item["required_recall"] < baseline_by_id[case_id]["required_recall"]
    ]
    forbidden_improvement = (
        candidate["summary"]["forbidden_hits"] < baseline["summary"]["forbidden_hits"]
    )
    precision_not_worse = (
        candidate["summary"]["macro_precision_proxy"] >= baseline["summary"]["macro_precision_proxy"]
    )
    candidate_safe = candidate["summary"]["failed"] == 0 and not recall_regressions
    adopt = candidate_safe and forbidden_improvement and precision_not_worse

    changed_cases = []
    for case_id, candidate_item in candidate_by_id.items():
        baseline_item = baseline_by_id[case_id]
        if candidate_item["returned"] != baseline_item["returned"]:
            changed_cases.append({
                "id": case_id,
                "baseline": baseline_item["returned"],
                "candidate": candidate_item["returned"],
                "suppressed": candidate_item["suppressed_concepts"],
                "baseline_forbidden": baseline_item["forbidden_found"],
                "candidate_forbidden": candidate_item["forbidden_found"],
                "baseline_recall": baseline_item["required_recall"],
                "candidate_recall": candidate_item["required_recall"],
            })

    return {
        "baseline": baseline,
        "candidate": candidate,
        "decision": {
            "adopt": adopt,
            "candidate_safe": candidate_safe,
            "forbidden_improvement": forbidden_improvement,
            "precision_not_worse": precision_not_worse,
            "recall_regressions": recall_regressions,
            "changed_cases": changed_cases,
            "rule": "Adopt only if candidate has no failed cases or required-recall regressions, reduces forbidden hits, and does not reduce macro precision proxy.",
        },
    }


def print_report(report: dict, title: str | None = None) -> None:
    if title:
        print(title)
    for item in report["cases"]:
        status = "PASS" if item["passed"] else "FAIL"
        print(
            f"{status} {item['id']}: precision={item['precision_proxy']:.3f} "
            f"required_recall={item['required_recall']:.3f} returned={','.join(item['returned'])}"
        )
        if item.get("feedback_activations"):
            ids = ",".join(entry["feedback_id"] for entry in item["feedback_activations"])
            print(f"  feedback: {ids}; suppressed={','.join(item['suppressed_concepts'])}")
        for failure in item["failures"]:
            print(f"  - {failure}")
        for trace in item["traces"]:
            if trace["type"] == "lexical":
                print(f"  trace {trace['concept_id']}: terms={','.join(trace['matched_terms'])}")
            else:
                via = ",".join(f"{hop['seed']}:{hop['type']}:{hop['direction']}" for hop in trace["via"])
                print(f"  trace {trace['concept_id']}: via={via}")
    summary = report["summary"]
    print(
        f"Summary: {summary['passed']}/{summary['case_count']} passed; "
        f"forbidden hits={summary['forbidden_hits']}; "
        f"macro precision={summary['macro_precision_proxy']:.3f}; "
        f"macro required recall={summary['macro_required_recall']:.3f}"
    )


def print_comparison(comparison: dict) -> None:
    print_report(comparison["baseline"], "=== Baseline ===")
    print()
    print_report(comparison["candidate"], "=== Feedback-aware candidate ===")
    decision = comparison["decision"]
    print()
    print(
        "Decision: "
        + ("ADOPT" if decision["adopt"] else "DO NOT ADOPT")
        + f"; candidate_safe={decision['candidate_safe']}"
        + f"; forbidden_improvement={decision['forbidden_improvement']}"
        + f"; precision_not_worse={decision['precision_not_worse']}"
        + f"; recall_regressions={','.join(decision['recall_regressions']) or 'none'}"
    )
    for item in decision["changed_cases"]:
        print(
            f"  changed {item['id']}: baseline={','.join(item['baseline'])} "
            f"candidate={','.join(item['candidate'])} suppressed={','.join(item['suppressed'])}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK)
    parser.add_argument("--compare-feedback", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if args.compare_feedback:
            comparison = compare_benchmarks(args.fixture, args.feedback)
            if args.json:
                print(json.dumps(comparison, ensure_ascii=False, indent=2))
            else:
                print_comparison(comparison)
            # Baseline is allowed to expose the measured problem. The experiment is CI-safe only
            # when the feedback candidate itself has no failed cases or recall regressions.
            return 0 if comparison["decision"]["candidate_safe"] else 1

        report = run_benchmark(args.fixture)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, BenchmarkError) as exc:
        print(f"Retrieval benchmark error: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
