#!/usr/bin/env python3
"""Atomically materialize one researched review case into the shared knowledge registries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
FROZEN_PUBLIC_REFERENCE_KEYS = {"id", "insight_ids", "public"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert(items: list[dict], key: str, value: dict) -> None:
    target = value[key]
    for index, item in enumerate(items):
        if item.get(key) == target:
            items[index] = value
            return
    items.append(value)


def validate_public_freeze(existing: dict | None, patch: dict, published_ids: set[str], current_insight_id: str) -> None:
    if existing is None:
        raise SystemExit("frozen public projection requires an existing concept")
    if set(patch) != FROZEN_PUBLIC_REFERENCE_KEYS:
        raise SystemExit("public projection is only allowed on a reference-only existing concept patch")
    public = patch.get("public")
    if not isinstance(public, dict):
        raise SystemExit("frozen public projection must be an object")
    existing_public = existing.get("public")
    if existing_public is not None and existing_public != public:
        raise SystemExit("review case cannot change an existing public concept projection")
    if public.get("summary") != existing.get("summary") or public.get("coverage") != existing.get("coverage"):
        raise SystemExit("review case public projection must freeze existing summary and coverage")
    evidence = public.get("evidence_insights")
    if not isinstance(evidence, list) or not evidence:
        raise SystemExit("review case public projection requires published evidence")
    if current_insight_id in evidence:
        raise SystemExit("current review insight cannot enter frozen public projection")
    if any(item_id not in set(existing.get("insight_ids", [])) for item_id in evidence):
        raise SystemExit("frozen public evidence must already support the existing concept")
    if any(item_id not in published_ids for item_id in evidence):
        raise SystemExit("frozen public evidence must already be published")


def merge_concept(existing: dict, patch: dict) -> None:
    """Merge a concept patch without deleting evidence/public projection owned by other cases."""
    patch_ids = list(patch.get("insight_ids", []))
    existing_ids = existing.setdefault("insight_ids", [])
    for insight_id in patch_ids:
        if insight_id not in existing_ids:
            existing_ids.append(insight_id)

    public = patch.get("public")
    if public is not None:
        existing_public = existing.get("public")
        if existing_public is not None and existing_public != public:
            raise SystemExit("review case cannot replace an existing public concept projection")
        existing["public"] = public

    if set(patch) <= FROZEN_PUBLIC_REFERENCE_KEYS:
        return

    for key, value in patch.items():
        if key in {"id", "insight_ids", "public"}:
            continue
        existing[key] = value


def merge_relation(existing: dict, patch: dict) -> None:
    """Allow a researched case to revise its relation while preserving an unrelated public override."""
    public = existing.get("public")
    for key, value in patch.items():
        if key == "public":
            continue
        existing[key] = value
    if public is not None:
        existing["public"] = public


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patch", help="Path to a case-patch JSON file")
    args = parser.parse_args()

    patch_path = Path(args.patch)
    if not patch_path.is_absolute():
        patch_path = ROOT / patch_path
    patch = load(patch_path)

    inbox = load(INBOX)
    sources = load(SOURCES)
    insights = load(INSIGHTS)
    graph = load(GRAPH)

    intake_id = patch.get("intake_id")
    intake = next((item for item in inbox.get("items", []) if item.get("id") == intake_id), None)
    if intake is None:
        raise SystemExit(f"intake not found: {intake_id}")

    source = patch.get("source") or {}
    insight = patch.get("insight") or {}
    current_insight = next(
        (item for item in insights.get("insights", []) if item.get("id") == insight.get("id")),
        None,
    )

    if current_insight is not None and current_insight.get("status") == "published":
        raise SystemExit(
            f"refusing to overwrite published insight '{insight.get('id')}' with a review case patch"
        )

    if patch.get("intake_status") != "review" or insight.get("status") != "review":
        raise SystemExit("case patches are review-only; publication requires a separate reviewed transition")
    if source.get("canonical_url") != intake.get("source_url"):
        raise SystemExit("case patch canonical URL differs from intake source_url")
    if source.get("type") != intake.get("source_type"):
        raise SystemExit("case patch source type differs from intake source_type")
    if insight.get("source_id") != source.get("id"):
        raise SystemExit("insight.source_id must equal source.id")
    if insight.get("id") not in source.get("derived_records", []):
        raise SystemExit("source.derived_records must contain the current insight id")

    graph_patch = patch.get("graph") or {}
    for relation in graph_patch.get("relations", []):
        if "public" in relation:
            raise SystemExit("review case patches may not mutate public relation projection")

    published_ids = {
        item.get("id")
        for item in insights.get("insights", [])
        if isinstance(item, dict) and item.get("status") == "published"
    }
    concept_map = {item["id"]: item for item in graph.setdefault("concepts", [])}
    for concept_patch in graph_patch.get("concepts", []):
        if "public" in concept_patch:
            validate_public_freeze(
                concept_map.get(concept_patch.get("id")),
                concept_patch,
                published_ids,
                insight["id"],
            )

    upsert(sources.setdefault("sources", []), "id", source)
    upsert(insights.setdefault("insights", []), "id", insight)

    intake["status"] = "review"
    intake["source_id"] = source["id"]
    intake["insight_id"] = insight["id"]

    for concept_patch in graph_patch.get("concepts", []):
        concept_id = concept_patch["id"]
        existing = concept_map.get(concept_id)
        if existing is None:
            graph["concepts"].append(concept_patch)
            concept_map[concept_id] = concept_patch
            continue
        merge_concept(existing, concept_patch)

    relation_map = {item["id"]: item for item in graph.setdefault("relations", [])}
    for relation_patch in graph_patch.get("relations", []):
        relation_id = relation_patch["id"]
        existing = relation_map.get(relation_id)
        if existing is None:
            graph["relations"].append(relation_patch)
            relation_map[relation_id] = relation_patch
        else:
            merge_relation(existing, relation_patch)

    if patch.get("graph_version"):
        graph["graph_version"] = patch["graph_version"]
    graph["updated_at"] = patch.get("updated_at", graph.get("updated_at"))

    dump(INBOX, inbox)
    dump(SOURCES, sources)
    dump(INSIGHTS, insights)
    dump(GRAPH, graph)
    print(
        f"materialized {insight['id']} from {patch_path.relative_to(ROOT)} -> "
        f"review / {source['id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
