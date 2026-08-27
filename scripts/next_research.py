#!/usr/bin/env python3
"""Derive a transparent next-research queue from explicit knowledge gaps.

Candidates come from unresolved prerequisites, synthesis gaps, unresolved contradiction/refinement
reviews and low-coverage concepts. Generic graph neighbors are intentionally not used as a feed.
User dispositions live under .local/; generated briefs never invent a source URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import personal_baseline
except ImportError:  # pragma: no cover
    personal_baseline = None

ROOT = Path(__file__).resolve().parents[1]
PREREQUISITES = ROOT / "data" / "prerequisite-maps.json"
SYNTHESES = ROOT / "data" / "syntheses.json"
REVIEWS = ROOT / "data" / "knowledge-reviews.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
INBOX = ROOT / "data" / "inbox.json"
DEFAULT_STORE = ROOT / ".local" / "next-research.json"
VERSION = "1.0.0"
DISPOSITIONS = {"new", "queued", "deferred", "ignored", "closed"}
KINDS = {"learn_prerequisite", "verify_claim", "resolve_contradiction", "update_living_source", "explore_adjacent_leverage"}
UNPROCESSED_STATUSES = {"queued", "researching", "prepared", "mapped"}


class NextResearchError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def empty_store() -> dict:
    return {"version": VERSION, "dispositions": []}


def load_store(path: Path) -> dict:
    if not path.exists():
        return empty_store()
    data = load(path)
    validate_store(data)
    return data


def write_store(path: Path, data: dict) -> None:
    validate_store(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_store(data: dict) -> None:
    if data.get("version") != VERSION:
        raise NextResearchError(f"unsupported next-research store version: {data.get('version')!r}")
    rows = data.get("dispositions")
    if not isinstance(rows, list):
        raise NextResearchError("dispositions must be a list")
    seen: set[str] = set()
    for index, row in enumerate(rows):
        where = f"dispositions[{index}]"
        if not isinstance(row, dict):
            raise NextResearchError(f"{where} must be an object")
        if not isinstance(row.get("candidate_id"), str) or not row["candidate_id"]:
            raise NextResearchError(f"{where}.candidate_id must be non-empty")
        if row["candidate_id"] in seen:
            raise NextResearchError(f"duplicate candidate disposition: {row['candidate_id']}")
        seen.add(row["candidate_id"])
        if row.get("status") not in DISPOSITIONS - {"new"}:
            raise NextResearchError(f"{where}.status invalid")
        if row.get("materially_closed") not in {None, True, False}:
            raise NextResearchError(f"{where}.materially_closed must be null/bool")
        if row.get("status") == "closed" and not row.get("closed_by_intake_id"):
            raise NextResearchError(f"{where}.closed_by_intake_id required when closed")


def tokens(value: str) -> set[str]:
    return {part for part in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", value.casefold()) if len(part) > 2}


def candidate_id(kind: str, source_key: str, statement: str) -> str:
    digest = hashlib.sha1(f"{kind}|{source_key}|{statement}".encode("utf-8")).hexdigest()[:10]
    return f"next-{kind.replace('_', '-')}-{digest}"


def make_candidate(kind: str, source_key: str, statement: str, reason: str, base_score: int, evidence_refs: list[str]) -> dict:
    if kind not in KINDS:
        raise NextResearchError(f"unknown candidate kind: {kind}")
    return {
        "id": candidate_id(kind, source_key, statement),
        "kind": kind,
        "statement": statement.strip(),
        "reason": reason.strip(),
        "base_score": base_score,
        "evidence_refs": evidence_refs,
        "source_key": source_key,
    }


def derive_candidates(prerequisites: dict, syntheses: dict, reviews: dict, graph: dict) -> list[dict]:
    candidates: list[dict] = []

    for record in prerequisites.get("records", []):
        for item in record.get("items", []):
            unresolved = item.get("state") not in {"known_in_graph", "explained_here"}
            if unresolved and item.get("priority") in {"must_know_now", "learn_next"}:
                statement = f"Learn enough about {item.get('label', item.get('concept_id'))} to resolve the prerequisite for {record.get('insight_id')}."
                candidates.append(make_candidate(
                    "learn_prerequisite", item.get("id", record.get("insight_id", "prerequisite")), statement,
                    item.get("reason") or "An explicit prerequisite remains unresolved.",
                    90 if item.get("priority") == "must_know_now" else 80,
                    [item.get("id")],
                ))

    for synthesis in syntheses.get("records", []):
        for gap in synthesis.get("unresolved_gaps", []):
            statement = gap.get("statement") or "Resolve an explicit synthesis gap."
            candidates.append(make_candidate(
                "verify_claim", gap.get("id", synthesis.get("id", "synthesis")), statement,
                f"Unresolved gap in synthesis: {synthesis.get('title', synthesis.get('id', 'unknown'))}",
                100,
                list(gap.get("claim_refs", [])),
            ))

    for review in reviews.get("reviews", []):
        if review.get("status") != "resolved":
            statement = f"Resolve whether {review.get('concept_id')} is truly {review.get('candidate_type', 'changed')} in light of {review.get('trigger_insight_id')}."
            candidates.append(make_candidate(
                "resolve_contradiction", review.get("id", "review"), statement,
                review.get("rationale") or "A contradiction/refinement review remains unresolved.",
                95,
                list(review.get("evidence", {}).get("new_claim_ids", [])) + list(review.get("evidence", {}).get("prior_claim_ids", [])),
            ))

    for concept in graph.get("concepts", []):
        if concept.get("coverage") == "introduced" and len(concept.get("insight_ids", [])) <= 1:
            statement = f"Find independent evidence or a practical source that deepens {concept.get('label', concept.get('id'))}."
            candidates.append(make_candidate(
                "explore_adjacent_leverage", concept.get("id", "concept"), statement,
                "The concept is only introduced and currently depends on a narrow evidence base.",
                55,
                list(concept.get("insight_ids", [])),
            ))

    unique = {item["id"]: item for item in candidates}
    return list(unique.values())


def personal_terms(store_path: Path | None) -> set[str]:
    if personal_baseline is None or store_path is None or not store_path.exists():
        return set()
    data = personal_baseline.load_store(store_path)
    text = " ".join(
        data["active_context"]["goals"] + data["active_context"]["projects"] + data["active_context"]["questions"]
    )
    return tokens(text)


def link_existing_inbox(candidate: dict, inbox: dict) -> dict | None:
    target_terms = tokens(candidate["statement"] + " " + candidate["reason"])
    best = None
    best_score = 0
    for item in inbox.get("items", []):
        if item.get("status") not in UNPROCESSED_STATUSES:
            continue
        text = " ".join([item.get("requested_focus") or "", item.get("notes") or "", item.get("source_url") or ""])
        score = len(target_terms & tokens(text))
        if score > best_score:
            best = item
            best_score = score
    if best is None or best_score < 2:
        return None
    return {"intake_id": best["id"], "source_url": best.get("source_url"), "match_terms": best_score}


def rank_candidates(candidates: list[dict], inbox: dict, personal: set[str]) -> list[dict]:
    ranked = []
    for candidate in candidates:
        overlap = sorted(personal & tokens(candidate["statement"] + " " + candidate["reason"]))
        score = candidate["base_score"] + 8 * len(overlap)
        existing = link_existing_inbox(candidate, inbox)
        item = dict(candidate)
        item["score"] = score
        item["personal_context_matches"] = overlap
        item["existing_inbox"] = existing
        item["research_brief"] = (
            f"Use existing intake {existing['intake_id']} to test whether it closes this target: {candidate['statement']}"
            if existing else
            f"Find a primary, official or otherwise high-quality source that can answer this research target without assuming the conclusion: {candidate['statement']}"
        )
        ranked.append(item)
    ranked.sort(key=lambda item: (-item["score"], item["kind"], item["id"]))
    return ranked


def disposition_map(store: dict) -> dict[str, dict]:
    return {row["candidate_id"]: row for row in store["dispositions"]}


def apply_dispositions(candidates: list[dict], store: dict) -> list[dict]:
    dispositions = disposition_map(store)
    output = []
    for item in candidates:
        row = dispositions.get(item["id"])
        enriched = dict(item)
        enriched["disposition"] = row.get("status") if row else "new"
        enriched["disposition_note"] = row.get("note") if row else None
        enriched["closed_by_intake_id"] = row.get("closed_by_intake_id") if row else None
        enriched["materially_closed"] = row.get("materially_closed") if row else None
        output.append(enriched)
    return output


def set_disposition(store: dict, candidate_id_value: str, status: str, note: str | None, closed_by: str | None, materially_closed: bool | None) -> dict:
    if status not in DISPOSITIONS - {"new"}:
        raise NextResearchError(f"status must be one of {sorted(DISPOSITIONS - {'new'})}")
    if status == "closed" and not closed_by:
        raise NextResearchError("--closed-by-intake is required for closed status")
    rows = disposition_map(store)
    row = rows.get(candidate_id_value)
    if row is None:
        row = {"candidate_id": candidate_id_value}
        store["dispositions"].append(row)
    row.update({
        "status": status,
        "note": note or None,
        "closed_by_intake_id": closed_by if status == "closed" else None,
        "materially_closed": materially_closed if status == "closed" else None,
        "updated_at": now_iso(),
    })
    validate_store(store)
    return row


def load_ranked(personal_store: Path | None = None) -> list[dict]:
    candidates = derive_candidates(load(PREREQUISITES), load(SYNTHESES), load(REVIEWS), load(GRAPH))
    return rank_candidates(candidates, load(INBOX), personal_terms(personal_store))


def self_test() -> int:
    prereq = {"records": [{"insight_id": "i1", "items": [{"id": "p1", "label": "X", "priority": "learn_next", "state": "unresolved", "reason": "Needed for workflow retry"}]}]}
    synth = {"records": [{"id": "s1", "title": "S", "unresolved_gaps": [{"id": "g1", "statement": "Does workflow retry preserve external correctness?", "claim_refs": ["c1"]}]}]}
    reviews = {"reviews": []}
    graph = {"concepts": [{"id": "c-low", "label": "Low coverage", "coverage": "introduced", "insight_ids": ["i1"]}]}
    inbox = {"items": [{"id": "intake-1", "status": "queued", "source_url": "https://example.com", "requested_focus": "workflow retry external correctness", "notes": ""}]}
    candidates = derive_candidates(prereq, synth, reviews, graph)
    ranked = rank_candidates(candidates, inbox, {"workflow", "retry"})
    if ranked[0]["kind"] != "verify_claim" or ranked[0]["existing_inbox"] is None:
        print("next research self-test failed: ranking/inbox matching")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        store = load_store(path)
        set_disposition(store, ranked[0]["id"], "queued", "test", None, None)
        write_store(path, store)
        if apply_dispositions(ranked, load_store(path))[0]["disposition"] != "queued":
            print("next research self-test failed: disposition persistence")
            return 1
    print("next research self-test passed; explicit gaps, transparent ranking, inbox reuse and dispositions work.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--personal-store", type=Path, default=(personal_baseline.DEFAULT_STORE if personal_baseline else None))
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show")
    show.add_argument("--limit", type=int, default=20)
    show.add_argument("--include-ignored", action="store_true")
    show.add_argument("--json", action="store_true")

    set_cmd = sub.add_parser("set")
    set_cmd.add_argument("--candidate", required=True)
    set_cmd.add_argument("--status", choices=sorted(DISPOSITIONS - {"new"}), required=True)
    set_cmd.add_argument("--note")
    set_cmd.add_argument("--closed-by-intake")
    closure = set_cmd.add_mutually_exclusive_group()
    closure.add_argument("--materially-closed", action="store_true")
    closure.add_argument("--not-materially-closed", action="store_true")

    sub.add_parser("self-test")
    args = parser.parse_args()
    try:
        if args.command == "self-test":
            return self_test()
        store = load_store(args.store)
        if args.command == "set":
            closure_value = True if args.materially_closed else False if args.not_materially_closed else None
            row = set_disposition(store, args.candidate, args.status, args.note, args.closed_by_intake, closure_value)
            write_store(args.store, store)
            print(json.dumps(row, ensure_ascii=False, indent=2))
        else:
            candidates = apply_dispositions(load_ranked(args.personal_store), store)
            if not args.include_ignored:
                candidates = [item for item in candidates if item["disposition"] not in {"ignored", "closed"}]
            candidates = candidates[: max(args.limit, 0)]
            if args.json:
                print(json.dumps({"candidates": candidates}, ensure_ascii=False, indent=2))
            else:
                for item in candidates:
                    print(f"{item['id']} [{item['kind']}] score={item['score']} status={item['disposition']}")
                    print(f"  target: {item['statement']}")
                    print(f"  why: {item['reason']}")
                    print(f"  next: {item['research_brief']}")
                    if item["personal_context_matches"]:
                        print("  context matches: " + ", ".join(item["personal_context_matches"]))
    except (NextResearchError, json.JSONDecodeError, ValueError) as exc:
        print(f"next research error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
