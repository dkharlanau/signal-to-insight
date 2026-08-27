#!/usr/bin/env python3
"""Prepare/resume a source run with an explicit private personal-context sidecar.

This wraps scripts/run_source.py. Public/versioned run manifests receive only baseline
metadata (version, revision and fingerprint); selected personal entries stay under .local/.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import run_source
from personal_baseline import (
    DEFAULT_STORE,
    empty_store,
    load_store,
    select_context,
    upsert_entry,
    write_store,
)

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_CONTEXT_DIR = ROOT / ".local" / "run-context"


def write_private_context(item: dict, store_path: Path, limit: int) -> dict:
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
    snapshot = select_context(data, query, limit=limit)
    target = PRIVATE_CONTEXT_DIR / f"{item['id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "available": bool(snapshot["entries"] or any(snapshot["active_context"].values())),
        "baseline_version": snapshot["baseline_version"],
        "baseline_revision": snapshot["baseline_revision"],
        "baseline_fingerprint": snapshot["baseline_fingerprint"],
        "private_sidecar": str(target.relative_to(ROOT)),
        "selected_entries": len(snapshot["entries"]),
        "privacy": "private_local_not_public_evidence",
    }


def self_test() -> int:
    """Prove that private content stays in the gitignored sidecar, not manifest metadata."""
    global PRIVATE_CONTEXT_DIR
    local_root = ROOT / ".local"
    local_root.mkdir(parents=True, exist_ok=True)
    original_context_dir = PRIVATE_CONTEXT_DIR

    with tempfile.TemporaryDirectory(dir=local_root) as tmp:
        tmp_path = Path(tmp)
        store_path = tmp_path / "personal-baseline.json"
        PRIVATE_CONTEXT_DIR = tmp_path / "run-context"
        try:
            baseline = empty_store()
            secret_concept = "Private fixture concept that must never enter a public manifest"
            secret_note = "Private fixture note"
            upsert_entry(
                baseline,
                secret_concept,
                "partially_known",
                "user_assertion",
                note=secret_note,
                tags=["fixture", "private"],
            )
            write_store(store_path, baseline)

            item = {
                "id": "intake-private-boundary-fixture",
                "source_url": "https://example.com/private-boundary",
                "source_type": "article",
                "requested_focus": "fixture private concept",
            }
            metadata = write_private_context(item, store_path, limit=8)
            sidecar = ROOT / metadata["private_sidecar"]
            sidecar_text = sidecar.read_text(encoding="utf-8")
            metadata_text = json.dumps(metadata, ensure_ascii=False, sort_keys=True)

            if secret_concept not in sidecar_text or secret_note not in sidecar_text:
                print("personalized run self-test failed: private sidecar lost selected context")
                return 1
            if secret_concept in metadata_text or secret_note in metadata_text:
                print("personalized run self-test failed: private content leaked into manifest metadata")
                return 1
            if not metadata["private_sidecar"].startswith(".local/"):
                print("personalized run self-test failed: sidecar is not under .local/")
                return 1
            if not metadata["baseline_fingerprint"] or metadata["baseline_revision"] != 1:
                print("personalized run self-test failed: reproducibility metadata missing")
                return 1
            if metadata["privacy"] != "private_local_not_public_evidence":
                print("personalized run self-test failed: privacy classification missing")
                return 1
        finally:
            PRIVATE_CONTEXT_DIR = original_context_dir

    print("personalized run self-test passed; private context stays in .local and only reproducibility metadata is exposed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", help="Intake ID or http(s) source URL")
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
    parser.add_argument("--personal-limit", type=int, default=8)
    parser.add_argument("--no-checks", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.source:
        parser.error("source URL or intake ID is required unless --self-test is used")

    focus = args.focus.strip() or None
    note = args.note.strip() or None
    if args.source.startswith(("http://", "https://")):
        item = run_source.queue_url(args.source, args.source_type, focus, note)
    else:
        item = run_source.get_intake(args.source)

    bundle, bundle_path, created_bundle = run_source.ensure_bundle(item)
    state = run_source.evaluate_state(item, bundle)
    manifest = run_source.write_manifest(item, state, bundle_path, created_bundle)

    personal = write_private_context(item, args.baseline_store, args.personal_limit)
    manifest["personal_context"] = personal
    instruction = manifest.setdefault("agent_handoff", {}).get("instruction", "")
    manifest["agent_handoff"]["instruction"] = (
        instruction
        + " If personal_context.available is true, read the private sidecar before selecting explanation depth/relevance. "
        + "Treat user assertions and personal experience as private context only: never cite them as source evidence, "
        + "never merge them into the public knowledge graph, and keep evidence-backed Knowledge Delta separate from "
        + "personal novelty/relevance."
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
        print(f"private context: {personal['private_sidecar']} ({personal['selected_entries']} selected entries)")
        print(f"baseline revision: {personal['baseline_revision']} / {personal['baseline_fingerprint'][:12]}")
        print(f"next: {manifest['state']['next_blocking_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())