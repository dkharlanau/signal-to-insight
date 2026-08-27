#!/usr/bin/env python3
"""Query evidence-backed concept evolution from durable Knowledge Delta and review records."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELTAS = ROOT / "data" / "knowledge-deltas.json"
REVIEWS = ROOT / "data" / "knowledge-reviews.json"
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"
TRANSITIONS = {"new": "established", "reinforces": "reinforced", "refines": "refined", "contradicts": "contradicted"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def insight_dates() -> dict[str, str]:
    sources = {x["id"]: x for x in load(SOURCES).get("sources", [])}
    dates: dict[str, str] = {}
    for item in load(INSIGHTS).get("insights", []):
        source = sources.get(item.get("source_id"), {})
        provenance = item.get("provenance") or {}
        dates[item["id"]] = (
            provenance.get("analyzed_at")
            or source.get("analyzed_at")
            or source.get("captured_at")
            or source.get("publication_date")
            or "9999-12-31"
        )
    return dates


def build() -> dict[str, list[dict]]:
    dates = insight_dates()
    history: dict[str, list[dict]] = defaultdict(list)
    for record in load(DELTAS).get("records", []):
        insight_id = record.get("insight_id")
        for item in record.get("items", []):
            relationship = item.get("relationship")
            concept_id = item.get("concept_id")
            if relationship not in TRANSITIONS or not concept_id:
                continue
            history[concept_id].append({
                "at": dates.get(insight_id, "9999-12-31"),
                "transition": TRANSITIONS[relationship],
                "insight_id": insight_id,
                "review_id": None,
                "source_basis": item.get("source_basis"),
                "prior_basis": item.get("prior_basis"),
                "interpretation": item.get("interpretation"),
            })
    for review in load(REVIEWS).get("reviews", []):
        concept_id = review.get("concept_id")
        if not concept_id or review.get("status") != "resolved":
            continue
        assessment = (review.get("scope_check") or {}).get("assessment")
        transition = {
            "narrower_scope": "narrowed",
            "different_layer": "refined",
            "different_scope": "refined",
        }.get(assessment, {
            "refinement": "refined",
            "contradiction": "contradicted",
            "not_conflict": "reconsidered",
        }.get(review.get("resolution"), "reconsidered"))
        history[concept_id].append({
            "at": review.get("reviewed_at") or dates.get(review.get("trigger_insight_id"), "9999-12-31"),
            "transition": transition,
            "insight_id": review.get("trigger_insight_id"),
            "review_id": review.get("id"),
            "source_basis": None,
            "prior_basis": None,
            "interpretation": review.get("rationale"),
        })
    for events in history.values():
        events.sort(key=lambda x: (x["at"], x.get("insight_id") or "", x.get("review_id") or ""))
    return dict(sorted(history.items()))


def validate(history: dict[str, list[dict]]) -> None:
    allowed = {"established", "reinforced", "refined", "narrowed", "contradicted", "superseded", "restored", "reconsidered"}
    for concept_id, events in history.items():
        if not concept_id or not events:
            raise ValueError("history entries require concept id and events")
        if events[0]["transition"] != "established" and not any(e["transition"] == "established" for e in events):
            # Some concepts predate the current curated delta store; this is allowed but explicit.
            pass
        for event in events:
            if event["transition"] not in allowed:
                raise ValueError(f"invalid transition for {concept_id}: {event['transition']}")
            if not event.get("insight_id") and not event.get("review_id"):
                raise ValueError(f"history event for {concept_id} has no provenance")


def self_test() -> int:
    history = build()
    validate(history)
    if "controlled-execution" not in history:
        print("knowledge_history self-test failed: controlled-execution missing")
        return 1
    transitions = {e["transition"] for e in history["controlled-execution"]}
    if "established" not in transitions or not ({"reinforced", "refined", "narrowed"} & transitions):
        print(f"knowledge_history self-test failed: unexpected transitions {sorted(transitions)}")
        return 1
    print("knowledge_history self-test passed; cumulative evidence yields a provenance-preserving timeline.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("concept", nargs="?")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    history = build()
    validate(history)
    if args.concept:
        events = history.get(args.concept, [])
        if args.json:
            print(json.dumps({"concept_id": args.concept, "events": events}, ensure_ascii=False, indent=2))
        else:
            if not events:
                print(f"No evolution events for {args.concept}")
            for event in events:
                print(f"{event['at']}  {event['transition']}  {event.get('insight_id') or event.get('review_id')}")
                if event.get("interpretation"):
                    print(f"  {event['interpretation']}")
    else:
        print(json.dumps(history, ensure_ascii=False, indent=2) if args.json else f"Concepts with evolution history: {len(history)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
