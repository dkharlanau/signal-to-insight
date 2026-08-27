#!/usr/bin/env python3
"""Operate a physically separate local overlay for sensitive sources and insights.

Private records live under .local/private by default. Public builders never read this directory.
The overlay reuses public source/bundle/insight/graph shapes where possible, while private context
is combined with public prior knowledge only in a local research sidecar.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import tempfile
from datetime import date
from pathlib import Path

from graph_context import rank as public_rank
from new_source import normalize_url, source_key
from scaffold_bundle import build_bundle, prior_query

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / ".local" / "private"
ALLOWED_TYPES = {
    "video", "article", "paper", "podcast", "documentation", "repository", "tool",
    "product", "course", "presentation", "notes", "system",
}


class PrivateOverlayError(ValueError):
    pass


def load(path: Path, default: dict | None = None) -> dict:
    if not path.exists() and default is not None:
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def paths(root: Path) -> dict[str, Path]:
    data = root / "data"
    return {
        "root": root,
        "data": data,
        "inbox": data / "inbox.json",
        "sources": data / "sources.json",
        "insights": data / "insights.json",
        "graph": data / "knowledge-graph.json",
        "bundles": data / "research-bundles",
        "context": root / "run-context",
        "exports": root / "exports",
    }


def init_overlay(root: Path) -> None:
    p = paths(root)
    root.mkdir(parents=True, exist_ok=True)
    defaults = {
        "inbox": {"items": []},
        "sources": {"sources": []},
        "insights": {"insights": []},
        "graph": {"graph_version": "private-1.0.0", "updated_at": date.today().isoformat(), "concepts": [], "relations": []},
    }
    for name, value in defaults.items():
        if not p[name].exists():
            dump(p[name], value)
    p["bundles"].mkdir(parents=True, exist_ok=True)
    p["context"].mkdir(parents=True, exist_ok=True)
    p["exports"].mkdir(parents=True, exist_ok=True)


def find_private_source(root: Path, normalized_url: str) -> dict | None:
    for source in load(paths(root)["sources"], {"sources": []}).get("sources", []):
        try:
            if normalize_url(source.get("canonical_url", "")) == normalized_url:
                return source
        except ValueError:
            continue
    return None


def queue_source(root: Path, url: str, source_type: str, focus: str | None, note: str | None) -> dict:
    if source_type not in ALLOWED_TYPES:
        raise PrivateOverlayError(f"unsupported source type: {source_type}")
    init_overlay(root)
    p = paths(root)
    normalized = normalize_url(url)
    inbox = load(p["inbox"])
    for item in inbox.get("items", []):
        if normalize_url(item.get("source_url", "")) == normalized and (item.get("requested_focus") or None) == focus:
            return item

    existing_source = find_private_source(root, normalized)
    today = date.today().isoformat()
    base = f"intake-{today}-{source_key(normalized)}"
    existing_ids = {item.get("id") for item in inbox.get("items", [])}
    intake_id = base
    suffix = 2
    while intake_id in existing_ids:
        intake_id = f"{base}-{suffix}"
        suffix += 1
    item = {
        "id": intake_id,
        "source_url": normalized,
        "source_type": source_type,
        "submitted_at": today,
        "requested_focus": focus,
        "status": "queued",
        "source_id": existing_source.get("id") if existing_source else None,
        "insight_id": None,
        "notes": note,
    }
    inbox.setdefault("items", []).append(item)
    dump(p["inbox"], inbox)
    return item


def tokens(text: str) -> set[str]:
    return {part for part in re.findall(r"[a-z0-9][a-z0-9_-]+", text.casefold()) if len(part) > 2}


def private_rank(root: Path, query: str, limit: int = 5) -> list[dict]:
    graph = load(paths(root)["graph"], {"concepts": [], "relations": []})
    insights = {item.get("id"): item for item in load(paths(root)["insights"], {"insights": []}).get("insights", [])}
    query_tokens = tokens(query)
    scored: list[tuple[float, dict]] = []
    for concept in graph.get("concepts", []):
        text = " ".join([
            str(concept.get("id") or ""), str(concept.get("label") or ""), str(concept.get("summary") or ""),
            " ".join(concept.get("aliases") or []), " ".join(concept.get("tags") or []),
        ])
        concept_tokens = tokens(text)
        overlap = query_tokens & concept_tokens
        if not overlap:
            continue
        score = len(overlap) / max(1, len(query_tokens))
        evidence = []
        for insight_id in concept.get("insight_ids") or []:
            insight = insights.get(insight_id) or {}
            evidence.append({"id": insight_id, "status": insight.get("status"), "title": insight.get("title")})
        scored.append((score, {
            "concept_id": concept.get("id"),
            "label": concept.get("label"),
            "coverage": concept.get("coverage"),
            "matched_terms": sorted(overlap),
            "evidence_insights": evidence,
            "provenance": "private_overlay",
        }))
    scored.sort(key=lambda item: (-item[0], item[1].get("concept_id") or ""))
    return [item for _, item in scored[:limit]]


def combined_context(root: Path, query: str, limit: int = 5) -> dict:
    public = public_rank(query, limit=limit)
    public_matches = []
    for match in public.get("matches", []):
        item = copy.deepcopy(match)
        item["provenance"] = "public_graph"
        public_matches.append(item)
    return {
        "captured_at": date.today().isoformat(),
        "query": query,
        "public_matches": public_matches,
        "private_matches": private_rank(root, query, limit=limit),
        "rule": "Private matches may guide local explanation/relevance but are never public evidence unless explicitly exported, redacted and reviewed.",
    }


def get_intake(root: Path, intake_id: str) -> dict:
    item = next((row for row in load(paths(root)["inbox"]).get("items", []) if row.get("id") == intake_id), None)
    if item is None:
        raise PrivateOverlayError(f"private intake not found: {intake_id}")
    return item


def scaffold(root: Path, intake_id: str) -> tuple[Path, Path]:
    init_overlay(root)
    p = paths(root)
    item = get_intake(root, intake_id)
    target = p["bundles"] / f"{intake_id}.json"
    context_target = p["context"] / f"{intake_id}.json"
    if target.exists():
        raise PrivateOverlayError(f"private bundle already exists: {target}")
    bundle = build_bundle(item)
    # Keep the normalized bundle shape compatible with the public contract. Private knowledge is
    # added only in the local sidecar so the core bundle does not gain secret/public semantics.
    dump(target, bundle)
    dump(context_target, combined_context(root, prior_query(item), limit=5))
    return target, context_target


def strip_public_markers(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: strip_public_markers(item)
            for key, item in value.items()
            if key not in {"public", "private", "privacy", "internal_note", "private_note"}
        }
    if isinstance(value, list):
        return [strip_public_markers(item) for item in value]
    return value


def redact_urls(value: object) -> object:
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            if key in {"url", "canonical_url", "source_url", "html_url", "download_url"}:
                output[key] = None
            else:
                output[key] = redact_urls(item)
        return output
    if isinstance(value, list):
        return [redact_urls(item) for item in value]
    return value


def export_candidate(root: Path, insight_id: str, keep_urls: bool, confirm: str) -> Path:
    if confirm != f"EXPORT:{insight_id}":
        raise PrivateOverlayError(f"export confirmation must exactly equal EXPORT:{insight_id}")
    init_overlay(root)
    p = paths(root)
    insights = load(p["insights"]).get("insights", [])
    insight = next((item for item in insights if item.get("id") == insight_id), None)
    if insight is None:
        raise PrivateOverlayError(f"private insight not found: {insight_id}")
    source_id = insight.get("source_id")
    source = next((item for item in load(p["sources"]).get("sources", []) if item.get("id") == source_id), None)
    if source is None:
        raise PrivateOverlayError(f"private insight source not found: {source_id}")

    clean_insight = strip_public_markers(copy.deepcopy(insight))
    clean_source = strip_public_markers(copy.deepcopy(source))
    if isinstance(clean_insight, dict):
        clean_insight["status"] = "review"
    if not keep_urls:
        clean_source = redact_urls(clean_source)
        clean_insight = redact_urls(clean_insight)
    candidate = {
        "export_version": "1.0.0",
        "created_at": date.today().isoformat(),
        "source": clean_source,
        "insight": clean_insight,
        "redaction": {
            "urls_retained": bool(keep_urls),
            "automatic_steps": [
                "Removed overlay-only/private/public-projection metadata.",
                "Forced insight status to review.",
                "Removed URLs by default." if not keep_urls else "URLs explicitly retained by export operator.",
            ],
            "manual_review_required": [
                "Check title, examples, claims, names, identifiers and business context for sensitive information.",
                "Replace or verify canonical public source provenance before any public registry write.",
                "Re-run normal claim/evidence, Knowledge Delta, graph and publication review gates.",
            ],
        },
        "public_write_allowed": False,
        "next_step": "Human-review this local export candidate. A separate normal public case/review workflow is required; this command never writes public data.",
    }
    target = p["exports"] / f"{insight_id}.json"
    dump(target, candidate)
    return target


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "private"
        init_overlay(root)
        p = paths(root)
        source = {
            "id": "private-src-fixture",
            "type": "article",
            "title": "Private source sentinel",
            "canonical_url": "https://private.example.invalid/secret",
            "creators": [],
            "publisher": None,
            "published_at": None,
            "event_date": None,
            "captured_at": "2026-08-27",
            "analyzed_at": "2026-08-27",
            "date_note": "Private fixture.",
            "verification": [],
        }
        insight = {
            "id": "private-insight-fixture",
            "source_id": "private-src-fixture",
            "status": "review",
            "title": "Private insight sentinel",
        }
        graph = load(p["graph"])
        graph["concepts"].append({
            "id": "private-secret-concept",
            "label": "Private secret concept",
            "summary": "A private sentinel model used only for the overlay self-test.",
            "domain": "fixture",
            "coverage": "explained",
            "insight_ids": ["private-insight-fixture"],
            "aliases": ["private sentinel"],
            "tags": ["private", "sentinel"],
        })
        dump(p["sources"], {"sources": [source]})
        dump(p["insights"], {"insights": [insight]})
        dump(p["graph"], graph)

        item = queue_source(root, "https://private.example.invalid/second", "article", "private sentinel", "fixture")
        bundle, context_path = scaffold(root, item["id"])
        if not bundle.exists() or not context_path.exists():
            print("Private overlay self-test failed: scaffold outputs missing.")
            return 1
        context = load(context_path)
        if not any(match.get("concept_id") == "private-secret-concept" for match in context.get("private_matches", [])):
            print("Private overlay self-test failed: private knowledge did not assist research context.")
            return 1
        if any(match.get("provenance") != "private_overlay" for match in context.get("private_matches", [])):
            print("Private overlay self-test failed: private context provenance lost.")
            return 1

        exported = export_candidate(root, "private-insight-fixture", keep_urls=False, confirm="EXPORT:private-insight-fixture")
        candidate = load(exported)
        if candidate["source"].get("canonical_url") is not None or candidate["public_write_allowed"] is not False:
            print("Private overlay self-test failed: safe export boundary not preserved.")
            return 1
        if candidate["insight"].get("status") != "review":
            print("Private overlay self-test failed: export candidate did not stop at review.")
            return 1
    print("Private overlay self-test passed; private context stays local and export stops at a redacted review candidate.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Private overlay root (default: .local/private)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")

    queue = sub.add_parser("queue")
    queue.add_argument("url")
    queue.add_argument("--type", dest="source_type", choices=sorted(ALLOWED_TYPES), default="article")
    queue.add_argument("--focus", default="")
    queue.add_argument("--note", default="")

    scaffold_cmd = sub.add_parser("scaffold")
    scaffold_cmd.add_argument("intake_id")

    context_cmd = sub.add_parser("context")
    context_cmd.add_argument("query")
    context_cmd.add_argument("--limit", type=int, default=5)
    context_cmd.add_argument("--json", action="store_true")

    export = sub.add_parser("export")
    export.add_argument("--insight", required=True)
    export.add_argument("--keep-urls", action="store_true")
    export.add_argument("--confirm", required=True)

    sub.add_parser("self-test")
    args = parser.parse_args()
    try:
        if args.command == "init":
            init_overlay(args.root)
            print(f"initialized {args.root}")
        elif args.command == "queue":
            item = queue_source(args.root, args.url, args.source_type, args.focus.strip() or None, args.note.strip() or None)
            print(json.dumps(item, ensure_ascii=False, indent=2))
        elif args.command == "scaffold":
            bundle, context_path = scaffold(args.root, args.intake_id)
            print(f"bundle: {bundle}\nprivate context: {context_path}")
        elif args.command == "context":
            result = combined_context(args.root, args.query, args.limit)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "export":
            target = export_candidate(args.root, args.insight, args.keep_urls, args.confirm)
            print(f"created local redacted export candidate: {target}")
        else:
            return self_test()
    except (PrivateOverlayError, ValueError, json.JSONDecodeError) as exc:
        print(f"Private overlay command failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
