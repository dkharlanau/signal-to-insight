#!/usr/bin/env python3
"""Generate a public-safe temporal knowledge history feed from reviewed published evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from knowledge_history import HISTORY, load, projection

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "knowledge" / "history.json"


def payload() -> dict:
    history = load(HISTORY)
    entities = [projection(record, public_only=True) for record in history.get("entities", [])]
    entities.sort(key=lambda item: (item.get("entity_type", ""), item.get("entity_id", "")))
    return {
        "history_version": history.get("history_version"),
        "projection": "published-evidence-only",
        "entities": entities,
    }


def build(check: bool = False) -> int:
    content = json.dumps(payload(), ensure_ascii=False, indent=2) + "\n"
    if check:
        if not OUTPUT.exists():
            print(f"missing generated history feed: {OUTPUT.relative_to(ROOT)}")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != content:
            print(f"stale generated history feed: {OUTPUT.relative_to(ROOT)}")
            return 1
        print("Public knowledge history feed check passed.")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"generated {OUTPUT.relative_to(ROOT)}")
    return 0


def self_test() -> int:
    data = payload()
    controlled = next((item for item in data.get("entities", []) if item.get("entity_id") == "controlled-execution"), None)
    if controlled is None:
        print("History feed self-test failed: controlled-execution missing.")
        return 1
    if "timeline" in controlled or controlled.get("timeline_visible") is not False:
        print("History feed self-test failed: one public state exposed a timeline.")
        return 1
    if controlled.get("observations"):
        print("History feed self-test failed: review-only observations leaked publicly.")
        return 1
    active = controlled.get("active_state") or {}
    if active.get("review_status") != "reviewed":
        print("History feed self-test failed: public active state is not reviewed.")
        return 1
    print("Public knowledge history feed self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    return build(check=args.check)


if __name__ == "__main__":
    sys.exit(main())
