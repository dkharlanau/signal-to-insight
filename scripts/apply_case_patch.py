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


def freeze_public_concept_before_review(
    existing: dict,
    patch: dict,
    status_by_insight: dict[str, str | None],
) -> None:
    """Freeze the published projection before review evidence is added.

    Review case patches are forbidden from writing `public` themselves. When an existing
    concept has only published evidence and a review case adds the first non-published
    evidence, preserve the pre-review public state explicitly. If the concept already mixes
    published and non-published support without a curated public projection, fail closed
    rather than guessing what was safe to expose.
    """
    if existing.get("public") is not None:
        return

    incoming_ids = list(patch.get("insight_ids", []))
    incoming_review_ids = [
        insight_id
        for insight_id in incoming_ids
        if status_by_insight.get(insight_id) != "published"
    ]
    if not incoming_review_ids:
        return

    existing_ids = list(existing.get("insight_ids", []))
    published_ids = [
        insight_id
        for insight_id in existing_ids
        if status_by_insight.get(insight_id) == "published"
    ]
    non_published_ids = [
        insight_id
        for insight_id in existing_ids
        if status_by_insight.get(insight_id) != "published"
    ]

    if published_ids and non_published_ids:
        raise SystemExit(
            f"concept '{existing.get('id')}' already mixes published and non-published "
            "evidence without a public projection; curate that projection before adding "
            "more review evidence"
        )
    if not published_ids:
        return

    existing["public"] = {
        "summary": existing["summary"],
        "coverage": existing["coverage"],
        "evidence_insights": published_ids,
    }


def merge_concept(existing: dict, patch: dict) -> None:
    """Merge a concept patch without deleting evidence/public projection owned by other cases."""
    patch_ids = list(patch.get("insight_ids", []))
    existing_ids = existing.setdefault("insight_ids", [])
    for insight_id in patch_ids:
        if insight_id not in existing_ids:
            existing_ids.append(insight_id)

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

    # A case patch is a review snapshot. Explicit publication is terminal for this snapshot:
    # materialization must never silently downgrade it back to review.
    if current_insight is not None and current_insight.get("status") == "published":
        raise SystemExit(
            f"refusing to overwrite published insight '{insight.get('id')}' with a review case patch"
        )

    # Defense in depth: researched case patches can prepare review artifacts, never publish them.
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
    for concept in graph_patch.get("concepts", []):
        if "public" in concept:
            raise SystemExit("review case patches may not mutate public concept projection")
    for relation in graph_patch.get("relations", []):
        if "public" in relation:
            raise SystemExit("review case patches may not mutate public relation projection")

    upsert(sources.setdefault("sources", []), "id", source)
    upsert(insights.setdefault("insights", []), "id", insight)
    status_by_insight = {
        item["id"]: item.get("status")
        for item in insights.get("insights", [])
        if isinstance(item, dict) and item.get("id")
    }

    intake["status"] = "review"
    intake["source_id"] = source["id"]
    intake["insight_id"] = insight["id"]

    concept_map = {item["id"]: item for item in graph.setdefault("concepts", [])}
    for concept_patch in graph_patch.get("concepts", []):
        concept_id = concept_patch["id"]
        existing = concept_map.get(concept_id)
        if existing is None:
            graph["concepts"].append(concept_patch)
            concept_map[concept_id] = concept_patch
            continue
        freeze_public_concept_before_review(existing, concept_patch, status_by_insight)
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
