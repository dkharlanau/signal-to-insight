#!/usr/bin/env python3
"""Validate compact prerequisite maps and publication blockers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "data" / "prerequisite-maps.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    maps_data = load(MAPS)
    graph_data = load(GRAPH)
    insights_data = load(INSIGHTS)

    concepts = {item["id"]: item for item in graph_data.get("concepts", []) if item.get("id")}
    insights = {item["id"]: item for item in insights_data.get("insights", []) if item.get("id")}
    records: dict[str, dict] = {}
    item_ids: set[str] = set()

    for record_index, record in enumerate(maps_data.get("records", [])):
        where = f"data/prerequisite-maps.json records[{record_index}]"
        insight_id = record.get("insight_id")
        insight = insights.get(insight_id)
        if insight is None:
            errors.append(f"{where}: unknown insight '{insight_id}'")
            continue
        if insight.get("status") not in {"review", "published"}:
            errors.append(f"{where}: prerequisite map should only exist for review/published insight")
        if insight_id in records:
            errors.append(f"{where}: duplicate map for '{insight_id}'")
        records[insight_id] = record

        summary = record.get("summary")
        if not isinstance(summary, str) or len(summary.split()) < 8:
            errors.append(f"{where}.summary: expected compact explanation of why these prerequisites matter")

        items = record.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 5:
            errors.append(f"{where}.items: expected 1..5 prerequisites; avoid generic prerequisite inflation")
            continue
        if not any(item.get("priority") == "must_know_now" for item in items if isinstance(item, dict)):
            errors.append(f"{where}.items: at least one must_know_now prerequisite is required")

        seen_concepts: set[str] = set()
        for item_index, item in enumerate(items):
            i_where = f"{where}.items[{item_index}]"
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id:
                errors.append(f"{i_where}.id: expected non-empty string")
            elif item_id in item_ids:
                errors.append(f"{i_where}: duplicate global prerequisite id '{item_id}'")
            else:
                item_ids.add(item_id)

            priority = item.get("priority")
            if priority not in {"must_know_now", "learn_next", "optional_depth"}:
                errors.append(f"{i_where}.priority: invalid priority '{priority}'")
            prior_coverage = item.get("prior_coverage")
            if prior_coverage not in {"absent", "partial", "established"}:
                errors.append(f"{i_where}.prior_coverage: invalid value '{prior_coverage}'")
            state = item.get("state")
            if state not in {"known_in_graph", "explained_here", "gap"}:
                errors.append(f"{i_where}.state: invalid state '{state}'")
            reason = item.get("reason")
            if not isinstance(reason, str) or len(reason.split()) < 8:
                errors.append(f"{i_where}.reason: explain why this prerequisite is necessary")

            concept_id = item.get("concept_id")
            concept = concepts.get(concept_id) if concept_id else None
            if state != "gap" and concept is None:
                errors.append(f"{i_where}: non-gap prerequisite must reference an existing graph concept")
            if concept_id:
                if concept_id in seen_concepts:
                    errors.append(f"{i_where}: duplicate concept '{concept_id}' in one prerequisite map")
                seen_concepts.add(concept_id)

            support_ids = set(concept.get("insight_ids", [])) if concept else set()
            prior_support = support_ids - {insight_id}
            if prior_coverage == "absent" and prior_support:
                errors.append(f"{i_where}: prior_coverage=absent but concept has prior/other support {sorted(prior_support)}")
            if prior_coverage == "established" and not prior_support:
                errors.append(f"{i_where}: prior_coverage=established requires support outside the current insight")
            if state == "known_in_graph" and not prior_support:
                errors.append(f"{i_where}: known_in_graph requires another supporting insight")
            if state == "explained_here" and insight_id not in support_ids:
                errors.append(f"{i_where}: explained_here concept is not evidenced by the current insight")

            resolution = item.get("resolution")
            if not isinstance(resolution, dict):
                errors.append(f"{i_where}.resolution: expected object")
                resolution = {}
            kind = resolution.get("kind")
            target_insight_id = resolution.get("insight_id")
            target = resolution.get("target")
            if kind == "explained_here":
                if state != "explained_here" or target_insight_id != insight_id or target is not None:
                    errors.append(f"{i_where}: explained_here resolution must point to current insight only")
            elif kind == "existing_concept":
                if state != "known_in_graph" or target != concept_id or target_insight_id is not None:
                    errors.append(f"{i_where}: existing_concept resolution must point to the known concept")
            elif kind == "existing_explainer":
                target_insight = insights.get(target_insight_id)
                if state != "known_in_graph" or target is not None:
                    errors.append(f"{i_where}: existing_explainer requires known_in_graph and no free target")
                if target_insight is None:
                    errors.append(f"{i_where}: existing_explainer points to unknown insight '{target_insight_id}'")
                elif target_insight.get("status") != "published":
                    errors.append(f"{i_where}: existing_explainer must point to a published explainer")
                elif concept_id not in {
                    c["id"] for c in concepts.values() if target_insight_id in c.get("insight_ids", [])
                }:
                    errors.append(f"{i_where}: target explainer does not evidence concept '{concept_id}'")
            elif kind == "learning_target":
                if state != "gap" or not isinstance(target, str) or not target.strip() or target_insight_id is not None:
                    errors.append(f"{i_where}: learning_target must describe an unresolved gap")
            else:
                errors.append(f"{i_where}.resolution.kind: invalid kind '{kind}'")

            if insight.get("status") == "published" and priority == "must_know_now" and state == "gap":
                errors.append(f"{i_where}: published insight cannot leave a must_know_now prerequisite unresolved")

        coherence = insight.get("coherence_review", {})
        has_required_gap = any(
            item.get("priority") == "must_know_now" and item.get("state") == "gap"
            for item in items
        )
        if coherence.get("prerequisites_complete") is True and has_required_gap:
            errors.append(f"{where}: coherence says prerequisites complete but map still contains a required gap")

    required = {
        item["id"]
        for item in insights.values()
        if item.get("status") in {"review", "published"}
    }
    missing = sorted(required - set(records))
    if missing:
        errors.append(f"missing prerequisite map(s): {missing}")

    if errors:
        print(f"Prerequisite validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Prerequisite validation passed: {len(records)} map(s), {len(item_ids)} prerequisite(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
