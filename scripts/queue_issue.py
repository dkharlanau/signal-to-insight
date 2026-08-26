#!/usr/bin/env python3
"""Convert a GitHub source-intake Issue Form event into the canonical inbox record."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from new_source import normalize_url, source_key

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
SOURCES = ROOT / "data" / "sources.json"
ALLOWED_TYPES = {"video", "article", "paper", "podcast", "documentation", "repository", "tool", "product", "course", "presentation", "notes", "system"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value == "_No response_":
        return None
    return value


def parse_issue_body(body: str) -> dict[str, str | None]:
    sections: dict[str, str | None] = {}
    pattern = re.compile(r"^### (.+?)\n\n(.*?)(?=\n\n### |\Z)", re.MULTILINE | re.DOTALL)
    for label, value in pattern.findall(body or ""):
        sections[label.strip()] = clean(value)
    return sections


def build_queue_result(event: dict, inbox: dict, sources: dict) -> dict:
    issue = event.get("issue") or {}
    fields = parse_issue_body(issue.get("body") or "")

    raw_url = fields.get("Source URL")
    source_type = fields.get("Source type")
    focus = fields.get("Focus")
    note = fields.get("Note")

    if not raw_url:
        raise ValueError("Issue Form is missing Source URL")
    if source_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported or missing source type: {source_type!r}")

    normalized = normalize_url(raw_url)

    for source in sources.get("sources", []):
        if normalize_url(source.get("canonical_url", "")) == normalized:
            return {"status": "known_source", "id": source["id"], "changed": False, "url": normalized}

    for item in inbox.get("items", []):
        if normalize_url(item.get("source_url", "")) == normalized and (item.get("requested_focus") or None) == focus:
            return {"status": "already_queued", "id": item["id"], "changed": False, "url": normalized}

    created = (issue.get("created_at") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", created):
        raise ValueError("Issue event has no usable created_at date")

    base_id = f"intake-{created}-{source_key(normalized)}"
    existing_ids = {item.get("id") for item in inbox.get("items", [])}
    intake_id = base_id
    suffix = 2
    while intake_id in existing_ids:
        intake_id = f"{base_id}-{suffix}"
        suffix += 1

    issue_number = issue.get("number")
    note_parts = [f"GitHub source intake issue #{issue_number}." if issue_number else "GitHub source intake issue."]
    if note:
        note_parts.append(note)

    inbox.setdefault("items", []).append({
        "id": intake_id,
        "source_url": normalized,
        "source_type": source_type,
        "submitted_at": created,
        "requested_focus": focus,
        "status": "queued",
        "source_id": None,
        "insight_id": None,
        "notes": " ".join(note_parts),
    })

    return {"status": "queued", "id": intake_id, "changed": True, "url": normalized}


def write_outputs(result: dict) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key in ("status", "id", "url"):
            handle.write(f"{key}={result[key]}\n")
        handle.write(f"changed={'true' if result['changed'] else 'false'}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, help="Path to GitHub event JSON")
    args = parser.parse_args()

    event = load(Path(args.event))
    inbox = load(INBOX)
    sources = load(SOURCES)
    result = build_queue_result(event, inbox, sources)

    if result["changed"]:
        INBOX.write_text(json.dumps(inbox, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_outputs(result)
    print(f"{result['status']}: {result['id']} ({result['url']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
