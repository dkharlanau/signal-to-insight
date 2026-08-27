#!/usr/bin/env python3
"""Export/import Signal to Insight private local state as one versioned JSON bundle.

This moves explicit personal context and learning/usage evidence between devices without an
account or backend. It never reads public source payloads and rejects suspicious full-source
content keys on export/import.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import action_outcomes
import dogfood
import learning_utility
import personal_baseline
import source_decision_benchmark

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
FORBIDDEN_KEYS = {
    "transcript", "full_transcript", "full_text", "raw_content", "source_text",
    "article_text", "pdf_text", "repository_contents", "document_text"
}

STORE_SPECS = {
    "personal_baseline": (personal_baseline.DEFAULT_STORE, personal_baseline.validate_store),
    "learning_utility": (learning_utility.DEFAULT_STORE, learning_utility.validate_store),
    "action_outcomes": (action_outcomes.DEFAULT_STORE, action_outcomes.validate_store),
    "dogfood_cohort": (dogfood.DEFAULT_STORE, dogfood.validate_store),
    "source_decision_benchmark": (source_decision_benchmark.DEFAULT_STORE, source_decision_benchmark.validate_store),
}


class LocalStateError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reject_full_source_content(value, trail: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_KEYS:
                raise LocalStateError(f"forbidden full-source field in private state bundle: {trail}.{key}")
            reject_full_source_content(child, f"{trail}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_full_source_content(child, f"{trail}[{index}]")


def validate_bundle(bundle: dict) -> None:
    if bundle.get("bundle_version") != VERSION:
        raise LocalStateError(f"unsupported local-state bundle version: {bundle.get('bundle_version')!r}")
    if bundle.get("privacy") != "private_local_not_public_evidence":
        raise LocalStateError("local-state bundle must declare private_local_not_public_evidence")
    stores = bundle.get("stores")
    if not isinstance(stores, dict):
        raise LocalStateError("stores must be an object")
    unknown = set(stores) - set(STORE_SPECS)
    if unknown:
        raise LocalStateError(f"unknown stores in bundle: {sorted(unknown)}")
    reject_full_source_content(stores)
    for name, data in stores.items():
        validator = STORE_SPECS[name][1]
        validator(data)


def export_bundle(overrides: dict[str, Path] | None = None) -> dict:
    overrides = overrides or {}
    stores: dict[str, dict] = {}
    for name, (default_path, validator) in STORE_SPECS.items():
        path = overrides.get(name, default_path)
        if not path.exists():
            continue
        data = load(path)
        validator(data)
        reject_full_source_content(data, name)
        stores[name] = data
    bundle = {
        "bundle_version": VERSION,
        "created_at": now_iso(),
        "privacy": "private_local_not_public_evidence",
        "stores": stores,
    }
    validate_bundle(bundle)
    return bundle


def record_timestamp(item: dict) -> str | None:
    for key in ("updated_at", "recorded_at", "created_at"):
        if isinstance(item.get(key), str) and item[key]:
            return item[key]
    return None


def merge_record_lists(current: list[dict], incoming: list[dict], store_name: str) -> list[dict]:
    merged = {item["id"]: item for item in current}
    for candidate in incoming:
        existing = merged.get(candidate["id"])
        if existing is None:
            merged[candidate["id"]] = candidate
            continue
        if existing == candidate:
            continue

        # Learning evidence can legitimately acquire delayed results later without changing recorded_at.
        if store_name == "learning_utility":
            comparable_existing = dict(existing)
            comparable_candidate = dict(candidate)
            delayed_existing = comparable_existing.pop("delayed", None)
            delayed_candidate = comparable_candidate.pop("delayed", None)
            transfer_existing = comparable_existing.pop("transfer", None)
            transfer_candidate = comparable_candidate.pop("transfer", None)
            if comparable_existing == comparable_candidate:
                if delayed_existing is None and delayed_candidate is not None:
                    merged[candidate["id"]] = candidate
                    continue
                if delayed_candidate is None and delayed_existing is not None:
                    continue
                if delayed_existing == delayed_candidate and transfer_existing == transfer_candidate:
                    continue

        old_ts = record_timestamp(existing)
        new_ts = record_timestamp(candidate)
        if old_ts and new_ts and old_ts != new_ts:
            merged[candidate["id"]] = candidate if new_ts > old_ts else existing
            continue
        raise LocalStateError(f"ambiguous conflict in {store_name} for id {candidate['id']}")
    return [merged[key] for key in sorted(merged)]


def merge_baseline(current: dict, incoming: dict) -> dict:
    personal_baseline.validate_store(current)
    personal_baseline.validate_store(incoming)
    entries = merge_record_lists(current["entries"], incoming["entries"], "personal_baseline")
    active = {}
    for key in ("goals", "projects", "questions"):
        active[key] = sorted(set(current["active_context"][key]) | set(incoming["active_context"][key]))
    result = {
        "version": personal_baseline.VERSION,
        "revision": max(current["revision"], incoming["revision"]) + 1,
        "updated_at": now_iso(),
        "entries": entries,
        "active_context": active,
    }
    personal_baseline.validate_store(result)
    return result


def empty_for_store(name: str) -> dict:
    if name == "personal_baseline":
        return personal_baseline.empty_store()
    return {"version": STORE_SPECS[name][1].__module__ and "1.0.0", "records": []}


def load_current(name: str, path: Path) -> dict:
    if path.exists():
        data = load(path)
        STORE_SPECS[name][1](data)
        return data
    if name == "personal_baseline":
        return personal_baseline.empty_store()
    module = {
        "learning_utility": learning_utility,
        "action_outcomes": action_outcomes,
        "dogfood_cohort": dogfood,
        "source_decision_benchmark": source_decision_benchmark,
    }[name]
    return {"version": module.VERSION, "records": []}


def merge_store(name: str, current: dict, incoming: dict) -> dict:
    if name == "personal_baseline":
        return merge_baseline(current, incoming)
    result = {"version": current.get("version") or incoming.get("version"), "records": merge_record_lists(current.get("records", []), incoming.get("records", []), name)}
    STORE_SPECS[name][1](result)
    return result


def import_bundle(bundle: dict, overrides: dict[str, Path] | None = None) -> dict:
    validate_bundle(bundle)
    overrides = overrides or {}
    written: list[str] = []
    for name, incoming in bundle["stores"].items():
        default_path = STORE_SPECS[name][0]
        target = overrides.get(name, default_path)
        current = load_current(name, target)
        merged = merge_store(name, current, incoming)
        reject_full_source_content(merged, name)
        dump(target, merged)
        written.append(name)
    return {"written_stores": sorted(written), "privacy": "private_local_not_public_evidence"}


def self_test() -> int:
    insight_id = next(iter(sorted(action_outcomes.known_insights())), None)
    if not insight_id:
        print("local state self-test requires an insight")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = {
            "personal_baseline": root / "device-a-baseline.json",
            "action_outcomes": root / "device-a-outcomes.json",
        }
        baseline = personal_baseline.empty_store()
        personal_baseline.upsert_entry(baseline, "Policy as code", "known", "experience")
        personal_baseline.write_store(paths["personal_baseline"], baseline)
        outcomes = action_outcomes.empty_store()
        action_outcomes.start_record(outcomes, insight_id, "try", "Test a policy boundary", "Observe enforcement separation", ["policy-as-code"], None, "fixture-action")
        action_outcomes.write_store(paths["action_outcomes"], outcomes)

        bundle = export_bundle(paths)
        if set(bundle["stores"]) != {"personal_baseline", "action_outcomes"}:
            print("local state self-test failed: export store selection")
            return 1

        target_paths = {
            "personal_baseline": root / "device-b-baseline.json",
            "action_outcomes": root / "device-b-outcomes.json",
        }
        import_bundle(bundle, target_paths)
        imported_baseline = personal_baseline.load_store(target_paths["personal_baseline"])
        imported_outcomes = action_outcomes.load_store(target_paths["action_outcomes"])
        if imported_baseline["entries"][0]["concept"] != "Policy as code" or imported_outcomes["records"][0]["id"] != "fixture-action":
            print("local state self-test failed: round trip")
            return 1

        malicious = dict(bundle)
        malicious["stores"] = {"action_outcomes": {"version": "1.0.0", "records": [{"id": "x", "transcript": "no"}]}}
        try:
            validate_bundle(malicious)
        except LocalStateError:
            pass
        else:
            print("local state self-test failed: full-source content guard")
            return 1
    print("local state self-test passed; versioned export/import, merge and full-source guards work.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--out", type=Path, required=True)
    import_cmd = sub.add_parser("import")
    import_cmd.add_argument("--in", dest="input", type=Path, required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--in", dest="input", type=Path, required=True)
    sub.add_parser("self-test")
    args = parser.parse_args()

    try:
        if args.command == "self-test":
            return self_test()
        if args.command == "export":
            bundle = export_bundle()
            dump(args.out, bundle)
            print(f"exported {len(bundle['stores'])} private store(s) to {args.out}")
        elif args.command == "import":
            result = import_bundle(load(args.input))
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            bundle = load(args.input)
            validate_bundle(bundle)
            print(json.dumps({"bundle_version": bundle["bundle_version"], "created_at": bundle["created_at"], "stores": sorted(bundle["stores"]), "privacy": bundle["privacy"]}, ensure_ascii=False, indent=2))
    except (LocalStateError, json.JSONDecodeError, ValueError) as exc:
        print(f"local state error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
