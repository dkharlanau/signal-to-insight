#!/usr/bin/env python3
"""Audit the frozen 20-source validation cohort using committed knowledge contracts only.

This is intentionally separate from .local/dogfood-cohort.json. The committed audit can prove
structural coverage and recorded failure modes, but it must not invent elapsed-time, subjective
utility, delayed-recall or Source Decision calibration evidence that requires a real user run.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "cohorts" / "validation-20.json"
DEFAULT_REPORT = ROOT / "docs" / "COHORT_20_REPORT.md"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def records(path: Path) -> list[dict]:
    return load(path).get("records", [])


def registry_ids(path: Path) -> set[str]:
    return {
        item.get("insight_id")
        for item in records(path)
        if isinstance(item, dict) and isinstance(item.get("insight_id"), str)
    }


def audit(manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    manifest = load(manifest_path)
    member_ids = manifest.get("members", [])
    errors: list[str] = []
    if len(member_ids) != 20:
        errors.append(f"manifest must contain exactly 20 intake ids, found {len(member_ids)}")
    if len(set(member_ids)) != len(member_ids):
        errors.append("manifest contains duplicate intake ids")

    inbox_data = load(ROOT / "data" / "inbox.json")
    source_data = load(ROOT / "data" / "sources.json")
    insight_data = load(ROOT / "data" / "insights.json")
    graph = load(ROOT / "data" / "knowledge-graph.json")

    inbox = {item.get("id"): item for item in inbox_data.get("items", []) if isinstance(item, dict)}
    sources = {item.get("id"): item for item in source_data.get("sources", []) if isinstance(item, dict)}
    insights = {item.get("id"): item for item in insight_data.get("insights", []) if isinstance(item, dict)}

    members: list[dict] = []
    source_types: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    member_insight_ids: set[str] = set()
    member_source_ids: set[str] = set()

    for intake_id in member_ids:
        item = inbox.get(intake_id)
        if item is None:
            errors.append(f"missing cohort intake: {intake_id}")
            continue
        source_type = item.get("source_type")
        status = item.get("status")
        source_id = item.get("source_id")
        insight_id = item.get("insight_id")
        if not isinstance(source_type, str) or not source_type:
            errors.append(f"{intake_id}: source_type missing")
        else:
            source_types[source_type] += 1
        if status not in {"review", "published"}:
            errors.append(f"{intake_id}: cohort item is not review/published: {status!r}")
        else:
            statuses[status] += 1
        if not isinstance(source_id, str) or source_id not in sources:
            errors.append(f"{intake_id}: linked source missing: {source_id!r}")
        else:
            member_source_ids.add(source_id)
        if not isinstance(insight_id, str) or insight_id not in insights:
            errors.append(f"{intake_id}: linked insight missing: {insight_id!r}")
        else:
            member_insight_ids.add(insight_id)
            if insights[insight_id].get("status") != status:
                errors.append(
                    f"{intake_id}: inbox/insight status mismatch "
                    f"({status!r} vs {insights[insight_id].get('status')!r})"
                )
        bundle = ROOT / "data" / "research-bundles" / f"{intake_id}.json"
        if not bundle.exists():
            errors.append(f"{intake_id}: research bundle missing")
        members.append(
            {
                "intake_id": intake_id,
                "source_type": source_type,
                "status": status,
                "source_id": source_id,
                "insight_id": insight_id,
            }
        )

    if len(source_types) < 5:
        errors.append(f"cohort must cover at least five source types, found {len(source_types)}")

    registry_paths = {
        "knowledge_deltas": ROOT / "data" / "knowledge-deltas.json",
        "claim_evidence": ROOT / "data" / "claim-evidence.json",
        "prerequisite_maps": ROOT / "data" / "prerequisite-maps.json",
        "learning_prompts": ROOT / "data" / "learning-prompts.json",
        "source_decisions": ROOT / "data" / "source-decisions.json",
    }
    registry_coverage: dict[str, int] = {}
    for label, path in registry_paths.items():
        ids = registry_ids(path)
        missing = sorted(member_insight_ids - ids)
        registry_coverage[label] = len(member_insight_ids & ids)
        if missing:
            errors.append(f"{label}: missing cohort insight records: {missing}")

    graph_linked = {
        insight_id
        for concept in graph.get("concepts", [])
        if isinstance(concept, dict)
        for insight_id in concept.get("insight_ids", [])
        if isinstance(insight_id, str)
    }
    missing_graph = sorted(member_insight_ids - graph_linked)
    if missing_graph:
        errors.append(f"knowledge graph: cohort insights without concept linkage: {missing_graph}")

    claim_records = records(ROOT / "data" / "claim-evidence.json")
    prereq_records = records(ROOT / "data" / "prerequisite-maps.json")
    claim_count = sum(
        len(item.get("claims", []))
        for item in claim_records
        if item.get("insight_id") in member_insight_ids
    )
    prerequisite_count = sum(
        len(item.get("items", []))
        for item in prereq_records
        if item.get("insight_id") in member_insight_ids
    )

    report = {
        "cohort_id": manifest.get("cohort_id"),
        "member_count": len(member_ids),
        "processed_members": len(members),
        "source_types": dict(sorted(source_types.items())),
        "statuses": dict(sorted(statuses.items())),
        "registry_coverage": registry_coverage,
        "metrics": {
            "sources": len(member_source_ids),
            "insights": len(member_insight_ids),
            "research_bundles": sum(
                (ROOT / "data" / "research-bundles" / f"{intake_id}.json").exists()
                for intake_id in member_ids
            ),
            "knowledge_deltas": registry_coverage["knowledge_deltas"],
            "claim_evidence_records": registry_coverage["claim_evidence"],
            "claims": claim_count,
            "prerequisite_maps": registry_coverage["prerequisite_maps"],
            "prerequisites": prerequisite_count,
            "learning_prompts": registry_coverage["learning_prompts"],
            "source_decisions": registry_coverage["source_decisions"],
            "graph_concepts_total": len(graph.get("concepts", [])),
            "graph_relations_total": len(graph.get("relations", [])),
            "case_patches_total": len(list((ROOT / "data" / "case-patches").glob("*.json"))),
            "case_contracts_total": len(list((ROOT / "data" / "case-contracts").glob("*.json"))),
        },
        "observed_failure_modes": manifest.get("observed_failure_modes", []),
        "human_evidence_gaps": manifest.get("human_evidence_gaps", []),
        "structural_ready": not errors,
        "errors": errors,
    }
    return report


def render_markdown(report: dict) -> str:
    ready = "YES" if report["structural_ready"] else "NO"
    lines = [
        "# Validation cohort — 20 sources",
        "",
        f"Structural readiness: **{ready}**",
        "",
        "This report audits committed source/knowledge contracts only. It deliberately does not claim human learning utility, delayed recall, elapsed work time or Source Decision calibration unless those measurements actually exist.",
        "",
        "## Coverage",
        "",
        f"- Cohort members: {report['processed_members']} / {report['member_count']}",
        f"- Sources linked: {report['metrics']['sources']}",
        f"- Insights linked: {report['metrics']['insights']}",
        f"- Research bundles: {report['metrics']['research_bundles']}",
        f"- Statuses: {', '.join(f'{key}={value}' for key, value in report['statuses'].items())}",
        "",
        "| Source type | Count |",
        "| --- | ---: |",
    ]
    for source_type, count in report["source_types"].items():
        lines.append(f"| {source_type} | {count} |")

    metrics = report["metrics"]
    lines.extend(
        [
            "",
            "## Structured knowledge evidence",
            "",
            "| Contract | Count |",
            "| --- | ---: |",
            f"| Knowledge Delta records | {metrics['knowledge_deltas']} |",
            f"| Claim-evidence records | {metrics['claim_evidence_records']} |",
            f"| Important claims | {metrics['claims']} |",
            f"| Prerequisite maps | {metrics['prerequisite_maps']} |",
            f"| Prerequisites | {metrics['prerequisites']} |",
            f"| Learning prompts | {metrics['learning_prompts']} |",
            f"| Source Decisions | {metrics['source_decisions']} |",
            f"| Graph concepts (total graph) | {metrics['graph_concepts_total']} |",
            f"| Graph relations (total graph) | {metrics['graph_relations_total']} |",
            f"| Review case patches | {metrics['case_patches_total']} |",
            f"| Companion case contracts | {metrics['case_contracts_total']} |",
            "",
            "## Failure modes exposed by dogfood",
            "",
        ]
    )
    for item in report["observed_failure_modes"]:
        lines.extend(
            [
                f"### {item['id']}",
                "",
                item["observation"],
                "",
                f"Resolution: {item['resolution']}",
                "",
                f"Status: `{item['status']}`",
                "",
            ]
        )

    lines.extend(["## What this cohort still does not prove", ""])
    for gap in report["human_evidence_gaps"]:
        lines.append(f"- {gap}")
    if report["errors"]:
        lines.extend(["", "## Audit errors", ""])
        for error in report["errors"]:
            lines.append(f"- {error}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write-report", type=Path)
    parser.add_argument("--check-report", type=Path)
    args = parser.parse_args()

    try:
        report = audit(args.manifest)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cohort audit error: {exc}")
        return 2

    markdown = render_markdown(report)
    if args.write_report:
        path = args.write_report
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        print(f"wrote cohort report: {path.relative_to(ROOT)}")
    if args.check_report:
        path = args.check_report
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists() or path.read_text(encoding="utf-8") != markdown:
            print(f"cohort audit error: report is stale: {path.relative_to(ROOT)}")
            return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Cohort {report['cohort_id']}: {report['processed_members']}/{report['member_count']} members; "
            f"types={len(report['source_types'])}; structural_ready={report['structural_ready']}"
        )
        if report["errors"]:
            for error in report["errors"]:
                print(f"- {error}")

    if args.check and not report["structural_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
