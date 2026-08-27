#!/usr/bin/env python3
"""Validate companion review contracts before materialization.

A case contract intentionally references the researched case patch rather than requiring
that the insight already exists in the shared registries. This lets one push contain the
pending case + all mandatory review records without making main temporarily invalid.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "data" / "case-contracts"
PATCHES = ROOT / "data" / "case-patches"
REQUIRED_RECORDS = {
    "knowledge_delta",
    "claim_evidence",
    "prerequisite_map",
    "learning_prompt",
    "source_decision",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def nonempty_text(value: object, words: int = 1) -> bool:
    return isinstance(value, str) and len(value.split()) >= words


def validate_contract(path: Path, payload: dict) -> list[str]:
    errors: list[str] = []
    where = str(path.relative_to(ROOT))
    patch_path = PATCHES / path.name
    if not patch_path.exists():
        return [f"{where}: matching researched case patch is missing: {patch_path.relative_to(ROOT)}"]
    patch = load(patch_path)
    insight = patch.get("insight") or {}
    insight_id = payload.get("insight_id")
    intake_id = payload.get("intake_id")
    if intake_id != patch.get("intake_id"):
        errors.append(f"{where}: intake_id differs from matching case patch")
    if insight_id != insight.get("id"):
        errors.append(f"{where}: insight_id differs from matching case patch")
    if patch.get("intake_status") != "review" or insight.get("status") != "review":
        errors.append(f"{where}: companion contracts are only for review-ready case patches")

    for key in REQUIRED_RECORDS:
        record = payload.get(key)
        if not isinstance(record, dict):
            errors.append(f"{where}.{key}: expected object")
            continue
        if record.get("insight_id") != insight_id:
            errors.append(f"{where}.{key}: insight_id must equal top-level insight_id")

    delta = payload.get("knowledge_delta") or {}
    if not nonempty_text(delta.get("summary"), 8):
        errors.append(f"{where}.knowledge_delta.summary: expected substantive summary")
    if not isinstance(delta.get("items"), list) or not delta.get("items"):
        errors.append(f"{where}.knowledge_delta.items: expected at least one delta item")
    if not isinstance(delta.get("suppressed_prior_matches"), list):
        errors.append(f"{where}.knowledge_delta.suppressed_prior_matches: expected list")

    claims = payload.get("claim_evidence") or {}
    if not isinstance(claims.get("claims"), list) or len(claims.get("claims", [])) < 2:
        errors.append(f"{where}.claim_evidence.claims: expected at least two claims")

    prereq = payload.get("prerequisite_map") or {}
    if not nonempty_text(prereq.get("summary"), 8):
        errors.append(f"{where}.prerequisite_map.summary: expected substantive summary")
    if not isinstance(prereq.get("items"), list) or not prereq.get("items"):
        errors.append(f"{where}.prerequisite_map.items: expected prerequisites")

    prompt = payload.get("learning_prompt") or {}
    if not nonempty_text(prompt.get("retention_prompt"), 12):
        errors.append(f"{where}.learning_prompt.retention_prompt: expected authored reconstruction prompt")
    if not isinstance(prompt.get("answer_key"), dict):
        errors.append(f"{where}.learning_prompt.answer_key: expected object")

    decision = payload.get("source_decision") or {}
    if decision.get("decision") not in {"consume", "skim_selected_parts", "explainer_is_enough", "skip_for_now"}:
        errors.append(f"{where}.source_decision.decision: invalid decision")
    if not nonempty_text(decision.get("rationale"), 12):
        errors.append(f"{where}.source_decision.rationale: expected substantive rationale")
    return errors


def main() -> int:
    errors: list[str] = []
    seen_insights: set[str] = set()
    paths = sorted(CONTRACTS.glob("*.json")) if CONTRACTS.exists() else []
    for path in paths:
        try:
            payload = load(path)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
            continue
        insight_id = payload.get("insight_id")
        if insight_id in seen_insights:
            errors.append(f"{path.relative_to(ROOT)}: duplicate companion contract for '{insight_id}'")
        elif isinstance(insight_id, str):
            seen_insights.add(insight_id)
        errors.extend(validate_contract(path, payload))

    if errors:
        print(f"Case contract validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Case contract validation passed: {len(paths)} contract(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
