#!/usr/bin/env python3
"""Export and validate a public-only research evidence handoff packet."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INSIGHTS = ROOT / "data" / "insights.json"
SOURCES = ROOT / "data" / "sources.json"
CLAIMS = ROOT / "data" / "claim-evidence.json"
SCHEMA_URL = "https://dkharlanau.github.io/signal-to-insight/contracts/research-evidence-handoff.schema.json"
SCHEMA_VERSION = "1.0.0"
SITE_BASE = "https://dkharlanau.github.io/signal-to-insight"
REPOSITORY = "https://github.com/dkharlanau/signal-to-insight"
CANONICALIZATION = "UTF-8 JSON with lexicographically sorted object keys and compact separators"
TOP_LEVEL_FIELDS = {
    "schema",
    "schema_version",
    "packet_id",
    "producer",
    "exported_from",
    "source",
    "claims",
    "operational_boundary",
    "integrity",
}
FORBIDDEN_RAW_KEYS = {
    "transcript",
    "full_transcript",
    "raw_text",
    "full_text",
    "article_body",
    "pdf_text",
    "source_content",
}


class HandoffError(ValueError):
    pass


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise HandoffError(f"expected a JSON object in {path}")
    return data


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def payload_digest(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def serialize(packet: dict) -> str:
    return json.dumps(packet, ensure_ascii=False, indent=2) + "\n"


def find_by_id(items: object, item_id: str, label: str) -> dict:
    if not isinstance(items, list):
        raise HandoffError(f"{label} collection must be a list")
    matches = [item for item in items if isinstance(item, dict) and item.get("id") == item_id]
    if len(matches) != 1:
        raise HandoffError(f"expected exactly one {label} with id {item_id!r}; found {len(matches)}")
    return matches[0]


def claim_record(records: object, insight_id: str) -> dict:
    if not isinstance(records, list):
        raise HandoffError("claim-evidence records must be a list")
    matches = [item for item in records if isinstance(item, dict) and item.get("insight_id") == insight_id]
    if len(matches) != 1:
        raise HandoffError(
            f"expected exactly one claim-evidence record for {insight_id!r}; found {len(matches)}"
        )
    return matches[0]


def clean_evidence(item: object) -> dict:
    if not isinstance(item, dict):
        raise HandoffError("claim evidence entries must be objects")
    return {
        "kind": item.get("kind"),
        "source_id": item.get("source_id"),
        "url": item.get("url"),
        "locator": item.get("locator"),
    }


def clean_claim(item: object) -> dict:
    if not isinstance(item, dict):
        raise HandoffError("claims must be objects")
    evidence = item.get("evidence")
    if not isinstance(evidence, list):
        raise HandoffError(f"claim {item.get('id')!r} evidence must be a list")
    return {
        "id": item.get("id"),
        "text": item.get("text"),
        "impact": item.get("impact"),
        "origin": item.get("origin"),
        "status": item.get("status"),
        "evidence": [clean_evidence(entry) for entry in evidence],
        "note": item.get("note"),
    }


def build_packet(
    insight_id: str,
    insights_data: Optional[dict] = None,
    sources_data: Optional[dict] = None,
    claims_data: Optional[dict] = None,
) -> dict:
    insights_data = insights_data or load_json(INSIGHTS)
    sources_data = sources_data or load_json(SOURCES)
    claims_data = claims_data or load_json(CLAIMS)

    insight = find_by_id(insights_data.get("insights"), insight_id, "insight")
    if insight.get("status") != "published":
        raise HandoffError(
            f"insight {insight_id!r} has status {insight.get('status')!r}; only published insights may be exported"
        )
    source_id = insight.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        raise HandoffError(f"insight {insight_id!r} has no source_id")
    source = find_by_id(sources_data.get("sources"), source_id, "source")
    record = claim_record(claims_data.get("records"), insight_id)
    claims = record.get("claims")
    if not isinstance(claims, list) or not claims:
        raise HandoffError(f"insight {insight_id!r} has no claim-level evidence")

    slug = insight.get("slug")
    if not isinstance(slug, str) or not slug:
        raise HandoffError(f"published insight {insight_id!r} has no slug")

    payload = {
        "schema": SCHEMA_URL,
        "schema_version": SCHEMA_VERSION,
        "packet_id": f"sti:{insight_id}:research-evidence-handoff:v1",
        "producer": {
            "name": "Signal to Insight",
            "repository": REPOSITORY,
        },
        "exported_from": {
            "insight_id": insight_id,
            "status": "published",
            "title": insight.get("title"),
            "one_liner": insight.get("one_liner"),
            "public_url": f"{SITE_BASE}/explainers/{slug}/",
            "reviewed_at": (insight.get("provenance") or {}).get("reviewed_at"),
            "tags": sorted(set(insight.get("tags") or [])),
        },
        "source": {
            "id": source_id,
            "type": source.get("type"),
            "title": source.get("title"),
            "canonical_url": source.get("canonical_url"),
            "creators": source.get("creators") or [],
            "publisher": source.get("publisher"),
            "published_at": source.get("published_at"),
            "event_date": source.get("event_date"),
            "captured_at": source.get("captured_at"),
            "analyzed_at": source.get("analyzed_at"),
        },
        "claims": [clean_claim(item) for item in claims],
        "operational_boundary": {
            "trust_level": "external_research_context",
            "requires_human_review": True,
            "permitted_uses": [
                "human review",
                "research traceability",
                "control-design discussion",
                "hypothesis formation",
            ],
            "prohibited_uses": [
                "authorization",
                "execution",
                "production incident evidence",
                "automatic policy change",
            ],
        },
    }
    packet = copy.deepcopy(payload)
    packet["integrity"] = {
        "algorithm": "sha256",
        "canonicalization": CANONICALIZATION,
        "digest": payload_digest(payload),
    }
    errors = validate_packet(packet)
    if errors:
        raise HandoffError("generated packet is invalid: " + "; ".join(errors))
    return packet


def forbidden_keys(node: object) -> list[str]:
    found: list[str] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if str(key).lower() in FORBIDDEN_RAW_KEYS:
                    found.append(str(key))
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return sorted(found)


def is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_packet(packet: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["packet must be a JSON object"]
    missing = sorted(TOP_LEVEL_FIELDS - set(packet))
    extra = sorted(set(packet) - TOP_LEVEL_FIELDS)
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    if extra:
        errors.append("unsupported fields: " + ", ".join(extra))
    if packet.get("schema") != SCHEMA_URL:
        errors.append("unsupported schema")
    if packet.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if not isinstance(packet.get("packet_id"), str) or not packet.get("packet_id"):
        errors.append("packet_id must be a non-empty string")

    producer = packet.get("producer")
    if not isinstance(producer, dict):
        errors.append("producer must be an object")
    elif producer != {"name": "Signal to Insight", "repository": REPOSITORY}:
        errors.append("producer must identify the canonical Signal to Insight repository")

    exported = packet.get("exported_from")
    if not isinstance(exported, dict):
        errors.append("exported_from must be an object")
    else:
        if exported.get("status") != "published":
            errors.append("exported_from.status must be published")
        for field in ("insight_id", "title", "one_liner", "public_url", "reviewed_at"):
            if not isinstance(exported.get(field), str) or not exported.get(field):
                errors.append(f"exported_from.{field} must be a non-empty string")
        if not is_http_url(exported.get("public_url")):
            errors.append("exported_from.public_url must be an HTTP(S) URL")
        tags = exported.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag for tag in tags):
            errors.append("exported_from.tags must be a list of non-empty strings")
        elif tags != sorted(set(tags)):
            errors.append("exported_from.tags must be unique and sorted")

    source = packet.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        for field in ("id", "type", "title", "canonical_url"):
            if not isinstance(source.get(field), str) or not source.get(field):
                errors.append(f"source.{field} must be a non-empty string")
        if not is_http_url(source.get("canonical_url")):
            errors.append("source.canonical_url must be an HTTP(S) URL")
        creators = source.get("creators")
        if not isinstance(creators, list) or not all(isinstance(item, str) for item in creators):
            errors.append("source.creators must be a list of strings")

    claims = packet.get("claims")
    if not isinstance(claims, list) or not claims:
        errors.append("claims must be a non-empty list")
    else:
        claim_ids: list[str] = []
        for index, claim in enumerate(claims):
            if not isinstance(claim, dict):
                errors.append(f"claims[{index}] must be an object")
                continue
            for field in ("id", "text", "impact", "origin", "status", "evidence", "note"):
                if field not in claim:
                    errors.append(f"claims[{index}] is missing {field}")
            claim_id = claim.get("id")
            if not isinstance(claim_id, str) or not claim_id:
                errors.append(f"claims[{index}].id must be a non-empty string")
            else:
                claim_ids.append(claim_id)
            if not isinstance(claim.get("text"), str) or not claim.get("text"):
                errors.append(f"claims[{index}].text must be a non-empty string")
            if claim.get("impact") not in {"high", "medium", "low"}:
                errors.append(f"claims[{index}].impact is unsupported")
            if claim.get("origin") not in {
                "source",
                "verification",
                "project_interpretation",
                "prior_knowledge",
            }:
                errors.append(f"claims[{index}].origin is unsupported")
            if claim.get("status") not in {"supported", "uncertain", "unresolved"}:
                errors.append(f"claims[{index}].status is unsupported")
            evidence = claim.get("evidence")
            if not isinstance(evidence, list):
                errors.append(f"claims[{index}].evidence must be a list")
            else:
                for evidence_index, item in enumerate(evidence):
                    where = f"claims[{index}].evidence[{evidence_index}]"
                    if not isinstance(item, dict):
                        errors.append(f"{where} must be an object")
                    elif not is_http_url(item.get("url")):
                        errors.append(f"{where}.url must be an HTTP(S) URL")
                    elif not isinstance(item.get("locator"), str) or not item.get("locator"):
                        errors.append(f"{where}.locator must be a non-empty string")
        if len(claim_ids) != len(set(claim_ids)):
            errors.append("claim ids must be unique")

    boundary = packet.get("operational_boundary")
    if not isinstance(boundary, dict):
        errors.append("operational_boundary must be an object")
    else:
        if boundary.get("trust_level") != "external_research_context":
            errors.append("operational_boundary.trust_level must be external_research_context")
        if boundary.get("requires_human_review") is not True:
            errors.append("operational_boundary.requires_human_review must be true")
        permitted = boundary.get("permitted_uses")
        if not isinstance(permitted, list) or not permitted:
            errors.append("operational_boundary.permitted_uses must be a non-empty list")
        prohibited = boundary.get("prohibited_uses")
        if not isinstance(prohibited, list):
            errors.append("operational_boundary.prohibited_uses must be a list")
        else:
            for required_use in ("authorization", "execution", "production incident evidence"):
                if required_use not in prohibited:
                    errors.append(f"operational_boundary must prohibit {required_use}")

    raw = forbidden_keys(packet)
    if raw:
        errors.append("packet contains forbidden raw-source keys: " + ", ".join(raw))

    integrity = packet.get("integrity")
    if not isinstance(integrity, dict):
        errors.append("integrity must be an object")
    else:
        if integrity.get("algorithm") != "sha256":
            errors.append("integrity.algorithm must be sha256")
        if integrity.get("canonicalization") != CANONICALIZATION:
            errors.append("integrity.canonicalization is unsupported")
        unsigned = copy.deepcopy(packet)
        unsigned.pop("integrity", None)
        expected = payload_digest(unsigned)
        if integrity.get("digest") != expected:
            errors.append("integrity.digest does not match the canonical packet payload")
    return errors


def export_packet(insight_id: str, output: Path, force: bool = False, check: bool = False) -> int:
    packet = build_packet(insight_id)
    rendered = serialize(packet)
    if check:
        if not output.exists():
            print(f"missing generated handoff packet: {output}", file=sys.stderr)
            return 1
        if output.read_text(encoding="utf-8") != rendered:
            print(f"stale generated handoff packet: {output}", file=sys.stderr)
            return 1
        print(f"Research evidence handoff is current: {output}")
        return 0
    if output.exists() and not force:
        print(f"output already exists: {output}; use --force to replace it", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Exported published research evidence handoff: {output}")
    return 0


def validate_file(path: Path, as_json: bool = False) -> int:
    try:
        packet = load_json(path)
    except HandoffError as exc:
        print(f"Research evidence handoff invalid: {exc}", file=sys.stderr)
        return 2
    errors = validate_packet(packet)
    result = {
        "valid": not errors,
        "packet_id": packet.get("packet_id"),
        "claims": len(packet.get("claims") or []) if isinstance(packet.get("claims"), list) else 0,
        "trust_level": (packet.get("operational_boundary") or {}).get("trust_level")
        if isinstance(packet.get("operational_boundary"), dict)
        else None,
        "errors": errors,
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        print(f"Research evidence handoff invalid: {path}", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    else:
        print(f"Research evidence handoff valid: {result['packet_id']}")
        print(f"claims: {result['claims']}")
        print(f"trust:  {result['trust_level']} (human review required)")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="Export one published insight as a deterministic evidence packet")
    export.add_argument("insight_id")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--force", action="store_true")
    export.add_argument("--check", action="store_true")
    validate = sub.add_parser("validate", help="Validate an exported evidence packet and its digest")
    validate.add_argument("packet", type=Path)
    validate.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "export":
            return export_packet(args.insight_id, args.output, force=args.force, check=args.check)
        return validate_file(args.packet, as_json=args.json)
    except HandoffError as exc:
        print(f"Research evidence handoff failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
