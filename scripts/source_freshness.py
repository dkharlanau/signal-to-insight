#!/usr/bin/env python3
"""Track reliable living-source revision checks without silently rewriting reviewed knowledge."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / "data" / "source-revisions.json"
SOURCES = ROOT / "data" / "sources.json"
VERSION = "1.0.0"
KINDS = {"commit", "release", "version", "docs_version"}


class FreshnessError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def known_sources() -> set[str]:
    return {x["id"] for x in load(SOURCES).get("sources", []) if x.get("id")}


def validate(store: dict) -> None:
    if store.get("version") != VERSION or not isinstance(store.get("records"), list):
        raise FreshnessError("invalid source revision store")
    seen: set[str] = set()
    for item in store["records"]:
        source_id = item.get("source_id")
        if not source_id or source_id in seen:
            raise FreshnessError(f"invalid/duplicate source_id: {source_id!r}")
        seen.add(source_id)
        if item.get("revision_kind") not in KINDS:
            raise FreshnessError(f"unsupported revision_kind for {source_id}")
        if not item.get("analyzed_revision"):
            raise FreshnessError(f"missing analyzed_revision for {source_id}")
        events = item.get("reanalysis_events")
        if not isinstance(events, list):
            raise FreshnessError("reanalysis_events must be a list")
        for event in events:
            if event.get("from_revision") == event.get("to_revision"):
                raise FreshnessError("reanalysis event must change revision")
            if event.get("status") not in {"detected", "reviewed_no_model_change", "reviewed_model_change"}:
                raise FreshnessError("invalid reanalysis event status")


def find_record(store: dict, source_id: str) -> dict:
    item = next((x for x in store["records"] if x.get("source_id") == source_id), None)
    if item is None:
        raise FreshnessError(f"no revision contract for source: {source_id}")
    return item


def check(store: dict, source_id: str, current_revision: str) -> dict:
    validate(store)
    item = find_record(store, source_id)
    changed = current_revision != item["analyzed_revision"]
    return {
        "source_id": source_id,
        "revision_kind": item["revision_kind"],
        "analyzed_revision": item["analyzed_revision"],
        "current_revision": current_revision,
        "changed": changed,
        "next_action": (
            "Create a re-analysis evidence event and inspect the diff before changing any insight."
            if changed else "No re-analysis needed for this revision."
        ),
    }


def detect(store: dict, source_id: str, current_revision: str, note: str | None = None) -> dict:
    result = check(store, source_id, current_revision)
    if not result["changed"]:
        return result
    item = find_record(store, source_id)
    duplicate = next((e for e in item["reanalysis_events"] if e.get("to_revision") == current_revision and e.get("status") == "detected"), None)
    if duplicate is None:
        item["reanalysis_events"].append({
            "id": f"reanalysis-{source_id}-{len(item['reanalysis_events'])+1}",
            "detected_at": now(),
            "from_revision": item["analyzed_revision"],
            "to_revision": current_revision,
            "status": "detected",
            "note": note,
            "model_change_summary": None,
            "reviewed_at": None,
            "reviewed_by": None,
        })
        validate(store)
    return result


def review(store: dict, source_id: str, event_id: str, model_changed: bool, summary: str, reviewer: str) -> dict:
    item = find_record(store, source_id)
    event = next((e for e in item["reanalysis_events"] if e.get("id") == event_id), None)
    if event is None:
        raise FreshnessError(f"event not found: {event_id}")
    if event["status"] != "detected":
        raise FreshnessError("only detected events can be reviewed")
    event["status"] = "reviewed_model_change" if model_changed else "reviewed_no_model_change"
    event["model_change_summary"] = summary.strip()
    event["reviewed_at"] = now()
    event["reviewed_by"] = reviewer.strip()
    if not event["model_change_summary"] or not event["reviewed_by"]:
        raise FreshnessError("summary and reviewer are required")
    # Advancing analyzed_revision records that this revision was reviewed; it does not publish or rewrite insights.
    item["analyzed_revision"] = event["to_revision"]
    item["analyzed_at"] = event["reviewed_at"][:10]
    validate(store)
    return event


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "revisions.json"
        store = {"version": VERSION, "records": [{
            "source_id": "src-fixture", "revision_kind": "release", "analyzed_revision": "v1", "analyzed_at": "2026-01-01", "revision_url": None, "reanalysis_events": []
        }]}
        save(path, store)
        loaded = load(path)
        validate(loaded)
        result = detect(loaded, "src-fixture", "v2", "fixture")
        if not result["changed"] or len(loaded["records"][0]["reanalysis_events"]) != 1:
            print("source_freshness self-test failed at detection")
            return 1
        event_id = loaded["records"][0]["reanalysis_events"][0]["id"]
        review(loaded, "src-fixture", event_id, False, "No material model change", "tester")
        if loaded["records"][0]["analyzed_revision"] != "v2":
            print("source_freshness self-test failed at review")
            return 1
    print("source_freshness self-test passed; revision changes require explicit re-analysis review.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check")
    c.add_argument("--source", required=True)
    c.add_argument("--revision", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--source", required=True)
    d.add_argument("--revision", required=True)
    d.add_argument("--note")
    r = sub.add_parser("review")
    r.add_argument("--source", required=True)
    r.add_argument("--event", required=True)
    r.add_argument("--model-changed", choices=["yes", "no"], required=True)
    r.add_argument("--summary", required=True)
    r.add_argument("--reviewer", required=True)
    sub.add_parser("self-test")
    args = parser.parse_args()
    try:
        if args.command == "self-test":
            return self_test()
        store = load(args.store)
        validate(store)
        if args.command == "check":
            value = check(store, args.source, args.revision)
        elif args.command == "detect":
            value = detect(store, args.source, args.revision, args.note)
            save(args.store, store)
        else:
            value = review(store, args.source, args.event, args.model_changed == "yes", args.summary, args.reviewer)
            save(args.store, store)
        print(json.dumps(value, ensure_ascii=False, indent=2))
    except (FreshnessError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
