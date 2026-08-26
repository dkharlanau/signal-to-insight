#!/usr/bin/env python3
"""Run deterministic precision-oriented prior-knowledge retrieval benchmarks."""

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


def evaluate_case(case: dict) -> dict:
    result = rank(case["query"], int(case.get("limit", 5)))
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
        "traces": traces,
        "passed": not failures,
        "failures": failures,
    }


def run_benchmark(fixture: Path = DEFAULT_FIXTURE) -> dict:
    data = load(fixture)
    cases = data.get("cases", [])
    results = [evaluate_case(case) for case in cases]
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
            "macro_precision_proxy": round(macro_precision, 3),
            "macro_required_recall": round(macro_recall, 3),
        },
    }


def print_report(report: dict) -> None:
    for item in report["cases"]:
        status = "PASS" if item["passed"] else "FAIL"
        print(
            f"{status} {item['id']}: precision={item['precision_proxy']:.3f} "
            f"required_recall={item['required_recall']:.3f} returned={','.join(item['returned'])}"
        )
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
        f"macro precision={summary['macro_precision_proxy']:.3f}; "
        f"macro required recall={summary['macro_required_recall']:.3f}"
    )


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
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
