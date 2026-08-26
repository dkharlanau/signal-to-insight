#!/usr/bin/env python3
"""Create a normalized, source-safe research bundle scaffold from an intake item."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from graph_context import rank

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
OUTPUT = ROOT / "data" / "research-bundles"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def prior_query(item: dict) -> str:
    focus = (item.get("requested_focus") or "").strip()
    if focus:
        return focus
    return f"{item.get('source_type', '')} {item.get('source_url', '')}".strip()


def prior_snapshot(item: dict, captured_at: str) -> dict:
    query = prior_query(item)
    result = rank(query, limit=5)
    matches = []
    for match in result.get("matches", []):
        evidence = [
            {
                "id": item.get("id"),
                "status": item.get("status"),
                "title": item.get("title"),
            }
            for item in match.get("evidence", [])
        ]
        matches.append({
            "concept_id": match["concept_id"],
            "label": match["label"],
            "coverage": match["coverage"],
            "evidence_insights": evidence,
            "relationship_to_source": "unclassified",
        })
    return {
        "captured_at": captured_at,
        "query": query,
        "matches": matches,
        "classification_required": True,
    }


def build_bundle(item: dict, created_at: str | None = None) -> dict:
    today = created_at or date.today().isoformat()
    return {
        "bundle_version": "1.1.0",
        "intake_id": item["id"],
        "source_id": item.get("source_id"),
        "source": {
            "type": item["source_type"],
            "canonical_url": item["source_url"],
            "title": None,
            "creators": [],
            "publisher": None,
            "published_at": None,
            "event_date": None,
            "version": None,
            "language": None,
            "duration": None,
            "date_note": None
        },
        "inspection": {
            "method": "not inspected",
            "full_content_used_ephemerally": False,
            "full_content_committed": False,
            "confidence": "metadata_only",
            "gaps": ["Source content has not been mapped yet."]
        },
        "prior_knowledge": prior_snapshot(item, today),
        "content_map": {
            "problem": None,
            "thesis": None,
            "sections": [],
            "concepts": [],
            "mechanisms": [],
            "tools": [],
            "examples": [],
            "claims": [],
            "evidence": [],
            "assumptions": [],
            "limitations": [],
            "open_questions": []
        },
        "selection": {
            "requested_focus": item.get("requested_focus"),
            "coherent_core": [],
            "prerequisites": [],
            "drop_notes": [],
            "connections": []
        },
        "verification_candidates": [],
        "source_locators": [],
        "created_at": today
    }


def self_test() -> int:
    fixture = {
        "id": "intake-self-test",
        "source_id": None,
        "source_type": "article",
        "source_url": "https://example.com/durable-workflow-retry",
        "requested_focus": "durable workflow retry"
    }
    bundle = build_bundle(fixture, "2026-08-26")
    prior = bundle.get("prior_knowledge", {})
    ids = {item.get("concept_id") for item in prior.get("matches", [])}
    if "durable-execution" not in ids or "idempotency-under-retry" not in ids:
        print(f"bundle scaffold self-test failed; unexpected prior knowledge: {sorted(ids)}")
        return 1
    if any(item.get("relationship_to_source") != "unclassified" for item in prior.get("matches", [])):
        print("bundle scaffold self-test failed; prior knowledge must begin unclassified")
        return 1
    if prior.get("classification_required") is not True:
        print("bundle scaffold self-test failed; classification_required must be true")
        return 1
    print("Research bundle prior-knowledge self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a research bundle from an intake ID")
    parser.add_argument("intake_id", nargs="?")
    parser.add_argument("--preview", action="store_true", help="Print the bundle without writing it")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.intake_id:
        parser.error("intake_id is required unless --self-test is used")

    inbox = load(INBOX)
    item = next((x for x in inbox.get("items", []) if x.get("id") == args.intake_id), None)
    if item is None:
        parser.error(f"intake not found: {args.intake_id}")

    bundle = build_bundle(item)
    if args.preview:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
        return 0

    target = OUTPUT / f"{args.intake_id}.json"
    if target.exists():
        parser.error(f"bundle already exists: {target.relative_to(ROOT)}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"created {target.relative_to(ROOT)} with {len(bundle['prior_knowledge']['matches'])} prior-knowledge match(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
