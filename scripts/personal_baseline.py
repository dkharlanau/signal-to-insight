#!/usr/bin/env python3
"""Manage a private, explicit personal knowledge baseline for Signal to Insight.

The default store lives under .local/ and is therefore excluded from git. It contains only
facts the user explicitly chooses to record; this script never infers a profile from behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / ".local" / "personal-baseline.json"
VERSION = "1.0.0"
STATES = {"known", "partially_known", "uncertain", "unknown"}
ORIGINS = {"user_assertion", "experience"}
CONTEXT_KINDS = {"goal", "project", "question"}


class PersonalBaselineError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def empty_store() -> dict:
    return {
        "version": VERSION,
        "revision": 0,
        "updated_at": None,
        "entries": [],
        "active_context": {"goals": [], "projects": [], "questions": []},
    }


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
        raise PersonalBaselineError(f"unsupported baseline version: {data.get('version')!r}")
    revision = data.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise PersonalBaselineError("revision must be a non-negative integer")
    if data.get("updated_at") is not None:
        try:
            datetime.fromisoformat(str(data["updated_at"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise PersonalBaselineError("updated_at must be null or ISO datetime") from exc

    entries = data.get("entries")
    if not isinstance(entries, list):
        raise PersonalBaselineError("entries must be a list")
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        where = f"entries[{index}]"
        if not isinstance(entry, dict):
            raise PersonalBaselineError(f"{where} must be an object")
        entry_id = entry.get("id")
        concept = entry.get("concept")
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise PersonalBaselineError(f"{where}.id must be non-empty")
        if entry_id in seen:
            raise PersonalBaselineError(f"duplicate entry id: {entry_id}")
        seen.add(entry_id)
        if not isinstance(concept, str) or not concept.strip():
            raise PersonalBaselineError(f"{where}.concept must be non-empty")
        if entry.get("state") not in STATES:
            raise PersonalBaselineError(f"{where}.state invalid")
        if entry.get("origin") not in ORIGINS:
            raise PersonalBaselineError(f"{where}.origin invalid")
        tags = entry.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(item, str) and item.strip() for item in tags):
            raise PersonalBaselineError(f"{where}.tags must be a list of non-empty strings")
        if entry.get("note") is not None and not isinstance(entry.get("note"), str):
            raise PersonalBaselineError(f"{where}.note must be null or string")

    context = data.get("active_context")
    if not isinstance(context, dict):
        raise PersonalBaselineError("active_context must be an object")
    for plural in ("goals", "projects", "questions"):
        values = context.get(plural)
        if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
            raise PersonalBaselineError(f"active_context.{plural} must be a list of non-empty strings")


def canonical_fingerprint(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def slug(value: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return candidate[:60] or "concept"


def touch(data: dict) -> None:
    data["revision"] += 1
    data["updated_at"] = now_iso()


def upsert_entry(
    data: dict,
    concept: str,
    state: str,
    origin: str,
    note: str | None = None,
    tags: list[str] | None = None,
    entry_id: str | None = None,
) -> dict:
    if state not in STATES:
        raise PersonalBaselineError(f"state must be one of {sorted(STATES)}")
    if origin not in ORIGINS:
        raise PersonalBaselineError(f"origin must be one of {sorted(ORIGINS)}")
    concept = concept.strip()
    if not concept:
        raise PersonalBaselineError("concept must not be empty")
    tags = sorted({item.strip() for item in (tags or []) if item.strip()})
    target = None
    if entry_id:
        target = next((item for item in data["entries"] if item["id"] == entry_id), None)
    if target is None:
        target = next((item for item in data["entries"] if item["concept"].casefold() == concept.casefold()), None)
    if target is None:
        base = entry_id or f"personal-{slug(concept)}"
        candidate = base
        existing = {item["id"] for item in data["entries"]}
        counter = 2
        while candidate in existing:
            candidate = f"{base}-{counter}"
            counter += 1
        target = {"id": candidate}
        data["entries"].append(target)

    target.update(
        {
            "concept": concept,
            "state": state,
            "origin": origin,
            "note": note.strip() if isinstance(note, str) and note.strip() else None,
            "tags": tags,
            "updated_at": now_iso(),
        }
    )
    touch(data)
    return target


def add_context(data: dict, kind: str, text: str) -> None:
    if kind not in CONTEXT_KINDS:
        raise PersonalBaselineError(f"context kind must be one of {sorted(CONTEXT_KINDS)}")
    text = text.strip()
    if not text:
        raise PersonalBaselineError("context text must not be empty")
    key = {"goal": "goals", "project": "projects", "question": "questions"}[kind]
    if text not in data["active_context"][key]:
        data["active_context"][key].append(text)
        touch(data)


def remove_context(data: dict, kind: str, text: str) -> bool:
    if kind not in CONTEXT_KINDS:
        raise PersonalBaselineError(f"context kind must be one of {sorted(CONTEXT_KINDS)}")
    key = {"goal": "goals", "project": "projects", "question": "questions"}[kind]
    if text in data["active_context"][key]:
        data["active_context"][key].remove(text)
        touch(data)
        return True
    return False


def tokens(text: str) -> set[str]:
    return {part for part in re.findall(r"[a-z0-9][a-z0-9_-]{1,}", text.casefold()) if len(part) > 2}


def select_context(data: dict, query: str, limit: int = 8) -> dict:
    query_tokens = tokens(query)
    ranked: list[tuple[int, str, dict]] = []
    for item in data["entries"]:
        haystack = " ".join(
            [
                item["concept"],
                item.get("note") or "",
                " ".join(item.get("tags", [])),
            ]
        )
        overlap = query_tokens & tokens(haystack)
        score = len(overlap) * 10
        if item["state"] in {"uncertain", "unknown"}:
            score += 2
        if overlap or not query_tokens:
            ranked.append((score, item["concept"].casefold(), item))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    selected = [item for _, _, item in ranked[: max(0, limit)]]
    return {
        "baseline_version": data["version"],
        "baseline_revision": data["revision"],
        "baseline_fingerprint": canonical_fingerprint(data),
        "query": query,
        "active_context": data["active_context"],
        "entries": selected,
        "privacy": {
            "classification": "private_local",
            "public_evidence": False,
            "rule": "User assertions and personal experience may guide relevance/explanation depth but never become public source evidence.",
        },
    }


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "baseline.json"
        data = load_store(path)
        upsert_entry(data, "Durable execution", "known", "experience", tags=["workflow", "reliability"])
        upsert_entry(data, "Policy as code", "partially_known", "user_assertion", tags=["policy"])
        add_context(data, "goal", "Understand production agent control")
        write_store(path, data)
        restored = load_store(path)
        selected = select_context(restored, "workflow durable agent", limit=1)
        if selected["entries"][0]["concept"] != "Durable execution":
            print("personal baseline self-test failed: retrieval ranking")
            return 1
        if selected["baseline_revision"] != 3:
            print(f"personal baseline self-test failed: revision={selected['baseline_revision']}")
            return 1
        if not selected["baseline_fingerprint"]:
            print("personal baseline self-test failed: fingerprint missing")
            return 1
    print("personal baseline self-test passed; private store, explicit context and deterministic selection work.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create an empty private baseline if it does not exist")

    set_cmd = sub.add_parser("set", help="Add or update an explicit knowledge entry")
    set_cmd.add_argument("--concept", required=True)
    set_cmd.add_argument("--state", choices=sorted(STATES), required=True)
    set_cmd.add_argument("--origin", choices=sorted(ORIGINS), required=True)
    set_cmd.add_argument("--note")
    set_cmd.add_argument("--tags", default="", help="Comma-separated tags")
    set_cmd.add_argument("--id")

    context_add = sub.add_parser("context-add", help="Add an active goal/project/question")
    context_add.add_argument("--kind", choices=sorted(CONTEXT_KINDS), required=True)
    context_add.add_argument("--text", required=True)

    context_remove = sub.add_parser("context-remove", help="Remove an active goal/project/question")
    context_remove.add_argument("--kind", choices=sorted(CONTEXT_KINDS), required=True)
    context_remove.add_argument("--text", required=True)

    context = sub.add_parser("context", help="Print the private context relevant to a query")
    context.add_argument("--query", default="")
    context.add_argument("--limit", type=int, default=8)
    context.add_argument("--out", type=Path)

    show = sub.add_parser("show", help="Print baseline metadata or full local data")
    show.add_argument("--full", action="store_true")

    sub.add_parser("self-test")

    args = parser.parse_args()
    try:
        if args.command == "self-test":
            return self_test()

        data = load_store(args.store)
        if args.command == "init":
            if not args.store.exists():
                write_store(args.store, data)
            print(f"baseline ready: {args.store}")
        elif args.command == "set":
            item = upsert_entry(
                data,
                args.concept,
                args.state,
                args.origin,
                note=args.note,
                tags=[part.strip() for part in args.tags.split(",") if part.strip()],
                entry_id=args.id,
            )
            write_store(args.store, data)
            print(json.dumps(item, ensure_ascii=False, indent=2))
        elif args.command == "context-add":
            add_context(data, args.kind, args.text)
            write_store(args.store, data)
            print(f"added {args.kind}: {args.text}")
        elif args.command == "context-remove":
            removed = remove_context(data, args.kind, args.text)
            if removed:
                write_store(args.store, data)
            print("removed" if removed else "not found")
        elif args.command == "context":
            snapshot = select_context(data, args.query, args.limit)
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(args.out)
            else:
                print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        elif args.command == "show":
            if args.full:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(
                    json.dumps(
                        {
                            "version": data["version"],
                            "revision": data["revision"],
                            "updated_at": data["updated_at"],
                            "entries": len(data["entries"]),
                            "active_context_counts": {key: len(value) for key, value in data["active_context"].items()},
                            "fingerprint": canonical_fingerprint(data),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
    except (PersonalBaselineError, json.JSONDecodeError) as exc:
        print(f"personal baseline error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
