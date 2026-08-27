#!/usr/bin/env python3
"""Derive transparent next-research targets from explicit gaps, unresolved synthesis and review needs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREQS = ROOT / "data" / "prerequisite-maps.json"
SYNTHESES = ROOT / "data" / "syntheses.json"
REVIEWS = ROOT / "data" / "knowledge-reviews.json"
INBOX = ROOT / "data" / "inbox.json"
DEFAULT_DECISIONS = ROOT / ".local" / "next-research-decisions.json"
VERSION = "1.0.0"


def load(path: Path, default: dict | None = None) -> dict:
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: str) -> set[str]:
    return {token.strip(".,:;()[]{}!?\"'").lower() for token in text.split() if len(token.strip(".,:;()[]{}!?\"'")) > 3}


def inbox_match(question: str) -> str | None:
    q = normalize(question)
    if not q:
        return None
    best: tuple[int, str] | None = None
    for item in load(INBOX).get("items", []):
        if item.get("status") not in {"queued", "researching"}:
            continue
        hay = " ".join(filter(None, [item.get("requested_focus"), item.get("notes"), item.get("source_url")]))
        score = len(q & normalize(hay))
        if score and (best is None or score > best[0]):
            best = (score, item["id"])
    return best[1] if best else None


def candidates() -> list[dict]:
    result: list[dict] = []
    for record in load(PREREQS).get("records", []):
        for item in record.get("items", []):
            if item.get("state") != "gap":
                continue
            priority = item.get("priority")
            question = f"What do I need to understand about {item.get('label')} to close the prerequisite gap for {record.get('insight_id')}?"
            result.append({
                "id": f"prereq:{item.get('id')}",
                "kind": "learn_prerequisite",
                "priority": 100 if priority == "must_know_now" else 70 if priority == "learn_next" else 40,
                "target": item.get("label"),
                "reason": item.get("reason"),
                "question": question,
                "origin": {"insight_id": record.get("insight_id"), "item_id": item.get("id")},
            })
    for synthesis in load(SYNTHESES).get("records", []):
        for gap in synthesis.get("unresolved_gaps", []):
            statement = gap.get("statement") or ""
            result.append({
                "id": f"synthesis:{synthesis.get('id')}:{gap.get('id')}",
                "kind": "verify_claim",
                "priority": 80,
                "target": synthesis.get("question"),
                "reason": statement,
                "question": f"What evidence would resolve this synthesis gap: {statement}",
                "origin": {"synthesis_id": synthesis.get("id"), "gap_id": gap.get("id")},
            })
    for review in load(REVIEWS).get("reviews", []):
        if review.get("status") == "resolved" and review.get("resolution") != "needs_more_evidence":
            continue
        if review.get("resolution") == "needs_more_evidence" or review.get("status") != "resolved":
            result.append({
                "id": f"review:{review.get('id')}",
                "kind": "resolve_contradiction",
                "priority": 90,
                "target": review.get("concept_id"),
                "reason": review.get("rationale") or "Knowledge review requires more evidence.",
                "question": f"What evidence resolves the open knowledge review for {review.get('concept_id')} without confusing scope or layer?",
                "origin": {"review_id": review.get("id")},
            })
    for item in result:
        item["existing_inbox_id"] = inbox_match(item["question"])
    result.sort(key=lambda x: (-x["priority"], x["kind"], x["id"]))
    return result


def apply_decisions(items: list[dict], decisions_path: Path) -> list[dict]:
    decisions = load(decisions_path, {"version": VERSION, "decisions": {}})
    mapped = decisions.get("decisions", {})
    output = []
    for item in items:
        decision = mapped.get(item["id"], {})
        item = dict(item)
        item["decision"] = decision.get("decision", "open")
        item["decision_note"] = decision.get("note")
        if item["decision"] != "ignored":
            output.append(item)
    return output


def self_test() -> int:
    items = candidates()
    # The current corpus may have no prerequisite gaps, but the synthesis has unresolved gaps.
    if not any(item["kind"] == "verify_claim" for item in items):
        print("next_research self-test failed: expected unresolved synthesis target")
        return 1
    if any(not item.get("question") or not item.get("reason") for item in items):
        print("next_research self-test failed: incomplete candidate")
        return 1
    print(f"next_research self-test passed; derived {len(items)} transparent next-research targets.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    items = apply_decisions(candidates(), args.decisions)
    if args.json:
        print(json.dumps({"version": VERSION, "targets": items}, ensure_ascii=False, indent=2))
    else:
        if not items:
            print("No unresolved next-research targets.")
        for index, item in enumerate(items, 1):
            existing = f" [inbox {item['existing_inbox_id']}]" if item.get("existing_inbox_id") else ""
            print(f"{index}. [{item['kind']}] {item['question']}{existing}")
            print(f"   reason: {item['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
