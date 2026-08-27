#!/usr/bin/env python3
"""Materialize one companion review contract into mandatory shared registries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "knowledge_delta": ROOT / "data" / "knowledge-deltas.json",
    "claim_evidence": ROOT / "data" / "claim-evidence.json",
    "prerequisite_map": ROOT / "data" / "prerequisite-maps.json",
    "learning_prompt": ROOT / "data" / "learning-prompts.json",
    "source_decision": ROOT / "data" / "source-decisions.json",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert(path: Path, record: dict, insight_id: str) -> bool:
    payload = load(path)
    records = payload.setdefault("records", [])
    index = next((i for i, item in enumerate(records) if item.get("insight_id") == insight_id), None)
    if index is None:
        records.append(record)
        changed = True
    elif records[index] != record:
        records[index] = record
        changed = True
    else:
        changed = False
    if changed:
        dump(path, payload)
    return changed


def apply(path: Path) -> int:
    payload = load(path)
    insight_id = payload.get("insight_id")
    if not isinstance(insight_id, str) or not insight_id:
        print("case contract missing insight_id", file=sys.stderr)
        return 1
    changed: list[str] = []
    for key, target in TARGETS.items():
        record = payload.get(key)
        if not isinstance(record, dict) or record.get("insight_id") != insight_id:
            print(f"case contract {key} is missing or has the wrong insight_id", file=sys.stderr)
            return 1
        if upsert(target, record, insight_id):
            changed.append(str(target.relative_to(ROOT)))
    if changed:
        print(f"materialized companion contract for {insight_id}: {', '.join(changed)}")
    else:
        print(f"companion contract already materialized for {insight_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract")
    args = parser.parse_args()
    path = ROOT / args.contract
    if not path.exists():
        parser.error(f"contract not found: {args.contract}")
    return apply(path)


if __name__ == "__main__":
    sys.exit(main())
