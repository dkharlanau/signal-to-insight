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
STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "architecture", "because", "before", "between",
    "can", "could", "does", "from", "have", "how", "into", "learn", "like", "make", "making", "more",
    "need", "other", "our", "should", "source", "that", "the", "their", "them", "then", "this", "through",
    "try", "use", "using", "what", "when", "where", "which", "why", "with", "would", "your"
}


def words(value: str) -> set[str]:
    return {
        token
        for token in TOKEN.findall(value.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def normalized_phrase(value: str) -> str:
    return " ".join(TOKEN.findall(value.lower()))


def searchable(concept: dict) -> str:
    return " ".join([
        concept.get("label", ""),
        concept.get("summary", ""),
        concept.get("domain", ""),
        " ".join(concept.get("aliases", [])),
        " ".join(concept.get("tags", [])),
    ])


def lexical_features(query: str, query_words: set[str], concept: dict) -> dict:
    label_and_aliases = concept.get("label", "") + " " + " ".join(concept.get("aliases", []))
    label_words = words(label_and_aliases)
    tag_words = words(" ".join(concept.get("tags", [])) + " " + concept.get("domain", ""))
    body_words = words(concept.get("summary", ""))
    label_hits = query_words & label_words
    tag_hits = query_words & tag_words
    body_hits = query_words & body_words

    normalized_query = normalized_phrase(query)
    phrases = [concept.get("label", ""), *concept.get("aliases", [])]
    phrase_match = any(
        phrase and len(words(phrase)) > 0 and normalized_phrase(phrase) in normalized_query
        for phrase in phrases
    )
    score = len(label_hits) * 6 + len(tag_hits) * 3 + len(body_hits) + (8 if phrase_match else 0)
    return {
        "score": score,
        "label_hits": label_hits,
        "tag_hits": tag_hits,
        "body_hits": body_hits,
        "phrase_match": phrase_match,
        "distinct_hits": label_hits | tag_hits | body_hits,
    }


def is_strong_seed(features: dict) -> bool:
    """Reject accidental single-token tag/body matches before graph expansion amplifies them."""
    if features["phrase_match"]:
        return True
    if features["label_hits"]:
        return True
    # No label match: require at least two independent topical terms. A single tag such as
    # 'retrieval', 'engine' or 'system' is not enough evidence that two domains are related.
    if len(features["distinct_hits"]) >= 2 and (features["tag_hits"] or len(features["body_hits"]) >= 2):
        return True
    return False


def rank(query: str, limit: int = 5) -> dict:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    insight_data = json.loads(INSIGHTS.read_text(encoding="utf-8"))
    insights = {item["id"]: item for item in insight_data.get("insights", [])}
    concepts = {item["id"]: item for item in graph.get("concepts", [])}
    query_words = words(query)
    if not query_words:
        return {"query": query, "matches": [], "message": "No searchable terms."}

    scored: list[tuple[int, str]] = []
    feature_map: dict[str, dict] = {}
    for concept in concepts.values():
        features = lexical_features(query, query_words, concept)
        feature_map[concept["id"]] = features
        if is_strong_seed(features):
            scored.append((features["score"], concept["id"]))
    scored.sort(key=lambda item: (-item[0], concepts[item[1]]["label"].lower()))

    seed_limit = min(max(1, limit), 3)
    seeds = [concept_id for _, concept_id in scored[:seed_limit]]
    score_map = {concept_id: score for score, concept_id in scored}

    neighbors: dict[str, list[dict]] = defaultdict(list)
    neighbor_candidates: dict[str, dict] = {}
    for relation in graph.get("relations", []):
        left = relation["from"]
        right = relation["to"]
        if left in seeds:
            entry = {
                "direction": "out",
                "type": relation["type"],
                "concept_id": right,
                "label": concepts[right]["label"],
                "rationale": relation["rationale"],
            }
            neighbors[left].append(entry)
            if right not in seeds:
                neighbor_candidates.setdefault(right, {"via": [], "strength": 0})
                neighbor_candidates[right]["via"].append({"seed": left, "type": relation["type"], "direction": "out"})
                neighbor_candidates[right]["strength"] += score_map.get(left, 0)
        if right in seeds:
            entry = {
                "direction": "in",
                "type": relation["type"],
                "concept_id": left,
                "label": concepts[left]["label"],
                "rationale": relation["rationale"],
            }
            neighbors[right].append(entry)
            if left not in seeds:
                neighbor_candidates.setdefault(left, {"via": [], "strength": 0})
                neighbor_candidates[left]["via"].append({"seed": right, "type": relation["type"], "direction": "in"})
                neighbor_candidates[left]["strength"] += score_map.get(right, 0)

    remaining = max(0, limit - len(seeds))
    expanded = sorted(
        neighbor_candidates,
        key=lambda concept_id: (
            -neighbor_candidates[concept_id]["strength"],
            -feature_map.get(concept_id, {}).get("score", 0),
            concepts[concept_id]["label"].lower(),
        ),
    )[:remaining]
    selected = seeds + expanded

    selected_set = set(selected)
    for relation in graph.get("relations", []):
        if relation["from"] in selected_set and not any(
            item["concept_id"] == relation["to"] and item["type"] == relation["type"] and item["direction"] == "out"
            for item in neighbors[relation["from"]]
        ):
            neighbors[relation["from"]].append({
                "direction": "out",
                "type": relation["type"],
                "concept_id": relation["to"],
                "label": concepts[relation["to"]]["label"],
                "rationale": relation["rationale"],
            })
        if relation["to"] in selected_set and not any(
            item["concept_id"] == relation["from"] and item["type"] == relation["type"] and item["direction"] == "in"
            for item in neighbors[relation["to"]]
        ):
            neighbors[relation["to"]].append({
                "direction": "in",
                "type": relation["type"],
                "concept_id": relation["from"],
                "label": concepts[relation["from"]]["label"],
                "rationale": relation["rationale"],
            })

    matches = []
    for concept_id in selected:
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
        lexical = concept_id in seeds
        features = feature_map.get(concept_id, {})
        matches.append({
            "concept_id": concept_id,
            "label": concept["label"],
            "score": score_map.get(concept_id, 0),
            "match_type": "lexical" if lexical else "graph_neighbor",
            "matched_terms": sorted(features.get("distinct_hits", [])) if lexical else [],
            "via": [] if lexical else neighbor_candidates.get(concept_id, {}).get("via", []),
            "coverage": concept["coverage"],
            "summary": concept["summary"],
            "evidence": evidence,
            "neighbors": neighbors.get(concept_id, [])[:8],
        })

    return {
        "query": query,
        "query_terms": sorted(query_words),
        "matches": matches,
        "instruction": "Use lexical matches as likely prior concepts and graph-neighbor matches as context. Distinguish reinforcement, refinement, contradiction and genuinely new concepts before drafting a new insight."
    }


def self_test() -> int:
    durable = rank("durable workflow retry", limit=5)
    durable_ids = {item["concept_id"] for item in durable.get("matches", [])}
    expected = {"durable-execution", "idempotency-under-retry"}
    missing = expected - durable_ids
    if missing:
        print(f"graph context self-test failed; missing {sorted(missing)}")
        return 1
    if not any(item.get("neighbors") for item in durable["matches"]):
        print("graph context self-test failed; expected expanded neighbors")
        return 1

    opa = rank(
        "How does OPA separate policy decision-making from enforcement, and what should I learn or try from that architecture?",
        limit=5,
    )
    opa_ids = [item["concept_id"] for item in opa.get("matches", [])]
    if "open-policy-agent" not in opa_ids or "policy-decision-enforcement-separation" not in opa_ids:
        print(f"graph context self-test failed; OPA query missed direct concepts: {opa_ids}")
        return 1
    if "activity-execution" in opa_ids:
        print(f"graph context self-test failed; OPA query retained lexical noise: {opa_ids}")
        return 1
    if not any(item["match_type"] == "graph_neighbor" for item in opa["matches"]):
        print("graph context self-test failed; expected one-hop graph context")
        return 1

    learning = rank(
        "testing retrieval practice immediate performance delayed retention repeated study confidence experiment mental model",
        limit=5,
    )
    learning_ids = [item["concept_id"] for item in learning.get("matches", [])]
    expected_learning = {"retrieval-practice", "performance-retention-gap", "metacognitive-confidence-gap"}
    missing_learning = expected_learning - set(learning_ids)
    if missing_learning:
        print(f"graph context self-test failed; learning query missed concepts {sorted(missing_learning)}: {learning_ids}")
        return 1
    forbidden_learning = {"open-policy-agent", "controlled-execution", "policy-as-code", "observation-grounding"}
    leaked_learning = forbidden_learning & set(learning_ids)
    if leaked_learning:
        print(f"graph context self-test failed; cross-domain noise leaked into learning query: {sorted(leaked_learning)}")
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
    print(f"Query terms: {', '.join(result.get('query_terms', []))}")
    if not result["matches"]:
        print("- no graph matches")
        return 0
    for match in result["matches"]:
        origin = "direct" if match["match_type"] == "lexical" else "via graph"
        print(f"\n[{match['score']}] {match['label']} ({match['coverage']}; {origin})")
        if match.get("matched_terms"):
            print(f"  terms: {', '.join(match['matched_terms'])}")
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
