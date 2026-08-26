#!/usr/bin/env python3
"""Project internal cumulative knowledge into a published-only public graph."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"
COVERAGE = {"introduced", "explained", "applied"}


class ProjectionError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_public_concept(concept: dict, published_ids: set[str], linked: list[str]) -> tuple[str, str, list[str]]:
    override = concept.get("public")
    if not isinstance(override, dict):
        raise ProjectionError(
            f"concept '{concept.get('id')}' mixes published and non-published evidence but has no public projection"
        )
    summary = override.get("summary")
    coverage = override.get("coverage")
    evidence = override.get("evidence_insights")
    if not isinstance(summary, str) or len(summary.strip()) < 10:
        raise ProjectionError(f"concept '{concept.get('id')}' public.summary must be meaningful")
    if coverage not in COVERAGE:
        raise ProjectionError(f"concept '{concept.get('id')}' public.coverage is invalid")
    if not isinstance(evidence, list) or not evidence:
        raise ProjectionError(f"concept '{concept.get('id')}' public.evidence_insights must be non-empty")
    if len(set(evidence)) != len(evidence):
        raise ProjectionError(f"concept '{concept.get('id')}' public.evidence_insights contains duplicates")
    if any(item_id not in linked for item_id in evidence):
        raise ProjectionError(f"concept '{concept.get('id')}' public evidence must also be linked internally")
    if any(item_id not in published_ids for item_id in evidence):
        raise ProjectionError(f"concept '{concept.get('id')}' public evidence must be published")
    return summary, coverage, evidence


def _require_public_relation(relation: dict, published_ids: set[str], evidence: list[str]) -> tuple[str, list[str]]:
    override = relation.get("public")
    if not isinstance(override, dict):
        raise ProjectionError(
            f"relation '{relation.get('id')}' mixes published and non-published evidence but has no public projection"
        )
    rationale = override.get("rationale")
    public_evidence = override.get("evidence_insights")
    if not isinstance(rationale, str) or len(rationale.strip()) < 10:
        raise ProjectionError(f"relation '{relation.get('id')}' public.rationale must be meaningful")
    if not isinstance(public_evidence, list) or not public_evidence:
        raise ProjectionError(f"relation '{relation.get('id')}' public.evidence_insights must be non-empty")
    if len(set(public_evidence)) != len(public_evidence):
        raise ProjectionError(f"relation '{relation.get('id')}' public.evidence_insights contains duplicates")
    if any(item_id not in evidence for item_id in public_evidence):
        raise ProjectionError(f"relation '{relation.get('id')}' public evidence must also be internal evidence")
    if any(item_id not in published_ids for item_id in public_evidence):
        raise ProjectionError(f"relation '{relation.get('id')}' public evidence must be published")
    return rationale, public_evidence


def public_graph() -> tuple[list[dict], list[dict], dict[str, dict], int, str]:
    """Return the public-safe graph shape expected by build_graph.py."""
    graph = load(GRAPH)
    insight_data = load(INSIGHTS)
    insights = {item["id"]: item for item in insight_data.get("insights", [])}
    published_ids = {item_id for item_id, item in insights.items() if item.get("status") == "published"}

    visible: list[dict] = []
    hidden_count = 0
    for concept in graph.get("concepts", []):
        linked = list(concept.get("insight_ids", []))
        published_support = [item_id for item_id in linked if item_id in published_ids]
        non_published = [item_id for item_id in linked if item_id not in published_ids]
        if not published_support:
            hidden_count += 1
            continue

        item = dict(concept)
        if non_published:
            summary, coverage, public_support = _require_public_concept(concept, published_ids, linked)
            item["summary"] = summary
            item["coverage"] = coverage
            item["published_support"] = public_support
        else:
            item["published_support"] = published_support
        item.pop("public", None)
        visible.append(item)

    visible_ids = {item["id"] for item in visible}
    projected_relations: list[dict] = []
    for relation in graph.get("relations", []):
        if relation.get("from") not in visible_ids or relation.get("to") not in visible_ids:
            continue
        evidence = list(relation.get("evidence_insights", []))
        published_evidence = [item_id for item_id in evidence if item_id in published_ids]
        if not published_evidence:
            continue
        non_published = [item_id for item_id in evidence if item_id not in published_ids]
        item = dict(relation)
        if non_published:
            rationale, public_evidence = _require_public_relation(relation, published_ids, evidence)
            item["rationale"] = rationale
            item["evidence_insights"] = public_evidence
        else:
            item["evidence_insights"] = published_evidence
        item.pop("public", None)
        projected_relations.append(item)

    leaked = {
        item_id
        for concept in visible
        for item_id in concept.get("published_support", [])
        if item_id not in published_ids
    }
    leaked |= {
        item_id
        for relation in projected_relations
        for item_id in relation.get("evidence_insights", [])
        if item_id not in published_ids
    }
    if leaked:
        raise ProjectionError(f"public graph leaked non-published evidence: {sorted(leaked)}")

    return visible, projected_relations, insights, hidden_count, graph.get("graph_version", "0.0.0")


def self_test() -> int:
    concepts, relations, insights, _, _ = public_graph()
    published_ids = {item_id for item_id, item in insights.items() if item.get("status") == "published"}
    if not concepts:
        raise ProjectionError("public projection unexpectedly contains no concepts")
    for concept in concepts:
        if not set(concept.get("published_support", [])) <= published_ids:
            raise ProjectionError(f"concept '{concept['id']}' leaks non-published support")
    for relation in relations:
        if not set(relation.get("evidence_insights", [])) <= published_ids:
            raise ProjectionError(f"relation '{relation['id']}' leaks non-published support")
    print(f"Public projection self-test passed: {len(concepts)} concepts, {len(relations)} relations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
