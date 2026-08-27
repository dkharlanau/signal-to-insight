#!/usr/bin/env python3
"""Prepare/resume a source run with explicit private personal context.

This wraps scripts/run_source.py. Versioned manifests receive only fingerprints/counts;
selected baseline entries and personal action outcomes stay under .local/ and never become
public/source evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import action_outcomes
import run_source
from personal_baseline import DEFAULT_STORE, load_store, select_context

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_CONTEXT_DIR = ROOT / ".local" / "run-context"
DEFAULT_OUTCOME_STORE = action_outcomes.DEFAULT_STORE


def fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_private_context(item: dict, store_path: Path, outcome_store: Path, limit: int) -> dict:
    data = load_store(store_path)
    query = " ".join(
        part
        for part in (
            item.get("requested_focus") or "",
            item.get("source_type") or "",
            item.get("source_url") or "",
        )
        if part
    )
    baseline_snapshot = select_context(data, query, limit=limit)
    outcomes_store = action_outcomes.load_store(outcome_store)
    outcomes = action_outcomes.select_context(outcomes_store, query, limit=limit)
    sidecar = {
        "query": query,
        "baseline": baseline_snapshot,
        "action_outcomes": outcomes,
        "privacy": {
            "classification": "private_local",
            "public_evidence": False,
            "rule": "Explicit personal knowledge and outcomes may guide relevance/action recommendations but never become external evidence.",
        },
    }
    target = PRIVATE_CONTEXT_DIR / f"{item['id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "available": bool(baseline_snapshot["entries"] or any(baseline_snapshot["active_context"].values()) or outcomes),
        "baseline_version": baseline_snapshot["baseline_version"],
        "baseline_revision": baseline_snapshot["baseline_revision"],
        "baseline_fingerprint": baseline_snapshot["baseline_fingerprint"],
        "outcomes_fingerprint": fingerprint(outcomes_store),
        "private_sidecar": str(target.relative_to(ROOT)),
        "selected_entries": len(baseline_snapshot["entries"]),
        "selected_outcomes": len(outcomes),
        "privacy": "private_local_not_public_evidence",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Intake ID or http(s) source URL")
    parser.add_argument(
        "--type",
        dest="source_type",
        default="article",
        choices=[
            "video",
            "article",
            "paper",
            "podcast",
            "documentation",
            "repository",
            "tool",
            "product",
            "course",
            "presentation",
            "notes",
            "system",
        ],
    )
    parser.add_argument("--focus", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--baseline-store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--outcome-store", type=Path, default=DEFAULT_OUTCOME_STORE)
    parser.add_argument("--personal-limit", type=int, default=8)
    parser.add_argument("--no-checks", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    focus = args.focus.strip() or None
    note = args.note.strip() or None
    if args.source.startswith(("http://", "https://")):
        item = run_source.queue_url(args.source, args.source_type, focus, note)
    else:
        item = run_source.get_intake(args.source)

    bundle, bundle_path, created_bundle = run_source.ensure_bundle(item)
    state = run_source.evaluate_state(item, bundle)
    manifest = run_source.write_manifest(item, state, bundle_path, created_bundle)

    personal = write_private_context(item, args.baseline_store, args.outcome_store, args.personal_limit)
    manifest["personal_context"] = personal
    instruction = manifest.setdefault("agent_handoff", {}).get("instruction", "")
    manifest["agent_handoff"]["instruction"] = (
        instruction
        + " If personal_context.available is true, read the private sidecar before selecting explanation depth, practical relevance and action recommendations. "
        + "Treat user assertions, experience and personal action outcomes as private context only: never cite them as source evidence, "
        + "never merge them into the public knowledge graph, and keep evidence-backed Knowledge Delta separate from personal novelty/relevance. "
        + "An adopted/rejected personal outcome can adjust what is worth trying next, but it cannot prove or disprove an external claim."
    ).strip()

    mature = (
        state["insight_review_ready"]
        and state["knowledge_delta_ready"]
        and state["learning_prompt_ready"]
        and item.get("status") in {"review", "published"}
    )
    if mature and not args.no_checks:
        ok, results = run_source.run_checks()
        manifest["checks"] = {"ok": ok, "results": results}
        manifest["last_checked_at"] = run_source.now_iso()
        if not ok:
            failed = next((result for result in results if not result["ok"]), None)
            if failed:
                manifest["state"]["next_blocking_action"] = (
                    f"Fix failing repository check: {failed['command']}. Then rerun personalized source orchestration."
                )

    manifest_path = run_source.MANIFESTS / f"{item['id']}.json"
    run_source.dump(manifest_path, manifest)

    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"intake: {item['id']}")
        print(
            f"private context: {personal['private_sidecar']} "
            f"({personal['selected_entries']} baseline entries, {personal['selected_outcomes']} prior outcomes)"
        )
        print(f"baseline revision: {personal['baseline_revision']} / {personal['baseline_fingerprint'][:12]}")
        print(f"outcomes fingerprint: {personal['outcomes_fingerprint'][:12]}")
        print(f"next: {manifest['state']['next_blocking_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
