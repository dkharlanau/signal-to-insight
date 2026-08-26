#!/usr/bin/env python3
"""Atomically materialize one researched case into the shared knowledge registries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"


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


def merge_concept(existing: dict, patch: dict) -> None:
    """Merge a concept patch without deleting evidence/public projection owned by other cases."""
    patch_ids = list(patch.get("insight_ids", []))
    existing_ids = existing.setdefault("insight_ids", [])
    for insight_id in patch_ids:
        if insight_id not in existing_ids:
            existing_ids.append(insight_id)

    # A reference-only patch intentionally contains only id + insight_ids.
    if set(patch) <= {"id", "insight_ids"}:
        return

    for key, value in patch.items():
        if key in {"id", "insight_ids"}:
            continue
        existing[key] = value


def merge_relation(existing: dict, patch: dict) -> None:
    """Allow a researched case to revise its relation while preserving an unrelated public override."""
    public = existing.get("public")
    for key, value in patch.items():
        if key == "public":
            continue
        existing[key] = value
    if "public" in patch:
        existing["public"] = patch["public"]
    elif public is not None:
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

    intake_id = patch["intake_id"]
    intake = next((item for item in inbox.get("items", []) if item.get("id") == intake_id), None)
    if intake is None:
        raise SystemExit(f"intake not found: {intake_id}")

    source = patch["source"]
    insight = patch["insight"]
    upsert(sources.setdefault("sources", []), "id", source)
    upsert(insights.setdefault("insights", []), "id", insight)

    intake["status"] = patch.get("intake_status", insight.get("status", "review"))
    intake["source_id"] = source["id"]
    intake["insight_id"] = insight["id"]

    concept_map = {item["id"]: item for item in graph.setdefault("concepts", [])}
    for concept_patch in patch.get("graph", {}).get("concepts", []):
        concept_id = concept_patch["id"]
        existing = concept_map.get(concept_id)
        if existing is None:
            graph["concepts"].append(concept_patch)
            concept_map[concept_id] = concept_patch
            continue
        merge_concept(existing, concept_patch)

    relation_map = {item["id"]: item for item in graph.setdefault("relations", [])}
    for relation_patch in patch.get("graph", {}).get("relations", []):
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
        f"{intake['status']} / {source['id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
