#!/usr/bin/env python3
"""Run deterministic baseline-vs-candidate prior-knowledge retrieval benchmarks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from graph_context import rank

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "retrieval-benchmark.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_case(case: dict, mode: str) -> dict:
    if mode not in {"baseline", "candidate"}:
        raise ValueError(f"unknown retrieval mode: {mode}")
    candidate = mode == "candidate"
    result = rank(
        case["query"],
        int(case.get("limit", 5)),
        strict_seed_gating=candidate,
        query_relevant_bridge=candidate,
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
        "forbidden_count": len(forbidden_found),
        "traces": traces,
        "passed": not failures,
        "failures": failures,
    }


def summarize(results: list[dict]) -> dict:
    if results:
        macro_precision = sum(item["precision_proxy"] for item in results) / len(results)
        macro_recall = sum(item["required_recall"] for item in results) / len(results)
    else:
        macro_precision = 0.0
        macro_recall = 0.0
    return {
        "case_count": len(results),
        "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "macro_precision_proxy": round(macro_precision, 3),
        "macro_required_recall": round(macro_recall, 3),
        "forbidden_hits": sum(item["forbidden_count"] for item in results),
    }


def run_benchmark(fixture: Path = DEFAULT_FIXTURE) -> dict:
    data = load(fixture)
    cases = data.get("cases", [])
    baseline = [evaluate_case(case, "baseline") for case in cases]
    candidate = [evaluate_case(case, "candidate") for case in cases]
    baseline_by_id = {item["id"]: item for item in baseline}
    candidate_by_id = {item["id"]: item for item in candidate}

    recall_regressions: list[str] = []
    forbidden_regressions: list[str] = []
    precision_improvements: list[str] = []
    recall_improvements: list[str] = []
    for case in cases:
        case_id = case["id"]
        before = baseline_by_id[case_id]
        after = candidate_by_id[case_id]
        if after["required_recall"] < before["required_recall"]:
            recall_regressions.append(case_id)
        if after["forbidden_count"] > before["forbidden_count"]:
            forbidden_regressions.append(case_id)
        if after["precision_proxy"] > before["precision_proxy"]:
            precision_improvements.append(case_id)
        if after["required_recall"] > before["required_recall"]:
            recall_improvements.append(case_id)

    baseline_summary = summarize(baseline)
    candidate_summary = summarize(candidate)
    false_positive_improved = (
        candidate_summary["forbidden_hits"] < baseline_summary["forbidden_hits"]
        or candidate_summary["macro_precision_proxy"] > baseline_summary["macro_precision_proxy"]
    )
    accepted = (
        candidate_summary["failed"] == 0
        and not recall_regressions
        and not forbidden_regressions
        and candidate_summary["macro_precision_proxy"] >= baseline_summary["macro_precision_proxy"]
        and candidate_summary["macro_required_recall"] >= baseline_summary["macro_required_recall"]
        and false_positive_improved
    )

    return {
        "version": data.get("version"),
        "baseline_mode": {
            "strict_seed_gating": False,
            "query_relevant_bridge": False,
            "description": "Permissive pre-dogfood comparison: any non-zero lexical concept can seed one-hop graph expansion.",
        },
        "candidate_mode": {
            "strict_seed_gating": True,
            "query_relevant_bridge": True,
            "description": "Current deterministic ranker: strong seed gating plus second hop only through a query-relevant graph bridge.",
        },
        "baseline": {"cases": baseline, "summary": baseline_summary},
        "candidate": {"cases": candidate, "summary": candidate_summary},
        "comparison": {
            "macro_precision_delta": round(candidate_summary["macro_precision_proxy"] - baseline_summary["macro_precision_proxy"], 3),
            "macro_required_recall_delta": round(candidate_summary["macro_required_recall"] - baseline_summary["macro_required_recall"], 3),
            "forbidden_hits_delta": candidate_summary["forbidden_hits"] - baseline_summary["forbidden_hits"],
            "precision_improved_cases": precision_improvements,
            "recall_improved_cases": recall_improvements,
            "recall_regressions": recall_regressions,
            "forbidden_regressions": forbidden_regressions,
            "accepted": accepted,
        },
    }


def print_case(item: dict, prefix: str = "") -> None:
    status = "PASS" if item["passed"] else "FAIL"
    print(
        f"{prefix}{status} {item['id']}: precision={item['precision_proxy']:.3f} "
        f"required_recall={item['required_recall']:.3f} forbidden={item['forbidden_count']} "
        f"returned={','.join(item['returned'])}"
    )
    for failure in item["failures"]:
        print(f"  - {failure}")


def print_report(report: dict) -> None:
    print("Baseline — permissive lexical seeds + one graph hop")
    for item in report["baseline"]["cases"]:
        print_case(item, "  ")
    before = report["baseline"]["summary"]
    print(
        f"  Summary: precision={before['macro_precision_proxy']:.3f}; "
        f"required_recall={before['macro_required_recall']:.3f}; "
        f"forbidden_hits={before['forbidden_hits']}"
    )

    print("\nCandidate — strict seeds + query-relevant bridge")
    for item in report["candidate"]["cases"]:
        print_case(item, "  ")
    after = report["candidate"]["summary"]
    print(
        f"  Summary: {after['passed']}/{after['case_count']} passed; "
        f"precision={after['macro_precision_proxy']:.3f}; "
        f"required_recall={after['macro_required_recall']:.3f}; "
        f"forbidden_hits={after['forbidden_hits']}"
    )

    comparison = report["comparison"]
    print(
        "\nComparison: "
        f"precision_delta={comparison['macro_precision_delta']:+.3f}; "
        f"recall_delta={comparison['macro_required_recall_delta']:+.3f}; "
        f"forbidden_delta={comparison['forbidden_hits_delta']:+d}; "
        f"accepted={comparison['accepted']}"
    )
    if comparison["precision_improved_cases"]:
        print("  precision improved: " + ", ".join(comparison["precision_improved_cases"]))
    if comparison["recall_improved_cases"]:
        print("  recall improved: " + ", ".join(comparison["recall_improved_cases"]))
    if comparison["recall_regressions"]:
        print("  recall regressions: " + ", ".join(comparison["recall_regressions"]))
    if comparison["forbidden_regressions"]:
        print("  forbidden regressions: " + ", ".join(comparison["forbidden_regressions"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        report = run_benchmark(args.fixture)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Retrieval benchmark error: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 0 if report["comparison"]["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
