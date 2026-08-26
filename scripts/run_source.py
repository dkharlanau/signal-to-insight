#!/usr/bin/env python3
"""Prepare/resume one source-to-insight run and report the exact next blocker.

This command orchestrates deterministic repository work only. It does not embed an LLM,
transcription provider or automatic publisher. A capable external research agent consumes
the prepared bundle and writes the normalized artifacts described by AGENTS.md.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from new_source import normalize_url, source_key
from scaffold_bundle import build_bundle

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"
DELTAS = ROOT / "data" / "knowledge-deltas.json"
PROMPTS = ROOT / "data" / "learning-prompts.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
PROFILE = ROOT / "config" / "research-profile.json"
BUNDLES = ROOT / "data" / "research-bundles"
MANIFESTS = ROOT / "data" / "run-manifests"
MANIFEST_VERSION = "1.0.0"


class RunSourceError(ValueError):
    pass


def load(path: Path, default: dict | None = None) -> dict:
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def find_existing_intake(inbox: dict, normalized_url: str, focus: str | None) -> dict | None:
    exact = [
        item
        for item in inbox.get("items", [])
        if normalize_url(item.get("source_url", "")) == normalized_url
        and (item.get("requested_focus") or None) == focus
    ]
    if exact:
        return exact[-1]
    same_source = [
        item
        for item in inbox.get("items", [])
        if normalize_url(item.get("source_url", "")) == normalized_url
    ]
    if focus is None and same_source:
        return same_source[-1]
    return None


def queue_url(url: str, source_type: str, focus: str | None, note: str | None) -> dict:
    normalized = normalize_url(url)
    inbox = load(INBOX)
    existing = find_existing_intake(inbox, normalized, focus)
    if existing is not None:
        return existing

    sources = load(SOURCES)
    registered = next(
        (source for source in sources.get("sources", []) if normalize_url(source.get("canonical_url", "")) == normalized),
        None,
    )

    today = date.today().isoformat()
    base_id = f"intake-{today}-{source_key(normalized)}"
    existing_ids = {item.get("id") for item in inbox.get("items", [])}
    intake_id = base_id
    suffix = 2
    while intake_id in existing_ids:
        intake_id = f"{base_id}-{suffix}"
        suffix += 1

    item = {
        "id": intake_id,
        "source_url": normalized,
        "source_type": source_type,
        "submitted_at": today,
        "requested_focus": focus,
        "status": "queued",
        "source_id": registered.get("id") if registered else None,
        "insight_id": None,
        "notes": note,
    }
    inbox.setdefault("items", []).append(item)
    dump(INBOX, inbox)
    return item


def get_intake(intake_id: str) -> dict:
    inbox = load(INBOX)
    item = next((entry for entry in inbox.get("items", []) if entry.get("id") == intake_id), None)
    if item is None:
        raise RunSourceError(f"intake not found: {intake_id}")
    return item


def ensure_bundle(item: dict) -> tuple[dict, Path, bool]:
    path = BUNDLES / f"{item['id']}.json"
    if path.exists():
        return load(path), path, False
    bundle = build_bundle(item)
    dump(path, bundle)
    return bundle, path, True


def index_by_id(path: Path, key: str) -> dict[str, dict]:
    data = load(path, default={key: []})
    return {item["id"]: item for item in data.get(key, []) if isinstance(item, dict) and item.get("id")}


def record_by_insight(path: Path) -> dict[str, dict]:
    data = load(path, default={"records": []})
    return {
        item["insight_id"]: item
        for item in data.get("records", [])
        if isinstance(item, dict) and item.get("insight_id")
    }


def classify_bundle_state(bundle: dict) -> dict:
    inspection = bundle.get("inspection") or {}
    content_map = bundle.get("content_map") or {}
    prior = bundle.get("prior_knowledge") or {}
    matches = prior.get("matches") or []
    unclassified = [
        item.get("concept_id")
        for item in matches
        if item.get("relationship_to_source") == "unclassified"
    ]
    mapped = bool(content_map.get("problem") and content_map.get("thesis"))
    inspected = inspection.get("method") not in {None, "", "not inspected"} and inspection.get("confidence") != "metadata_only"
    return {
        "inspected": inspected,
        "whole_source_mapped": mapped,
        "prior_knowledge_matches": len(matches),
        "unclassified_prior_concepts": unclassified,
        "prior_knowledge_classified": not unclassified,
    }


def evaluate_state(item: dict, bundle: dict) -> dict:
    sources = index_by_id(SOURCES, "sources")
    insights = index_by_id(INSIGHTS, "insights")
    deltas = record_by_insight(DELTAS)
    prompts = record_by_insight(PROMPTS)
    bundle_state = classify_bundle_state(bundle)

    source_id = item.get("source_id") or bundle.get("source_id")
    insight_id = item.get("insight_id")
    source_registered = bool(source_id and source_id in sources)
    insight = insights.get(insight_id) if insight_id else None
    insight_ready = bool(insight and insight.get("status") in {"review", "published"})
    delta_ready = bool(insight_id and insight_id in deltas)
    prompt_ready = bool(insight_id and insight_id in prompts)

    if not bundle_state["inspected"] or not bundle_state["whole_source_mapped"]:
        next_action = (
            "Research the source with the available external agent/tools, map the whole source, "
            "and replace the metadata-only research bundle fields. Do not draft isolated takeaways first."
        )
    elif not bundle_state["prior_knowledge_classified"]:
        concepts = ", ".join(bundle_state["unclassified_prior_concepts"])
        next_action = (
            "Classify every prior-knowledge candidate as reinforcement, refinement, contradiction, "
            f"new knowledge or not relevant before drafting. Still unclassified: {concepts}."
        )
    elif not source_registered:
        next_action = "Create/update the canonical source registry record and link its source_id back to the intake/bundle."
    elif not insight_id or insight is None:
        next_action = "Create the structured insight record from the coherent source model and link insight_id to the intake."
    elif not insight_ready:
        next_action = f"Bring insight {insight_id} to review-ready state; current status is {insight.get('status')!r}."
    elif not delta_ready:
        next_action = f"Curate data/knowledge-deltas.json for {insight_id}; reject irrelevant prior matches explicitly."
    elif not prompt_ready:
        next_action = f"Author reconstruction/transfer material in data/learning-prompts.json for {insight_id}."
    elif item.get("status") not in {"review", "published"}:
        next_action = f"Synchronize intake status with the review-ready insight; current intake status is {item.get('status')!r}."
    else:
        next_action = "Run validation/generated-output checks. If green, the artifact is ready for human review or explicit publication."

    return {
        "intake_status": item.get("status"),
        "source_id": source_id,
        "insight_id": insight_id,
        "bundle": bundle_state,
        "source_registered": source_registered,
        "insight_review_ready": insight_ready,
        "knowledge_delta_ready": delta_ready,
        "learning_prompt_ready": prompt_ready,
        "next_blocking_action": next_action,
    }


def context_snapshot() -> dict:
    profile = load(PROFILE)
    graph = load(GRAPH)
    return {
        "profile_version": profile.get("profile_version"),
        "graph_version": graph.get("graph_version"),
        "graph_updated_at": graph.get("updated_at"),
    }


def expected_artifacts(item: dict) -> dict:
    return {
        "intake": "data/inbox.json",
        "research_bundle": f"data/research-bundles/{item['id']}.json",
        "source_registry": "data/sources.json",
        "insight_registry": "data/insights.json",
        "knowledge_delta": "data/knowledge-deltas.json",
        "learning_prompt": "data/learning-prompts.json",
        "knowledge_graph": "data/knowledge-graph.json",
        "review_preview": "previews/<insight-slug>/index.html",
        "published_explainer": "explainers/<insight-slug>/index.html",
    }


def write_manifest(item: dict, state: dict, bundle_path: Path, created_bundle: bool) -> dict:
    target = MANIFESTS / f"{item['id']}.json"
    existing = load(target, default={})
    timestamp = now_iso()
    snapshot = context_snapshot()
    initial = existing.get("initial_context") or snapshot
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "intake_id": item["id"],
        "source_url": item["source_url"],
        "source_type": item["source_type"],
        "requested_focus": item.get("requested_focus"),
        "created_at": existing.get("created_at") or timestamp,
        "last_checked_at": timestamp,
        "initial_context": initial,
        "current_context": snapshot,
        "research_bundle": str(bundle_path.relative_to(ROOT)),
        "bundle_created_this_run": created_bundle,
        "expected_artifacts": expected_artifacts(item),
        "state": state,
        "agent_handoff": {
            "contract": "AGENTS.md",
            "instruction": "Use the prepared bundle + prior-knowledge snapshot as context. Inspect the source with available tools, write normalized artifacts, keep full third-party content ephemeral, stop at human review rather than auto-publishing.",
        },
    }
    dump(target, manifest)
    return manifest


def run_checks() -> tuple[bool, list[dict]]:
    commands = [
        [sys.executable, "scripts/validate.py"],
        [sys.executable, "scripts/validate_knowledge_deltas.py"],
        [sys.executable, "scripts/validate_learning_prompts.py"],
        [sys.executable, "scripts/validate_graph.py"],
        [sys.executable, "scripts/validate_bundles.py"],
        [sys.executable, "scripts/build.py", "--check"],
        [sys.executable, "scripts/build_previews.py", "--check"],
    ]
    results: list[dict] = []
    all_ok = True
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        ok = completed.returncode == 0
        all_ok = all_ok and ok
        results.append({
            "command": " ".join(command[1:]),
            "ok": ok,
            "output": (completed.stdout + completed.stderr).strip()[-2000:],
        })
        if not ok:
            break
    return all_ok, results


def self_test() -> int:
    inbox = load(INBOX)
    if not inbox.get("items"):
        print("run_source self-test requires at least one intake")
        return 1
    item = inbox["items"][0]
    bundle_path = BUNDLES / f"{item['id']}.json"
    if not bundle_path.exists():
        print("run_source self-test requires the first intake bundle")
        return 1
    state = evaluate_state(item, load(bundle_path))
    required_keys = {
        "intake_status",
        "source_registered",
        "insight_review_ready",
        "knowledge_delta_ready",
        "learning_prompt_ready",
        "next_blocking_action",
    }
    if not required_keys <= set(state):
        print(f"run_source self-test failed; missing state keys: {sorted(required_keys - set(state))}")
        return 1
    if not state["next_blocking_action"]:
        print("run_source self-test failed; next_blocking_action is empty")
        return 1

    fixture = {
        "id": "intake-run-source-fixture",
        "source_url": "https://example.com/new",
        "source_type": "article",
        "status": "queued",
        "source_id": None,
        "insight_id": None,
    }
    fixture_bundle = build_bundle(fixture, created_at="2026-08-26")
    fixture_state = evaluate_state(fixture, fixture_bundle)
    if "Research the source" not in fixture_state["next_blocking_action"]:
        print(f"run_source self-test failed; unexpected first blocker: {fixture_state['next_blocking_action']}")
        return 1
    print("run_source self-test passed; prepared and mature states expose deterministic next actions.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", help="Intake ID or http(s) source URL")
    parser.add_argument("--type", dest="source_type", default="article", choices=["video", "article", "paper", "podcast", "documentation", "repository", "tool", "product", "course", "presentation", "notes", "system"])
    parser.add_argument("--focus", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--no-checks", action="store_true", help="Skip mature-artifact validation/build checks")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.source:
        parser.error("source URL or intake ID is required unless --self-test is used")

    try:
        focus = args.focus.strip() or None
        note = args.note.strip() or None
        if args.source.startswith("http://") or args.source.startswith("https://"):
            item = queue_url(args.source, args.source_type, focus, note)
        else:
            item = get_intake(args.source)

        bundle, bundle_path, created_bundle = ensure_bundle(item)
        state = evaluate_state(item, bundle)
        manifest = write_manifest(item, state, bundle_path, created_bundle)

        checks = None
        mature = (
            state["insight_review_ready"]
            and state["knowledge_delta_ready"]
            and state["learning_prompt_ready"]
            and item.get("status") in {"review", "published"}
        )
        if mature and not args.no_checks:
            ok, check_results = run_checks()
            checks = {"ok": ok, "results": check_results}
            manifest["checks"] = checks
            manifest["last_checked_at"] = now_iso()
            if not ok:
                failed = next((result for result in check_results if not result["ok"]), None)
                manifest["state"]["next_blocking_action"] = (
                    f"Fix failing repository check: {failed['command']}. "
                    "Then rerun this command to resume from the same intake."
                )
            else:
                manifest["state"]["next_blocking_action"] = (
                    "All deterministic checks are green. Perform human review; publish only through the explicit owner-confirmed publication workflow."
                )
            dump(MANIFESTS / f"{item['id']}.json", manifest)

        if args.json:
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
        else:
            print(f"Run manifest: data/run-manifests/{item['id']}.json")
            print(f"Bundle: {bundle_path.relative_to(ROOT)}")
            print(f"Context: profile {manifest['current_context']['profile_version']} · graph {manifest['current_context']['graph_version']}")
            print(f"Next: {manifest['state']['next_blocking_action']}")
            if checks is not None:
                print(f"Checks: {'green' if checks['ok'] else 'failed'}")
        return 0 if checks is None or checks["ok"] else 1
    except (RunSourceError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"run_source error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
