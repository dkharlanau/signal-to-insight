#!/usr/bin/env python3
"""Validate committed research bundles for structure and source-safety."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "data" / "research-bundles"
INBOX = ROOT / "data" / "inbox.json"
ALLOWED_CONFIDENCE = {"direct", "metadata_only", "secondary", "mixed"}
errors: list[str] = []


def valid_url(value: object, where: str) -> None:
    if not isinstance(value, str):
        errors.append(f"{where}: URL must be a string")
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{where}: invalid URL '{value}'")


def valid_date(value: object, where: str) -> None:
    if not isinstance(value, str):
        errors.append(f"{where}: expected ISO date")
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        errors.append(f"{where}: invalid ISO date '{value}'")


def main() -> int:
    inbox = json.loads(INBOX.read_text(encoding="utf-8"))
    intake = {item["id"]: item for item in inbox.get("items", [])}

    if not BUNDLES.exists():
        print("No research bundles committed yet.")
        return 0

    files = sorted(BUNDLES.glob("*.json"))
    for path in files:
        rel = path.relative_to(ROOT)
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue

        required = ["bundle_version", "intake_id", "source", "inspection", "content_map", "selection", "verification_candidates", "created_at"]
        for key in required:
            if key not in bundle:
                errors.append(f"{rel}: missing '{key}'")

        intake_id = bundle.get("intake_id")
        if intake_id not in intake:
            errors.append(f"{rel}: dangling intake_id '{intake_id}'")

        source = bundle.get("source", {})
        valid_url(source.get("canonical_url"), f"{rel}.source.canonical_url")
        if intake_id in intake and source.get("canonical_url") != intake[intake_id].get("source_url"):
            errors.append(f"{rel}: canonical_url differs from normalized intake source_url")

        inspection = bundle.get("inspection", {})
        if inspection.get("full_content_committed") is not False:
            errors.append(f"{rel}: full_content_committed must be false")
        if inspection.get("confidence") not in ALLOWED_CONFIDENCE:
            errors.append(f"{rel}: invalid inspection confidence '{inspection.get('confidence')}'")

        content_map = bundle.get("content_map", {})
        expected_map = {"problem", "thesis", "sections", "concepts", "mechanisms", "tools", "examples", "claims", "evidence", "assumptions", "limitations", "open_questions"}
        missing = expected_map - set(content_map)
        if missing:
            errors.append(f"{rel}.content_map: missing {sorted(missing)}")

        selection = bundle.get("selection", {})
        expected_selection = {"requested_focus", "coherent_core", "prerequisites", "drop_notes", "connections"}
        missing = expected_selection - set(selection)
        if missing:
            errors.append(f"{rel}.selection: missing {sorted(missing)}")

        for index, candidate in enumerate(bundle.get("verification_candidates", [])):
            if candidate.get("priority") not in {"high", "medium", "low"}:
                errors.append(f"{rel}.verification_candidates[{index}]: invalid priority")

        valid_date(bundle.get("created_at"), f"{rel}.created_at")

        # Guard against accidentally adding raw source dumps under tempting field names.
        forbidden_keys = {"transcript", "full_transcript", "raw_text", "full_text", "article_body", "pdf_text", "source_content"}
        stack: list[object] = [bundle]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.lower() in forbidden_keys:
                        errors.append(f"{rel}: forbidden raw-source field '{key}'")
                    stack.append(value)
            elif isinstance(node, list):
                stack.extend(node)

    if errors:
        print(f"Research bundle validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Research bundle validation passed: {len(files)} bundle(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
