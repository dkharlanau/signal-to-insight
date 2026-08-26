#!/usr/bin/env python3
"""Validate researched case patches before they can mutate shared registries."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / "data" / "case-patches"
INBOX = ROOT / "data" / "inbox.json"
BUNDLES = ROOT / "data" / "research-bundles"

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
COVERAGE = {"introduced", "explained", "applied"}
RELATION_TYPES = {"depends_on", "enables", "realized_by", "refines", "related_to"}
FULL_CONCEPT_KEYS = {"id", "label", "summary", "domain", "coverage", "insight_ids", "aliases", "tags"}
REFERENCE_CONCEPT_KEYS = {"id", "insight_ids"}
RELATION_KEYS = {"id", "from", "to", "type", "rationale", "evidence_insights"}
TOP_KEYS = {"patch_version", "intake_id", "intake_status", "updated_at", "graph_version", "source", "insight", "graph"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def valid_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def main() -> int:
    errors: list[str] = []
    inbox_data = load(INBOX)
    inbox = {item.get("id"): item for item in inbox_data.get("items", []) if isinstance(item, dict)}
    files = sorted(PATCHES.glob("*.json")) if PATCHES.exists() else []

    for path in files:
        rel = path.relative_to(ROOT)
        try:
            patch = load(path)
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue

        if not isinstance(patch, dict):
            errors.append(f"{rel}: expected JSON object")
            continue
        missing = TOP_KEYS - set(patch)
        extra = set(patch) - TOP_KEYS
        if missing:
            errors.append(f"{rel}: missing top-level fields {sorted(missing)}")
        if extra:
            errors.append(f"{rel}: unsupported top-level fields {sorted(extra)}")

        if not SEMVER.fullmatch(str(patch.get("patch_version", ""))):
            errors.append(f"{rel}.patch_version: expected semver")
        if not SEMVER.fullmatch(str(patch.get("graph_version", ""))):
            errors.append(f"{rel}.graph_version: expected semver")
        if not valid_date(patch.get("updated_at")):
            errors.append(f"{rel}.updated_at: expected ISO date")

        # Publication is deliberately outside the case-patch contract.
        if patch.get("intake_status") != "review":
            errors.append(f"{rel}.intake_status: must be 'review'; case patches cannot publish")

        intake_id = patch.get("intake_id")
        item = inbox.get(intake_id)
        if item is None:
            errors.append(f"{rel}.intake_id: intake not found: {intake_id!r}")

        source = patch.get("source")
        insight = patch.get("insight")
        graph = patch.get("graph")
        if not isinstance(source, dict):
            errors.append(f"{rel}.source: expected object")
            source = {}
        if not isinstance(insight, dict):
            errors.append(f"{rel}.insight: expected object")
            insight = {}
        if not isinstance(graph, dict):
            errors.append(f"{rel}.graph: expected object")
            graph = {}

        source_id = source.get("id")
        insight_id = insight.get("id")
        if not isinstance(source_id, str) or not source_id.startswith("src-") or not SLUG.fullmatch(source_id[4:]):
            errors.append(f"{rel}.source.id: expected src-* lowercase slug")
        if not isinstance(insight_id, str) or not SLUG.fullmatch(insight_id):
            errors.append(f"{rel}.insight.id: expected lowercase slug")
        if insight.get("status") != "review":
            errors.append(f"{rel}.insight.status: must be 'review'; publication requires a separate reviewed transition")
        if insight.get("source_id") != source_id:
            errors.append(f"{rel}: insight.source_id must equal source.id")
        slug = insight.get("slug")
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            errors.append(f"{rel}.insight.slug: expected lowercase slug")

        canonical = source.get("canonical_url")
        if not valid_url(canonical):
            errors.append(f"{rel}.source.canonical_url: expected http(s) URL")
        if item is not None:
            if canonical != item.get("source_url"):
                errors.append(f"{rel}: source.canonical_url must equal intake source_url")
            if source.get("type") != item.get("source_type"):
                errors.append(f"{rel}: source.type must equal intake source_type")

        derived = source.get("derived_records")
        if not isinstance(derived, list) or insight_id not in derived:
            errors.append(f"{rel}.source.derived_records: must contain current insight id")

        concepts = graph.get("concepts")
        relations = graph.get("relations")
        if set(graph) != {"concepts", "relations"}:
            errors.append(f"{rel}.graph: only concepts and relations are allowed")
        if not isinstance(concepts, list):
            errors.append(f"{rel}.graph.concepts: expected list")
            concepts = []
        if not isinstance(relations, list):
            errors.append(f"{rel}.graph.relations: expected list")
            relations = []

        concept_ids: set[str] = set()
        for index, concept in enumerate(concepts):
            where = f"{rel}.graph.concepts[{index}]"
            if not isinstance(concept, dict):
                errors.append(f"{where}: expected object")
                continue
            if "public" in concept:
                errors.append(f"{where}: review case patches may not mutate public projection")
            keys = set(concept)
            if keys != REFERENCE_CONCEPT_KEYS and keys != FULL_CONCEPT_KEYS:
                errors.append(
                    f"{where}: expected reference-only keys {sorted(REFERENCE_CONCEPT_KEYS)} "
                    f"or full concept keys {sorted(FULL_CONCEPT_KEYS)}"
                )
            concept_id = concept.get("id")
            if not isinstance(concept_id, str) or not SLUG.fullmatch(concept_id):
                errors.append(f"{where}.id: expected lowercase slug")
            elif concept_id in concept_ids:
                errors.append(f"{where}.id: duplicate concept patch '{concept_id}'")
            else:
                concept_ids.add(concept_id)
            linked = concept.get("insight_ids")
            if not isinstance(linked, list) or insight_id not in linked:
                errors.append(f"{where}.insight_ids: must contain current insight id")
            elif len(set(linked)) != len(linked):
                errors.append(f"{where}.insight_ids: duplicates are not allowed")
            if keys == FULL_CONCEPT_KEYS:
                if concept.get("coverage") not in COVERAGE:
                    errors.append(f"{where}.coverage: invalid value")
                if not isinstance(concept.get("summary"), str) or len(concept.get("summary", "").strip()) < 10:
                    errors.append(f"{where}.summary: expected meaningful summary")
                for key in ("aliases", "tags"):
                    values = concept.get(key)
                    if not isinstance(values, list) or (key == "tags" and not values):
                        errors.append(f"{where}.{key}: expected {'non-empty ' if key == 'tags' else ''}list")

        relation_ids: set[str] = set()
        for index, relation in enumerate(relations):
            where = f"{rel}.graph.relations[{index}]"
            if not isinstance(relation, dict):
                errors.append(f"{where}: expected object")
                continue
            if "public" in relation:
                errors.append(f"{where}: review case patches may not mutate public projection")
            if set(relation) != RELATION_KEYS:
                errors.append(f"{where}: relation keys must equal {sorted(RELATION_KEYS)}")
            relation_id = relation.get("id")
            if not isinstance(relation_id, str) or not relation_id.startswith("rel-") or not SLUG.fullmatch(relation_id[4:]):
                errors.append(f"{where}.id: expected rel-* lowercase slug")
            elif relation_id in relation_ids:
                errors.append(f"{where}.id: duplicate relation patch '{relation_id}'")
            else:
                relation_ids.add(relation_id)
            if relation.get("type") not in RELATION_TYPES:
                errors.append(f"{where}.type: invalid relation type")
            evidence = relation.get("evidence_insights")
            if not isinstance(evidence, list) or insight_id not in evidence:
                errors.append(f"{where}.evidence_insights: must contain current insight id")
            elif len(set(evidence)) != len(evidence):
                errors.append(f"{where}.evidence_insights: duplicates are not allowed")
            if not isinstance(relation.get("rationale"), str) or len(relation.get("rationale", "").strip()) < 10:
                errors.append(f"{where}.rationale: expected meaningful explanation")

        # A review patch cannot bypass the prior-knowledge classification gate.
        bundle_path = BUNDLES / f"{intake_id}.json"
        if bundle_path.exists():
            try:
                bundle = load(bundle_path)
            except json.JSONDecodeError as exc:
                errors.append(f"{bundle_path.relative_to(ROOT)}: invalid JSON: {exc}")
            else:
                prior = bundle.get("prior_knowledge")
                if isinstance(prior, dict) and prior.get("classification_required") is True:
                    unresolved = [
                        match.get("concept_id")
                        for match in prior.get("matches", [])
                        if match.get("relationship_to_source") == "unclassified"
                    ]
                    if unresolved:
                        errors.append(f"{rel}: unresolved prior knowledge {unresolved}")
        else:
            errors.append(f"{rel}: research bundle is required before review materialization")

    if errors:
        print(f"Case-patch validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Case-patch validation passed: {len(files)} patch(es). Review-only boundary intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
