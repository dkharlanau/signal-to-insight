#!/usr/bin/env python3
"""Validate Signal to Insight's machine-readable contracts without third-party deps."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ACTION_BUCKETS = {"use_now", "try", "learn", "build", "watch", "ignore_for_now"}
QUEUE_STATUSES = {"queued", "capturing", "mapping", "researching", "drafting", "review", "published", "archived", "blocked", "rejected"}
INSIGHT_STATUSES = {"draft", "review", "published", "archived"}
VISUAL_TYPES = {"causal_chain", "sequence", "layers", "comparison", "decision"}
SUPPORTING_VISUALS = VISUAL_TYPES | {"concept_grid", "tool_map", "examples", "limitations", "action_map", "source_map"}
QUALITY_SCORE_KEYS = {"coherence", "prerequisite_completeness", "evidence_confidence", "practical_leverage"}

errors: list[str] = []


def load_json(path: str):
    full = ROOT / path
    try:
        return json.loads(full.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
    return None


def require(obj: dict, keys: list[str], where: str) -> None:
    for key in keys:
        if key not in obj:
            errors.append(f"{where}: missing required field '{key}'")


def valid_date(value, where: str, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str):
        errors.append(f"{where}: expected ISO date string")
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        errors.append(f"{where}: invalid ISO date '{value}'")


def valid_url(value, where: str) -> None:
    if not isinstance(value, str):
        errors.append(f"{where}: URL must be a string")
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{where}: invalid http(s) URL '{value}'")


def unique(values: list[str], where: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            errors.append(f"{where}: duplicate '{value}'")
        seen.add(value)


def validate_schemas() -> None:
    for path in sorted((ROOT / "schemas").glob("*.json")):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                errors.append(f"{path.relative_to(ROOT)}: expected draft 2020-12 schema")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON schema {path.relative_to(ROOT)}: {exc}")


def validate_profile(profile: dict) -> None:
    where = "config/research-profile.json"
    require(profile, ["profile_version", "purpose", "scope", "goals", "selection", "explanation_preferences", "publishing"], where)
    publishing = profile.get("publishing", {})
    if publishing.get("auto_publish") is not False:
        errors.append(f"{where}: auto_publish must remain false for review-first publishing")
    if publishing.get("store_full_third_party_transcripts") is not False:
        errors.append(f"{where}: public project must not store full third-party transcripts")
    if publishing.get("require_source_and_date") is not True:
        errors.append(f"{where}: require_source_and_date must be true")
    buckets = set(profile.get("explanation_preferences", {}).get("action_buckets", []))
    if buckets != ACTION_BUCKETS:
        errors.append(f"{where}: action_buckets must equal {sorted(ACTION_BUCKETS)}")


def validate_sources(data: dict) -> set[str]:
    sources = data.get("sources")
    if not isinstance(sources, list):
        errors.append("data/sources.json: 'sources' must be a list")
        return set()
    ids: list[str] = []
    for index, source in enumerate(sources):
        where = f"data/sources.json sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{where}: expected object")
            continue
        require(source, ["id", "type", "title", "canonical_url", "creators", "captured_at", "analyzed_at", "derived_records"], where)
        source_id = source.get("id")
        if isinstance(source_id, str):
            ids.append(source_id)
            if not source_id.startswith("src-"):
                errors.append(f"{where}: source id must start with 'src-'")
        valid_url(source.get("canonical_url"), f"{where}.canonical_url")
        valid_date(source.get("published_at"), f"{where}.published_at", nullable=True)
        valid_date(source.get("event_date"), f"{where}.event_date", nullable=True)
        valid_date(source.get("captured_at"), f"{where}.captured_at")
        valid_date(source.get("analyzed_at"), f"{where}.analyzed_at")
        if source.get("published_at") is None and source.get("event_date") is None and not source.get("date_note"):
            errors.append(f"{where}: unknown source date requires date_note")
        for v_index, verification in enumerate(source.get("verification", [])):
            valid_url(verification.get("url"), f"{where}.verification[{v_index}].url")
            valid_date(verification.get("accessed_at"), f"{where}.verification[{v_index}].accessed_at")
    unique(ids, "data/sources.json source ids")
    return set(ids)


def validate_coherence(insight: dict, where: str) -> None:
    review = insight.get("coherence_review")
    if not isinstance(review, dict):
        errors.append(f"{where}.coherence_review: expected object")
        return
    require(review, ["central_chain", "prerequisites_complete", "source_vs_enrichment_clear", "open_gaps", "scores"], f"{where}.coherence_review")

    chain = review.get("central_chain")
    if not isinstance(chain, list) or len(chain) < 2 or not all(isinstance(item, str) and item.strip() for item in chain):
        errors.append(f"{where}.coherence_review.central_chain: expected at least two non-empty steps")

    if not isinstance(review.get("prerequisites_complete"), bool):
        errors.append(f"{where}.coherence_review.prerequisites_complete: expected boolean")
    if not isinstance(review.get("source_vs_enrichment_clear"), bool):
        errors.append(f"{where}.coherence_review.source_vs_enrichment_clear: expected boolean")

    gaps = review.get("open_gaps")
    if not isinstance(gaps, list) or not all(isinstance(item, str) for item in gaps):
        errors.append(f"{where}.coherence_review.open_gaps: expected list of strings")

    scores = review.get("scores")
    if not isinstance(scores, dict) or set(scores) != QUALITY_SCORE_KEYS:
        errors.append(f"{where}.coherence_review.scores: keys must equal {sorted(QUALITY_SCORE_KEYS)}")
    else:
        for key, value in scores.items():
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
                errors.append(f"{where}.coherence_review.scores.{key}: expected integer 1..5")

    if insight.get("status") == "published":
        if review.get("prerequisites_complete") is not True:
            errors.append(f"{where}: published insight requires prerequisites_complete=true")
        if review.get("source_vs_enrichment_clear") is not True:
            errors.append(f"{where}: published insight requires source_vs_enrichment_clear=true")


def validate_visual_plan(insight: dict, where: str) -> None:
    plan = insight.get("visual_plan")
    if not isinstance(plan, dict):
        errors.append(f"{where}.visual_plan: expected object")
        return
    require(plan, ["dominant", "supporting", "image"], f"{where}.visual_plan")

    dominant = plan.get("dominant")
    if not isinstance(dominant, dict):
        errors.append(f"{where}.visual_plan.dominant: expected object")
    else:
        require(dominant, ["type", "title", "nodes"], f"{where}.visual_plan.dominant")
        visual_type = dominant.get("type")
        if visual_type not in VISUAL_TYPES:
            errors.append(f"{where}.visual_plan.dominant.type: invalid visual type '{visual_type}'")
        if not isinstance(dominant.get("title"), str) or not dominant.get("title", "").strip():
            errors.append(f"{where}.visual_plan.dominant.title: expected non-empty string")
        nodes = dominant.get("nodes")
        if not isinstance(nodes, list) or len(nodes) < 2:
            errors.append(f"{where}.visual_plan.dominant.nodes: expected at least two nodes")
        else:
            for index, node in enumerate(nodes):
                n_where = f"{where}.visual_plan.dominant.nodes[{index}]"
                if not isinstance(node, dict):
                    errors.append(f"{n_where}: expected object")
                    continue
                require(node, ["label", "title", "text"], n_where)
                for key in ("label", "title", "text"):
                    if not isinstance(node.get(key), str) or not node.get(key, "").strip():
                        errors.append(f"{n_where}.{key}: expected non-empty string")
        if visual_type == "comparison" and isinstance(nodes, list) and len(nodes) != 2:
            errors.append(f"{where}.visual_plan.dominant: comparison requires exactly two nodes")

    supporting = plan.get("supporting")
    if not isinstance(supporting, list):
        errors.append(f"{where}.visual_plan.supporting: expected list")
    else:
        invalid = [item for item in supporting if item not in SUPPORTING_VISUALS]
        if invalid:
            errors.append(f"{where}.visual_plan.supporting: invalid values {invalid}")

    image = plan.get("image")
    if not isinstance(image, dict):
        errors.append(f"{where}.visual_plan.image: expected object")
    else:
        require(image, ["needed", "reason"], f"{where}.visual_plan.image")
        if not isinstance(image.get("needed"), bool):
            errors.append(f"{where}.visual_plan.image.needed: expected boolean")
        if not isinstance(image.get("reason"), str) or not image.get("reason", "").strip():
            errors.append(f"{where}.visual_plan.image.reason: explain why an image is or is not useful")


def validate_insights(data: dict, source_ids: set[str]) -> set[str]:
    insights = data.get("insights")
    if not isinstance(insights, list):
        errors.append("data/insights.json: 'insights' must be a list")
        return set()
    ids: list[str] = []
    slugs: list[str] = []
    for index, insight in enumerate(insights):
        where = f"data/insights.json insights[{index}]"
        if not isinstance(insight, dict):
            errors.append(f"{where}: expected object")
            continue
        require(insight, ["id", "source_id", "slug", "status", "title", "one_liner", "why_this_matters", "whole_source_map", "derived_model", "coherence_review", "visual_plan", "concepts", "tool_map", "examples", "limitations", "action_map", "supporting_sources", "provenance"], where)
        insight_id = insight.get("id")
        slug = insight.get("slug")
        if isinstance(insight_id, str):
            ids.append(insight_id)
        if isinstance(slug, str):
            slugs.append(slug)
        if insight.get("source_id") not in source_ids:
            errors.append(f"{where}: dangling source_id '{insight.get('source_id')}'")
        if insight.get("status") not in INSIGHT_STATUSES:
            errors.append(f"{where}: invalid status '{insight.get('status')}'")

        validate_coherence(insight, where)
        validate_visual_plan(insight, where)

        action_map = insight.get("action_map")
        if not isinstance(action_map, dict):
            errors.append(f"{where}.action_map: expected object")
        else:
            if set(action_map) != ACTION_BUCKETS:
                errors.append(f"{where}.action_map: buckets must equal {sorted(ACTION_BUCKETS)}")
            for bucket, items in action_map.items():
                if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                    errors.append(f"{where}.action_map.{bucket}: expected list of strings")

        for t_index, tool in enumerate(insight.get("tool_map", [])):
            t_where = f"{where}.tool_map[{t_index}]"
            valid_url(tool.get("url"), f"{t_where}.url")
            if tool.get("status") not in ACTION_BUCKETS:
                errors.append(f"{t_where}: invalid status '{tool.get('status')}'")
            if not tool.get("relationship"):
                errors.append(f"{t_where}: relationship must distinguish source content from project enrichment")

        for s_index, supporting in enumerate(insight.get("supporting_sources", [])):
            s_where = f"{where}.supporting_sources[{s_index}]"
            valid_url(supporting.get("url"), f"{s_where}.url")
            valid_date(supporting.get("accessed_at"), f"{s_where}.accessed_at")

        provenance = insight.get("provenance", {})
        if provenance.get("source_linked") is not True:
            errors.append(f"{where}.provenance: source_linked must be true")
        if provenance.get("source_dates_recorded") is not True:
            errors.append(f"{where}.provenance: source_dates_recorded must be true")
        if provenance.get("full_transcript_stored") is not False:
            errors.append(f"{where}.provenance: full_transcript_stored must be false")
        valid_date(provenance.get("reviewed_at"), f"{where}.provenance.reviewed_at")

    unique(ids, "data/insights.json insight ids")
    unique(slugs, "data/insights.json slugs")
    return set(ids)


def validate_inbox(data: dict, source_ids: set[str], insight_ids: set[str]) -> None:
    items = data.get("items")
    if not isinstance(items, list):
        errors.append("data/inbox.json: 'items' must be a list")
        return
    ids: list[str] = []
    for index, item in enumerate(items):
        where = f"data/inbox.json items[{index}]"
        require(item, ["id", "source_url", "source_type", "submitted_at", "status"], where)
        item_id = item.get("id")
        if isinstance(item_id, str):
            ids.append(item_id)
            if not item_id.startswith("intake-"):
                errors.append(f"{where}: intake id must start with 'intake-'")
        valid_url(item.get("source_url"), f"{where}.source_url")
        valid_date(item.get("submitted_at"), f"{where}.submitted_at")
        status = item.get("status")
        if status not in QUEUE_STATUSES:
            errors.append(f"{where}: invalid status '{status}'")
        source_id = item.get("source_id")
        insight_id = item.get("insight_id")
        if source_id is not None and source_id not in source_ids:
            errors.append(f"{where}: dangling source_id '{source_id}'")
        if insight_id is not None and insight_id not in insight_ids:
            errors.append(f"{where}: dangling insight_id '{insight_id}'")
        if status == "published" and (source_id is None or insight_id is None):
            errors.append(f"{where}: published item must link source_id and insight_id")
    unique(ids, "data/inbox.json intake ids")


def main() -> int:
    validate_schemas()
    profile = load_json("config/research-profile.json")
    sources = load_json("data/sources.json")
    insights = load_json("data/insights.json")
    inbox = load_json("data/inbox.json")

    if isinstance(profile, dict):
        validate_profile(profile)
    source_ids = validate_sources(sources) if isinstance(sources, dict) else set()
    insight_ids = validate_insights(insights, source_ids) if isinstance(insights, dict) else set()
    if isinstance(inbox, dict):
        validate_inbox(inbox, source_ids, insight_ids)

    if errors:
        print(f"Signal to Insight validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Signal to Insight validation passed.")
    print(f"Sources: {len(source_ids)} | Insights: {len(insight_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
