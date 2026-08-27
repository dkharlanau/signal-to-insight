#!/usr/bin/env python3
"""Manage a gitignored private knowledge overlay and prove public builds cannot depend on it."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / ".local" / "private"
PUBLIC_FILES = [
    ROOT / "data" / "sources.json",
    ROOT / "data" / "insights.json",
    ROOT / "data" / "knowledge-graph.json",
    ROOT / "data" / "knowledge-deltas.json",
    ROOT / "data" / "claim-evidence.json",
    ROOT / "data" / "syntheses.json",
]
VERSION = "1.0.0"


class PrivateOverlayError(ValueError):
    pass


def read(path: Path, default=None):
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def empty_overlay() -> dict:
    return {
        "version": VERSION,
        "sources": [],
        "insights": [],
        "concepts": [],
        "relations": [],
    }


def init(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    target = root / "overlay.json"
    if not target.exists():
        write(target, empty_overlay())


def validate(data: dict) -> None:
    if data.get("version") != VERSION:
        raise PrivateOverlayError("unsupported private overlay version")
    for key in ("sources", "insights", "concepts", "relations"):
        if not isinstance(data.get(key), list):
            raise PrivateOverlayError(f"{key} must be a list")
    ids: dict[str, set[str]] = {}
    for key in ("sources", "insights", "concepts"):
        values = set()
        for item in data[key]:
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id.startswith("private-"):
                raise PrivateOverlayError(f"{key} ids must start with private-")
            if item_id in values:
                raise PrivateOverlayError(f"duplicate private id: {item_id}")
            values.add(item_id)
        ids[key] = values
    for rel in data["relations"]:
        if rel.get("from") not in ids["concepts"] or rel.get("to") not in ids["concepts"]:
            raise PrivateOverlayError("private relation has dangling concept")
    for insight in data["insights"]:
        source_id = insight.get("source_id")
        if source_id and source_id not in ids["sources"]:
            raise PrivateOverlayError(f"private insight has unknown source: {source_id}")


def private_tokens(data: dict) -> set[str]:
    tokens: set[str] = set()
    for key in ("sources", "insights", "concepts"):
        for item in data[key]:
            if item.get("id"):
                tokens.add(item["id"])
    return tokens


def leak_check(data: dict, public_files: list[Path] | None = None) -> list[str]:
    validate(data)
    tokens = private_tokens(data)
    leaks = []
    for path in public_files or PUBLIC_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            if token in text:
                leaks.append(f"{path.relative_to(ROOT)} references {token}")
    return sorted(leaks)


def context(data: dict, query: str, limit: int = 8) -> dict:
    validate(data)
    terms = {x.lower() for x in re.findall(r"[A-Za-z0-9_-]{3,}", query)}
    scored = []
    for item in data["concepts"]:
        hay = " ".join(str(item.get(k, "")) for k in ("id", "label", "definition", "tags")).lower()
        score = sum(term in hay for term in terms)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return {
        "privacy": "private_local_not_public_evidence",
        "concepts": [item for _, item in scored[:limit]],
        "instruction": "Use as private context only. Do not cite or merge into public evidence unless explicitly redacted/exported and re-reviewed.",
    }


def redact_export(data: dict, insight_id: str) -> dict:
    validate(data)
    insight = next((x for x in data["insights"] if x.get("id") == insight_id), None)
    if insight is None:
        raise PrivateOverlayError(f"private insight not found: {insight_id}")
    # Export only a review scaffold. Private IDs and raw source content must be replaced during public review.
    return {
        "export_version": VERSION,
        "status": "redaction_required",
        "private_origin_id": insight_id,
        "candidate": {
            "title": insight.get("title"),
            "mental_model": insight.get("mental_model"),
            "limitations": insight.get("limitations", []),
        },
        "required_before_publication": [
            "register a publishable canonical source or remove private-source dependence",
            "replace private IDs with public stable IDs",
            "rebuild claim evidence from publishable sources",
            "run normal human review and publication boundary",
        ],
    }


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data = empty_overlay()
        data["sources"].append({"id": "private-src-1", "canonical_url": "internal://fixture"})
        data["concepts"].append({"id": "private-concept-1", "label": "Confidential workflow", "definition": "fixture", "tags": ["workflow"]})
        data["insights"].append({"id": "private-insight-1", "source_id": "private-src-1", "title": "Private fixture", "mental_model": "fixture", "limitations": []})
        validate(data)
        public = root / "public.json"
        public.write_text('{"safe":true}\n', encoding="utf-8")
        if leak_check(data, [public]):
            print("private_overlay self-test failed: false leak")
            return 1
        public.write_text('{"concept":"private-concept-1"}\n', encoding="utf-8")
        if not leak_check(data, [public]):
            print("private_overlay self-test failed: leak not detected")
            return 1
        selected = context(data, "workflow")
        if selected["concepts"][0]["id"] != "private-concept-1":
            print("private_overlay self-test failed: context retrieval")
            return 1
        exported = redact_export(data, "private-insight-1")
        if exported["status"] != "redaction_required":
            print("private_overlay self-test failed: unsafe export")
            return 1
    print("private_overlay self-test passed; private evidence is isolated, searchable locally and leak-checkable.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("validate")
    sub.add_parser("leak-check")
    c = sub.add_parser("context")
    c.add_argument("query")
    c.add_argument("--limit", type=int, default=8)
    e = sub.add_parser("redact-export")
    e.add_argument("--insight", required=True)
    e.add_argument("--out", type=Path)
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.command == "self-test":
        return self_test()
    try:
        if args.command == "init":
            init(args.root)
            print(f"Initialized private overlay at {args.root}")
            return 0
        data = read(args.root / "overlay.json")
        validate(data)
        if args.command == "validate":
            print("Private overlay valid.")
        elif args.command == "leak-check":
            leaks = leak_check(data)
            if leaks:
                print("Private overlay leak detected:")
                for leak in leaks:
                    print(f"- {leak}")
                return 1
            print("No private IDs referenced by public knowledge stores.")
        elif args.command == "context":
            print(json.dumps(context(data, args.query, args.limit), ensure_ascii=False, indent=2))
        else:
            value = redact_export(data, args.insight)
            if args.out:
                write(args.out, value)
                print(f"Wrote redaction scaffold: {args.out}")
            else:
                print(json.dumps(value, ensure_ascii=False, indent=2))
    except (PrivateOverlayError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
