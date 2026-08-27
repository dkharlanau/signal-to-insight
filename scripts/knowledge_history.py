#!/usr/bin/env python3
"""Query temporal knowledge history without pretending every observation is a new state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "knowledge-history.json"
INSIGHTS = ROOT / "data" / "insights.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def record_for(entity_id: str, history: dict) -> dict | None:
    return next((item for item in history.get("entities", []) if item.get("entity_id") == entity_id), None)


def evidence_is_public(evidence: dict, insights: dict[str, dict]) -> bool:
    insight_ids = evidence.get("insight_ids") or []
    return bool(insight_ids) and all((insights.get(item) or {}).get("status") == "published" for item in insight_ids)


def projection(record: dict, public_only: bool = False) -> dict:
    insights = {item["id"]: item for item in load(INSIGHTS).get("insights", [])}
    states = record.get("states") or []
    state_map = {item["id"]: item for item in states}
    active_id = record.get("public_state_id") if public_only else record.get("active_state_id")
    active = state_map.get(active_id)

    visible_states = []
    for state in states:
        if public_only and not evidence_is_public(state.get("evidence") or {}, insights):
            continue
        visible_states.append(state)
    visible_ids = {item["id"] for item in visible_states}

    transitions = [
        item for item in record.get("transitions", [])
        if item.get("from_state_id") in visible_ids
        and item.get("to_state_id") in visible_ids
        and (not public_only or evidence_is_public(item.get("evidence") or {}, insights))
    ]
    observations = [
        item for item in record.get("observations", [])
        if not public_only or evidence_is_public(item.get("evidence") or {}, insights)
    ]

    output = {
        "entity_type": record.get("entity_type"),
        "entity_id": record.get("entity_id"),
        "active_state": active,
        "observations": observations,
        "timeline_visible": len(visible_states) > 1,
    }
    if len(visible_states) > 1:
        output["timeline"] = {
            "states": visible_states,
            "transitions": transitions,
        }
    return output


def human_print(result: dict) -> None:
    print(f"Knowledge history: {result['entity_type']} · {result['entity_id']}")
    active = result.get("active_state") or {}
    if active:
        print(f"Current state: {active.get('id')} · effective {active.get('effective_at')} · {active.get('review_status')}")
        snapshot = active.get("snapshot") or {}
        if "summary" in snapshot:
            print(f"  {snapshot.get('summary')}")
        else:
            print(f"  {snapshot.get('from')} → {snapshot.get('type')} → {snapshot.get('to')}")
            print(f"  {snapshot.get('rationale')}")

    if result.get("timeline_visible"):
        timeline = result["timeline"]
        print("\nMaterial state timeline:")
        transitions_by_to = {item["to_state_id"]: item for item in timeline.get("transitions", [])}
        for state in sorted(timeline.get("states", []), key=lambda item: (item.get("effective_at", ""), item.get("id", ""))):
            transition = transitions_by_to.get(state["id"])
            prefix = f"{transition['kind']} → " if transition else "baseline → "
            print(f"- {prefix}{state['id']} ({state['effective_at']})")
    else:
        print("\nMaterial state timeline: hidden — only one meaningful reviewed state exists.")

    observations = result.get("observations") or []
    if observations:
        print("\nReviewed observations that did not rewrite the state:")
        for item in observations:
            print(f"- {item['at']} · {item['kind']} · {item['rationale']}")


def self_test() -> int:
    history = load(HISTORY)
    record = record_for("controlled-execution", history)
    if record is None:
        print("Knowledge history self-test failed: controlled-execution fixture missing.")
        return 1
    result = projection(record)
    if result.get("timeline_visible") is not False:
        print("Knowledge history self-test failed: single-state entity exposed a fake timeline.")
        return 1
    if len(result.get("observations") or []) < 2:
        print("Knowledge history self-test failed: reviewed no-change observations were lost.")
        return 1
    public = projection(record, public_only=True)
    if public.get("observations"):
        print("Knowledge history self-test failed: review-only observations leaked into public projection.")
        return 1
    print("Knowledge history query self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entity_id", nargs="?")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--public", action="store_true", help="Project only states/evidence backed by published insights")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.entity_id:
        parser.error("entity_id is required unless --self-test is used")
    record = record_for(args.entity_id, load(HISTORY))
    if record is None:
        print(f"No tracked temporal history for {args.entity_id}.", file=sys.stderr)
        return 1
    result = projection(record, public_only=args.public)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        human_print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
