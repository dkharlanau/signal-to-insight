#!/usr/bin/env python3
"""Validate contradiction/refinement reviews and guard against false conflicts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "data" / "knowledge-reviews.json"
CLAIMS = ROOT / "data" / "claim-evidence.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"
FALSE_FIXTURE = ROOT / "tests" / "fixtures" / "knowledge-review-false-contradiction.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def contradiction_scope_valid(scope: dict) -> bool:
    return bool(
        scope.get("same_subject") is True
        and scope.get("same_layer") is True
        and scope.get("same_conditions") is True
        and scope.get("assessment") == "same_scope"
    )


def validate_reviews() -> list[str]:
    errors: list[str] = []
    reviews_data = load(REVIEWS)
    claims_data = load(CLAIMS)
    graph_data = load(GRAPH)
    insights_data = load(INSIGHTS)

    concepts = {item["id"] for item in graph_data.get("concepts", []) if item.get("id")}
    relations = {item["id"] for item in graph_data.get("relations", []) if item.get("id")}
    insights = {item["id"]: item for item in insights_data.get("insights", []) if item.get("id")}
    claims: dict[str, tuple[str, dict]] = {}
    for record in claims_data.get("records", []):
        insight_id = record.get("insight_id")
        for claim in record.get("claims", []):
            claim_id = claim.get("id")
            if claim_id:
                claims[claim_id] = (insight_id, claim)

    seen: set[str] = set()
    for index, review in enumerate(reviews_data.get("reviews", [])):
        where = f"data/knowledge-reviews.json reviews[{index}]"
        review_id = review.get("id")
        if not isinstance(review_id, str) or not review_id:
            errors.append(f"{where}.id: expected non-empty string")
        elif review_id in seen:
            errors.append(f"{where}: duplicate review id '{review_id}'")
        else:
            seen.add(review_id)

        concept_id = review.get("concept_id")
        if concept_id not in concepts:
            errors.append(f"{where}: unknown concept_id '{concept_id}'")
        trigger_id = review.get("trigger_insight_id")
        if trigger_id not in insights:
            errors.append(f"{where}: unknown trigger insight '{trigger_id}'")

        candidate = review.get("candidate_type")
        if candidate not in {"refinement", "contradiction"}:
            errors.append(f"{where}.candidate_type: invalid candidate '{candidate}'")

        evidence = review.get("evidence")
        if not isinstance(evidence, dict):
            errors.append(f"{where}.evidence: expected object")
            evidence = {}
        new_claim_ids = evidence.get("new_claim_ids")
        prior_claim_ids = evidence.get("prior_claim_ids")
        if not isinstance(new_claim_ids, list) or not new_claim_ids:
            errors.append(f"{where}.evidence.new_claim_ids: expected non-empty list")
            new_claim_ids = []
        if not isinstance(prior_claim_ids, list) or not prior_claim_ids:
            errors.append(f"{where}.evidence.prior_claim_ids: expected non-empty list")
            prior_claim_ids = []
        for claim_id in new_claim_ids:
            owner = claims.get(claim_id)
            if owner is None:
                errors.append(f"{where}: unknown new claim '{claim_id}'")
            elif owner[0] != trigger_id:
                errors.append(f"{where}: new claim '{claim_id}' is not owned by trigger insight '{trigger_id}'")
        for claim_id in prior_claim_ids:
            owner = claims.get(claim_id)
            if owner is None:
                errors.append(f"{where}: unknown prior claim '{claim_id}'")
            elif owner[0] == trigger_id:
                errors.append(f"{where}: prior claim '{claim_id}' cannot come from the trigger insight")

        scope = review.get("scope_check")
        if not isinstance(scope, dict):
            errors.append(f"{where}.scope_check: expected object")
            scope = {}
        for key in ("same_subject", "same_layer", "same_conditions"):
            if not isinstance(scope.get(key), bool):
                errors.append(f"{where}.scope_check.{key}: expected boolean")
        if scope.get("assessment") not in {
            "same_scope",
            "different_subject",
            "different_layer",
            "different_conditions",
            "narrower_scope",
            "broader_scope",
        }:
            errors.append(f"{where}.scope_check.assessment: invalid assessment")
        if not isinstance(scope.get("explanation"), str) or len(scope.get("explanation", "").split()) < 8:
            errors.append(f"{where}.scope_check.explanation: expected substantive scope explanation")

        resolution = review.get("resolution")
        if resolution not in {"refinement", "contradiction", "different_scope", "not_conflict", "needs_more_evidence"}:
            errors.append(f"{where}.resolution: invalid resolution '{resolution}'")
        if resolution == "contradiction" and not contradiction_scope_valid(scope):
            errors.append(
                f"{where}: contradiction resolution requires same subject/layer/conditions and assessment=same_scope"
            )
        if candidate == "contradiction" and not contradiction_scope_valid(scope) and resolution == "contradiction":
            errors.append(f"{where}: false contradiction must be resolved as different_scope/refinement/not_conflict")
        if not isinstance(review.get("rationale"), str) or len(review.get("rationale", "").split()) < 10:
            errors.append(f"{where}.rationale: expected substantive human-readable rationale")

        model_change = review.get("model_change")
        if not isinstance(model_change, dict):
            errors.append(f"{where}.model_change: expected object")
            model_change = {}
        kind = model_change.get("kind")
        target = model_change.get("target_id")
        before = model_change.get("before")
        after = model_change.get("after")
        if kind not in {"none", "concept_definition", "relation"}:
            errors.append(f"{where}.model_change.kind: invalid kind '{kind}'")
        if kind == "none":
            if before is not None or after is not None:
                errors.append(f"{where}.model_change: kind=none requires before/after=null")
        elif kind == "concept_definition":
            if target not in concepts:
                errors.append(f"{where}.model_change: unknown concept target '{target}'")
            if not isinstance(before, str) or not isinstance(after, str) or not before.strip() or not after.strip() or before == after:
                errors.append(f"{where}.model_change: concept definition change must preserve distinct before/after text")
        elif kind == "relation":
            if target not in relations:
                errors.append(f"{where}.model_change: unknown relation target '{target}'")
            if not isinstance(before, dict) or not isinstance(after, dict) or before == after:
                errors.append(f"{where}.model_change: relation change must preserve distinct before/after objects")
        if not isinstance(model_change.get("reason"), str) or not model_change.get("reason", "").strip():
            errors.append(f"{where}.model_change.reason: required")

        status = review.get("status")
        if status not in {"open", "resolved"}:
            errors.append(f"{where}.status: invalid status '{status}'")
        reviewed_by = review.get("reviewed_by")
        reviewed_at = review.get("reviewed_at")
        if status == "resolved":
            if not isinstance(reviewed_by, str) or not reviewed_by.strip():
                errors.append(f"{where}: resolved review requires reviewed_by")
            try:
                date.fromisoformat(reviewed_at)
            except (TypeError, ValueError):
                errors.append(f"{where}: resolved review requires ISO reviewed_at")

        history = review.get("history")
        if not isinstance(history, list) or not history:
            errors.append(f"{where}.history: expected non-empty event history")
            history = []
        actions = []
        for event_index, event in enumerate(history):
            h_where = f"{where}.history[{event_index}]"
            action = event.get("action") if isinstance(event, dict) else None
            actions.append(action)
            if action not in {"candidate_created", "scope_reviewed", "resolved", "model_changed", "reopened"}:
                errors.append(f"{h_where}.action: invalid action '{action}'")
            try:
                date.fromisoformat(event.get("at"))
            except (AttributeError, TypeError, ValueError):
                errors.append(f"{h_where}.at: expected ISO date")
            if not isinstance(event.get("note"), str) or not event.get("note", "").strip():
                errors.append(f"{h_where}.note: required")
        if "candidate_created" not in actions:
            errors.append(f"{where}.history: must preserve candidate_created event")
        if status == "resolved" and "resolved" not in actions:
            errors.append(f"{where}.history: resolved review must preserve resolution event")
        if kind != "none" and "model_changed" not in actions:
            errors.append(f"{where}.history: applied model change must preserve model_changed event")

    return errors


def self_test() -> int:
    fixture = load(FALSE_FIXTURE)
    scope = fixture["scope_check"]
    if fixture.get("attempted_resolution") != "contradiction":
        print("Knowledge review self-test fixture is malformed.")
        return 1
    if contradiction_scope_valid(scope):
        print("Knowledge review self-test failed: different-layer case was accepted as same-scope contradiction.")
        return 1
    if fixture.get("expected") != "reject_as_false_contradiction":
        print("Knowledge review self-test failed: fixture expectation missing.")
        return 1
    print("Knowledge review false-contradiction self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    try:
        errors = validate_reviews()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Knowledge review validation error: {exc}")
        return 1
    if errors:
        print(f"Knowledge review validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    data = load(REVIEWS)
    print(f"Knowledge review validation passed: {len(data.get('reviews', []))} review(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
