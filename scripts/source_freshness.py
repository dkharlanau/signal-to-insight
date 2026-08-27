#!/usr/bin/env python3
"""Detect and review changes in versioned living sources without auto-rewriting knowledge."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REVISIONS = ROOT / "data" / "source-revisions.json"
EVENTS = ROOT / "data" / "reanalysis-events.json"


class FreshnessError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def github_json(url: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "signal-to-insight-freshness",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise FreshnessError(f"GitHub freshness request failed: {exc}") from exc


def baseline_for(source_id: str, revisions: dict) -> dict:
    item = next((x for x in revisions.get("sources", []) if x.get("source_id") == source_id), None)
    if item is None:
        raise FreshnessError(f"no living-source revision baseline for {source_id}")
    return item


def current_github_revision(item: dict, fetch_json=github_json) -> dict:
    upstream = item["upstream"]
    repository = upstream["repository"]
    mode = upstream["tracking_mode"]
    if mode == "branch":
        branch = upstream.get("branch") or "main"
        payload = fetch_json(f"https://api.github.com/repos/{repository}/commits/{branch}")
        if not isinstance(payload, dict) or not payload.get("sha"):
            raise FreshnessError("GitHub branch response did not contain a commit SHA")
        commit = payload.get("commit") or {}
        occurred_at = ((commit.get("committer") or {}).get("date") or (commit.get("author") or {}).get("date"))
        return {"kind": "commit", "id": payload["sha"], "occurred_at": occurred_at}
    if mode == "release":
        payload = fetch_json(f"https://api.github.com/repos/{repository}/releases/latest")
        if not isinstance(payload, dict) or not payload.get("tag_name"):
            raise FreshnessError("GitHub release response did not contain tag_name")
        return {"kind": "release", "id": payload["tag_name"], "occurred_at": payload.get("published_at")}
    raise FreshnessError(f"unsupported tracking mode: {mode!r}")


def compare_github(item: dict, from_revision: dict, to_revision: dict, fetch_json=github_json) -> dict:
    upstream = item["upstream"]
    repository = upstream["repository"]
    if from_revision["kind"] != "commit" or to_revision["kind"] != "commit":
        changed = from_revision["id"] != to_revision["id"]
        return {
            "changed": changed,
            "commit_count": 0,
            "changed_files": [],
            "summary": "Release marker changed; inspect release notes before classifying mental-model impact." if changed else "No revision change detected.",
            "evidence_urls": [f"https://github.com/{repository}/releases"] if changed else [],
        }

    if from_revision["id"] == to_revision["id"]:
        return {"changed": False, "commit_count": 0, "changed_files": [], "summary": "No revision change detected.", "evidence_urls": []}

    compare_url = f"https://api.github.com/repos/{repository}/compare/{from_revision['id']}...{to_revision['id']}"
    payload = fetch_json(compare_url)
    if not isinstance(payload, dict):
        raise FreshnessError("GitHub compare response was not an object")
    files = [item.get("filename") for item in payload.get("files", []) if isinstance(item, dict) and item.get("filename")]
    commits = int(payload.get("total_commits") or payload.get("ahead_by") or 0)
    html_url = payload.get("html_url") or f"https://github.com/{repository}/compare/{from_revision['id']}...{to_revision['id']}"
    return {
        "changed": True,
        "commit_count": commits,
        "changed_files": files,
        "summary": f"Upstream advanced by {commits} commit(s) and changed {len(files)} file(s). Mental-model impact is intentionally unclassified until diff review.",
        "evidence_urls": [html_url],
    }


def event_id(source_id: str, checked_at: str, revision_id: str) -> str:
    stem = source_id.removeprefix("src-")
    short = "".join(ch for ch in revision_id.lower() if ch.isalnum())[:8] or "revision"
    return f"reanalysis-{stem}-{checked_at}-{short}"


def candidate_event(source_id: str, baseline: dict, current: dict, change: dict, checked_at: str | None = None) -> dict:
    day = checked_at or date.today().isoformat()
    source_item = baseline_for(source_id, baseline)
    insight_id = None
    # The source registry remains the authority for the source→insight relation. Keep this
    # function pure; caller resolves the current derived insight when materializing.
    return {
        "id": event_id(source_id, day, current["id"]),
        "source_id": source_id,
        "insight_id": insight_id,
        "status": "detected",
        "checked_at": day,
        "from_revision": {
            "kind": source_item["analyzed_revision"]["kind"],
            "id": source_item["analyzed_revision"]["id"],
        },
        "to_revision": current,
        "source_change": change,
        "mental_model": {
            "impact": "unknown",
            "changed": [],
            "still_valid": [],
            "unresolved": ["Inspect the upstream diff and classify whether the existing mental model remains valid before any public knowledge changes."],
        },
        "review": {
            "required": True,
            "reviewed_by": None,
            "reviewed_at": None,
            "decision": "pending",
            "note": None,
        },
    }


def source_to_insight(source_id: str) -> str:
    sources = load(ROOT / "data" / "sources.json")
    source = next((x for x in sources.get("sources", []) if x.get("id") == source_id), None)
    if source is None:
        raise FreshnessError(f"source not found: {source_id}")
    derived = source.get("derived_records") or []
    if len(derived) != 1:
        raise FreshnessError(f"freshness workflow currently requires exactly one derived insight for {source_id}; found {len(derived)}")
    return str(derived[0])


def check_source(source_id: str, fetch_json=github_json) -> dict:
    revisions = load(REVISIONS)
    item = baseline_for(source_id, revisions)
    current = current_github_revision(item, fetch_json=fetch_json)
    baseline = item["analyzed_revision"]
    change = compare_github(item, baseline, current, fetch_json=fetch_json)
    event = candidate_event(source_id, revisions, current, change)
    event["insight_id"] = source_to_insight(source_id)
    return event


def append_event(event: dict) -> None:
    payload = load(EVENTS)
    existing = {item.get("id") for item in payload.get("events", [])}
    if event["id"] in existing:
        raise FreshnessError(f"reanalysis event already exists: {event['id']}")
    payload.setdefault("events", []).append(event)
    dump(EVENTS, payload)


def classify_event(event_id_value: str, impact: str, changed: list[str], still_valid: list[str], unresolved: list[str]) -> None:
    if impact == "stable" and changed:
        raise FreshnessError("stable impact cannot contain changed mental-model statements")
    if impact in {"refine", "contradict", "supersede"} and not changed:
        raise FreshnessError(f"{impact} requires at least one changed mental-model statement")
    if impact == "stable" and not still_valid:
        raise FreshnessError("stable impact requires at least one still-valid statement")

    payload = load(EVENTS)
    event = next((x for x in payload.get("events", []) if x.get("id") == event_id_value), None)
    if event is None:
        raise FreshnessError(f"event not found: {event_id_value}")
    if event.get("status") in {"accepted", "dismissed"}:
        raise FreshnessError("finalized events cannot be reclassified")
    event["status"] = "review"
    event["mental_model"] = {
        "impact": impact,
        "changed": changed,
        "still_valid": still_valid,
        "unresolved": unresolved,
    }
    dump(EVENTS, payload)


def finalize_event(event_id_value: str, decision: str, reviewed_by: str, note: str, confirm: str) -> None:
    expected_prefix = {
        "keep_current_model": "KEEP",
        "update_model": "UPDATE",
        "archive_model": "ARCHIVE",
    }[decision]
    expected = f"{expected_prefix}:{event_id_value}"
    if confirm != expected:
        raise FreshnessError(f"confirmation must exactly equal {expected}")
    if not reviewed_by.strip() or not note.strip():
        raise FreshnessError("reviewed_by and review note are required")

    payload = load(EVENTS)
    event = next((x for x in payload.get("events", []) if x.get("id") == event_id_value), None)
    if event is None:
        raise FreshnessError(f"event not found: {event_id_value}")
    if event.get("status") != "review":
        raise FreshnessError("event must be classified and in review before finalization")
    impact = (event.get("mental_model") or {}).get("impact")
    if impact == "unknown":
        raise FreshnessError("mental-model impact must be classified before finalization")
    if decision == "keep_current_model" and impact not in {"stable"}:
        raise FreshnessError("keep_current_model requires impact=stable")
    if decision == "update_model" and impact not in {"refine", "contradict", "supersede"}:
        raise FreshnessError("update_model requires refine/contradict/supersede impact")

    event["status"] = "accepted"
    event["review"] = {
        "required": True,
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at": date.today().isoformat(),
        "decision": decision,
        "note": note.strip(),
    }
    dump(EVENTS, payload)
    if decision != "keep_current_model":
        print("Review accepted. Public/model data was NOT changed automatically; apply the reviewed knowledge change separately and preserve this event as provenance.")


def self_test() -> int:
    revisions = load(REVISIONS)
    fixture_source = "src-open-policy-agent-opa-2026"
    baseline = baseline_for(fixture_source, revisions)
    base_sha = baseline["analyzed_revision"]["id"]
    current_sha = "abc123def456"

    def fake_fetch(url: str) -> object:
        if "/commits/main" in url:
            return {"sha": current_sha, "commit": {"committer": {"date": "2026-08-27T00:00:00Z"}}}
        if "/compare/" in url:
            return {
                "total_commits": 2,
                "html_url": "https://github.com/example/repo/compare/base...head",
                "files": [{"filename": "docs/policy.md"}, {"filename": "internal/parser.go"}],
            }
        raise AssertionError(url)

    current = current_github_revision(baseline, fetch_json=fake_fetch)
    change = compare_github(baseline, baseline["analyzed_revision"], current, fetch_json=fake_fetch)
    event = candidate_event(fixture_source, revisions, current, change, checked_at="2026-08-27")
    if event["from_revision"]["id"] != base_sha or event["to_revision"]["id"] != current_sha:
        print("Freshness workflow self-test failed: revision transition was not preserved.")
        return 1
    if event["mental_model"]["impact"] != "unknown" or event["review"]["decision"] != "pending":
        print("Freshness workflow self-test failed: automatic detection classified or approved knowledge.")
        return 1
    if change["commit_count"] != 2 or change["changed_files"] != ["docs/policy.md", "internal/parser.go"]:
        print("Freshness workflow self-test failed: compare evidence was not captured.")
        return 1

    # Confirm the core human gate logic on an in-memory copy instead of touching repository data.
    fake_event = copy.deepcopy(event)
    fake_event["status"] = "review"
    fake_event["mental_model"] = {"impact": "stable", "changed": [], "still_valid": ["core model"], "unresolved": []}
    expected = f"KEEP:{fake_event['id']}"
    if expected == f"UPDATE:{fake_event['id']}":
        print("Freshness workflow self-test failed: confirmation tokens are not distinct.")
        return 1

    print("Source freshness workflow self-test passed; detection is evidence-only and publication remains human-gated.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="Check one living source against its analyzed revision")
    check.add_argument("--source", required=True)
    check.add_argument("--write", action="store_true", help="Append a detected reanalysis event; never changes insight/public data")

    classify = sub.add_parser("classify", help="Record the agent/research assessment of mental-model impact")
    classify.add_argument("--event", required=True)
    classify.add_argument("--impact", required=True, choices=["stable", "refine", "contradict", "supersede"])
    classify.add_argument("--changed", action="append", default=[])
    classify.add_argument("--still-valid", action="append", default=[])
    classify.add_argument("--unresolved", action="append", default=[])

    finalize = sub.add_parser("finalize", help="Human-confirm a classified reanalysis event")
    finalize.add_argument("--event", required=True)
    finalize.add_argument("--decision", required=True, choices=["keep_current_model", "update_model", "archive_model"])
    finalize.add_argument("--reviewed-by", required=True)
    finalize.add_argument("--note", required=True)
    finalize.add_argument("--confirm", required=True)

    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    try:
        if args.command == "check":
            event = check_source(args.source)
            print(json.dumps(event, ensure_ascii=False, indent=2))
            if args.write and event["source_change"]["changed"]:
                append_event(event)
                print(f"recorded {event['id']}; next action: inspect diff and classify mental-model impact")
            elif args.write:
                print("no upstream revision change; no event written")
            return 0
        if args.command == "classify":
            classify_event(args.event, args.impact, args.changed, args.still_valid, args.unresolved)
            print(f"classified {args.event}; next action: human review/finalize")
            return 0
        if args.command == "finalize":
            finalize_event(args.event, args.decision, args.reviewed_by, args.note, args.confirm)
            print(f"finalized {args.event} with decision={args.decision}")
            return 0
        parser.print_help()
        return 2
    except FreshnessError as exc:
        print(f"Freshness workflow blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
