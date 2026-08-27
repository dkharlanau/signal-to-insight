#!/usr/bin/env python3
"""Track private insight → action → outcome evidence.

Personal outcomes are useful future context, but they are not external/source evidence and are
never written to public knowledge records. The default store lives under .local/.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / ".local" / "action-outcomes.json"
INSIGHTS = ROOT / "data" / "insights.json"
VERSION = "1.0.0"
STATUSES = {"planned", "tried", "adopted", "rejected", "inconclusive", "superseded"}
ACTION_BUCKETS = {"use_now", "try", "learn", "build", "watch", "ignore_for_now"}
FINAL_STATUSES = {"adopted", "rejected", "inconclusive", "superseded"}


class OutcomeError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def empty_store() -> dict:
    return {"version": VERSION, "records": []}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_store(path: Path) -> dict:
    if not path.exists():
        return empty_store()
    data = load_json(path)
    validate_store(data)
    return data


def write_store(path: Path, data: dict) -> None:
    validate_store(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def known_insights() -> set[str]:
    data = load_json(INSIGHTS)
    return {item.get("id") for item in data.get("insights", []) if item.get("id")}


def validate_iso(value: str | None, field: str) -> None:
    if value is None:
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise OutcomeError(f"{field} must be null or ISO date/datetime") from exc


def validate_store(data: dict) -> None:
    if data.get("version") != VERSION:
        raise OutcomeError(f"unsupported outcome store version: {data.get('version')!r}")
    records = data.get("records")
    if not isinstance(records, list):
        raise OutcomeError("records must be a list")
    seen: set[str] = set()
    for index, item in enumerate(records):
        where = f"records[{index}]"
        required = {
            "id", "insight_id", "concept_ids", "action_bucket", "hypothesis", "intended_outcome",
            "status", "review_at", "result_summary", "created_at", "updated_at", "history"
        }
        if not isinstance(item, dict):
            raise OutcomeError(f"{where} must be an object")
        missing = required - set(item)
        if missing:
            raise OutcomeError(f"{where} missing fields: {sorted(missing)}")
        if not isinstance(item["id"], str) or not item["id"].strip():
            raise OutcomeError(f"{where}.id must be non-empty")
        if item["id"] in seen:
            raise OutcomeError(f"duplicate outcome id: {item['id']}")
        seen.add(item["id"])
        if not isinstance(item["insight_id"], str) or not item["insight_id"].strip():
            raise OutcomeError(f"{where}.insight_id must be non-empty")
        concepts = item["concept_ids"]
        if not isinstance(concepts, list) or not all(isinstance(value, str) and value.strip() for value in concepts):
            raise OutcomeError(f"{where}.concept_ids must be a list of non-empty strings")
        if item["action_bucket"] not in ACTION_BUCKETS:
            raise OutcomeError(f"{where}.action_bucket invalid")
        for field in ("hypothesis", "intended_outcome"):
            if not isinstance(item[field], str) or not item[field].strip():
                raise OutcomeError(f"{where}.{field} must be non-empty")
        if item["status"] not in STATUSES:
            raise OutcomeError(f"{where}.status invalid")
        if item["status"] in FINAL_STATUSES and not (isinstance(item["result_summary"], str) and item["result_summary"].strip()):
            raise OutcomeError(f"{where}.result_summary required for final status")
        if item["result_summary"] is not None and not isinstance(item["result_summary"], str):
            raise OutcomeError(f"{where}.result_summary must be null or string")
        validate_iso(item["review_at"], f"{where}.review_at")
        validate_iso(item["created_at"], f"{where}.created_at")
        validate_iso(item["updated_at"], f"{where}.updated_at")
        if not isinstance(item["history"], list):
            raise OutcomeError(f"{where}.history must be a list")


def make_id(insight_id: str, store: dict) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", insight_id.lower()).strip("-")[:48] or "outcome"
    existing = {item["id"] for item in store["records"]}
    candidate = f"action-{stem}"
    index = 2
    while candidate in existing:
        candidate = f"action-{stem}-{index}"
        index += 1
    return candidate


def start_record(
    store: dict,
    insight_id: str,
    action_bucket: str,
    hypothesis: str,
    intended_outcome: str,
    concept_ids: list[str],
    review_at: str | None,
    record_id: str | None = None,
) -> dict:
    if insight_id not in known_insights():
        raise OutcomeError(f"unknown insight: {insight_id}")
    if action_bucket not in ACTION_BUCKETS:
        raise OutcomeError(f"action bucket must be one of {sorted(ACTION_BUCKETS)}")
    timestamp = now_iso()
    item = {
        "id": record_id or make_id(insight_id, store),
        "insight_id": insight_id,
        "concept_ids": sorted({value.strip() for value in concept_ids if value.strip()}),
        "action_bucket": action_bucket,
        "hypothesis": hypothesis.strip(),
        "intended_outcome": intended_outcome.strip(),
        "status": "planned",
        "review_at": review_at,
        "result_summary": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "history": [{"at": timestamp, "status": "planned", "note": "Action created from an insight recommendation."}],
        "privacy": "private_personal_experience_not_source_evidence",
    }
    if any(existing["id"] == item["id"] for existing in store["records"]):
        raise OutcomeError(f"outcome id already exists: {item['id']}")
    store["records"].append(item)
    validate_store(store)
    return item


def update_record(store: dict, record_id: str, status: str, result: str | None, note: str | None = None) -> dict:
    if status not in STATUSES:
        raise OutcomeError(f"status must be one of {sorted(STATUSES)}")
    item = next((record for record in store["records"] if record["id"] == record_id), None)
    if item is None:
        raise OutcomeError(f"outcome not found: {record_id}")
    if status in FINAL_STATUSES and not (result and result.strip()):
        raise OutcomeError("final outcome status requires --result")
    timestamp = now_iso()
    item["status"] = status
    if result is not None:
        item["result_summary"] = result.strip() or None
    item["updated_at"] = timestamp
    item["history"].append({"at": timestamp, "status": status, "note": note or item["result_summary"]})
    validate_store(store)
    return item


def tokens(value: str) -> set[str]:
    return {part for part in re.findall(r"[a-z0-9][a-z0-9_-]{1,}", value.casefold()) if len(part) > 2}


def select_context(store: dict, query: str, limit: int = 8) -> list[dict]:
    query_terms = tokens(query)
    ranked: list[tuple[int, str, dict]] = []
    for item in store["records"]:
        text = " ".join([
            item["insight_id"], " ".join(item["concept_ids"]), item["hypothesis"],
            item["intended_outcome"], item.get("result_summary") or ""
        ])
        overlap = query_terms & tokens(text)
        score = 10 * len(overlap)
        if item["status"] in {"adopted", "rejected"}:
            score += 3
        elif item["status"] == "inconclusive":
            score += 1
        if overlap or not query_terms:
            ranked.append((score, item["updated_at"], item))
    ranked.sort(key=lambda row: (-row[0], row[1], row[2]["id"]), reverse=False)
    return [item for _, _, item in ranked[: max(limit, 0)]]


def summarize(store: dict) -> dict:
    validate_store(store)
    statuses = Counter(item["status"] for item in store["records"])
    by_insight = Counter(item["insight_id"] for item in store["records"])
    return {
        "records": len(store["records"]),
        "statuses": dict(sorted(statuses.items())),
        "insights_with_outcomes": len(by_insight),
        "adoption_rate_among_resolved": (
            round(statuses["adopted"] / sum(statuses[name] for name in FINAL_STATUSES), 3)
            if sum(statuses[name] for name in FINAL_STATUSES) else None
        ),
    }


def self_test() -> int:
    insight_id = next(iter(sorted(known_insights())), None)
    if not insight_id:
        print("action outcomes self-test requires an insight")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "outcomes.json"
        store = load_store(path)
        item = start_record(store, insight_id, "try", "A smaller control boundary reduces rework", "Observe fewer unsafe retries", ["controlled-execution"], None, "fixture")
        update_record(store, item["id"], "adopted", "The pattern was useful in the test case.")
        write_store(path, store)
        restored = load_store(path)
        if restored["records"][0]["status"] != "adopted":
            print("action outcomes self-test failed: status update")
            return 1
        context = select_context(restored, "control retry", 3)
        if not context or context[0]["id"] != "fixture":
            print("action outcomes self-test failed: context selection")
            return 1
        if summarize(restored)["adoption_rate_among_resolved"] != 1.0:
            print("action outcomes self-test failed: aggregate")
            return 1
    print("action outcomes self-test passed; private experiment lifecycle and future-context retrieval work.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--insight", required=True)
    start.add_argument("--action", choices=sorted(ACTION_BUCKETS), required=True)
    start.add_argument("--hypothesis", required=True)
    start.add_argument("--outcome", required=True)
    start.add_argument("--concepts", default="", help="Semicolon-separated concept IDs")
    start.add_argument("--review-at")
    start.add_argument("--id")

    update = sub.add_parser("update")
    update.add_argument("--id", required=True)
    update.add_argument("--status", choices=sorted(STATUSES), required=True)
    update.add_argument("--result")
    update.add_argument("--note")

    context = sub.add_parser("context")
    context.add_argument("--query", default="")
    context.add_argument("--limit", type=int, default=8)

    report = sub.add_parser("report")
    report.add_argument("--json", action="store_true")
    sub.add_parser("self-test")

    args = parser.parse_args()
    try:
        if args.command == "self-test":
            return self_test()
        store = load_store(args.store)
        if args.command == "start":
            item = start_record(store, args.insight, args.action, args.hypothesis, args.outcome, [part.strip() for part in args.concepts.split(";") if part.strip()], args.review_at, args.id)
            write_store(args.store, store)
            print(json.dumps(item, ensure_ascii=False, indent=2))
        elif args.command == "update":
            item = update_record(store, args.id, args.status, args.result, args.note)
            write_store(args.store, store)
            print(json.dumps(item, ensure_ascii=False, indent=2))
        elif args.command == "context":
            print(json.dumps({"privacy": "private_personal_experience_not_source_evidence", "records": select_context(store, args.query, args.limit)}, ensure_ascii=False, indent=2))
        else:
            report_data = summarize(store)
            if args.json:
                print(json.dumps(report_data, ensure_ascii=False, indent=2))
            else:
                print(f"Records: {report_data['records']}")
                print("Statuses: " + json.dumps(report_data["statuses"], sort_keys=True))
                print(f"Insights with outcomes: {report_data['insights_with_outcomes']}")
                print(f"Adoption rate among resolved: {report_data['adoption_rate_among_resolved'] if report_data['adoption_rate_among_resolved'] is not None else 'n/a'}")
    except (OutcomeError, json.JSONDecodeError) as exc:
        print(f"action outcome error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
