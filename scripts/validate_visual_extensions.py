#!/usr/bin/env python3
"""Validate evidence-driven visual extensions and real-source exercise cases."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = ROOT / "data" / "visual-extensions.json"
INSIGHTS = ROOT / "data" / "insights.json"
SOURCES = ROOT / "data" / "sources.json"
PRIMITIVES = {"decision_tree", "state_transition", "source_figure"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def reachable(root: str, edges: list[dict]) -> set[str]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adjacency[edge["from"]].append(edge["to"])
    seen = {root}
    queue = deque([root])
    while queue:
        node = queue.popleft()
        for target in adjacency.get(node, []):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def directed_cycle(node_ids: set[str], edges: list[dict]) -> bool:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adjacency[edge["from"]].append(edge["to"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for target in adjacency.get(node, []):
            if visit(target):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in node_ids)


def validate_graph_shape(nodes: list[dict], edges: list[dict], where: str, errors: list[str]) -> tuple[set[str], dict[str, int], dict[str, int]]:
    ids = [node.get("id") for node in nodes]
    node_ids = {item for item in ids if isinstance(item, str)}
    if len(node_ids) != len(ids):
        errors.append(f"{where}: node/state IDs must be unique non-empty strings")
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: 0 for node_id in node_ids}
    for index, edge in enumerate(edges):
        e_where = f"{where}.edges[{index}]"
        left = edge.get("from")
        right = edge.get("to")
        if left not in node_ids or right not in node_ids:
            errors.append(f"{e_where}: edge endpoints must reference defined nodes")
            continue
        if left == right:
            errors.append(f"{e_where}: self-edge is not allowed")
        if not str(edge.get("label") or "").strip():
            errors.append(f"{e_where}: edge label is required")
        outgoing[left] += 1
        incoming[right] += 1
    return node_ids, incoming, outgoing


def validate(payload: dict, insight_data: dict, source_data: dict) -> list[str]:
    errors: list[str] = []
    insights = {item.get("id"): item for item in insight_data.get("insights", [])}
    sources = {item.get("id"): item for item in source_data.get("sources", [])}
    seen_ids: set[str] = set()
    exercised: set[str] = set()

    for index, record in enumerate(payload.get("records", [])):
        where = f"data/visual-extensions.json records[{index}]"
        record_id = record.get("id")
        if record_id in seen_ids:
            errors.append(f"{where}: duplicate extension id {record_id!r}")
        seen_ids.add(record_id)

        primitive = record.get("primitive")
        if primitive not in PRIMITIVES:
            errors.append(f"{where}: unsupported primitive {primitive!r}")
            continue
        exercised.add(primitive)
        insight = insights.get(record.get("insight_id"))
        source = sources.get(record.get("source_id"))
        if insight is None:
            errors.append(f"{where}: insight_id does not exist")
            continue
        if source is None:
            errors.append(f"{where}: source_id does not exist")
            continue
        if insight.get("source_id") != record.get("source_id"):
            errors.append(f"{where}: extension source_id differs from the insight source")
        if insight.get("status") not in {"review", "published"}:
            errors.append(f"{where}: visual extension requires a real review/published insight")
        if len(str(record.get("reason") or "").strip()) < 40:
            errors.append(f"{where}: reason must explain why this visual improves comprehension")
        fallback = record.get("fallback") or {}
        if len(fallback.get("items") or []) < 2:
            errors.append(f"{where}: accessible fallback must preserve at least two semantic points")

        present_payloads = [name for name in PRIMITIVES if isinstance(record.get(name), dict)]
        if present_payloads != [primitive]:
            errors.append(f"{where}: exactly the selected primitive payload must be present; found {present_payloads}")
            continue

        if primitive == "decision_tree":
            tree = record["decision_tree"]
            nodes = tree.get("nodes") or []
            edges = tree.get("edges") or []
            node_ids, incoming, outgoing = validate_graph_shape(nodes, edges, f"{where}.decision_tree", errors)
            root = tree.get("root_id")
            if root not in node_ids:
                errors.append(f"{where}.decision_tree: root_id must reference a node")
            else:
                if incoming.get(root) != 0:
                    errors.append(f"{where}.decision_tree: root must have no incoming edge")
                for node_id in node_ids - {root}:
                    if incoming.get(node_id) != 1:
                        errors.append(f"{where}.decision_tree: non-root node {node_id!r} must have exactly one incoming edge")
                if reachable(root, edges) != node_ids:
                    errors.append(f"{where}.decision_tree: every node must be reachable from root")
            if directed_cycle(node_ids, edges):
                errors.append(f"{where}.decision_tree: decision tree cannot contain a cycle")
            if max(outgoing.values(), default=0) < 2:
                errors.append(f"{where}.decision_tree: at least one decision must branch to two or more outcomes")
            decision_nodes = {node.get("id") for node in nodes if node.get("kind") == "decision"}
            if not any(outgoing.get(node_id, 0) >= 2 for node_id in decision_nodes):
                errors.append(f"{where}.decision_tree: a node marked decision must own the branch")

        elif primitive == "state_transition":
            state_machine = record["state_transition"]
            states = state_machine.get("states") or []
            transitions = state_machine.get("transitions") or []
            node_ids, _, _ = validate_graph_shape(states, transitions, f"{where}.state_transition", errors)
            initial = state_machine.get("initial_state_id")
            if initial not in node_ids:
                errors.append(f"{where}.state_transition: initial_state_id must reference a state")
            elif reachable(initial, transitions) != node_ids:
                errors.append(f"{where}.state_transition: every state must be reachable from the initial state")
            if not directed_cycle(node_ids, transitions):
                errors.append(f"{where}.state_transition: real state-transition primitive must express at least one return/recovery cycle")
            if not any(state.get("kind") == "recovery" for state in states):
                errors.append(f"{where}.state_transition: recovery case requires at least one recovery state")

        elif primitive == "source_figure":
            figure = record["source_figure"]
            image_url = urlparse(str(figure.get("url") or ""))
            page_url = urlparse(str(figure.get("source_page") or ""))
            if image_url.scheme != "https" or page_url.scheme != "https":
                errors.append(f"{where}.source_figure: image and source page must use https")
            if not image_url.netloc or image_url.netloc != page_url.netloc:
                errors.append(f"{where}.source_figure: remote figure must be hosted by the declared source page domain")
            source_urls = {item.get("url") for item in insight.get("supporting_sources", [])}
            source_urls.add(source.get("canonical_url"))
            if figure.get("source_page") not in source_urls:
                errors.append(f"{where}.source_figure: source_page must already be recorded in insight provenance")
            if figure.get("copy_policy") != "remote_source_owned":
                errors.append(f"{where}.source_figure: source-owned figure must remain remote rather than copied into the repository")
            if len(str(figure.get("alt") or "").strip()) < 20:
                errors.append(f"{where}.source_figure: meaningful alt text is required")
            if not str(figure.get("attribution") or "").strip():
                errors.append(f"{where}.source_figure: attribution is required")
            if len(str(figure.get("rights_note") or "").strip()) < 20:
                errors.append(f"{where}.source_figure: rights/copy boundary note is required")

    if exercised != PRIMITIVES:
        errors.append(f"data/visual-extensions.json: real corpus must exercise exactly {sorted(PRIMITIVES)}, found {sorted(exercised)}")
    return errors


def self_test() -> int:
    payload = load(EXTENSIONS)
    insights = load(INSIGHTS)
    sources = load(SOURCES)
    errors = validate(payload, insights, sources)
    if errors:
        print("Visual extension fixture is invalid:")
        for error in errors:
            print(f"- {error}")
        return 1

    broken = copy.deepcopy(payload)
    tree = next(item for item in broken["records"] if item["primitive"] == "decision_tree")["decision_tree"]
    tree["edges"].append({"from": "allow", "to": tree["root_id"], "label": "synthetic cycle"})
    if not any("cannot contain a cycle" in item for item in validate(broken, insights, sources)):
        print("Visual extension self-test failed: cyclic decision tree was accepted.")
        return 1

    broken = copy.deepcopy(payload)
    machine = next(item for item in broken["records"] if item["primitive"] == "state_transition")["state_transition"]
    machine["transitions"] = [edge for edge in machine["transitions"] if edge["to"] != "workflow-active" and edge["to"] != "task-ready"]
    if not any("return/recovery cycle" in item or "reachable" in item for item in validate(broken, insights, sources)):
        print("Visual extension self-test failed: linearized recovery model was accepted.")
        return 1

    broken = copy.deepcopy(payload)
    figure = next(item for item in broken["records"] if item["primitive"] == "source_figure")["source_figure"]
    figure["url"] = "https://example.com/copied-diagram.png"
    if not any("hosted by the declared source" in item for item in validate(broken, insights, sources)):
        print("Visual extension self-test failed: unrelated remote figure host was accepted.")
        return 1

    print("Visual extension self-test passed: decision tree, state transition and source-owned figure are exercised on real sources.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    errors = validate(load(EXTENSIONS), load(INSIGHTS), load(SOURCES))
    if errors:
        print(f"Visual extension validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Visual extension validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
