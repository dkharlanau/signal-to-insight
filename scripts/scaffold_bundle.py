#!/usr/bin/env python3
"""Create a normalized, source-safe research bundle scaffold from an intake item."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
OUTPUT = ROOT / "data" / "research-bundles"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a research bundle from an intake ID")
    parser.add_argument("intake_id")
    args = parser.parse_args()

    inbox = load(INBOX)
    item = next((x for x in inbox.get("items", []) if x.get("id") == args.intake_id), None)
    if item is None:
        parser.error(f"intake not found: {args.intake_id}")

    target = OUTPUT / f"{args.intake_id}.json"
    if target.exists():
        parser.error(f"bundle already exists: {target.relative_to(ROOT)}")

    bundle = {
        "bundle_version": "1.0.0",
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
        "created_at": date.today().isoformat()
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"created {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
