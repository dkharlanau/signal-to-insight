#!/usr/bin/env python3
"""Validate curated Knowledge Delta records against insights, graph and research bundles."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELTAS = ROOT / "data" / "knowledge-deltas.json"
INSIGHTS = ROOT / "data" / "insights.json"
INBOX = ROOT / "data" / "inbox.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
BUNDLES = ROOT / "data" / "research-bundles"

RELATIONSHIP_TO_BUNDLE = {
    "reinforces": "reinforcement",
    "refines": "refinement",
    "contradicts": "contradiction",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    deltas = load(DELTAS)
    insights_data = load(INSIGHTS)
    inbox_data = load(INBOX)
    graph_data = load(GRAPH)

    insights = {item["id"]: item for item in insights_data.get("insights", [])}
    intakes = {item.get("insight_id"): item for item in inbox_data.get("items", []) if item.get("insight_id")}
    concepts = {item["id"]: item for item in graph_data.get("concepts", [])}

    records: dict[str, dict] = {}
    for index, record in enumerate(deltas.get("records", [])):
        where = f"data/knowledge-deltas.json records[{index}]"
        insight_id = record.get("insight_id")
        if not isinstance(insight_id, str) or not insight_id:
            errors.append(f"{where}: insight_id is required")
            continue
        if insight_id in records:
            errors.append(f"{where}: duplicate insight_id '{insight_id}'")
            continue
        records[insight_id] = record

        insight = insights.get(insight_id)
        if insight is None:
            errors.append(f"{where}: unknown insight '{insight_id}'")
            continue
        if insight.get("status") not in {"review", "published"}:
            errors.append(f"{where}: delta should only exist for review/published insight, found {insight.get('status')!r}")

        intake = intakes.get(insight_id)
        bundle_matches: dict[str, dict] = {}
        if intake:
            bundle_path = BUNDLES / f"{intake['id']}.json"
            if bundle_path.exists():
                bundle = load(bundle_path)
                prior = bundle.get("prior_knowledge") or {}
                bundle_matches = {
                    item.get("concept_id"): item
                    for item in prior.get("matches", [])
                    if isinstance(item, dict) and item.get("concept_id")
                }

        items = record.get("items")
        if not isinstance(items, list) or not items:
            errors.append(f"{where}.items: expected at least one delta item")
            continue

        seen_concepts: set[str] = set()
        for item_index, item in enumerate(items):
            i_where = f"{where}.items[{item_index}]"
            relationship = item.get("relationship")
            if relationship not in {"new", "reinforces", "refines", "contradicts"}:
                errors.append(f"{i_where}: invalid relationship '{relationship}'")
            concept_id = item.get("concept_id")
            if concept_id in seen_concepts:
                errors.append(f"{i_where}: duplicate concept_id '{concept_id}'")
            if isinstance(concept_id, str):
                seen_concepts.add(concept_id)
            concept = concepts.get(concept_id)
            if concept is None:
                errors.append(f"{i_where}: unknown graph concept '{concept_id}'")
            elif insight_id not in concept.get("insight_ids", []):
                errors.append(f"{i_where}: concept '{concept_id}' is not supported by insight '{insight_id}'")

            for key in ("label", "source_basis", "prior_basis", "interpretation"):
                if not isinstance(item.get(key), str) or not item.get(key, "").strip():
                    errors.append(f"{i_where}.{key}: expected non-empty string")

            evidence = item.get("evidence_insights")
            if not isinstance(evidence, list):
                errors.append(f"{i_where}.evidence_insights: expected list")
                evidence = []
            if relationship == "new" and evidence:
                errors.append(f"{i_where}: new knowledge should not cite prior insight evidence")
            if relationship in RELATIONSHIP_TO_BUNDLE and not evidence:
                errors.append(f"{i_where}: {relationship} requires prior insight evidence")
            for evidence_id in evidence:
                prior_insight = insights.get(evidence_id)
                if prior_insight is None:
                    errors.append(f"{i_where}: unknown evidence insight '{evidence_id}'")
                elif evidence_id == insight_id:
                    errors.append(f"{i_where}: delta cannot cite itself as prior evidence")
                elif insight.get("status") == "published" and prior_insight.get("status") != "published":
                    errors.append(f"{i_where}: published delta cannot depend on non-published evidence '{evidence_id}'")

            bundle_match = bundle_matches.get(concept_id)
            expected_bundle_relationship = RELATIONSHIP_TO_BUNDLE.get(relationship)
            if bundle_match is not None and expected_bundle_relationship is not None:
                actual = bundle_match.get("relationship_to_source")
                if actual != expected_bundle_relationship:
                    errors.append(
                        f"{i_where}: curated relationship '{relationship}' conflicts with bundle classification '{actual}'"
                    )

        suppressed = record.get("suppressed_prior_matches")
        if not isinstance(suppressed, list):
            errors.append(f"{where}.suppressed_prior_matches: expected list")
        else:
            for concept_id in suppressed:
                match = bundle_matches.get(concept_id)
                if match is None:
                    errors.append(f"{where}: suppressed concept '{concept_id}' is not in the prior-knowledge snapshot")
                elif match.get("relationship_to_source") != "not_relevant":
                    errors.append(
                        f"{where}: suppressed concept '{concept_id}' must be classified not_relevant, found {match.get('relationship_to_source')!r}"
                    )

    required = {
        item["id"]
        for item in insights.values()
        if item.get("status") in {"review", "published"}
    }
    missing = sorted(required - set(records))
    if missing:
        errors.append(f"missing Knowledge Delta record(s): {missing}")

    if errors:
        print(f"Knowledge Delta validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Knowledge Delta validation passed: {len(records)} record(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
