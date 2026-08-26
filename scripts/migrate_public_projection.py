#!/usr/bin/env python3
"""One-time migration for concepts that currently mix published and review evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "data" / "knowledge-graph.json"

CONCEPT_OVERRIDES = {
    "controlled-execution": {
        "summary": "A production work substrate that makes consequential execution authorized, observable, interruptible, reconstructable and testable.",
        "coverage": "explained",
        "evidence_insights": ["enterprise-agents-production-substrate"],
    },
    "execution-history": {
        "summary": "A durable record of what happened during work so state, decisions and actions can be reconstructed later.",
        "coverage": "explained",
        "evidence_insights": ["enterprise-agents-production-substrate"],
    },
    "policy-as-code": {
        "summary": "Representing authorization and policy decisions as explicit, reviewable rules rather than scattered application logic.",
        "coverage": "introduced",
        "evidence_insights": ["enterprise-agents-production-substrate"],
    },
    "durable-execution": {
        "summary": "A reliability pattern for long-running work where progress can survive interruptions instead of depending only on one running process.",
        "coverage": "introduced",
        "evidence_insights": ["enterprise-agents-production-substrate"],
    },
}

RELATION_OVERRIDES = {
    "rel-durable-execution-related-to-controlled-execution": {
        "rationale": "Durability addresses continuity of work; controlled execution additionally requires authority, evidence, intervention and other governance controls.",
        "evidence_insights": ["enterprise-agents-production-substrate"],
    }
}


def main() -> int:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    changed = False
    for concept in graph.get("concepts", []):
        override = CONCEPT_OVERRIDES.get(concept.get("id"))
        if override is not None and concept.get("public") != override:
            concept["public"] = override
            changed = True
    for relation in graph.get("relations", []):
        override = RELATION_OVERRIDES.get(relation.get("id"))
        if override is not None and relation.get("public") != override:
            relation["public"] = override
            changed = True
    if graph.get("graph_version") == "0.2.0":
        graph["graph_version"] = "0.2.1"
        changed = True
    if changed:
        GRAPH.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Applied current public projection migration.")
    else:
        print("Public projection migration already applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
