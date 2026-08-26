#!/usr/bin/env python3
"""Validate claim-level evidence traces and epistemic labels."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "data" / "claim-evidence.json"
INSIGHTS = ROOT / "data" / "insights.json"
SOURCES = ROOT / "data" / "sources.json"

ALLOWED_ORIGINS = {"source", "verification", "project_interpretation", "prior_knowledge"}
ALLOWED_STATUSES = {"supported", "uncertain", "unresolved"}
ALLOWED_KINDS = {"primary_source", "verification", "prior_insight"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def main() -> int:
    errors: list[str] = []
    claims_data = load(CLAIMS)
    insights_data = load(INSIGHTS)
    sources_data = load(SOURCES)

    insights = {item["id"]: item for item in insights_data.get("insights", []) if item.get("id")}
    sources = {item["id"]: item for item in sources_data.get("sources", []) if item.get("id")}
    records: dict[str, dict] = {}
    claim_ids: set[str] = set()

    for record_index, record in enumerate(claims_data.get("records", [])):
        where = f"data/claim-evidence.json records[{record_index}]"
        insight_id = record.get("insight_id")
        if not isinstance(insight_id, str) or not insight_id:
            errors.append(f"{where}: insight_id is required")
            continue
        if insight_id in records:
            errors.append(f"{where}: duplicate insight_id '{insight_id}'")
            continue
        records[insight_id] = record

        insight = insights.get(insight_id)
        if insight is None:
            errors.append(f"{where}: unknown insight '{insight_id}'")
            continue
        if insight.get("status") not in {"review", "published"}:
            errors.append(f"{where}: evidence trace should only exist for review/published insights")

        current_source_id = insight.get("source_id")
        current_source = sources.get(current_source_id)
        if current_source is None:
            errors.append(f"{where}: insight source_id '{current_source_id}' is not registered")
            continue
        allowed_source_urls = {current_source.get("canonical_url")}
        allowed_source_urls.update(
            entry.get("url") for entry in current_source.get("verification", []) if entry.get("url")
        )

        claims = record.get("claims")
        if not isinstance(claims, list) or len(claims) < 2:
            errors.append(f"{where}.claims: expected at least two important claims")
            continue

        for claim_index, claim in enumerate(claims):
            c_where = f"{where}.claims[{claim_index}]"
            claim_id = claim.get("id")
            if not isinstance(claim_id, str) or not claim_id:
                errors.append(f"{c_where}.id: expected non-empty string")
            elif claim_id in claim_ids:
                errors.append(f"{c_where}: duplicate global claim id '{claim_id}'")
            else:
                claim_ids.add(claim_id)

            text = claim.get("text")
            if not isinstance(text, str) or len(text.split()) < 6:
                errors.append(f"{c_where}.text: expected a substantive paraphrased claim")
            for forbidden_key in ("quote", "excerpt", "full_text", "source_text"):
                if forbidden_key in claim:
                    errors.append(f"{c_where}: forbidden copied-content field '{forbidden_key}'")

            impact = claim.get("impact")
            if impact not in {"high", "medium"}:
                errors.append(f"{c_where}.impact: expected high or medium")
            origin = claim.get("origin")
            if origin not in ALLOWED_ORIGINS:
                errors.append(f"{c_where}.origin: invalid origin '{origin}'")
            status = claim.get("status")
            if status not in ALLOWED_STATUSES:
                errors.append(f"{c_where}.status: invalid status '{status}'")

            note = claim.get("note")
            if status in {"uncertain", "unresolved"} and (not isinstance(note, str) or not note.strip()):
                errors.append(f"{c_where}: {status} claim requires a note explaining uncertainty")
            if origin == "project_interpretation" and (not isinstance(note, str) or not note.strip()):
                errors.append(f"{c_where}: project_interpretation requires a note separating synthesis from source content")

            evidence = claim.get("evidence")
            if not isinstance(evidence, list):
                errors.append(f"{c_where}.evidence: expected list")
                evidence = []
            if impact == "high" and status == "supported" and not evidence:
                errors.append(f"{c_where}: supported high-impact claim requires evidence")

            has_current_primary = False
            has_verification = False
            has_prior = False
            for evidence_index, item in enumerate(evidence):
                e_where = f"{c_where}.evidence[{evidence_index}]"
                if not isinstance(item, dict):
                    errors.append(f"{e_where}: expected object")
                    continue
                kind = item.get("kind")
                if kind not in ALLOWED_KINDS:
                    errors.append(f"{e_where}.kind: invalid kind '{kind}'")
                    continue
                locator = item.get("locator")
                if not isinstance(locator, str) or not locator.strip():
                    errors.append(f"{e_where}.locator: required non-empty locator")

                if kind in {"primary_source", "verification"}:
                    source_id = item.get("source_id")
                    url = item.get("url")
                    if source_id != current_source_id:
                        errors.append(
                            f"{e_where}: source evidence must reference current source '{current_source_id}', found '{source_id}'"
                        )
                    if not valid_http_url(url):
                        errors.append(f"{e_where}.url: expected valid http(s) URL")
                    elif url not in allowed_source_urls:
                        errors.append(f"{e_where}.url: URL is not registered on current source provenance")
                    if kind == "primary_source":
                        has_current_primary = True
                    else:
                        has_verification = True

                if kind == "prior_insight":
                    prior_id = item.get("insight_id")
                    prior = insights.get(prior_id)
                    if prior is None:
                        errors.append(f"{e_where}: unknown prior insight '{prior_id}'")
                    elif prior_id == insight_id:
                        errors.append(f"{e_where}: claim cannot cite its own insight as prior knowledge")
                    elif insight.get("status") == "published" and prior.get("status") != "published":
                        errors.append(
                            f"{e_where}: published claim cannot depend on non-published prior insight '{prior_id}'"
                        )
                    else:
                        has_prior = True

            if origin == "source" and not has_current_primary:
                errors.append(f"{c_where}: source-origin claim requires primary_source evidence from the current source")
            if origin == "verification" and not has_verification:
                errors.append(f"{c_where}: verification-origin claim requires verification evidence")
            if origin == "prior_knowledge" and not has_prior:
                errors.append(f"{c_where}: prior_knowledge claim requires a prior_insight evidence item")
            if origin == "project_interpretation" and not (has_current_primary or has_verification or has_prior):
                errors.append(f"{c_where}: project interpretation requires traceable source/prior evidence")

    required = {
        item["id"]
        for item in insights.values()
        if item.get("status") in {"review", "published"}
    }
    missing = sorted(required - set(records))
    if missing:
        errors.append(f"missing claim-evidence record(s): {missing}")

    if errors:
        print(f"Claim evidence validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    total_claims = sum(len(record.get("claims", [])) for record in records.values())
    print(f"Claim evidence validation passed: {len(records)} insight(s), {total_claims} claim(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
