#!/usr/bin/env python3
"""Query and register reviewed knowledge evolution without rewriting history.

The active knowledge graph is still edited through the normal reviewed change. This command
records why that reviewed change became the new active semantic state, or records a reviewed
non-material refinement/reconsideration when the active state did not need to change.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVOLUTION = ROOT / "data" / "knowledge-evolution.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
REVIEWS = ROOT / "data" / "knowledge-reviews.json"
REANALYSIS = ROOT / "data" / "reanalysis-events.json"

KINDS = ["reinforced", "refined", "narrowed", "contradicted", "superseded", "restored", "reconsidered"]


class EvolutionError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def maps(graph: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    concepts = {item["id"]: item for item in graph.get("concepts", []) if item.get("id")}
    relations = {item["id"]: item for item in graph.get("relations", []) if item.get("id")}
    return concepts, relations


def snapshot(subject_type: str, subject_id: str, graph: dict) -> dict:
    concepts, relations = maps(graph)
    item = (concepts if subject_type == "concept" else relations).get(subject_id)
    if item is None:
        raise EvolutionError(f"{subject_type} not found in knowledge graph: {subject_id}")
    if subject_type == "concept":
        return {"summary": item.get("summary"), "coverage": item.get("coverage")}
    return {"from": item.get("from"), "to": item.get("to"), "type": item.get("type"), "rationale": item.get("rationale")}


def subject_record(data: dict, subject_type: str, subject_id: str) -> dict:
    item = next(
        (row for row in data.get("subjects", []) if row.get("subject_type") == subject_type and row.get("subject_id") == subject_id),
        None,
    )
    if item is None:
        raise EvolutionError(
            f"subject is not evolution-tracked yet: {subject_type}:{subject_id}. "
            "Create its initial state from the current reviewed graph before recording later events."
        )
    return item


def state_by_id(subject: dict, state_id: str) -> dict:
    item = next((state for state in subject.get("states", []) if state.get("id") == state_id), None)
    if item is None:
        raise EvolutionError(f"state not found: {state_id}")
    return item


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "state"


def next_state_id(subject: dict) -> str:
    base = f"state-{slug(subject['subject_id'])}-{date.today().isoformat()}"
    ids = {state.get("id") for state in subject.get("states", [])}
    candidate = f"{base}-v{len(ids) + 1}"
    index = len(ids) + 1
    while candidate in ids:
        index += 1
        candidate = f"{base}-v{index}"
    return candidate


def next_event_id(subject: dict, kind: str, trigger: str) -> str:
    stem = f"evolution-{slug(subject['subject_id'])}-{slug(kind)}-{slug(trigger)}-{date.today().isoformat()}"
    ids = {event.get("id") for event in subject.get("events", [])}
    candidate = stem
    index = 2
    while candidate in ids:
        candidate = f"{stem}-{index}"
        index += 1
    return candidate


def review_map() -> dict[str, dict]:
    return {item["id"]: item for item in load(REVIEWS).get("reviews", []) if item.get("id")}


def reanalysis_map() -> dict[str, dict]:
    return {item["id"]: item for item in load(REANALYSIS).get("events", []) if item.get("id")}


def apply_state_change(subject: dict, graph: dict, kind: str, reason: str, event_fields: dict) -> dict:
    if kind in {"reinforced", "reconsidered"}:
        raise EvolutionError(f"{kind} cannot create a material semantic state")
    current_id = subject["active_state_id"]
    current = state_by_id(subject, current_id)
    before = current.get("snapshot")
    after = snapshot(subject["subject_type"], subject["subject_id"], graph)
    if before == after:
        raise EvolutionError("material transition requested but active graph snapshot did not change")

    new_id = next_state_id(subject)
    current["status"] = "superseded"
    subject["states"].append({
        "id": new_id,
        "recorded_at": date.today().isoformat(),
        "status": "active",
        "snapshot": after,
        "evidence_insight_ids": event_fields.get("evidence_insight_ids", []),
        "review_ids": event_fields.get("review_ids", []),
        "reanalysis_event_ids": event_fields.get("reanalysis_event_ids", []),
    })
    subject["active_state_id"] = new_id
    event = {
        "id": next_event_id(subject, kind, event_fields["trigger_label"]),
        "kind": kind,
        "recorded_at": date.today().isoformat(),
        "material_state_change": True,
        "from_state_id": current_id,
        "to_state_id": new_id,
        "evidence_lineage": event_fields["evidence_lineage"],
        "trigger_insight_id": event_fields.get("trigger_insight_id"),
        "trigger_reanalysis_event_id": event_fields.get("trigger_reanalysis_event_id"),
        "review_ids": event_fields.get("review_ids", []),
        "evidence_claim_ids": event_fields.get("evidence_claim_ids", []),
        "reason": reason,
    }
    subject.setdefault("events", []).append(event)
    return event


def apply_non_material(subject: dict, kind: str, reason: str, event_fields: dict) -> dict:
    if kind in {"superseded", "restored"}:
        raise EvolutionError(f"{kind} requires a material semantic state")
    active_id = subject["active_state_id"]
    event = {
        "id": next_event_id(subject, kind, event_fields["trigger_label"]),
        "kind": kind,
        "recorded_at": date.today().isoformat(),
        "material_state_change": False,
        "from_state_id": active_id,
        "to_state_id": None,
        "evidence_lineage": event_fields["evidence_lineage"],
        "trigger_insight_id": event_fields.get("trigger_insight_id"),
        "trigger_reanalysis_event_id": event_fields.get("trigger_reanalysis_event_id"),
        "review_ids": event_fields.get("review_ids", []),
        "evidence_claim_ids": event_fields.get("evidence_claim_ids", []),
        "reason": reason,
    }
    subject.setdefault("events", []).append(event)
    return event


def record_review(subject_type: str, subject_id: str, review_id: str, kind: str, reason: str, material: bool, confirm: str | None) -> dict:
    data = load(EVOLUTION)
    graph = load(GRAPH)
    subject = subject_record(data, subject_type, subject_id)
    review = review_map().get(review_id)
    if review is None or review.get("status") != "resolved":
        raise EvolutionError("knowledge review must exist and be resolved")
    if subject_type == "concept" and review.get("concept_id") != subject_id:
        raise EvolutionError("knowledge review targets a different concept")
    model_change = (review.get("model_change") or {}).get("kind")
    if material and model_change == "none":
        raise EvolutionError("review explicitly records model_change=none; cannot create a material state")
    if not material and model_change != "none":
        raise EvolutionError("review records a material model change; record it as a material state transition")
    if material and confirm != f"EVOLVE:{subject_id}":
        raise EvolutionError(f"material transition confirmation must exactly equal EVOLVE:{subject_id}")

    evidence = review.get("evidence") or {}
    fields = {
        "trigger_label": review_id,
        "evidence_lineage": "independent_source",
        "trigger_insight_id": review.get("trigger_insight_id"),
        "trigger_reanalysis_event_id": None,
        "review_ids": [review_id],
        "evidence_claim_ids": list(dict.fromkeys((evidence.get("new_claim_ids") or []) + (evidence.get("prior_claim_ids") or []))),
        "evidence_insight_ids": [review.get("trigger_insight_id")] if review.get("trigger_insight_id") else [],
        "reanalysis_event_ids": [],
    }
    event = apply_state_change(subject, graph, kind, reason, fields) if material else apply_non_material(subject, kind, reason, fields)
    dump(EVOLUTION, data)
    return event


def record_reanalysis(subject_type: str, subject_id: str, reanalysis_id: str, kind: str, reason: str, material: bool, confirm: str | None) -> dict:
    data = load(EVOLUTION)
    graph = load(GRAPH)
    subject = subject_record(data, subject_type, subject_id)
    upstream = reanalysis_map().get(reanalysis_id)
    if upstream is None or upstream.get("status") != "accepted":
        raise EvolutionError("reanalysis event must exist and be human-accepted before entering knowledge evolution")
    decision = (upstream.get("review") or {}).get("decision")
    impact = (upstream.get("mental_model") or {}).get("impact")
    if material and decision != "update_model":
        raise EvolutionError("material reanalysis evolution requires review decision=update_model")
    if not material and decision != "keep_current_model":
        raise EvolutionError("non-material reanalysis evolution requires review decision=keep_current_model")
    if material and confirm != f"EVOLVE:{subject_id}":
        raise EvolutionError(f"material transition confirmation must exactly equal EVOLVE:{subject_id}")
    if not material and kind != "reconsidered":
        raise EvolutionError("stable accepted source reanalysis should be recorded as reconsidered, not independent reinforcement")
    if material and impact not in {"refine", "contradict", "supersede"}:
        raise EvolutionError("material reanalysis requires refine/contradict/supersede impact")

    insight_id = upstream.get("insight_id")
    fields = {
        "trigger_label": reanalysis_id,
        "evidence_lineage": "same_source_revision",
        "trigger_insight_id": None,
        "trigger_reanalysis_event_id": reanalysis_id,
        "review_ids": [],
        "evidence_claim_ids": [],
        "evidence_insight_ids": [insight_id] if insight_id else [],
        "reanalysis_event_ids": [reanalysis_id],
    }
    event = apply_state_change(subject, graph, kind, reason, fields) if material else apply_non_material(subject, kind, reason, fields)
    dump(EVOLUTION, data)
    return event


def print_timeline(subject: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(subject, ensure_ascii=False, indent=2))
        return
    print(f"{subject['subject_type']}:{subject['subject_id']}")
    print(f"active: {subject['active_state_id']}")
    for state in subject.get("states", []):
        print(f"state {state['recorded_at']} {state['id']} [{state['status']}]")
    for event in subject.get("events", []):
        suffix = f" -> {event['to_state_id']}" if event.get("to_state_id") else " (active state unchanged)"
        print(f"event {event['recorded_at']} {event['kind']}: {event['from_state_id']}{suffix}")
        print(f"  {event['reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show", help="Show one tracked concept/relation timeline")
    show.add_argument("--type", dest="subject_type", choices=["concept", "relation"], required=True)
    show.add_argument("--subject", required=True)
    show.add_argument("--json", action="store_true")

    review = sub.add_parser("record-review", help="Record a resolved knowledge review as evolution")
    review.add_argument("--type", dest="subject_type", choices=["concept", "relation"], required=True)
    review.add_argument("--subject", required=True)
    review.add_argument("--review", required=True)
    review.add_argument("--kind", choices=KINDS, required=True)
    review.add_argument("--reason", required=True)
    review.add_argument("--material", action="store_true")
    review.add_argument("--confirm")

    upstream = sub.add_parser("record-reanalysis", help="Record an accepted living-source reanalysis in knowledge history")
    upstream.add_argument("--type", dest="subject_type", choices=["concept", "relation"], required=True)
    upstream.add_argument("--subject", required=True)
    upstream.add_argument("--event", required=True)
    upstream.add_argument("--kind", choices=KINDS, required=True)
    upstream.add_argument("--reason", required=True)
    upstream.add_argument("--material", action="store_true")
    upstream.add_argument("--confirm")

    args = parser.parse_args()
    try:
        if args.command == "show":
            print_timeline(subject_record(load(EVOLUTION), args.subject_type, args.subject), args.json)
            return 0
        if args.command == "record-review":
            event = record_review(args.subject_type, args.subject, args.review, args.kind, args.reason, args.material, args.confirm)
        else:
            event = record_reanalysis(args.subject_type, args.subject, args.event, args.kind, args.reason, args.material, args.confirm)
    except (EvolutionError, json.JSONDecodeError) as exc:
        print(f"Knowledge evolution command failed: {exc}")
        return 1
    print(json.dumps(event, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
