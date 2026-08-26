#!/usr/bin/env python3
"""Record and summarize local-first learning utility evidence.

The default store is .local/learning-utility.json, which is intentionally gitignored.
No free-text reconstruction answer is stored: delayed reviews record only model-piece labels
that were recalled or missed.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / ".local" / "learning-utility.json"
INSIGHTS = ROOT / "data" / "insights.json"
VERSION = "1.0.0"
IMMEDIATE = {"yes", "partial", "no"}
DECISIONS = {"use_now", "try", "learn", "build", "watch", "ignore_for_now"}
RECONSTRUCTION = {"complete", "partial", "failed"}
TRANSFER = {"applied", "partial", "failed", "not_tested"}


class LearningUtilityError(ValueError):
    pass


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_store(path: Path) -> dict:
    if not path.exists():
        return {"version": VERSION, "records": []}
    data = load_json(path)
    validate_store(data)
    return data


def write_store(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_store(data: dict) -> None:
    if data.get("version") != VERSION:
        raise LearningUtilityError(f"unsupported store version: {data.get('version')!r}")
    records = data.get("records")
    if not isinstance(records, list):
        raise LearningUtilityError("records must be a list")

    seen: set[str] = set()
    for index, record in enumerate(records):
        where = f"records[{index}]"
        if not isinstance(record, dict):
            raise LearningUtilityError(f"{where} must be an object")
        required = {
            "id",
            "insight_id",
            "recorded_at",
            "source_minutes_estimate",
            "explainer_minutes",
            "immediate_model",
            "decision",
            "delayed",
            "transfer",
        }
        missing = required - set(record)
        if missing:
            raise LearningUtilityError(f"{where} missing fields: {sorted(missing)}")
        record_id = record["id"]
        if not isinstance(record_id, str) or not record_id:
            raise LearningUtilityError(f"{where}.id must be a non-empty string")
        if record_id in seen:
            raise LearningUtilityError(f"duplicate record id: {record_id}")
        seen.add(record_id)
        if not isinstance(record["insight_id"], str) or not record["insight_id"]:
            raise LearningUtilityError(f"{where}.insight_id must be a non-empty string")
        try:
            datetime.fromisoformat(record["recorded_at"].replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            raise LearningUtilityError(f"{where}.recorded_at must be ISO datetime")
        for field in ("source_minutes_estimate", "explainer_minutes"):
            value = record[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise LearningUtilityError(f"{where}.{field} must be > 0")
        if record["immediate_model"] not in IMMEDIATE:
            raise LearningUtilityError(f"{where}.immediate_model invalid")
        if record["decision"] not in DECISIONS:
            raise LearningUtilityError(f"{where}.decision invalid")
        if record["transfer"] not in TRANSFER:
            raise LearningUtilityError(f"{where}.transfer invalid")

        delayed = record["delayed"]
        if delayed is not None:
            if not isinstance(delayed, dict):
                raise LearningUtilityError(f"{where}.delayed must be null or object")
            if delayed.get("reconstruction") not in RECONSTRUCTION:
                raise LearningUtilityError(f"{where}.delayed.reconstruction invalid")
            days = delayed.get("delay_days")
            if isinstance(days, bool) or not isinstance(days, (int, float)) or days < 0:
                raise LearningUtilityError(f"{where}.delayed.delay_days must be >= 0")
            for field in ("recalled_pieces", "missed_pieces"):
                values = delayed.get(field)
                if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
                    raise LearningUtilityError(f"{where}.delayed.{field} must be a list of non-empty labels")
            overlap = set(delayed["recalled_pieces"]) & set(delayed["missed_pieces"])
            if overlap:
                raise LearningUtilityError(f"{where}.delayed has recalled/missed overlap: {sorted(overlap)}")


def known_insights() -> set[str]:
    data = load_json(INSIGHTS)
    return {item.get("id") for item in data.get("insights", []) if item.get("id")}


def make_record_id(insight_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{insight_id}-{stamp}"


def record_immediate(
    store_path: Path,
    insight_id: str,
    source_minutes: float,
    explainer_minutes: float,
    immediate_model: str,
    decision: str,
    note: str | None = None,
    record_id: str | None = None,
) -> dict:
    if insight_id not in known_insights():
        raise LearningUtilityError(f"unknown insight: {insight_id}")
    if source_minutes <= 0 or explainer_minutes <= 0:
        raise LearningUtilityError("source/explainer minutes must be > 0")
    if immediate_model not in IMMEDIATE:
        raise LearningUtilityError(f"immediate_model must be one of {sorted(IMMEDIATE)}")
    if decision not in DECISIONS:
        raise LearningUtilityError(f"decision must be one of {sorted(DECISIONS)}")

    store = load_store(store_path)
    item = {
        "id": record_id or make_record_id(insight_id),
        "insight_id": insight_id,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_minutes_estimate": float(source_minutes),
        "explainer_minutes": float(explainer_minutes),
        "immediate_model": immediate_model,
        "decision": decision,
        "delayed": None,
        "transfer": "not_tested",
        "note": note or None,
    }
    if any(existing.get("id") == item["id"] for existing in store["records"]):
        raise LearningUtilityError(f"record id already exists: {item['id']}")
    store["records"].append(item)
    validate_store(store)
    write_store(store_path, store)
    return item


def split_labels(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(";") if item.strip()]


def record_delayed(
    store_path: Path,
    record_id: str,
    delay_days: float,
    reconstruction: str,
    recalled: list[str],
    missed: list[str],
    transfer: str,
) -> dict:
    if delay_days < 0:
        raise LearningUtilityError("delay_days must be >= 0")
    if reconstruction not in RECONSTRUCTION:
        raise LearningUtilityError(f"reconstruction must be one of {sorted(RECONSTRUCTION)}")
    if transfer not in TRANSFER:
        raise LearningUtilityError(f"transfer must be one of {sorted(TRANSFER)}")
    overlap = set(recalled) & set(missed)
    if overlap:
        raise LearningUtilityError(f"same model piece cannot be recalled and missed: {sorted(overlap)}")

    store = load_store(store_path)
    item = next((record for record in store["records"] if record.get("id") == record_id), None)
    if item is None:
        raise LearningUtilityError(f"record not found: {record_id}")
    item["delayed"] = {
        "delay_days": float(delay_days),
        "reconstruction": reconstruction,
        "recalled_pieces": recalled,
        "missed_pieces": missed,
    }
    item["transfer"] = transfer
    validate_store(store)
    write_store(store_path, store)
    return item


def summarize(store: dict) -> dict:
    validate_store(store)
    records = store["records"]
    if not records:
        return {
            "attempts": 0,
            "source_minutes": 0.0,
            "explainer_minutes": 0.0,
            "estimated_minutes_saved": 0.0,
            "compression_ratio": None,
            "immediate_can_explain_rate": None,
            "delayed_attempts": 0,
            "delayed_complete_rate": None,
            "transfer_attempts": 0,
            "transfer_applied_rate": None,
            "decisions": {},
            "most_missed_model_pieces": [],
        }

    source_minutes = sum(item["source_minutes_estimate"] for item in records)
    explainer_minutes = sum(item["explainer_minutes"] for item in records)
    delayed = [item for item in records if item["delayed"] is not None]
    transfer = [item for item in records if item["transfer"] != "not_tested"]
    missed = Counter(
        label
        for item in delayed
        for label in item["delayed"]["missed_pieces"]
    )
    decisions = Counter(item["decision"] for item in records)

    return {
        "attempts": len(records),
        "source_minutes": round(source_minutes, 2),
        "explainer_minutes": round(explainer_minutes, 2),
        "estimated_minutes_saved": round(source_minutes - explainer_minutes, 2),
        "compression_ratio": round(source_minutes / explainer_minutes, 2) if explainer_minutes else None,
        "immediate_can_explain_rate": round(sum(item["immediate_model"] == "yes" for item in records) / len(records), 3),
        "delayed_attempts": len(delayed),
        "delayed_complete_rate": round(sum(item["delayed"]["reconstruction"] == "complete" for item in delayed) / len(delayed), 3) if delayed else None,
        "transfer_attempts": len(transfer),
        "transfer_applied_rate": round(sum(item["transfer"] == "applied" for item in transfer) / len(transfer), 3) if transfer else None,
        "decisions": dict(sorted(decisions.items())),
        "most_missed_model_pieces": [
            {"piece": label, "count": count}
            for label, count in missed.most_common(10)
        ],
    }


def print_report(report: dict) -> None:
    print(f"Attempts: {report['attempts']}")
    print(f"Source minutes (estimated): {report['source_minutes']}")
    print(f"Explainer minutes: {report['explainer_minutes']}")
    print(f"Estimated minutes saved: {report['estimated_minutes_saved']}")
    print(f"Compression ratio: {report['compression_ratio'] if report['compression_ratio'] is not None else 'n/a'}")
    print(f"Immediate can-explain rate: {report['immediate_can_explain_rate'] if report['immediate_can_explain_rate'] is not None else 'n/a'}")
    print(f"Delayed attempts: {report['delayed_attempts']}")
    print(f"Delayed complete rate: {report['delayed_complete_rate'] if report['delayed_complete_rate'] is not None else 'n/a'}")
    print(f"Transfer attempts: {report['transfer_attempts']}")
    print(f"Transfer applied rate: {report['transfer_applied_rate'] if report['transfer_applied_rate'] is not None else 'n/a'}")
    print("Decisions: " + (json.dumps(report["decisions"], sort_keys=True) if report["decisions"] else "{}"))
    if report["most_missed_model_pieces"]:
        print("Most missed model pieces:")
        for item in report["most_missed_model_pieces"]:
            print(f"- {item['piece']}: {item['count']}")


def self_test() -> int:
    insight = next(iter(sorted(known_insights())), None)
    if insight is None:
        print("Learning utility self-test requires at least one insight.")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "learning-utility.json"
        first = record_immediate(
            path,
            insight,
            source_minutes=30,
            explainer_minutes=6,
            immediate_model="yes",
            decision="learn",
            record_id="self-test-1",
        )
        record_delayed(
            path,
            first["id"],
            delay_days=2,
            reconstruction="partial",
            recalled=["problem", "mechanism"],
            missed=["boundary"],
            transfer="partial",
        )
        record_immediate(
            path,
            insight,
            source_minutes=20,
            explainer_minutes=5,
            immediate_model="partial",
            decision="try",
            record_id="self-test-2",
        )
        store = load_store(path)
        report = summarize(store)
        expected = {
            "attempts": 2,
            "estimated_minutes_saved": 39.0,
            "delayed_attempts": 1,
            "transfer_attempts": 1,
        }
        for key, value in expected.items():
            if report.get(key) != value:
                print(f"Learning utility self-test failed: {key}={report.get(key)!r}, expected {value!r}")
                return 1
        if report["most_missed_model_pieces"] != [{"piece": "boundary", "count": 1}]:
            print("Learning utility self-test failed: missed-piece aggregation is wrong.")
            return 1

    print("Learning utility self-test passed; local store, delayed update and aggregate report work.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE, help="Local JSON store (default: .local/learning-utility.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    immediate = sub.add_parser("record", help="Record immediate comprehension/time evidence")
    immediate.add_argument("--insight", required=True)
    immediate.add_argument("--source-minutes", type=float, required=True)
    immediate.add_argument("--explainer-minutes", type=float, required=True)
    immediate.add_argument("--immediate", choices=sorted(IMMEDIATE), required=True)
    immediate.add_argument("--decision", choices=sorted(DECISIONS), required=True)
    immediate.add_argument("--note")
    immediate.add_argument("--record-id")

    delayed = sub.add_parser("delayed", help="Attach delayed reconstruction/transfer result to an existing local record")
    delayed.add_argument("--record-id", required=True)
    delayed.add_argument("--days", type=float, required=True)
    delayed.add_argument("--reconstruction", choices=sorted(RECONSTRUCTION), required=True)
    delayed.add_argument("--recalled", default="", help="Semicolon-separated model-piece labels, not the free-text answer")
    delayed.add_argument("--missed", default="", help="Semicolon-separated model-piece labels, not the free-text answer")
    delayed.add_argument("--transfer", choices=sorted(TRANSFER), default="not_tested")

    report = sub.add_parser("report", help="Aggregate local utility evidence")
    report.add_argument("--json", action="store_true")

    sub.add_parser("self-test", help="Run an isolated fixture-driven self-test")

    args = parser.parse_args()
    try:
        if args.command == "record":
            item = record_immediate(
                args.store,
                args.insight,
                args.source_minutes,
                args.explainer_minutes,
                args.immediate,
                args.decision,
                note=args.note,
                record_id=args.record_id,
            )
            print(item["id"])
            return 0
        if args.command == "delayed":
            record_delayed(
                args.store,
                args.record_id,
                args.days,
                args.reconstruction,
                split_labels(args.recalled),
                split_labels(args.missed),
                args.transfer,
            )
            print(args.record_id)
            return 0
        if args.command == "report":
            result = summarize(load_store(args.store))
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print_report(result)
            return 0
        return self_test()
    except (LearningUtilityError, json.JSONDecodeError, OSError) as exc:
        print(f"Learning utility error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
