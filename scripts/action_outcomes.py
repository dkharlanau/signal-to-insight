#!/usr/bin/env python3
"""Track private insight -> action -> outcome evidence without turning the project into a task manager."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / ".local" / "action-outcomes.json"
INSIGHTS = ROOT / "data" / "insights.json"
VERSION = "1.0.0"
STATUSES = {"planned", "tried", "adopted", "rejected", "inconclusive", "superseded"}


class OutcomeError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path, default: dict | None = None) -> dict:
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def known_insights() -> set[str]:
    data = load(INSIGHTS)
    return {item["id"] for item in data.get("insights", []) if item.get("id")}


def validate(store: dict) -> None:
    if store.get("version") != VERSION or not isinstance(store.get("records"), list):
        raise OutcomeError("unsupported or invalid action-outcome store")
    seen: set[str] = set()
    for item in store["records"]:
        required = {"id", "insight_id", "action", "hypothesis", "status", "created_at", "updated_at"}
        if required - set(item):
            raise OutcomeError(f"missing fields in {item.get('id')!r}: {sorted(required-set(item))}")
        if item["id"] in seen:
            raise OutcomeError(f"duplicate record id: {item['id']}")
        seen.add(item["id"])
        if item["status"] not in STATUSES:
            raise OutcomeError(f"invalid status: {item['status']}")
        if not isinstance(item.get("concept_ids", []), list):
            raise OutcomeError("concept_ids must be a list")
        if item.get("supersedes") == item["id"]:
            raise OutcomeError("record cannot supersede itself")


def load_store(path: Path) -> dict:
    store = load(path, {"version": VERSION, "records": []})
    validate(store)
    return store


def create_record(path: Path, insight_id: str, action: str, hypothesis: str, intended_outcome: str | None,
                  concept_ids: list[str], review_at: str | None, record_id: str | None = None) -> dict:
    if insight_id not in known_insights():
        raise OutcomeError(f"unknown insight: {insight_id}")
    stamp = now()
    item = {
        "id": record_id or f"outcome-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}",
        "insight_id": insight_id,
        "concept_ids": concept_ids,
        "action": action.strip(),
        "hypothesis": hypothesis.strip(),
        "intended_outcome": intended_outcome.strip() if intended_outcome else None,
        "review_at": review_at,
        "status": "planned",
        "result": None,
        "supersedes": None,
        "created_at": stamp,
        "updated_at": stamp,
    }
    if not item["action"] or not item["hypothesis"]:
        raise OutcomeError("action and hypothesis are required")
    store = load_store(path)
    if any(record["id"] == item["id"] for record in store["records"]):
        raise OutcomeError(f"record already exists: {item['id']}")
    store["records"].append(item)
    validate(store)
    save(path, store)
    return item


def update_record(path: Path, record_id: str, status: str, result: str | None, supersedes: str | None) -> dict:
    if status not in STATUSES - {"planned"}:
        raise OutcomeError("completion status must be tried/adopted/rejected/inconclusive/superseded")
    store = load_store(path)
    item = next((r for r in store["records"] if r["id"] == record_id), None)
    if item is None:
        raise OutcomeError(f"record not found: {record_id}")
    if supersedes and not any(r["id"] == supersedes for r in store["records"]):
        raise OutcomeError(f"superseded record not found: {supersedes}")
    item["status"] = status
    item["result"] = result.strip() if result else None
    item["supersedes"] = supersedes
    item["updated_at"] = now()
    validate(store)
    save(path, store)
    return item


def report(store: dict) -> dict:
    validate(store)
    statuses = Counter(item["status"] for item in store["records"])
    return {
        "records": len(store["records"]),
        "statuses": dict(sorted(statuses.items())),
        "adoption_rate": round(statuses["adopted"] / len(store["records"]), 3) if store["records"] else None,
        "resolved": sum(statuses[s] for s in ("adopted", "rejected", "inconclusive", "superseded")),
    }


def self_test() -> int:
    insight = next(iter(sorted(known_insights())), None)
    if not insight:
        print("action_outcomes self-test requires an insight")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "outcomes.json"
        item = create_record(path, insight, "Run a bounded experiment", "The model improves one concrete workflow", "Less manual rework", ["controlled-execution"], None, "fixture-1")
        update_record(path, item["id"], "adopted", "The bounded experiment reduced rework", None)
        result = report(load_store(path))
        if result["records"] != 1 or result["statuses"].get("adopted") != 1:
            print("action_outcomes self-test failed")
            return 1
    print("action_outcomes self-test passed; private action-to-outcome evidence works.")
    return 0


def split(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(";") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("--insight", required=True)
    add.add_argument("--action", required=True)
    add.add_argument("--hypothesis", required=True)
    add.add_argument("--intended-outcome")
    add.add_argument("--concepts", default="")
    add.add_argument("--review-at")
    finish = sub.add_parser("finish")
    finish.add_argument("--id", required=True)
    finish.add_argument("--status", choices=sorted(STATUSES - {"planned"}), required=True)
    finish.add_argument("--result")
    finish.add_argument("--supersedes")
    rep = sub.add_parser("report")
    rep.add_argument("--json", action="store_true")
    sub.add_parser("self-test")
    args = parser.parse_args()
    try:
        if args.command == "add":
            print(json.dumps(create_record(args.store, args.insight, args.action, args.hypothesis, args.intended_outcome, split(args.concepts), args.review_at), ensure_ascii=False, indent=2))
        elif args.command == "finish":
            print(json.dumps(update_record(args.store, args.id, args.status, args.result, args.supersedes), ensure_ascii=False, indent=2))
        elif args.command == "report":
            value = report(load_store(args.store))
            print(json.dumps(value, ensure_ascii=False, indent=2) if args.json else f"Records: {value['records']}\nStatuses: {value['statuses']}\nAdoption rate: {value['adoption_rate']}")
        else:
            return self_test()
    except (OutcomeError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
