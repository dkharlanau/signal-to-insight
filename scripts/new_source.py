#!/usr/bin/env python3
"""Add a source URL to data/inbox.json with normalized provenance-friendly metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
SOURCES = ROOT / "data" / "sources.json"
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "si", "feature", "t", "start"}


def normalize_url(raw: str) -> str:
    parsed = urlparse(raw.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source must be a valid http(s) URL")

    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key in TRACKING_PARAMS:
            continue
        query.append((key, value))

    # For YouTube, preserve the video id and drop presentation-only parameters.
    host = parsed.netloc.lower().removeprefix("www.")
    if host in {"youtube.com", "m.youtube.com"} and parsed.path == "/watch":
        video_id = dict(parse_qsl(parsed.query)).get("v")
        query = [("v", video_id)] if video_id else query
    elif host == "youtu.be":
        query = []

    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "/", "", urlencode(query), ""))


def slug_piece(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:48] or "source"


def source_key(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    query = dict(parse_qsl(parsed.query))
    if host.endswith("youtube.com") and query.get("v"):
        return f"youtube-{slug_piece(query['v'])}"
    if host == "youtu.be":
        return f"youtube-{slug_piece(parsed.path.strip('/'))}"
    path = parsed.path.strip("/").split("/")[-1] if parsed.path.strip("/") else host
    return f"{slug_piece(host.split('.')[0])}-{slug_piece(path)}"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue a new source for Signal to Insight")
    parser.add_argument("url", help="Source URL")
    parser.add_argument("--type", dest="source_type", default="article", choices=["video", "article", "paper", "podcast", "documentation", "repository", "tool", "product", "course", "presentation", "notes", "system"])
    parser.add_argument("--focus", default="", help="What the analysis should pay special attention to")
    parser.add_argument("--note", default="", help="Optional intake note")
    args = parser.parse_args()

    try:
        normalized = normalize_url(args.url)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    inbox = load(INBOX)
    sources = load(SOURCES)

    for source in sources.get("sources", []):
        if normalize_url(source.get("canonical_url", "")) == normalized:
            print(f"already registered as source: {source['id']}")
            return 0

    focus = args.focus.strip() or None
    for item in inbox.get("items", []):
        if normalize_url(item.get("source_url", "")) == normalized and (item.get("requested_focus") or None) == focus:
            print(f"already queued as intake: {item['id']}")
            return 0

    today = date.today().isoformat()
    base_id = f"intake-{today}-{source_key(normalized)}"
    existing_ids = {item.get("id") for item in inbox.get("items", [])}
    intake_id = base_id
    suffix = 2
    while intake_id in existing_ids:
        intake_id = f"{base_id}-{suffix}"
        suffix += 1

    inbox.setdefault("items", []).append({
        "id": intake_id,
        "source_url": normalized,
        "source_type": args.source_type,
        "submitted_at": today,
        "requested_focus": focus,
        "status": "queued",
        "source_id": None,
        "insight_id": None,
        "notes": args.note.strip() or None
    })

    INBOX.write_text(json.dumps(inbox, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"queued: {intake_id}")
    print(normalized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
