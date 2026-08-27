#!/usr/bin/env python3
"""Validate temporal knowledge history against the active graph and review evidence."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "knowledge-history.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"
REVIEWS = ROOT / "data" / "knowledge-reviews.json"
REANALYSIS = ROOT / "data" / "reanalysis-events.json"
STATE_TRANSITIONS = {"refined", "narrowed", "contradicted", "superseded", "restored_reconsidered"}
OBSERVATIONS = STATE_TRANSITIONS | {"reinforced"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def core_snapshot(entity_type: str, snapshot: dict) -> dict:
    if entity_type == "concept":
        return {key: snapshot.get(key) for key in ("summary", "domain", "coverage")}
    return {key: snapshot.get(key) for key in ("from", "to", "type", "rationale")}


def graph_snapshot(entity_type: str, entity: dict) -> dict:
    if entity_type == "concept":
        return {key: entity.get(key) for key in ("summary", "domain", "coverage")}
    return {key: entity.get(key) for key in ("from", "to", "type", "rationale")}


def validate_evidence(
    evidence: dict,
    where: str,
    insight_map: dict[str, dict],
    review_map: dict[str, dict],
    reanalysis_map: dict[str, dict],
    errors: list[str],
) -> None:
    insight_ids = evidence.get("insight_ids") or []
    review_ids = evidence.get("knowledge_review_ids") or []
    event_ids = evidence.get("reanalysis_event_ids") or []
    independence = evidence.get("independence")
    for insight_id in insight_ids:
        if insight_id not in insight_map:
            errors.append(f"{where}: unknown insight_id {insight_id!r}")
    for review_id in review_ids:
        review = review_map.get(review_id)
        if review is None:
            errors.append(f"{where}: unknown knowledge_review_id {review_id!r}")
        elif review.get("status") != "resolved":
            errors.append(f"{where}: knowledge review {review_id!r} is not resolved")
    for event_id in event_ids:
        if event_id not in reanalysis_map:
            errors.append(f"{where}: unknown reanalysis_event_id {event_id!r}")

    if event_ids and not insight_ids and independence != "source_revision":
        errors.append(f"{where}: a source revision without independent insight evidence must use independence=source_revision")
    if event_ids and independence == "independent":
        errors.append(f"{where}: reanalysis provenance cannot be labelled independent evidence")
    if not event_ids and independence == "source_revision":
        errors.append(f"{where}: source_revision independence requires a reanalysis event")
    if event_ids and insight_ids and independence not in {"mixed", "source_revision"}:
        errors.append(f"{where}: mixed source-revision + insight evidence must be labelled mixed or source_revision")


def has_material_authorization(
    evidence: dict,
    review_map: dict[str, dict],
    reanalysis_map: dict[str, dict],
) -> bool:
    for review_id in evidence.get("knowledge_review_ids") or []:
        review = review_map.get(review_id) or {}
        if review.get("status") == "resolved" and (review.get("model_change") or {}).get("kind") not in {None, "none"}:
            return True
    for event_id in evidence.get("reanalysis_event_ids") or []:
        event = reanalysis_map.get(event_id) or {}
        review = event.get("review") or {}
        if event.get("status") == "accepted" and review.get("decision") in {"update_model", "archive_model"}:
            return True
    return False


def cycle_exists(state_ids: set[str], transitions: list[dict]) -> bool:
    edges: dict[str, list[str]] = {state_id: [] for state_id in state_ids}
    for transition in transitions:
        left = transition.get("from_state_id")
        right = transition.get("to_state_id")
        if left in edges and right in state_ids:
            edges[left].append(right)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for target in edges.get(node, []):
            if visit(target):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in state_ids)


def validate(history: dict, graph: dict, insights: dict, reviews: dict, reanalysis: dict) -> list[str]:
    errors: list[str] = []
    insight_map = {item.get("id"): item for item in insights.get("insights", [])}
    review_map = {item.get("id"): item for item in reviews.get("reviews", [])}
    reanalysis_map = {item.get("id"): item for item in reanalysis.get("events", [])}
    concept_map = {item.get("id"): item for item in graph.get("concepts", [])}
    relation_map = {item.get("id"): item for item in graph.get("relations", [])}
    entity_keys: set[tuple[str, str]] = set()

    for e_index, record in enumerate(history.get("entities", [])):
        where = f"data/knowledge-history.json entities[{e_index}]"
        entity_type = record.get("entity_type")
        entity_id = record.get("entity_id")
        key = (str(entity_type), str(entity_id))
        if key in entity_keys:
            errors.append(f"{where}: duplicate tracked entity {entity_type}:{entity_id}")
        entity_keys.add(key)
        graph_entity = concept_map.get(entity_id) if entity_type == "concept" else relation_map.get(entity_id)
        if entity_type not in {"concept", "relation"}:
            errors.append(f"{where}: invalid entity_type {entity_type!r}")
            continue
        if graph_entity is None:
            errors.append(f"{where}: entity_id not found in knowledge graph")
            continue

        states = record.get("states") or []
        state_map: dict[str, dict] = {}
        for s_index, state in enumerate(states):
            s_where = f"{where}.states[{s_index}]"
            state_id = state.get("id")
            if state_id in state_map:
                errors.append(f"{s_where}: duplicate state id {state_id!r}")
            state_map[state_id] = state
            snapshot = state.get("snapshot") or {}
            if entity_type == "concept":
                required = {"summary", "domain", "coverage"}
            else:
                required = {"from", "to", "type", "rationale"}
            if set(snapshot) != required:
                errors.append(f"{s_where}.snapshot: keys must equal {sorted(required)}")
            if entity_type == "relation":
                if snapshot.get("from") not in concept_map or snapshot.get("to") not in concept_map:
                    errors.append(f"{s_where}.snapshot: relation endpoints must exist as concepts")
            validate_evidence(state.get("evidence") or {}, f"{s_where}.evidence", insight_map, review_map, reanalysis_map, errors)

        if not states:
            errors.append(f"{where}: at least one state is required")
            continue
        active_id = record.get("active_state_id")
        public_id = record.get("public_state_id")
        if active_id not in state_map:
            errors.append(f"{where}: active_state_id does not reference a state")
        else:
            active_state = state_map[active_id]
            if active_state.get("review_status") != "reviewed":
                errors.append(f"{where}: active graph state must be reviewed")
            if core_snapshot(entity_type, active_state.get("snapshot") or {}) != graph_snapshot(entity_type, graph_entity):
                errors.append(f"{where}: active state snapshot differs from current graph projection")
        if public_id is not None:
            public_state = state_map.get(public_id)
            if public_state is None:
                errors.append(f"{where}: public_state_id does not reference a state")
            else:
                if public_state.get("review_status") != "reviewed":
                    errors.append(f"{where}: public state must be reviewed")
                evidence_ids = (public_state.get("evidence") or {}).get("insight_ids") or []
                if not evidence_ids or any((insight_map.get(item) or {}).get("status") != "published" for item in evidence_ids):
                    errors.append(f"{where}: public state requires published insight evidence")
                if entity_type == "concept" and isinstance(graph_entity.get("public"), dict):
                    public_snapshot = public_state.get("snapshot") or {}
                    if public_snapshot.get("summary") != graph_entity["public"].get("summary") or public_snapshot.get("coverage") != graph_entity["public"].get("coverage"):
                        errors.append(f"{where}: public state differs from curated graph public projection")

        transitions = record.get("transitions") or []
        transition_ids: set[str] = set()
        incoming: dict[str, int] = {state_id: 0 for state_id in state_map}
        for t_index, transition in enumerate(transitions):
            t_where = f"{where}.transitions[{t_index}]"
            transition_id = transition.get("id")
            if transition_id in transition_ids:
                errors.append(f"{t_where}: duplicate transition id {transition_id!r}")
            transition_ids.add(transition_id)
            left = transition.get("from_state_id")
            right = transition.get("to_state_id")
            if left not in state_map or right not in state_map:
                errors.append(f"{t_where}: transition references unknown state")
                continue
            if left == right:
                errors.append(f"{t_where}: transition cannot point to the same state")
            incoming[right] = incoming.get(right, 0) + 1
            kind = transition.get("kind")
            if kind not in STATE_TRANSITIONS:
                errors.append(f"{t_where}: invalid material transition kind {kind!r}")
            left_snapshot = core_snapshot(entity_type, state_map[left].get("snapshot") or {})
            right_snapshot = core_snapshot(entity_type, state_map[right].get("snapshot") or {})
            if left_snapshot == right_snapshot:
                errors.append(f"{t_where}: material state transition cannot preserve an identical snapshot")
            evidence = transition.get("evidence") or {}
            validate_evidence(evidence, f"{t_where}.evidence", insight_map, review_map, reanalysis_map, errors)
            if not has_material_authorization(evidence, review_map, reanalysis_map):
                errors.append(f"{t_where}: material state change lacks a resolved model-change review or accepted reanalysis decision")
            for event_id in evidence.get("reanalysis_event_ids") or []:
                event = reanalysis_map.get(event_id) or {}
                if (event.get("mental_model") or {}).get("impact") == "stable":
                    errors.append(f"{t_where}: stable reanalysis event cannot authorize a material state change")

        if any(count > 1 for count in incoming.values()):
            errors.append(f"{where}: a state cannot have multiple incoming material transitions")
        if cycle_exists(set(state_map), transitions):
            errors.append(f"{where}: circular knowledge-state/supersession history is not allowed")
        if len(states) > 1:
            roots = [state_id for state_id, count in incoming.items() if count == 0]
            if len(roots) != 1:
                errors.append(f"{where}: multi-state history must have exactly one root state")
            for state_id, count in incoming.items():
                if state_id != (roots[0] if len(roots) == 1 else None) and count != 1:
                    errors.append(f"{where}: every non-root state must have exactly one incoming transition")

        observation_ids: set[str] = set()
        for o_index, observation in enumerate(record.get("observations") or []):
            o_where = f"{where}.observations[{o_index}]"
            observation_id = observation.get("id")
            if observation_id in observation_ids:
                errors.append(f"{o_where}: duplicate observation id {observation_id!r}")
            observation_ids.add(observation_id)
            if observation.get("kind") not in OBSERVATIONS:
                errors.append(f"{o_where}: invalid observation kind {observation.get('kind')!r}")
            evidence = observation.get("evidence") or {}
            validate_evidence(evidence, f"{o_where}.evidence", insight_map, review_map, reanalysis_map, errors)
            for review_id in evidence.get("knowledge_review_ids") or []:
                review = review_map.get(review_id) or {}
                if (review.get("model_change") or {}).get("kind") not in {None, "none"}:
                    errors.append(f"{o_where}: review records a material model change and should be represented as a state transition, not observation")

    return errors


def self_test() -> int:
    history = load(HISTORY)
    graph = load(GRAPH)
    insights = load(INSIGHTS)
    reviews = load(REVIEWS)
    reanalysis = load(REANALYSIS)
    errors = validate(history, graph, insights, reviews, reanalysis)
    if errors:
        print("Knowledge history fixture is invalid:")
        for error in errors:
            print(f"- {error}")
        return 1

    # Exact-snapshot changes are cosmetic, not new knowledge states.
    broken = copy.deepcopy(history)
    entity = broken["entities"][0]
    first = entity["states"][0]
    duplicate = copy.deepcopy(first)
    duplicate["id"] = "state-controlled-execution-cosmetic-test"
    entity["states"].append(duplicate)
    entity["transitions"].append({
        "id": "transition-controlled-execution-cosmetic-test",
        "from_state_id": first["id"],
        "to_state_id": duplicate["id"],
        "kind": "refined",
        "effective_at": "2026-08-27",
        "rationale": "Synthetic cosmetic change.",
        "evidence": {
            "insight_ids": ["open-policy-agent-decision-enforcement-model"],
            "knowledge_review_ids": ["review-opa-controlled-execution-component"],
            "reanalysis_event_ids": [],
            "independence": "independent"
        }
    })
    if not any("identical snapshot" in item for item in validate(broken, graph, insights, reviews, reanalysis)):
        print("Knowledge history self-test failed: cosmetic duplicate state was accepted.")
        return 1

    # A resolved review that explicitly says model_change=none cannot authorize a new state.
    if not any("lacks a resolved model-change review" in item for item in validate(broken, graph, insights, reviews, reanalysis)):
        print("Knowledge history self-test failed: no-change review authorized a new state.")
        return 1

    # Synthetic reviewed material change to exercise cycle detection.
    synthetic_reviews = copy.deepcopy(reviews)
    synthetic_reviews.setdefault("reviews", []).append({
        "id": "review-self-test-material-change",
        "status": "resolved",
        "model_change": {"kind": "definition"}
    })
    cyclic = copy.deepcopy(history)
    entity = cyclic["entities"][0]
    first = entity["states"][0]
    second = copy.deepcopy(first)
    second["id"] = "state-controlled-execution-material-test"
    second["snapshot"]["summary"] = "Synthetic materially changed definition."
    entity["states"].append(second)
    entity["transitions"] = [
        {
            "id": "transition-controlled-execution-material-test",
            "from_state_id": first["id"],
            "to_state_id": second["id"],
            "kind": "refined",
            "effective_at": "2026-08-27",
            "rationale": "Synthetic reviewed change.",
            "evidence": {
                "insight_ids": ["enterprise-agents-production-substrate"],
                "knowledge_review_ids": ["review-self-test-material-change"],
                "reanalysis_event_ids": [],
                "independence": "independent"
            }
        },
        {
            "id": "transition-controlled-execution-cycle-test",
            "from_state_id": second["id"],
            "to_state_id": first["id"],
            "kind": "restored_reconsidered",
            "effective_at": "2026-08-27",
            "rationale": "Synthetic circular restoration.",
            "evidence": {
                "insight_ids": ["enterprise-agents-production-substrate"],
                "knowledge_review_ids": ["review-self-test-material-change"],
                "reanalysis_event_ids": [],
                "independence": "independent"
            }
        }
    ]
    entity["active_state_id"] = first["id"]
    if not any("circular" in item for item in validate(cyclic, graph, insights, synthetic_reviews, reanalysis)):
        print("Knowledge history self-test failed: circular supersession was accepted.")
        return 1

    # A source revision is provenance, not independent evidence by itself.
    revision_noise = copy.deepcopy(history)
    revision_noise["entities"][0]["observations"].append({
        "id": "observation-revision-independence-test",
        "at": "2026-08-27",
        "kind": "reinforced",
        "rationale": "Synthetic revision evidence.",
        "evidence": {
            "insight_ids": [],
            "knowledge_review_ids": [],
            "reanalysis_event_ids": ["reanalysis-opa-2026-08-27"],
            "independence": "independent"
        }
    })
    if not any("cannot be labelled independent" in item for item in validate(revision_noise, graph, insights, reviews, reanalysis)):
        print("Knowledge history self-test failed: source revision was treated as independent evidence.")
        return 1

    print("Knowledge evolution history self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    errors = validate(load(HISTORY), load(GRAPH), load(INSIGHTS), load(REVIEWS), load(REANALYSIS))
    if errors:
        print(f"Knowledge evolution history validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Knowledge evolution history validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
