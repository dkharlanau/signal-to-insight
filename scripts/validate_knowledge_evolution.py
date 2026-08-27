#!/usr/bin/env python3
"""Validate temporal concept/relation evolution against active reviewed knowledge.

The graph remains the active projection. This ledger preserves meaningful reviewed evolution so
new evidence cannot silently rewrite earlier interpretations.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVOLUTION = ROOT / "data" / "knowledge-evolution.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"
CLAIMS = ROOT / "data" / "claim-evidence.json"
REVIEWS = ROOT / "data" / "knowledge-reviews.json"
REANALYSIS = ROOT / "data" / "reanalysis-events.json"

KINDS = {"reinforced", "refined", "narrowed", "contradicted", "superseded", "restored", "reconsidered"}
LINEAGES = {"independent_source", "same_source_revision", "review_resolution"}
STATE_CHANGING_REQUIRED = {"superseded", "restored"}
STATE_CHANGING_FORBIDDEN = {"reinforced", "reconsidered"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def graph_maps(graph: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    concepts = {item.get("id"): item for item in graph.get("concepts", []) if isinstance(item, dict) and item.get("id")}
    relations = {item.get("id"): item for item in graph.get("relations", []) if isinstance(item, dict) and item.get("id")}
    return concepts, relations


def active_snapshot(subject_type: str, item: dict) -> dict:
    if subject_type == "concept":
        return {"summary": item.get("summary"), "coverage": item.get("coverage")}
    return {
        "from": item.get("from"),
        "to": item.get("to"),
        "type": item.get("type"),
        "rationale": item.get("rationale"),
    }


def claim_ids(data: dict) -> set[str]:
    return {
        claim.get("id")
        for record in data.get("records", [])
        for claim in (record.get("claims", []) if isinstance(record, dict) else [])
        if isinstance(claim, dict) and claim.get("id")
    }


def has_cycle(edges: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in edges.get(node, set()):
            if walk(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(walk(node) for node in list(edges))


def validate(
    evolution: dict,
    graph: dict,
    insights_data: dict,
    claims_data: dict,
    reviews_data: dict,
    reanalysis_data: dict,
) -> list[str]:
    errors: list[str] = []
    concepts, relations = graph_maps(graph)
    insights = {item.get("id"): item for item in insights_data.get("insights", []) if isinstance(item, dict)}
    claims = claim_ids(claims_data)
    reviews = {item.get("id"): item for item in reviews_data.get("reviews", []) if isinstance(item, dict)}
    reanalysis = {item.get("id"): item for item in reanalysis_data.get("events", []) if isinstance(item, dict)}

    if not isinstance(evolution.get("version"), str) or not evolution.get("version"):
        errors.append("data/knowledge-evolution.json: version is required")
    subjects = evolution.get("subjects")
    if not isinstance(subjects, list):
        return errors + ["data/knowledge-evolution.json: subjects must be a list"]

    seen_subjects: set[tuple[str, str]] = set()
    seen_event_ids: set[str] = set()
    for s_index, subject in enumerate(subjects):
        where = f"data/knowledge-evolution.json subjects[{s_index}]"
        if not isinstance(subject, dict):
            errors.append(f"{where}: expected object")
            continue
        subject_type = subject.get("subject_type")
        subject_id = subject.get("subject_id")
        if subject_type not in {"concept", "relation"} or not isinstance(subject_id, str) or not subject_id:
            errors.append(f"{where}: invalid subject_type/subject_id")
            continue
        key = (subject_type, subject_id)
        if key in seen_subjects:
            errors.append(f"{where}: duplicate tracked subject {subject_type}:{subject_id}")
        seen_subjects.add(key)

        graph_item = (concepts if subject_type == "concept" else relations).get(subject_id)
        if graph_item is None:
            errors.append(f"{where}: subject is missing from active knowledge graph")
            continue

        states = subject.get("states")
        events = subject.get("events")
        if not isinstance(states, list) or not states:
            errors.append(f"{where}.states: expected non-empty list")
            continue
        if not isinstance(events, list):
            errors.append(f"{where}.events: expected list")
            events = []

        state_map: dict[str, dict] = {}
        active_states: list[str] = []
        for st_index, state in enumerate(states):
            st_where = f"{where}.states[{st_index}]"
            if not isinstance(state, dict):
                errors.append(f"{st_where}: expected object")
                continue
            state_id = state.get("id")
            if not isinstance(state_id, str) or not state_id:
                errors.append(f"{st_where}.id: non-empty string required")
                continue
            if state_id in state_map:
                errors.append(f"{st_where}: duplicate state id {state_id}")
            state_map[state_id] = state
            if not valid_date(state.get("recorded_at")):
                errors.append(f"{st_where}.recorded_at: ISO date required")
            if state.get("status") not in {"active", "superseded"}:
                errors.append(f"{st_where}.status: invalid")
            if state.get("status") == "active":
                active_states.append(state_id)
            if not isinstance(state.get("snapshot"), dict):
                errors.append(f"{st_where}.snapshot: object required")
            for insight_id in state.get("evidence_insight_ids", []):
                if insight_id not in insights:
                    errors.append(f"{st_where}: unknown evidence insight {insight_id}")
            for review_id in state.get("review_ids", []):
                review = reviews.get(review_id)
                if review is None or review.get("status") != "resolved":
                    errors.append(f"{st_where}: review must exist and be resolved: {review_id}")
            for event_id in state.get("reanalysis_event_ids", []):
                event = reanalysis.get(event_id)
                if event is None or event.get("status") != "accepted":
                    errors.append(f"{st_where}: reanalysis event must exist and be accepted: {event_id}")

        active_id = subject.get("active_state_id")
        if active_id not in state_map:
            errors.append(f"{where}.active_state_id: missing state {active_id!r}")
        if active_states != [active_id]:
            errors.append(f"{where}: exactly active_state_id must have status=active; found {active_states}")
        elif state_map[active_id].get("snapshot") != active_snapshot(subject_type, graph_item):
            errors.append(f"{where}: active state snapshot does not match current knowledge graph projection")

        edges: dict[str, set[str]] = {state_id: set() for state_id in state_map}
        outgoing_material: set[str] = set()
        incoming_material: dict[str, int] = {}
        for e_index, event in enumerate(events):
            e_where = f"{where}.events[{e_index}]"
            if not isinstance(event, dict):
                errors.append(f"{e_where}: expected object")
                continue
            event_id = event.get("id")
            if not isinstance(event_id, str) or not event_id:
                errors.append(f"{e_where}.id: non-empty string required")
            elif event_id in seen_event_ids:
                errors.append(f"{e_where}: duplicate evolution event id {event_id}")
            else:
                seen_event_ids.add(event_id)
            kind = event.get("kind")
            if kind not in KINDS:
                errors.append(f"{e_where}.kind: invalid {kind!r}")
            if not valid_date(event.get("recorded_at")):
                errors.append(f"{e_where}.recorded_at: ISO date required")
            material = event.get("material_state_change")
            if not isinstance(material, bool):
                errors.append(f"{e_where}.material_state_change: boolean required")
                material = False
            if kind in STATE_CHANGING_REQUIRED and material is not True:
                errors.append(f"{e_where}: {kind} requires a material state change")
            if kind in STATE_CHANGING_FORBIDDEN and material is True:
                errors.append(f"{e_where}: {kind} cannot create a new semantic state")

            from_id = event.get("from_state_id")
            to_id = event.get("to_state_id")
            if from_id not in state_map:
                errors.append(f"{e_where}.from_state_id: unknown state {from_id!r}")
            if material:
                if not isinstance(to_id, str) or to_id not in state_map:
                    errors.append(f"{e_where}.to_state_id: material change requires an existing target state")
                elif to_id == from_id:
                    errors.append(f"{e_where}: material transition cannot point to the same state")
                else:
                    edges.setdefault(from_id, set()).add(to_id)
                    outgoing_material.add(from_id)
                    incoming_material[to_id] = incoming_material.get(to_id, 0) + 1
                    if incoming_material[to_id] > 1:
                        errors.append(f"{e_where}: a semantic state may not have multiple predecessor transitions")
            elif to_id is not None:
                errors.append(f"{e_where}.to_state_id must be null when material_state_change=false")

            lineage = event.get("evidence_lineage")
            if lineage not in LINEAGES:
                errors.append(f"{e_where}.evidence_lineage: invalid {lineage!r}")
            trigger_insight = event.get("trigger_insight_id")
            trigger_reanalysis = event.get("trigger_reanalysis_event_id")
            if trigger_insight is None and trigger_reanalysis is None:
                errors.append(f"{e_where}: insight or reanalysis trigger is required")
            if trigger_insight is not None and trigger_insight not in insights:
                errors.append(f"{e_where}: unknown trigger insight {trigger_insight}")
            if trigger_reanalysis is not None:
                upstream_event = reanalysis.get(trigger_reanalysis)
                if upstream_event is None:
                    errors.append(f"{e_where}: unknown reanalysis trigger {trigger_reanalysis}")
                elif upstream_event.get("status") != "accepted":
                    errors.append(f"{e_where}: reanalysis trigger must be human-accepted before knowledge evolution")
                if lineage != "same_source_revision":
                    errors.append(f"{e_where}: reanalysis trigger must use evidence_lineage=same_source_revision")

            event_reviews = event.get("review_ids")
            if not isinstance(event_reviews, list):
                errors.append(f"{e_where}.review_ids: list required")
                event_reviews = []
            for review_id in event_reviews:
                review = reviews.get(review_id)
                if review is None or review.get("status") != "resolved":
                    errors.append(f"{e_where}: review must exist and be resolved: {review_id}")
                    continue
                if subject_type == "concept" and review.get("concept_id") != subject_id:
                    errors.append(f"{e_where}: review {review_id} targets another concept")
                if material and (review.get("model_change") or {}).get("kind") == "none":
                    errors.append(f"{e_where}: material change cannot cite a review that explicitly recorded model_change=none")

            event_claims = event.get("evidence_claim_ids")
            if not isinstance(event_claims, list):
                errors.append(f"{e_where}.evidence_claim_ids: list required")
                event_claims = []
            for claim_id in event_claims:
                if claim_id not in claims:
                    errors.append(f"{e_where}: unknown evidence claim {claim_id}")
            if material and not event_reviews and trigger_reanalysis is None:
                errors.append(f"{e_where}: material knowledge change requires resolved review or accepted reanalysis provenance")
            if not isinstance(event.get("reason"), str) or not event.get("reason", "").strip():
                errors.append(f"{e_where}.reason: non-empty rationale required")

        if has_cycle(edges):
            errors.append(f"{where}: material state-transition graph contains a cycle")
        if active_id in outgoing_material:
            errors.append(f"{where}: active state cannot already have an outgoing material transition")
        for state_id, state in state_map.items():
            if state_id != active_id and state.get("status") == "superseded" and state_id not in outgoing_material:
                errors.append(f"{where}: superseded state {state_id} has no outgoing reviewed transition")

    return errors


def self_test() -> int:
    graph = {
        "concepts": [{"id": "c", "summary": "new", "coverage": "explained"}],
        "relations": [],
    }
    insights = {"insights": [{"id": "i-old"}, {"id": "i-new"}]}
    claims = {"records": [{"insight_id": "i-new", "claims": [{"id": "claim-new"}]}]}
    reviews = {
        "reviews": [{
            "id": "review-1",
            "concept_id": "c",
            "trigger_insight_id": "i-new",
            "status": "resolved",
            "resolution": "refinement",
            "model_change": {"kind": "concept_definition"},
        }]
    }
    reanalysis = {"events": []}
    evolution = {
        "version": "1.0.0",
        "subjects": [{
            "subject_type": "concept",
            "subject_id": "c",
            "active_state_id": "c-v2",
            "states": [
                {"id": "c-v1", "recorded_at": "2026-08-26", "status": "superseded", "snapshot": {"summary": "old", "coverage": "introduced"}, "evidence_insight_ids": ["i-old"], "review_ids": [], "reanalysis_event_ids": []},
                {"id": "c-v2", "recorded_at": "2026-08-27", "status": "active", "snapshot": {"summary": "new", "coverage": "explained"}, "evidence_insight_ids": ["i-new"], "review_ids": ["review-1"], "reanalysis_event_ids": []},
            ],
            "events": [{
                "id": "e1", "kind": "refined", "recorded_at": "2026-08-27", "material_state_change": true,
                "from_state_id": "c-v1", "to_state_id": "c-v2", "evidence_lineage": "independent_source",
                "trigger_insight_id": "i-new", "trigger_reanalysis_event_id": null,
                "review_ids": ["review-1"], "evidence_claim_ids": ["claim-new"], "reason": "Reviewed definition refinement."
            }]
        }]
    }
    errors = validate(evolution, graph, insights, claims, reviews, reanalysis)
    if errors:
        print("Knowledge evolution self-test failed on valid fixture:")
        for error in errors:
            print(f"- {error}")
        return 1

    cycle = copy.deepcopy(evolution)
    cycle["subjects"][0]["states"][0]["status"] = "active"
    cycle["subjects"][0]["states"][1]["status"] = "superseded"
    cycle["subjects"][0]["active_state_id"] = "c-v1"
    cycle["subjects"][0]["events"].append({
        "id": "e2", "kind": "restored", "recorded_at": "2026-08-28", "material_state_change": true,
        "from_state_id": "c-v2", "to_state_id": "c-v1", "evidence_lineage": "independent_source",
        "trigger_insight_id": "i-new", "trigger_reanalysis_event_id": null,
        "review_ids": ["review-1"], "evidence_claim_ids": ["claim-new"], "reason": "Invalid circular restoration."
    })
    if not any("cycle" in error for error in validate(cycle, {"concepts": [{"id": "c", "summary": "old", "coverage": "introduced"}], "relations": []}, insights, claims, reviews, reanalysis)):
        print("Knowledge evolution self-test failed: circular state history was accepted.")
        return 1

    mismatch = copy.deepcopy(evolution)
    mismatch["subjects"][0]["states"][1]["snapshot"]["summary"] = "not the graph"
    if not any("active state snapshot" in error for error in validate(mismatch, graph, insights, claims, reviews, reanalysis)):
        print("Knowledge evolution self-test failed: active ledger state diverged from graph projection.")
        return 1

    print("Knowledge evolution self-test passed; active projection, reviewed provenance and acyclic history are enforced.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    errors = validate(load(EVOLUTION), load(GRAPH), load(INSIGHTS), load(CLAIMS), load(REVIEWS), load(REANALYSIS))
    if errors:
        print(f"Knowledge evolution validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Knowledge evolution validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
