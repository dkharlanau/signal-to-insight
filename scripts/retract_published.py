#!/usr/bin/env python3
"""Explicitly retract one published insight back to review or archive it."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
INSIGHTS = ROOT / "data" / "insights.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"


class RetractError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bump_patch(version: str) -> str:
    try:
        major, minor, patch = [int(part) for part in version.split(".")]
    except (AttributeError, ValueError):
        raise RetractError(f"invalid graph version: {version!r}")
    return f"{major}.{minor}.{patch + 1}"


def preflight(
    insight_id: str,
    target: str,
    confirm: str,
    changed_by: str,
    note: str,
) -> tuple[dict, dict, dict, dict, dict]:
    if target not in {"review", "archived"}:
        raise RetractError("target must be 'review' or 'archived'")
    verb = "REVIEW" if target == "review" else "ARCHIVE"
    if confirm != f"{verb}:{insight_id}":
        raise RetractError(f"confirmation must exactly equal {verb}:{insight_id}")
    if not changed_by.strip():
        raise RetractError("changed_by is required")
    if not note.strip():
        raise RetractError("note is required; record why the public state is changing")

    inbox = load(INBOX)
    insights = load(INSIGHTS)
    graph = load(GRAPH)

    insight = next((item for item in insights.get("insights", []) if item.get("id") == insight_id), None)
    if insight is None:
        raise RetractError(f"insight not found: {insight_id}")
    if insight.get("status") != "published":
        raise RetractError(f"insight must be published, found {insight.get('status')!r}")

    intake = next((item for item in inbox.get("items", []) if item.get("insight_id") == insight_id), None)
    if intake is None:
        raise RetractError(f"intake not linked to insight: {insight_id}")
    if intake.get("status") != "published":
        raise RetractError(f"linked intake must be published, found {intake.get('status')!r}")

    return inbox, insights, graph, insight, intake


def retract(
    insight_id: str,
    target: str,
    confirm: str,
    changed_by: str,
    note: str,
    dry_run: bool = False,
) -> int:
    inbox, insights, graph, insight, intake = preflight(
        insight_id,
        target,
        confirm,
        changed_by,
        note,
    )

    if dry_run:
        print(f"Retraction preflight passed for {insight_id} → {target}; no files changed.")
        return 0

    today = date.today().isoformat()
    previous = insight["status"]
    insight["status"] = target
    intake["status"] = target

    provenance = insight.setdefault("provenance", {})
    history = provenance.setdefault("publication_transitions", [])
    history.append(
        {
            "from": previous,
            "to": target,
            "changed_by": changed_by,
            "changed_at": today,
            "note": note,
        }
    )

    graph["updated_at"] = today
    graph["graph_version"] = bump_patch(graph.get("graph_version", "0.0.0"))

    dump(INBOX, inbox)
    dump(INSIGHTS, insights)
    dump(GRAPH, graph)
    print(f"retracted {insight_id} → {target}; public/review artifacts must now be regenerated in the same transaction")
    return 0


def self_test() -> int:
    insights = load(INSIGHTS)
    published = next((item for item in insights.get("insights", []) if item.get("status") == "published"), None)
    if published is None:
        print("Retraction self-test requires at least one published insight.")
        return 1
    insight_id = published["id"]

    try:
        preflight(insight_id, "review", "WRONG", "self-test", "self-test retraction")
    except RetractError:
        pass
    else:
        print("Retraction self-test failed: incorrect confirmation was accepted.")
        return 1

    try:
        retract(
            insight_id,
            "review",
            f"REVIEW:{insight_id}",
            "self-test",
            "Validate explicit public retraction boundary.",
            dry_run=True,
        )
        retract(
            insight_id,
            "archived",
            f"ARCHIVE:{insight_id}",
            "self-test",
            "Validate explicit archive boundary.",
            dry_run=True,
        )
    except RetractError as exc:
        print(f"Retraction self-test failed: {exc}")
        return 1

    print("Retraction self-test passed; published-only and explicit-confirmation boundaries hold.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--insight")
    parser.add_argument("--target", choices=["review", "archived"])
    parser.add_argument("--confirm")
    parser.add_argument("--changed-by", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.insight or not args.target:
        parser.error("--insight and --target are required unless --self-test is used")

    try:
        return retract(
            args.insight,
            args.target,
            args.confirm or "",
            args.changed_by,
            args.note,
            dry_run=args.dry_run,
        )
    except RetractError as exc:
        print(f"Retraction blocked: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
