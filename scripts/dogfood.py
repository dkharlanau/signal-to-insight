#!/usr/bin/env python3
"""Record and summarize the private 20-source dogfood/reliability cohort.

All observations default to .local/ and are intentionally excluded from public builds.
The goal is to discover repeated product failure modes, not to maximize processed-source count.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / ".local" / "dogfood-cohort.json"
VERSION = "1.0.0"
PUBLICATION = {"publish", "keep_review", "archive", "not_ready"}
YN_UNKNOWN = {"yes", "no", "unknown"}
SOURCE_DECISION_OUTCOME = {"correct", "too_optimistic", "too_conservative", "not_checked"}


class DogfoodError(ValueError):
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


def nonnegative_int(record: dict, field: str, where: str) -> None:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DogfoodError(f"{where}.{field} must be a non-negative integer")


def validate_store(data: dict) -> None:
    if data.get("version") != VERSION:
        raise DogfoodError(f"unsupported dogfood store version: {data.get('version')!r}")
    records = data.get("records")
    if not isinstance(records, list):
        raise DogfoodError("records must be a list")
    seen: set[str] = set()
    for index, record in enumerate(records):
        where = f"records[{index}]"
        if not isinstance(record, dict):
            raise DogfoodError(f"{where} must be an object")
        required = {
            "id",
            "intake_id",
            "source_type",
            "domain",
            "elapsed_work_minutes",
            "agent_provider",
            "manual_interventions",
            "validation_failures",
            "structural_rewrites",
            "publication_decision",
            "knowledge_delta_false_positives",
            "trivial_deltas",
            "prerequisite_misses",
            "retrieval_noise",
            "retrieval_saved_repetition",
            "source_decision_outcome",
            "recorded_at",
        }
        missing = required - set(record)
        if missing:
            raise DogfoodError(f"{where} missing fields: {sorted(missing)}")
        if not isinstance(record["id"], str) or not record["id"]:
            raise DogfoodError(f"{where}.id must be non-empty")
        if record["id"] in seen:
            raise DogfoodError(f"duplicate record id: {record['id']}")
        seen.add(record["id"])
        for field in ("intake_id", "source_type", "domain", "agent_provider"):
            if not isinstance(record[field], str) or not record[field].strip():
                raise DogfoodError(f"{where}.{field} must be non-empty")
        minutes = record["elapsed_work_minutes"]
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes <= 0:
            raise DogfoodError(f"{where}.elapsed_work_minutes must be > 0")
        for field in (
            "manual_interventions",
            "validation_failures",
            "structural_rewrites",
            "knowledge_delta_false_positives",
            "trivial_deltas",
            "prerequisite_misses",
            "retrieval_noise",
        ):
            nonnegative_int(record, field, where)
        if record["publication_decision"] not in PUBLICATION:
            raise DogfoodError(f"{where}.publication_decision invalid")
        if record["retrieval_saved_repetition"] not in YN_UNKNOWN:
            raise DogfoodError(f"{where}.retrieval_saved_repetition invalid")
        if record["source_decision_outcome"] not in SOURCE_DECISION_OUTCOME:
            raise DogfoodError(f"{where}.source_decision_outcome invalid")
        try:
            datetime.fromisoformat(record["recorded_at"].replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise DogfoodError(f"{where}.recorded_at must be ISO datetime") from exc


def make_record_id(intake_id: str, store: dict) -> str:
    existing = {item["id"] for item in store["records"]}
    base = intake_id
    candidate = base
    counter = 2
    while candidate in existing:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def record_run(store: dict, **values) -> dict:
    record = {
        "id": values.get("record_id") or make_record_id(values["intake_id"], store),
        "intake_id": values["intake_id"],
        "insight_id": values.get("insight_id") or None,
        "source_type": values["source_type"],
        "domain": values["domain"],
        "elapsed_work_minutes": float(values["elapsed_work_minutes"]),
        "agent_provider": values["agent_provider"],
        "manual_interventions": values["manual_interventions"],
        "validation_failures": values["validation_failures"],
        "structural_rewrites": values["structural_rewrites"],
        "publication_decision": values["publication_decision"],
        "knowledge_delta_false_positives": values["knowledge_delta_false_positives"],
        "trivial_deltas": values["trivial_deltas"],
        "prerequisite_misses": values["prerequisite_misses"],
        "retrieval_noise": values["retrieval_noise"],
        "retrieval_saved_repetition": values["retrieval_saved_repetition"],
        "source_decision_outcome": values["source_decision_outcome"],
        "learning_record_id": values.get("learning_record_id") or None,
        "note": values.get("note") or None,
        "recorded_at": now_iso(),
    }
    store["records"].append(record)
    validate_store(store)
    return record


def summarize(store: dict) -> dict:
    validate_store(store)
    records = store["records"]
    if not records:
        return {
            "runs": 0,
            "unique_intakes": 0,
            "source_types": {},
            "domains": {},
            "total_work_minutes": 0.0,
            "avg_work_minutes": None,
            "publication_decisions": {},
            "source_decision_outcomes": {},
            "retrieval_saved_repetition_yes": 0,
            "failure_totals": {},
            "top_failure_modes": [],
            "cohort_ready": False,
            "exit_gap": {"sources_remaining": 20, "source_types_remaining": 5},
        }

    unique_intakes = {item["intake_id"] for item in records}
    source_types = Counter(item["source_type"] for item in records)
    domains = Counter(item["domain"] for item in records)
    publication = Counter(item["publication_decision"] for item in records)
    decisions = Counter(item["source_decision_outcome"] for item in records)
    failure_fields = {
        "manual_interventions": "manual interventions",
        "validation_failures": "validation failures",
        "structural_rewrites": "structural rewrites",
        "knowledge_delta_false_positives": "Knowledge Delta false positives",
        "trivial_deltas": "trivial Knowledge Deltas",
        "prerequisite_misses": "prerequisite misses",
        "retrieval_noise": "prior-knowledge retrieval noise",
    }
    failure_totals = {label: sum(item[field] for item in records) for field, label in failure_fields.items()}
    ranked = sorted(
        [{"failure": label, "count": count} for label, count in failure_totals.items() if count],
        key=lambda item: (-item["count"], item["failure"]),
    )
    total_minutes = sum(item["elapsed_work_minutes"] for item in records)
    types_needed = max(0, 5 - len(source_types))
    sources_needed = max(0, 20 - len(unique_intakes))
    return {
        "runs": len(records),
        "unique_intakes": len(unique_intakes),
        "source_types": dict(sorted(source_types.items())),
        "domains": dict(sorted(domains.items())),
        "total_work_minutes": round(total_minutes, 2),
        "avg_work_minutes": round(total_minutes / len(records), 2),
        "publication_decisions": dict(sorted(publication.items())),
        "source_decision_outcomes": dict(sorted(decisions.items())),
        "retrieval_saved_repetition_yes": sum(item["retrieval_saved_repetition"] == "yes" for item in records),
        "failure_totals": failure_totals,
        "top_failure_modes": ranked[:7],
        "cohort_ready": sources_needed == 0 and types_needed == 0,
        "exit_gap": {"sources_remaining": sources_needed, "source_types_remaining": types_needed},
    }


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dogfood.json"
        store = load_store(path)
        for index, source_type in enumerate(("video", "article", "paper", "repository", "documentation"), start=1):
            record_run(
                store,
                record_id=f"case-{index}",
                intake_id=f"intake-{index}",
                insight_id=None,
                source_type=source_type,
                domain="test",
                elapsed_work_minutes=10 + index,
                agent_provider="fixture-agent",
                manual_interventions=index % 2,
                validation_failures=0,
                structural_rewrites=1 if index == 1 else 0,
                publication_decision="keep_review",
                knowledge_delta_false_positives=0,
                trivial_deltas=0,
                prerequisite_misses=0,
                retrieval_noise=1 if index == 2 else 0,
                retrieval_saved_repetition="yes",
                source_decision_outcome="not_checked",
                learning_record_id=None,
                note=None,
            )
        write_store(path, store)
        report = summarize(load_store(path))
        if report["unique_intakes"] != 5 or len(report["source_types"]) != 5:
            print("dogfood self-test failed: cohort diversity aggregation")
            return 1
        if report["failure_totals"]["structural rewrites"] != 1:
            print("dogfood self-test failed: failure aggregation")
            return 1
        if report["cohort_ready"]:
            print("dogfood self-test failed: five fixtures must not satisfy 20-source exit")
            return 1
    print("dogfood self-test passed; private cohort records and failure-mode aggregation work.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record")
    rec.add_argument("--intake", required=True)
    rec.add_argument("--insight")
    rec.add_argument("--source-type", required=True)
    rec.add_argument("--domain", required=True)
    rec.add_argument("--minutes", type=float, required=True)
    rec.add_argument("--agent", required=True)
    rec.add_argument("--manual-interventions", type=int, default=0)
    rec.add_argument("--validation-failures", type=int, default=0)
    rec.add_argument("--structural-rewrites", type=int, default=0)
    rec.add_argument("--publication", choices=sorted(PUBLICATION), required=True)
    rec.add_argument("--delta-false-positives", type=int, default=0)
    rec.add_argument("--trivial-deltas", type=int, default=0)
    rec.add_argument("--prerequisite-misses", type=int, default=0)
    rec.add_argument("--retrieval-noise", type=int, default=0)
    rec.add_argument("--retrieval-saved-repetition", choices=sorted(YN_UNKNOWN), default="unknown")
    rec.add_argument("--source-decision-outcome", choices=sorted(SOURCE_DECISION_OUTCOME), default="not_checked")
    rec.add_argument("--learning-record-id")
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
            item = record_run(
                store,
                record_id=args.record_id,
                intake_id=args.intake,
                insight_id=args.insight,
                source_type=args.source_type,
                domain=args.domain,
                elapsed_work_minutes=args.minutes,
                agent_provider=args.agent,
                manual_interventions=args.manual_interventions,
                validation_failures=args.validation_failures,
                structural_rewrites=args.structural_rewrites,
                publication_decision=args.publication,
                knowledge_delta_false_positives=args.delta_false_positives,
                trivial_deltas=args.trivial_deltas,
                prerequisite_misses=args.prerequisite_misses,
                retrieval_noise=args.retrieval_noise,
                retrieval_saved_repetition=args.retrieval_saved_repetition,
                source_decision_outcome=args.source_decision_outcome,
                learning_record_id=args.learning_record_id,
                note=args.note,
            )
            write_store(args.store, store)
            print(json.dumps(item, ensure_ascii=False, indent=2))
        else:
            report_data = summarize(store)
            if args.json:
                print(json.dumps(report_data, ensure_ascii=False, indent=2))
            else:
                print(f"Unique sources: {report_data['unique_intakes']} / 20")
                print(f"Source types: {len(report_data['source_types'])} / 5 minimum")
                print(f"Average work minutes: {report_data['avg_work_minutes'] if report_data['avg_work_minutes'] is not None else 'n/a'}")
                print(f"Cohort ready: {'yes' if report_data['cohort_ready'] else 'no'}")
                if report_data["top_failure_modes"]:
                    print("Top failure modes:")
                    for item in report_data["top_failure_modes"]:
                        print(f"- {item['failure']}: {item['count']}")
                print("Exit gap: " + json.dumps(report_data["exit_gap"], sort_keys=True))
    except (DogfoodError, json.JSONDecodeError) as exc:
        print(f"dogfood error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
