#!/usr/bin/env python3
"""Validate source-consumption decisions after whole-source mapping."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "data" / "source-decisions.json"
INSIGHTS = ROOT / "data" / "insights.json"
INBOX = ROOT / "data" / "inbox.json"
BUNDLES = ROOT / "data" / "research-bundles"
CLAIMS = ROOT / "data" / "claim-evidence.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    decision_data = load(DECISIONS)
    insight_data = load(INSIGHTS)
    inbox_data = load(INBOX)
    claim_data = load(CLAIMS)

    insights = {item["id"]: item for item in insight_data.get("insights", []) if item.get("id")}
    intake_by_insight = {
        item.get("insight_id"): item
        for item in inbox_data.get("items", [])
        if item.get("insight_id")
    }
    claims: dict[str, tuple[str, dict]] = {}
    locators_by_insight: dict[str, set[str]] = {}
    for record in claim_data.get("records", []):
        owner = record.get("insight_id")
        locators = locators_by_insight.setdefault(owner, set())
        for claim in record.get("claims", []):
            if claim.get("id"):
                claims[claim["id"]] = (owner, claim)
            for evidence in claim.get("evidence", []):
                locator = evidence.get("locator")
                if locator:
                    locators.add(locator)

    records: dict[str, dict] = {}
    for index, record in enumerate(decision_data.get("records", [])):
        where = f"data/source-decisions.json records[{index}]"
        insight_id = record.get("insight_id")
        insight = insights.get(insight_id)
        if insight is None:
            errors.append(f"{where}: unknown insight '{insight_id}'")
            continue
        if insight.get("status") not in {"review", "published"}:
            errors.append(f"{where}: source decision should only exist for review/published insight")
        if insight_id in records:
            errors.append(f"{where}: duplicate source decision for '{insight_id}'")
        records[insight_id] = record

        intake = intake_by_insight.get(insight_id)
        if intake is None:
            errors.append(f"{where}: no linked intake; cannot prove whole-source mapping happened first")
        else:
            bundle_path = BUNDLES / f"{intake['id']}.json"
            if not bundle_path.exists():
                errors.append(f"{where}: missing research bundle {bundle_path.relative_to(ROOT)}")
            else:
                bundle = load(bundle_path)
                content_map = bundle.get("content_map") or {}
                inspection = bundle.get("inspection") or {}
                if not content_map.get("problem") or not content_map.get("thesis"):
                    errors.append(f"{where}: source decision is forbidden before whole-source problem/thesis mapping")
                if inspection.get("method") in {None, "", "not inspected"} or inspection.get("confidence") == "metadata_only":
                    errors.append(f"{where}: source decision is forbidden before substantive source inspection")

        decision = record.get("decision")
        if decision not in {"consume", "skim_selected_parts", "explainer_is_enough", "skip_for_now"}:
            errors.append(f"{where}.decision: invalid decision '{decision}'")
        rationale = record.get("rationale")
        if not isinstance(rationale, str) or len(rationale.split()) < 12:
            errors.append(f"{where}.rationale: expected substantive decision rationale")

        factors = {}
        for field in ("novelty", "source_quality", "relevance", "practical_leverage", "compression_loss"):
            factor = record.get(field)
            factors[field] = factor if isinstance(factor, dict) else {}
            if not isinstance(factor, dict):
                errors.append(f"{where}.{field}: expected factor object")
                continue
            if factor.get("level") not in {"high", "medium", "low"}:
                errors.append(f"{where}.{field}.level: invalid level")
            if not isinstance(factor.get("reason"), str) or len(factor.get("reason", "").split()) < 8:
                errors.append(f"{where}.{field}.reason: expected explicit reason")

        if decision == "explainer_is_enough" and factors.get("compression_loss", {}).get("level") == "high":
            errors.append(f"{where}: explainer_is_enough conflicts with high compression loss")
        if decision == "skip_for_now":
            relevance_low = factors.get("relevance", {}).get("level") == "low"
            leverage_low = factors.get("practical_leverage", {}).get("level") == "low"
            quality_low = factors.get("source_quality", {}).get("level") == "low"
            if not (relevance_low or leverage_low or quality_low):
                errors.append(f"{where}: skip_for_now needs an explicit low relevance, leverage or quality reason")

        parts = record.get("selected_parts")
        if not isinstance(parts, list):
            errors.append(f"{where}.selected_parts: expected list")
            parts = []
        if len(parts) > 4:
            errors.append(f"{where}.selected_parts: keep skimming guidance compact (max 4 parts)")
        if decision == "skim_selected_parts" and not parts:
            errors.append(f"{where}: skim_selected_parts requires at least one locator")
        if decision == "explainer_is_enough" and parts:
            errors.append(f"{where}: explainer_is_enough should not simultaneously prescribe source sections to open")

        known_locators = locators_by_insight.get(insight_id, set())
        for part_index, part in enumerate(parts):
            p_where = f"{where}.selected_parts[{part_index}]"
            for field in ("label", "locator", "why"):
                if not isinstance(part.get(field), str) or not part.get(field, "").strip():
                    errors.append(f"{p_where}.{field}: required")
            locator = part.get("locator")
            if locator and locator not in known_locators:
                errors.append(f"{p_where}.locator: locator is not backed by the current claim-evidence trace")
            refs = part.get("claim_refs")
            if not isinstance(refs, list) or not refs:
                errors.append(f"{p_where}.claim_refs: expected non-empty claim refs")
                refs = []
            for claim_id in refs:
                owner_claim = claims.get(claim_id)
                if owner_claim is None:
                    errors.append(f"{p_where}: unknown claim '{claim_id}'")
                elif owner_claim[0] != insight_id:
                    errors.append(f"{p_where}: claim '{claim_id}' belongs to another insight '{owner_claim[0]}'")

    required = {
        item["id"]
        for item in insights.values()
        if item.get("status") in {"review", "published"}
    }
    missing = sorted(required - set(records))
    if missing:
        errors.append(f"missing source decision record(s): {missing}")

    if errors:
        print(f"Source decision validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Source decision validation passed: {len(records)} decision(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
