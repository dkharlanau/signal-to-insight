#!/usr/bin/env python3
"""List case patches whose source/insight/intake state has not been materialized yet."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / "data" / "case-patches"
INBOX = ROOT / "data" / "inbox.json"
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    inbox_data = load(INBOX)
    source_data = load(SOURCES)
    insight_data = load(INSIGHTS)
    inbox = {item.get("id"): item for item in inbox_data.get("items", [])}
    sources = {item.get("id"): item for item in source_data.get("sources", [])}
    insights = {item.get("id"): item for item in insight_data.get("insights", [])}

    for path in sorted(PATCHES.glob("*.json")):
        patch = load(path)
        intake = inbox.get(patch.get("intake_id"))
        source = patch.get("source", {})
        insight = patch.get("insight", {})
        expected_status = patch.get("intake_status", insight.get("status", "review"))
        materialized = (
            intake is not None
            and intake.get("source_id") == source.get("id")
            and intake.get("insight_id") == insight.get("id")
            and intake.get("status") == expected_status
            and sources.get(source.get("id")) == source
            and insights.get(insight.get("id")) == insight
        )
        if not materialized:
            print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
