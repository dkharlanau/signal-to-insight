#!/usr/bin/env python3
"""Validate multi-source synthesis records against claim evidence and review state."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "data" / "syntheses.json"
INSIGHTS = ROOT / "data" / "insights.json"
CLAIMS = ROOT / "data" / "claim-evidence.json"
REVIEWS = ROOT / "data" / "knowledge-reviews.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    synth_data = load(SYN)
    insight_data = load(INSIGHTS)
    claim_data = load(CLAIMS)
    review_data = load(REVIEWS)

    insights = {item["id"]: item for item in insight_data.get("insights", []) if item.get("id")}
    claims: dict[str, tuple[str, dict]] = {}
    for record in claim_data.get("records", []):
        owner = record.get("insight_id")
        for claim in record.get("claims", []):
            if claim.get("id"):
                claims[claim["id"]] = (owner, claim)
    reviews = {item["id"]: item for item in review_data.get("reviews", []) if item.get("id")}

    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    for index, synthesis in enumerate(synth_data.get("records", [])):
        where = f"data/syntheses.json records[{index}]"
        synth_id = synthesis.get("id")
        slug = synthesis.get("slug")
        if not isinstance(synth_id, str) or not synth_id:
            errors.append(f"{where}.id: required")
        elif synth_id in seen_ids:
            errors.append(f"{where}: duplicate id '{synth_id}'")
        else:
            seen_ids.add(synth_id)
        if not isinstance(slug, str) or not slug:
            errors.append(f"{where}.slug: required")
        elif slug in seen_slugs:
            errors.append(f"{where}: duplicate slug '{slug}'")
        else:
            seen_slugs.add(slug)

        status = synthesis.get("status")
        mode = synthesis.get("evidence_mode")
        if status not in {"review", "published", "archived"}:
            errors.append(f"{where}.status: invalid status '{status}'")
        if mode not in {"review_allowed", "published_only"}:
            errors.append(f"{where}.evidence_mode: invalid mode '{mode}'")
        if status == "published" and mode != "published_only":
            errors.append(f"{where}: published synthesis requires evidence_mode=published_only")

        question = synthesis.get("question")
        if not isinstance(question, str) or len(question.split()) < 6 or not question.strip().endswith("?"):
            errors.append(f"{where}.question: synthesis must start from a substantive question")
        for field in ("title", "one_liner", "thesis"):
            value = synthesis.get(field)
            if not isinstance(value, str) or len(value.split()) < 6:
                errors.append(f"{where}.{field}: expected substantive synthesis text")

        source_ids = synthesis.get("source_insight_ids")
        if not isinstance(source_ids, list) or len(source_ids) < 2 or len(set(source_ids)) != len(source_ids):
            errors.append(f"{where}.source_insight_ids: expected at least two unique insights")
            source_ids = []
        source_set = set(source_ids)
        for insight_id in source_ids:
            insight = insights.get(insight_id)
            if insight is None:
                errors.append(f"{where}: unknown source insight '{insight_id}'")
                continue
            if mode == "published_only" and insight.get("status") != "published":
                errors.append(f"{where}: published_only mode cannot use {insight.get('status')} insight '{insight_id}'")
            if mode == "review_allowed" and insight.get("status") not in {"review", "published"}:
                errors.append(f"{where}: review_allowed mode cannot use {insight.get('status')} insight '{insight_id}'")

        def validate_refs(refs: object, ref_where: str, min_distinct_sources: int = 1) -> set[str]:
            owners: set[str] = set()
            if not isinstance(refs, list) or not refs:
                errors.append(f"{ref_where}: expected non-empty claim_refs")
                return owners
            for claim_id in refs:
                owner_claim = claims.get(claim_id)
                if owner_claim is None:
                    errors.append(f"{ref_where}: unknown claim '{claim_id}'")
                    continue
                owner, claim = owner_claim
                owners.add(owner)
                if owner not in source_set:
                    errors.append(f"{ref_where}: claim '{claim_id}' belongs to non-source insight '{owner}'")
                if claim.get("status") == "unresolved":
                    errors.append(f"{ref_where}: unresolved claim '{claim_id}' cannot support a synthesis assertion")
                if status == "published" and insights.get(owner, {}).get("status") != "published":
                    errors.append(f"{ref_where}: published synthesis cannot cite non-published claim owner '{owner}'")
            if len(owners) < min_distinct_sources:
                errors.append(f"{ref_where}: expected evidence from at least {min_distinct_sources} distinct source insights")
            return owners

        consensus = synthesis.get("consensus")
        if not isinstance(consensus, list) or not consensus:
            errors.append(f"{where}.consensus: expected at least one cross-source agreement")
        else:
            for c_index, item in enumerate(consensus):
                c_where = f"{where}.consensus[{c_index}]"
                if not isinstance(item.get("statement"), str) or len(item.get("statement", "").split()) < 8:
                    errors.append(f"{c_where}.statement: expected concise synthesis statement")
                validate_refs(item.get("claim_refs"), f"{c_where}.claim_refs", min_distinct_sources=2)

        layers = synthesis.get("layers")
        if not isinstance(layers, list) or len(layers) < 2:
            errors.append(f"{where}.layers: expected at least two complementary layers")
            layers = []
        orders = [item.get("order") for item in layers if isinstance(item, dict)]
        if orders and sorted(orders) != list(range(1, len(orders) + 1)):
            errors.append(f"{where}.layers: order must be contiguous starting at 1")
        for l_index, layer in enumerate(layers):
            l_where = f"{where}.layers[{l_index}]"
            owner = layer.get("source_insight_id")
            if owner not in source_set:
                errors.append(f"{l_where}: source_insight_id '{owner}' is not part of synthesis sources")
            for field in ("name", "role", "does", "does_not"):
                if not isinstance(layer.get(field), str) or not layer.get(field, "").strip():
                    errors.append(f"{l_where}.{field}: required")
            owners = validate_refs(layer.get("claim_refs"), f"{l_where}.claim_refs")
            if owners and owners != {owner}:
                errors.append(f"{l_where}: layer claim refs must belong only to its source insight '{owner}'")

        disagreements = synthesis.get("reviewed_disagreements")
        if not isinstance(disagreements, list):
            errors.append(f"{where}.reviewed_disagreements: expected list")
            disagreements = []
        for d_index, item in enumerate(disagreements):
            d_where = f"{where}.reviewed_disagreements[{d_index}]"
            review = reviews.get(item.get("review_id"))
            if review is None:
                errors.append(f"{d_where}: unknown knowledge review '{item.get('review_id')}'")
            elif review.get("status") != "resolved":
                errors.append(f"{d_where}: synthesis may only cite resolved knowledge reviews")
            elif review.get("trigger_insight_id") not in source_set:
                errors.append(f"{d_where}: review trigger is outside synthesis sources")
            if not isinstance(item.get("why_it_matters"), str) or len(item.get("why_it_matters", "").split()) < 8:
                errors.append(f"{d_where}.why_it_matters: expected explanation")

        gaps = synthesis.get("unresolved_gaps")
        if not isinstance(gaps, list):
            errors.append(f"{where}.unresolved_gaps: expected list")
            gaps = []
        for g_index, item in enumerate(gaps):
            g_where = f"{where}.unresolved_gaps[{g_index}]"
            if not isinstance(item.get("statement"), str) or len(item.get("statement", "").split()) < 8:
                errors.append(f"{g_where}.statement: expected explicit unresolved boundary")
            validate_refs(item.get("claim_refs"), f"{g_where}.claim_refs", min_distinct_sources=2)

        visual = synthesis.get("visual_plan")
        if not isinstance(visual, dict) or visual.get("type") != "layers":
            errors.append(f"{where}.visual_plan: current synthesis contract requires layers visual")
        elif "project synthesis" not in visual.get("caption", "").lower():
            errors.append(f"{where}.visual_plan.caption: must explicitly label the composition as project synthesis")

        provenance = synthesis.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{where}.provenance: expected object")
            provenance = {}
        if provenance.get("source_claims_preserved") is not True:
            errors.append(f"{where}.provenance.source_claims_preserved must be true")
        if provenance.get("project_synthesis_explicit") is not True:
            errors.append(f"{where}.provenance.project_synthesis_explicit must be true")
        try:
            date.fromisoformat(provenance.get("created_at"))
        except (TypeError, ValueError):
            errors.append(f"{where}.provenance.created_at: expected ISO date")
        if status == "published":
            for field in ("reviewed_by", "review_note"):
                if not isinstance(provenance.get(field), str) or not provenance.get(field, "").strip():
                    errors.append(f"{where}: published synthesis requires {field}")
            try:
                date.fromisoformat(provenance.get("reviewed_at"))
            except (TypeError, ValueError):
                errors.append(f"{where}: published synthesis requires reviewed_at")

    if errors:
        print(f"Synthesis validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Synthesis validation passed: {len(seen_ids)} synthesis record(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
