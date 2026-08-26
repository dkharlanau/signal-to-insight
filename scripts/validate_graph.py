#!/usr/bin/env python3
"""Validate the cumulative concept graph and its links to insight records."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"
RELATION_TYPES = {"depends_on", "enables", "realized_by", "refines", "related_to"}
COVERAGE = {"introduced", "explained", "applied"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REL_ID = re.compile(r"^rel-[a-z0-9]+(?:-[a-z0-9]+)*$")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    graph = load(GRAPH)
    insight_data = load(INSIGHTS)
    insight_ids = {item.get("id") for item in insight_data.get("insights", []) if isinstance(item, dict)}

    try:
        date.fromisoformat(graph.get("updated_at", ""))
    except (TypeError, ValueError):
        errors.append("data/knowledge-graph.json: updated_at must be an ISO date")

    concepts = graph.get("concepts")
    relations = graph.get("relations")
    if not isinstance(concepts, list):
        errors.append("data/knowledge-graph.json: concepts must be a list")
        concepts = []
    if not isinstance(relations, list):
        errors.append("data/knowledge-graph.json: relations must be a list")
        relations = []

    concept_ids: list[str] = []
    concept_insights: dict[str, set[str]] = {}
    for index, concept in enumerate(concepts):
        where = f"concepts[{index}]"
        if not isinstance(concept, dict):
            errors.append(f"{where}: expected object")
            continue
        required = {"id", "label", "summary", "domain", "coverage", "insight_ids", "aliases", "tags"}
        missing = required - set(concept)
        if missing:
            errors.append(f"{where}: missing {sorted(missing)}")
        concept_id = concept.get("id")
        if not isinstance(concept_id, str) or not SLUG.fullmatch(concept_id):
            errors.append(f"{where}.id: expected lowercase slug")
            continue
        concept_ids.append(concept_id)
        if concept.get("coverage") not in COVERAGE:
            errors.append(f"{where}.coverage: invalid value '{concept.get('coverage')}'")
        linked = concept.get("insight_ids")
        if not isinstance(linked, list) or not linked:
            errors.append(f"{where}.insight_ids: expected non-empty list")
            linked_set: set[str] = set()
        else:
            linked_set = set(linked)
            if len(linked_set) != len(linked):
                errors.append(f"{where}.insight_ids: duplicates are not allowed")
            dangling = sorted(linked_set - insight_ids)
            if dangling:
                errors.append(f"{where}.insight_ids: dangling insight ids {dangling}")
        concept_insights[concept_id] = linked_set
        if not isinstance(concept.get("summary"), str) or len(concept.get("summary", "").strip()) < 10:
            errors.append(f"{where}.summary: expected meaningful summary")
        tags = concept.get("tags")
        if not isinstance(tags, list) or not tags or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            errors.append(f"{where}.tags: expected non-empty list of strings")

    if len(set(concept_ids)) != len(concept_ids):
        errors.append("concept ids must be unique")
    concept_id_set = set(concept_ids)

    relation_ids: list[str] = []
    relation_keys: set[tuple[str, str, str]] = set()
    connected: set[str] = set()
    for index, relation in enumerate(relations):
        where = f"relations[{index}]"
        if not isinstance(relation, dict):
            errors.append(f"{where}: expected object")
            continue
        required = {"id", "from", "to", "type", "rationale", "evidence_insights"}
        missing = required - set(relation)
        if missing:
            errors.append(f"{where}: missing {sorted(missing)}")
        relation_id = relation.get("id")
        if not isinstance(relation_id, str) or not REL_ID.fullmatch(relation_id):
            errors.append(f"{where}.id: expected rel-* lowercase slug")
        else:
            relation_ids.append(relation_id)
        source = relation.get("from")
        target = relation.get("to")
        relation_type = relation.get("type")
        if source not in concept_id_set:
            errors.append(f"{where}.from: dangling concept '{source}'")
        if target not in concept_id_set:
            errors.append(f"{where}.to: dangling concept '{target}'")
        if source == target:
            errors.append(f"{where}: self-relations are not allowed")
        if relation_type not in RELATION_TYPES:
            errors.append(f"{where}.type: invalid relation type '{relation_type}'")
        key = (str(source), str(target), str(relation_type))
        if key in relation_keys:
            errors.append(f"{where}: duplicate semantic relation {key}")
        relation_keys.add(key)
        evidence = relation.get("evidence_insights")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{where}.evidence_insights: expected non-empty list")
            evidence_set: set[str] = set()
        else:
            evidence_set = set(evidence)
            if len(evidence_set) != len(evidence):
                errors.append(f"{where}.evidence_insights: duplicates are not allowed")
            dangling = sorted(evidence_set - insight_ids)
            if dangling:
                errors.append(f"{where}.evidence_insights: dangling insight ids {dangling}")
        if source in concept_insights and target in concept_insights:
            shared = concept_insights[source] & concept_insights[target] & evidence_set
            if not shared:
                errors.append(f"{where}: relation needs at least one evidence insight linked to both endpoint concepts")
            connected.update([source, target])
        if not isinstance(relation.get("rationale"), str) or len(relation.get("rationale", "").strip()) < 10:
            errors.append(f"{where}.rationale: expected meaningful explanation")

    if len(set(relation_ids)) != len(relation_ids):
        errors.append("relation ids must be unique")
    isolated = sorted(concept_id_set - connected)
    if isolated:
        errors.append(f"isolated concepts are not allowed: {isolated}")

    if errors:
        print(f"Knowledge graph validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Knowledge graph validation passed.")
    print(f"Concepts: {len(concept_id_set)} | Relations: {len(relations)} | Insights linked: {len(insight_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
