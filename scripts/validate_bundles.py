#!/usr/bin/env python3
"""Validate committed research bundles for structure, source-safety and prior-knowledge resolution."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "data" / "research-bundles"
INBOX = ROOT / "data" / "inbox.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"
SOURCES = ROOT / "data" / "sources.json"
ALLOWED_CONFIDENCE = {"direct", "metadata_only", "secondary", "mixed"}
ALLOWED_KNOWLEDGE_RELATIONSHIPS = {"unclassified", "reinforcement", "refinement", "contradiction", "new_knowledge", "not_relevant"}
PUBLICATION_STATES = {"review", "published"}
errors: list[str] = []


def valid_url(value: object, where: str) -> None:
    if not isinstance(value, str):
        errors.append(f"{where}: URL must be a string")
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{where}: invalid URL '{value}'")


def valid_date(value: object, where: str) -> None:
    if not isinstance(value, str):
        errors.append(f"{where}: expected ISO date")
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        errors.append(f"{where}: invalid ISO date '{value}'")


def validate_prior_knowledge(
    bundle: dict,
    rel: Path,
    graph_ids: set[str],
    insight_ids: set[str],
    insight_status_by_source: dict[str, set[str]],
    source_id_by_url: dict[str, str],
) -> None:
    prior = bundle.get("prior_knowledge")
    if prior is None:
        return  # Bundles created before graph-aware scaffolding remain historically valid.
    if not isinstance(prior, dict):
        errors.append(f"{rel}.prior_knowledge: expected object")
        return
    valid_date(prior.get("captured_at"), f"{rel}.prior_knowledge.captured_at")
    if prior.get("classification_required") is not True:
        errors.append(f"{rel}.prior_knowledge.classification_required: must be true")
    if not isinstance(prior.get("query"), str):
        errors.append(f"{rel}.prior_knowledge.query: expected string")
    matches = prior.get("matches")
    if not isinstance(matches, list):
        errors.append(f"{rel}.prior_knowledge.matches: expected list")
        return

    seen: set[str] = set()
    unresolved: list[str] = []
    for index, match in enumerate(matches):
        where = f"{rel}.prior_knowledge.matches[{index}]"
        if not isinstance(match, dict):
            errors.append(f"{where}: expected object")
            continue
        concept_id = match.get("concept_id")
        if concept_id not in graph_ids:
            errors.append(f"{where}.concept_id: dangling graph concept '{concept_id}'")
        if concept_id in seen:
            errors.append(f"{where}.concept_id: duplicate prior-knowledge concept '{concept_id}'")
        seen.add(concept_id)
        classification = match.get("relationship_to_source")
        if classification not in ALLOWED_KNOWLEDGE_RELATIONSHIPS:
            errors.append(f"{where}.relationship_to_source: invalid classification '{classification}'")
        elif classification == "unclassified":
            unresolved.append(str(concept_id))
        if match.get("coverage") not in {"introduced", "explained", "applied"}:
            errors.append(f"{where}.coverage: invalid value '{match.get('coverage')}'")
        evidence = match.get("evidence_insights")
        if not isinstance(evidence, list):
            errors.append(f"{where}.evidence_insights: expected list")
            continue
        for evidence_index, item in enumerate(evidence):
            evidence_where = f"{where}.evidence_insights[{evidence_index}]"
            if not isinstance(item, dict) or item.get("id") not in insight_ids:
                evidence_id = item.get("id") if isinstance(item, dict) else None
                errors.append(f"{evidence_where}: dangling insight '{evidence_id}'")

    source = bundle.get("source", {})
    linked_source_id = bundle.get("source_id") or source_id_by_url.get(source.get("canonical_url"))
    linked_statuses = insight_status_by_source.get(linked_source_id, set()) if linked_source_id else set()
    if unresolved and linked_statuses & PUBLICATION_STATES:
        states = ", ".join(sorted(linked_statuses & PUBLICATION_STATES))
        errors.append(
            f"{rel}.prior_knowledge: unresolved classifications {sorted(unresolved)} block insight state(s) {states}; "
            "classify each match before review/publication"
        )


def main() -> int:
    inbox = json.loads(INBOX.read_text(encoding="utf-8"))
    intake = {item["id"]: item for item in inbox.get("items", [])}
    graph = json.loads(GRAPH.read_text(encoding="utf-8")) if GRAPH.exists() else {"concepts": []}
    graph_ids = {item.get("id") for item in graph.get("concepts", []) if isinstance(item, dict)}
    insight_data = json.loads(INSIGHTS.read_text(encoding="utf-8"))
    insight_records = [item for item in insight_data.get("insights", []) if isinstance(item, dict)]
    insight_ids = {item.get("id") for item in insight_records}
    insight_status_by_source: dict[str, set[str]] = defaultdict(set)
    for item in insight_records:
        if item.get("source_id"):
            insight_status_by_source[item["source_id"]].add(item.get("status"))
    source_data = json.loads(SOURCES.read_text(encoding="utf-8"))
    source_id_by_url = {
        item.get("canonical_url"): item.get("id")
        for item in source_data.get("sources", [])
        if isinstance(item, dict) and item.get("canonical_url") and item.get("id")
    }

    if not BUNDLES.exists():
        print("No research bundles committed yet.")
        return 0

    files = sorted(BUNDLES.glob("*.json"))
    for path in files:
        rel = path.relative_to(ROOT)
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue

        required = ["bundle_version", "intake_id", "source", "inspection", "content_map", "selection", "verification_candidates", "created_at"]
        for key in required:
            if key not in bundle:
                errors.append(f"{rel}: missing '{key}'")

        intake_id = bundle.get("intake_id")
        if intake_id not in intake:
            errors.append(f"{rel}: dangling intake_id '{intake_id}'")

        source = bundle.get("source", {})
        valid_url(source.get("canonical_url"), f"{rel}.source.canonical_url")
        if intake_id in intake and source.get("canonical_url") != intake[intake_id].get("source_url"):
            errors.append(f"{rel}: canonical_url differs from normalized intake source_url")

        inspection = bundle.get("inspection", {})
        if inspection.get("full_content_committed") is not False:
            errors.append(f"{rel}: full_content_committed must be false")
        if inspection.get("confidence") not in ALLOWED_CONFIDENCE:
            errors.append(f"{rel}: invalid inspection confidence '{inspection.get('confidence')}'")

        validate_prior_knowledge(
            bundle,
            rel,
            graph_ids,
            insight_ids,
            insight_status_by_source,
            source_id_by_url,
        )

        content_map = bundle.get("content_map", {})
        expected_map = {"problem", "thesis", "sections", "concepts", "mechanisms", "tools", "examples", "claims", "evidence", "assumptions", "limitations", "open_questions"}
        missing = expected_map - set(content_map)
        if missing:
            errors.append(f"{rel}.content_map: missing {sorted(missing)}")

        selection = bundle.get("selection", {})
        expected_selection = {"requested_focus", "coherent_core", "prerequisites", "drop_notes", "connections"}
        missing = expected_selection - set(selection)
        if missing:
            errors.append(f"{rel}.selection: missing {sorted(missing)}")

        for index, candidate in enumerate(bundle.get("verification_candidates", [])):
            if candidate.get("priority") not in {"high", "medium", "low"}:
                errors.append(f"{rel}.verification_candidates[{index}]: invalid priority")

        valid_date(bundle.get("created_at"), f"{rel}.created_at")

        # Guard against accidentally adding raw source dumps under tempting field names.
        forbidden_keys = {"transcript", "full_transcript", "raw_text", "full_text", "article_body", "pdf_text", "source_content"}
        stack: list[object] = [bundle]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.lower() in forbidden_keys:
                        errors.append(f"{rel}: forbidden raw-source field '{key}'")
                    stack.append(value)
            elif isinstance(node, list):
                stack.extend(node)

    if errors:
        print(f"Research bundle validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Research bundle validation passed: {len(files)} bundle(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
