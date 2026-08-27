#!/usr/bin/env python3
"""Export/import portable private Signal to Insight state with versioned conflict-safe merge rules."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
VERSION = "1.0.0"
FILES = {
    "personal_baseline": "personal-baseline.json",
    "learning_utility": "learning-utility.json",
    "dogfood": "dogfood.json",
    "source_decision_benchmark": "source-decision-benchmark.json",
    "action_outcomes": "action-outcomes.json",
    "next_research_decisions": "next-research-decisions.json",
}


class StateError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_bundle(local_dir: Path) -> dict:
    stores = {}
    for key, name in FILES.items():
        path = local_dir / name
        if path.exists():
            stores[key] = read_json(path)
    return {"bundle_version": VERSION, "exported_at": now(), "stores": stores}


def key_for_record(item: dict) -> str | None:
    for field in ("id", "insight_id", "source_id"):
        value = item.get(field)
        if isinstance(value, str) and value:
            return f"{field}:{value}"
    return None


def merge_lists(existing: list, incoming: list) -> list:
    result = list(existing)
    index = {key_for_record(item): i for i, item in enumerate(result) if isinstance(item, dict) and key_for_record(item)}
    for item in incoming:
        if not isinstance(item, dict):
            if item not in result:
                result.append(item)
            continue
        key = key_for_record(item)
        if key and key in index:
            current = result[index[key]]
            current_time = str(current.get("updated_at") or current.get("recorded_at") or current.get("created_at") or "")
            incoming_time = str(item.get("updated_at") or item.get("recorded_at") or item.get("created_at") or "")
            if incoming_time > current_time:
                result[index[key]] = item
        else:
            if key:
                index[key] = len(result)
            result.append(item)
    return result


def merge_dict(existing: dict, incoming: dict) -> dict:
    result = dict(existing)
    for key, value in incoming.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], list) and isinstance(value, list):
            result[key] = merge_lists(result[key], value)
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dict(result[key], value)
        elif key in {"version", "bundle_version"}:
            if result[key] != value:
                raise StateError(f"version conflict at {key}: {result[key]!r} vs {value!r}")
        else:
            # Prefer the incoming scalar only when its parent object is being imported deliberately.
            result[key] = value
    return result


def import_bundle(local_dir: Path, bundle: dict, replace: bool = False) -> dict:
    if bundle.get("bundle_version") != VERSION or not isinstance(bundle.get("stores"), dict):
        raise StateError("unsupported or invalid state bundle")
    changed = []
    for key, incoming in bundle["stores"].items():
        if key not in FILES:
            continue
        target = local_dir / FILES[key]
        if target.exists() and not replace:
            existing = read_json(target)
            merged = merge_dict(existing, incoming)
        else:
            merged = incoming
        write_json(target, merged)
        changed.append(str(target))
    return {"imported": len(changed), "paths": changed}


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / "a"
        b = Path(tmp) / "b"
        write_json(a / "learning-utility.json", {"version": "1.0.0", "records": [{"id": "x", "updated_at": "2026-01-01T00:00:00Z", "value": 1}]})
        bundle = export_bundle(a)
        if "learning_utility" not in bundle["stores"]:
            print("local_state self-test failed at export")
            return 1
        import_bundle(b, bundle)
        newer = {"bundle_version": VERSION, "stores": {"learning_utility": {"version": "1.0.0", "records": [{"id": "x", "updated_at": "2026-01-02T00:00:00Z", "value": 2}, {"id": "y", "updated_at": "2026-01-02T00:00:00Z", "value": 3}]}}}
        import_bundle(b, newer)
        records = read_json(b / "learning-utility.json")["records"]
        if len(records) != 2 or next(x for x in records if x["id"] == "x")["value"] != 2:
            print("local_state self-test failed at conflict-safe merge")
            return 1
    print("local_state self-test passed; private state exports and merges without a backend.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-dir", type=Path, default=LOCAL)
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("export")
    exp.add_argument("--out", type=Path, required=True)
    imp = sub.add_parser("import")
    imp.add_argument("--in", dest="input", type=Path, required=True)
    imp.add_argument("--replace", action="store_true")
    sub.add_parser("self-test")
    args = parser.parse_args()
    try:
        if args.command == "self-test":
            return self_test()
        if args.command == "export":
            bundle = export_bundle(args.local_dir)
            write_json(args.out, bundle)
            print(f"Exported {len(bundle['stores'])} private stores to {args.out}")
        else:
            result = import_bundle(args.local_dir, read_json(args.input), args.replace)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (StateError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
