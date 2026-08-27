#!/usr/bin/env python3
"""Validate living-source revision baselines and reanalysis review events."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"
REVISIONS = ROOT / "data" / "source-revisions.json"
EVENTS = ROOT / "data" / "reanalysis-events.json"
LIVING_TYPES = {"documentation", "repository", "tool", "product", "system"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(revisions: dict, events: dict, sources: dict, insights: dict) -> list[str]:
    errors: list[str] = []
    source_map = {item.get("id"): item for item in sources.get("sources", [])}
    insight_map = {item.get("id"): item for item in insights.get("insights", [])}

    baselines: dict[str, dict] = {}
    for index, item in enumerate(revisions.get("sources", [])):
        where = f"data/source-revisions.json sources[{index}]"
        source_id = item.get("source_id")
        if source_id in baselines:
            errors.append(f"{where}: duplicate source_id {source_id!r}")
            continue
        source = source_map.get(source_id)
        if source is None:
            errors.append(f"{where}: source_id does not exist in data/sources.json")
            continue
        if source.get("type") not in LIVING_TYPES:
            errors.append(f"{where}: revision tracking is only for living source types")
        if item.get("canonical_url") != source.get("canonical_url"):
            errors.append(f"{where}: canonical_url differs from source registry")
        upstream = item.get("upstream") or {}
        if upstream.get("tracking_mode") == "branch" and not upstream.get("branch"):
            errors.append(f"{where}.upstream: branch tracking requires branch")
        if upstream.get("tracking_mode") == "release" and not upstream.get("release"):
            errors.append(f"{where}.upstream: release tracking requires release")
        baseline = item.get("analyzed_revision") or {}
        if baseline.get("capture_quality") == "reconstructed" and not str(baseline.get("basis") or "").strip():
            errors.append(f"{where}.analyzed_revision: reconstructed baselines require an explicit basis")
        if not baseline.get("id"):
            errors.append(f"{where}.analyzed_revision: revision id is required")
        baselines[source_id] = baseline

    seen_events: set[str] = set()
    known_revisions: dict[str, set[str]] = {
        source_id: {str(baseline.get("id"))}
        for source_id, baseline in baselines.items()
        if baseline.get("id")
    }

    for index, event in enumerate(events.get("events", [])):
        where = f"data/reanalysis-events.json events[{index}]"
        event_id = event.get("id")
        if event_id in seen_events:
            errors.append(f"{where}: duplicate event id {event_id!r}")
        seen_events.add(event_id)
        source_id = event.get("source_id")
        if source_id not in baselines:
            errors.append(f"{where}: source has no analyzed revision baseline")
            continue
        insight = insight_map.get(event.get("insight_id"))
        if insight is None:
            errors.append(f"{where}: insight_id does not exist")
        elif insight.get("source_id") != source_id:
            errors.append(f"{where}: insight_id belongs to a different source")

        from_id = str((event.get("from_revision") or {}).get("id") or "")
        to_id = str((event.get("to_revision") or {}).get("id") or "")
        if from_id not in known_revisions.get(source_id, set()):
            errors.append(f"{where}: from_revision is not a known baseline/previous observation")
        changed = (event.get("source_change") or {}).get("changed")
        changed_files = (event.get("source_change") or {}).get("changed_files")
        if changed is True:
            if not to_id or to_id == from_id:
                errors.append(f"{where}: changed source requires a different to_revision")
            if not isinstance(changed_files, list) or not changed_files:
                errors.append(f"{where}: changed source requires changed_files evidence")
        elif changed is False and to_id != from_id:
            errors.append(f"{where}: unchanged source must keep the same revision id")

        model = event.get("mental_model") or {}
        impact = model.get("impact")
        changed_model = model.get("changed") or []
        stable_model = model.get("still_valid") or []
        if impact == "stable" and changed_model:
            errors.append(f"{where}.mental_model: stable impact cannot contain changed model statements")
        if impact in {"refine", "contradict", "supersede"} and not changed_model:
            errors.append(f"{where}.mental_model: {impact} requires at least one changed statement")
        if impact == "stable" and not stable_model:
            errors.append(f"{where}.mental_model: stable impact should name what remains valid")

        review = event.get("review") or {}
        status = event.get("status")
        if review.get("required") is not True:
            errors.append(f"{where}.review: human review must remain required")
        if status in {"detected", "review"}:
            if review.get("decision") != "pending":
                errors.append(f"{where}.review: unreviewed event must keep decision=pending")
            if review.get("reviewed_by") is not None or review.get("reviewed_at") is not None:
                errors.append(f"{where}.review: pending event cannot claim a reviewer")
        if status in {"accepted", "dismissed"}:
            if review.get("decision") == "pending":
                errors.append(f"{where}.review: finalized event requires an explicit decision")
            if not review.get("reviewed_by") or not review.get("reviewed_at") or not review.get("note"):
                errors.append(f"{where}.review: finalized event requires reviewer, date and note")

        if to_id:
            known_revisions.setdefault(source_id, set()).add(to_id)

    return errors


def self_test() -> int:
    revisions = load(REVISIONS)
    events = load(EVENTS)
    sources = load(SOURCES)
    insights = load(INSIGHTS)
    errors = validate(revisions, events, sources, insights)
    if errors:
        print("Freshness self-test fixture is invalid:")
        for error in errors:
            print(f"- {error}")
        return 1

    broken = copy.deepcopy(events)
    event = broken["events"][0]
    event["mental_model"]["impact"] = "stable"
    event["mental_model"]["changed"] = ["This should be rejected."]
    if not any("stable impact cannot contain changed" in item for item in validate(revisions, broken, sources, insights)):
        print("Freshness self-test failed: stable+changed contradiction was accepted.")
        return 1

    broken = copy.deepcopy(events)
    event = broken["events"][0]
    event["status"] = "accepted"
    if not any("finalized event" in item for item in validate(revisions, broken, sources, insights)):
        print("Freshness self-test failed: accepted event without human review was accepted.")
        return 1

    print("Living-source freshness self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    errors = validate(load(REVISIONS), load(EVENTS), load(SOURCES), load(INSIGHTS))
    if errors:
        print(f"Living-source freshness validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Living-source freshness validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
