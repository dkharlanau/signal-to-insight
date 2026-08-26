#!/usr/bin/env python3
"""Retrieve prior knowledge from the cumulative concept graph before researching a new source."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"
TOKEN = re.compile(r"[a-z0-9]+")


def words(value: str) -> set[str]:
    return {token for token in TOKEN.findall(value.lower()) if len(token) > 2}


def searchable(concept: dict) -> str:
    return " ".join([
        concept.get("label", ""),
        concept.get("summary", ""),
        concept.get("domain", ""),
        " ".join(concept.get("aliases", [])),
        " ".join(concept.get("tags", [])),
    ])


def rank(query: str, limit: int = 5) -> dict:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    insight_data = json.loads(INSIGHTS.read_text(encoding="utf-8"))
    insights = {item["id"]: item for item in insight_data.get("insights", [])}
    concepts = {item["id"]: item for item in graph.get("concepts", [])}
    query_words = words(query)
    if not query_words:
        return {"query": query, "matches": [], "message": "No searchable terms."}

    scored = []
    for concept in concepts.values():
        label_words = words(concept.get("label", "") + " " + " ".join(concept.get("aliases", [])))
        tag_words = words(" ".join(concept.get("tags", [])) + " " + concept.get("domain", ""))
        body_words = words(concept.get("summary", ""))
        exact = len(query_words & label_words)
        tagged = len(query_words & tag_words)
        body = len(query_words & body_words)
        score = exact * 5 + tagged * 3 + body
        if score:
            scored.append((score, concept["id"]))
    scored.sort(key=lambda item: (-item[0], concepts[item[1]]["label"].lower()))
    seeds = [concept_id for _, concept_id in scored[:limit]]

    neighbors: dict[str, list[dict]] = defaultdict(list)
    for relation in graph.get("relations", []):
        if relation["from"] in seeds:
            neighbors[relation["from"]].append({
                "direction": "out",
                "type": relation["type"],
                "concept_id": relation["to"],
                "label": concepts[relation["to"]]["label"],
                "rationale": relation["rationale"],
            })
        if relation["to"] in seeds:
            neighbors[relation["to"]].append({
                "direction": "in",
                "type": relation["type"],
                "concept_id": relation["from"],
                "label": concepts[relation["from"]]["label"],
                "rationale": relation["rationale"],
            })

    matches = []
    score_map = dict((concept_id, score) for score, concept_id in scored)
    for concept_id in seeds:
        concept = concepts[concept_id]
        evidence = []
        for insight_id in concept.get("insight_ids", []):
            insight = insights.get(insight_id, {})
            evidence.append({
                "id": insight_id,
                "status": insight.get("status"),
                "title": insight.get("title"),
                "slug": insight.get("slug"),
            })
        matches.append({
            "concept_id": concept_id,
            "label": concept["label"],
            "score": score_map[concept_id],
            "coverage": concept["coverage"],
            "summary": concept["summary"],
            "evidence": evidence,
            "neighbors": neighbors.get(concept_id, [])[:8],
        })

    return {
        "query": query,
        "matches": matches,
        "instruction": "Use these matches as prior knowledge. Distinguish reinforcement, refinement, contradiction and genuinely new concepts before drafting a new insight."
    }


def self_test() -> int:
    result = rank("durable workflow retry", limit=4)
    ids = {item["concept_id"] for item in result.get("matches", [])}
    expected = {"durable-execution", "idempotency-under-retry"}
    missing = expected - ids
    if missing:
        print(f"graph context self-test failed; missing {sorted(missing)}")
        return 1
    if not any(item.get("neighbors") for item in result["matches"]):
        print("graph context self-test failed; expected expanded neighbors")
        return 1
    print("Graph context self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="New-source topic, question or short description")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.query:
        parser.error("query is required unless --self-test is used")
    result = rank(args.query, max(1, args.limit))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print(f"Prior knowledge for: {result['query']}")
    if not result["matches"]:
        print("- no graph matches")
        return 0
    for match in result["matches"]:
        print(f"\n[{match['score']}] {match['label']} ({match['coverage']})")
        print(f"  {match['summary']}")
        for evidence in match["evidence"]:
            print(f"  evidence: {evidence['status']} · {evidence['title']}")
        for neighbor in match["neighbors"]:
            arrow = "→" if neighbor["direction"] == "out" else "←"
            print(f"  {arrow} {neighbor['type']} · {neighbor['label']}")
    print("\nClassify the new source as reinforcement, refinement, contradiction or new knowledge before drafting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
