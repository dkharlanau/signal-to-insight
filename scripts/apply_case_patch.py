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
        for insight_id in concept_patch.get("insight_ids", []):
            if insight_id not in existing.setdefault("insight_ids", []):
                existing["insight_ids"].append(insight_id)

    relation_map = {item["id"]: item for item in graph.setdefault("relations", [])}
    for relation in patch.get("graph", {}).get("relations", []):
        if relation["id"] not in relation_map:
            graph["relations"].append(relation)
            relation_map[relation["id"]] = relation

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
