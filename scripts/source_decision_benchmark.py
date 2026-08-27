#!/usr/bin/env python3
"""Calibrate Source Decision predictions against later full-source consumption.

Benchmark observations are private/local by default. Subjective human outcomes are not CI
assertions; only the deterministic store and aggregate math are self-tested.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / ".local" / "source-decision-benchmark.json"
VERSION = "1.0.0"
DECISIONS = {"consume", "skim_selected_parts", "explainer_is_enough", "skip_for_now"}
MISSED = {"none", "minor", "major"}
VERDICTS = {"correct", "too_optimistic", "too_conservative"}
SKIM = {"all", "partial", "none", "not_applicable"}


class BenchmarkError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def empty_store() -> dict:
    return {"version": VERSION, "records": []}


def load_store(path: Path) -> dict:
    if not path.exists():
        return empty_store()
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_store(data)
    return data


def write_store(path: Path, data: dict) -> None:
    validate_store(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_store(data: dict) -> None:
    if data.get("version") != VERSION:
        raise BenchmarkError(f"unsupported benchmark version: {data.get('version')!r}")
    records = data.get("records")
    if not isinstance(records, list):
        raise BenchmarkError("records must be a list")
    seen: set[str] = set()
    for index, item in enumerate(records):
        where = f"records[{index}]"
        if not isinstance(item, dict):
            raise BenchmarkError(f"{where} must be an object")
        required = {
            "id", "insight_id", "source_type", "predicted_decision", "original_consumed",
            "missed_meaningful_info", "verdict", "skim_targets_verified", "recorded_at"
        }
        missing = required - set(item)
        if missing:
            raise BenchmarkError(f"{where} missing fields: {sorted(missing)}")
        if not isinstance(item["id"], str) or not item["id"]:
            raise BenchmarkError(f"{where}.id must be non-empty")
        if item["id"] in seen:
            raise BenchmarkError(f"duplicate id: {item['id']}")
        seen.add(item["id"])
        for field in ("insight_id", "source_type"):
            if not isinstance(item[field], str) or not item[field].strip():
                raise BenchmarkError(f"{where}.{field} must be non-empty")
        if item["predicted_decision"] not in DECISIONS:
            raise BenchmarkError(f"{where}.predicted_decision invalid")
        if item["original_consumed"] is not True:
            raise BenchmarkError(f"{where}.original_consumed must be true for calibration evidence")
        if item["missed_meaningful_info"] not in MISSED:
            raise BenchmarkError(f"{where}.missed_meaningful_info invalid")
        if item["verdict"] not in VERDICTS:
            raise BenchmarkError(f"{where}.verdict invalid")
        if item["skim_targets_verified"] not in SKIM:
            raise BenchmarkError(f"{where}.skim_targets_verified invalid")
        if item["predicted_decision"] != "skim_selected_parts" and item["skim_targets_verified"] != "not_applicable":
            raise BenchmarkError(f"{where}.skim_targets_verified only applies to skim_selected_parts")
        try:
            datetime.fromisoformat(item["recorded_at"].replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise BenchmarkError(f"{where}.recorded_at must be ISO datetime") from exc


def add_record(store: dict, **values) -> dict:
    insight_id = values["insight_id"]
    base = values.get("record_id") or insight_id
    existing = {item["id"] for item in store["records"]}
    candidate = base
    counter = 2
    while candidate in existing:
        candidate = f"{base}-{counter}"
        counter += 1
    item = {
        "id": candidate,
        "insight_id": insight_id,
        "source_type": values["source_type"],
        "predicted_decision": values["predicted_decision"],
        "original_consumed": True,
        "missed_meaningful_info": values["missed_meaningful_info"],
        "verdict": values["verdict"],
        "skim_targets_verified": values["skim_targets_verified"],
        "note": values.get("note") or None,
        "recorded_at": now_iso(),
    }
    store["records"].append(item)
    validate_store(store)
    return item


def summarize(store: dict) -> dict:
    validate_store(store)
    records = store["records"]
    if not records:
        return {
            "cases": 0,
            "source_types": {},
            "verdicts": {},
            "accuracy": None,
            "false_explainer_enough": 0,
            "unnecessary_consume": 0,
            "skim_cases": 0,
            "skim_all_targets_hit_rate": None,
            "major_miss_rate": None,
        }

    verdicts = Counter(item["verdict"] for item in records)
    source_types = Counter(item["source_type"] for item in records)
    false_enough = sum(
        item["predicted_decision"] == "explainer_is_enough" and item["missed_meaningful_info"] in {"minor", "major"}
        for item in records
    )
    unnecessary_consume = sum(
        item["predicted_decision"] == "consume" and item["verdict"] == "too_conservative"
        for item in records
    )
    skim_cases = [item for item in records if item["predicted_decision"] == "skim_selected_parts"]
    return {
        "cases": len(records),
        "source_types": dict(sorted(source_types.items())),
        "verdicts": dict(sorted(verdicts.items())),
        "accuracy": round(verdicts["correct"] / len(records), 3),
        "false_explainer_enough": false_enough,
        "unnecessary_consume": unnecessary_consume,
        "skim_cases": len(skim_cases),
        "skim_all_targets_hit_rate": (
            round(sum(item["skim_targets_verified"] == "all" for item in skim_cases) / len(skim_cases), 3)
            if skim_cases else None
        ),
        "major_miss_rate": round(sum(item["missed_meaningful_info"] == "major" for item in records) / len(records), 3),
    }


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "benchmark.json"
        store = load_store(path)
        add_record(
            store,
            record_id="a",
            insight_id="insight-a",
            source_type="video",
            predicted_decision="explainer_is_enough",
            missed_meaningful_info="major",
            verdict="too_optimistic",
            skim_targets_verified="not_applicable",
        )
        add_record(
            store,
            record_id="b",
            insight_id="insight-b",
            source_type="documentation",
            predicted_decision="skim_selected_parts",
            missed_meaningful_info="none",
            verdict="correct",
            skim_targets_verified="all",
        )
        write_store(path, store)
        report = summarize(load_store(path))
        if report["false_explainer_enough"] != 1 or report["accuracy"] != 0.5:
            print("source-decision benchmark self-test failed: calibration aggregation")
            return 1
        if report["skim_all_targets_hit_rate"] != 1.0:
            print("source-decision benchmark self-test failed: skim target aggregation")
            return 1
    print("source-decision benchmark self-test passed; private calibration metrics work.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record")
    rec.add_argument("--insight", required=True)
    rec.add_argument("--source-type", required=True)
    rec.add_argument("--predicted", choices=sorted(DECISIONS), required=True)
    rec.add_argument("--missed", choices=sorted(MISSED), required=True)
    rec.add_argument("--verdict", choices=sorted(VERDICTS), required=True)
    rec.add_argument("--skim-targets", choices=sorted(SKIM), default="not_applicable")
    rec.add_argument("--note")
    rec.add_argument("--record-id")

    report = sub.add_parser("report")
    report.add_argument("--json", action="store_true")
    sub.add_parser("self-test")

    args = parser.parse_args()
    try:
        if args.command == "self-test":
            return self_test()
        store = load_store(args.store)
        if args.command == "record":
            item = add_record(
                store,
                insight_id=args.insight,
                source_type=args.source_type,
                predicted_decision=args.predicted,
                missed_meaningful_info=args.missed,
                verdict=args.verdict,
                skim_targets_verified=args.skim_targets,
                note=args.note,
                record_id=args.record_id,
            )
            write_store(args.store, store)
            print(json.dumps(item, ensure_ascii=False, indent=2))
        else:
            result = summarize(store)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Cases: {result['cases']}")
                print(f"Accuracy: {result['accuracy'] if result['accuracy'] is not None else 'n/a'}")
                print(f"False explainer-is-enough: {result['false_explainer_enough']}")
                print(f"Unnecessary consume: {result['unnecessary_consume']}")
                print(f"Major miss rate: {result['major_miss_rate'] if result['major_miss_rate'] is not None else 'n/a'}")
                print(
                    "Skim all-targets-hit rate: "
                    + (str(result["skim_all_targets_hit_rate"]) if result["skim_all_targets_hit_rate"] is not None else "n/a")
                )
    except (BenchmarkError, json.JSONDecodeError) as exc:
        print(f"source-decision benchmark error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
