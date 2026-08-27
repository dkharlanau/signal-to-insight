#!/usr/bin/env python3
"""Validate the physical private source/insight overlay and prove public projections cannot depend on it."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIVATE_ROOT = ROOT / ".local" / "private"
GITIGNORE = ROOT / ".gitignore"
PUBLIC_GRAPH = ROOT / "data" / "knowledge-graph.json"
PUBLIC_INSIGHTS = ROOT / "data" / "insights.json"
PUBLIC_SOURCES = ROOT / "data" / "sources.json"
PUBLIC_DATA_FILES = [
    ROOT / "data" / "inbox.json",
    PUBLIC_SOURCES,
    PUBLIC_INSIGHTS,
    ROOT / "data" / "claim-evidence.json",
    ROOT / "data" / "knowledge-deltas.json",
    ROOT / "data" / "knowledge-reviews.json",
    ROOT / "data" / "prerequisite-maps.json",
    ROOT / "data" / "learning-prompts.json",
    PUBLIC_GRAPH,
    ROOT / "data" / "knowledge-history.json",
    ROOT / "data" / "reanalysis-events.json",
    ROOT / "data" / "source-revisions.json",
    ROOT / "data" / "source-decisions.json",
    ROOT / "data" / "syntheses.json",
]
PUBLIC_OUTPUT_DIRS = [
    ROOT / "explainers",
    ROOT / "library",
    ROOT / "knowledge",
    ROOT / "syntheses",
]
PUBLIC_BUILDERS = [
    ROOT / "scripts" / "build.py",
    ROOT / "scripts" / "build_previews.py",
    ROOT / "scripts" / "build_graph.py",
    ROOT / "scripts" / "build_public_graph.py",
    ROOT / "scripts" / "build_library.py",
    ROOT / "scripts" / "build_syntheses.py",
    ROOT / "scripts" / "build_sitemap.py",
    ROOT / "scripts" / "build_history.py",
    ROOT / "scripts" / "build_reanalysis.py",
]
FORBIDDEN_BUILDER_MARKERS = [".local/private", "private_overlay", "PRIVATE_OVERLAY", "private-source-overlay"]
ALLOWED_INSIGHT_STATUSES = {"review", "archived"}


class PrivateOverlayValidationError(ValueError):
    pass


def load(path: Path, default: dict | None = None) -> dict:
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def text_files(root: Path):
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".html", ".json", ".xml", ".txt", ".md", ".js"}:
            yield path


def unique_ids(items: object, where: str, errors: list[str]) -> dict[str, dict]:
    if not isinstance(items, list):
        errors.append(f"{where} must be a list")
        return {}
    result: dict[str, dict] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{where}[{index}] must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{where}[{index}].id must be a non-empty string")
            continue
        if item_id in result:
            errors.append(f"{where}: duplicate id {item_id}")
        result[item_id] = item
    return result


def private_only_ids(private: dict[str, dict], public: dict[str, dict]) -> set[str]:
    return set(private) - set(public)


def validate_static_repo_boundary(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    ignore_path = root / ".gitignore"
    ignore = ignore_path.read_text(encoding="utf-8") if ignore_path.exists() else ""
    if ".local/" not in {line.strip() for line in ignore.splitlines()}:
        errors.append(".gitignore must contain an exact .local/ rule")

    for builder in PUBLIC_BUILDERS:
        candidate = root / builder.relative_to(ROOT) if root != ROOT else builder
        if not candidate.exists():
            errors.append(f"missing public builder: {candidate.relative_to(root)}")
            continue
        text = candidate.read_text(encoding="utf-8")
        hits = [marker for marker in FORBIDDEN_BUILDER_MARKERS if marker in text]
        if hits:
            errors.append(f"public builder {candidate.relative_to(root)} references private overlay: {hits}")
    return errors


def validate_overlay(private_root: Path, public_root: Path = ROOT) -> list[str]:
    errors = validate_static_repo_boundary(public_root)
    if not private_root.exists():
        return errors

    try:
        private_root.resolve().relative_to((public_root / ".local").resolve())
    except ValueError:
        errors.append("private overlay root must stay under .local/")

    data = private_root / "data"
    inbox_data = load(data / "inbox.json", {"items": []})
    sources_data = load(data / "sources.json", {"sources": []})
    insights_data = load(data / "insights.json", {"insights": []})
    graph_data = load(data / "knowledge-graph.json", {"concepts": [], "relations": []})

    inbox = unique_ids(inbox_data.get("items"), "private inbox.items", errors)
    private_sources = unique_ids(sources_data.get("sources"), "private sources.sources", errors)
    private_insights = unique_ids(insights_data.get("insights"), "private insights.insights", errors)
    private_concepts = unique_ids(graph_data.get("concepts"), "private graph.concepts", errors)
    private_relations = unique_ids(graph_data.get("relations"), "private graph.relations", errors)

    public_sources_data = load(public_root / "data" / "sources.json", {"sources": []})
    public_insights_data = load(public_root / "data" / "insights.json", {"insights": []})
    public_graph_data = load(public_root / "data" / "knowledge-graph.json", {"concepts": [], "relations": []})
    public_sources = unique_ids(public_sources_data.get("sources"), "public sources.sources", errors)
    public_insights = unique_ids(public_insights_data.get("insights"), "public insights.insights", errors)
    public_concepts = unique_ids(public_graph_data.get("concepts"), "public graph.concepts", errors)
    public_relations = unique_ids(public_graph_data.get("relations"), "public graph.relations", errors)

    for item_id, item in inbox.items():
        if item.get("status") == "published":
            errors.append(f"private intake {item_id} cannot have status=published")
        source_id = item.get("source_id")
        if source_id is not None and source_id not in private_sources:
            errors.append(f"private intake {item_id} references non-private source_id {source_id}")
        insight_id = item.get("insight_id")
        if insight_id is not None and insight_id not in private_insights:
            errors.append(f"private intake {item_id} references non-private insight_id {insight_id}")

    for source_id, source in private_sources.items():
        if "public" in source:
            errors.append(f"private source {source_id} must not contain a public projection object")
        if source_id in public_sources:
            errors.append(f"private source id collides with public registry: {source_id}; export must create/review a public case separately")

    for insight_id, insight in private_insights.items():
        if insight.get("status") not in ALLOWED_INSIGHT_STATUSES:
            errors.append(f"private insight {insight_id} status must be review/archived, not {insight.get('status')!r}")
        if "public" in insight:
            errors.append(f"private insight {insight_id} must not contain a public projection object")
        source_id = insight.get("source_id")
        if source_id not in private_sources:
            errors.append(f"private insight {insight_id} must reference a private source, got {source_id!r}")
        if insight_id in public_insights:
            errors.append(f"private insight id collides with public registry: {insight_id}; use explicit export/review instead")

    all_concepts = set(private_concepts) | set(public_concepts)
    all_evidence_insights = set(private_insights) | set(public_insights)
    for concept_id, concept in private_concepts.items():
        if "public" in concept:
            errors.append(f"private concept {concept_id} must not contain a public projection object")
        for insight_id in concept.get("insight_ids") or []:
            if insight_id not in all_evidence_insights:
                errors.append(f"private concept {concept_id} references unknown insight {insight_id}")
        if concept_id in public_concepts:
            errors.append(f"private concept id collides with public graph: {concept_id}; keep private overlay IDs distinct until explicit export")

    for relation_id, relation in private_relations.items():
        if "public" in relation:
            errors.append(f"private relation {relation_id} must not contain a public projection object")
        if relation.get("from") not in all_concepts or relation.get("to") not in all_concepts:
            errors.append(f"private relation {relation_id} has dangling concept endpoint")
        for insight_id in relation.get("evidence_insights") or []:
            if insight_id not in all_evidence_insights:
                errors.append(f"private relation {relation_id} references unknown evidence insight {insight_id}")
        if relation_id in public_relations:
            errors.append(f"private relation id collides with public graph: {relation_id}")

    bundles = data / "research-bundles"
    if bundles.exists():
        for path in sorted(bundles.glob("*.json")):
            bundle = load(path)
            intake_id = bundle.get("intake_id")
            item = inbox.get(intake_id)
            if item is None:
                errors.append(f"private bundle {path.name} references unknown private intake {intake_id!r}")
                continue
            if (bundle.get("inspection") or {}).get("full_content_committed") is not False:
                errors.append(f"private bundle {path.name} must keep full_content_committed=false")
            canonical = (bundle.get("source") or {}).get("canonical_url")
            if canonical != item.get("source_url"):
                errors.append(f"private bundle {path.name} canonical URL differs from private intake")

    private_only = (
        private_only_ids(private_sources, public_sources)
        | private_only_ids(private_insights, public_insights)
        | private_only_ids(private_concepts, public_concepts)
        | private_only_ids(private_relations, public_relations)
    )
    if private_only:
        searchable_files: list[Path] = []
        for relative in [
            "data/inbox.json", "data/sources.json", "data/insights.json", "data/claim-evidence.json",
            "data/knowledge-deltas.json", "data/knowledge-reviews.json", "data/prerequisite-maps.json",
            "data/learning-prompts.json", "data/knowledge-graph.json", "data/knowledge-history.json",
            "data/reanalysis-events.json", "data/source-revisions.json", "data/source-decisions.json", "data/syntheses.json",
        ]:
            path = public_root / relative
            if path.exists():
                searchable_files.append(path)
        for directory in ["explainers", "library", "knowledge", "syntheses"]:
            searchable_files.extend(list(text_files(public_root / directory) or []))

        for path in searchable_files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            leaked = sorted(item_id for item_id in private_only if item_id and item_id in text)
            if leaked:
                errors.append(f"public/versioned file {path.relative_to(public_root)} contains private-only ids: {leaked[:5]}")

        public_graph_text = json.dumps(public_graph_data, ensure_ascii=False)
        leaked_graph_ids = sorted(item_id for item_id in private_only if item_id in public_graph_text)
        if leaked_graph_ids:
            errors.append(f"public graph depends on private-only ids: {leaked_graph_ids[:10]}")

    exports = private_root / "exports"
    if exports.exists():
        for path in sorted(exports.glob("*.json")):
            candidate = load(path)
            if candidate.get("public_write_allowed") is not False:
                errors.append(f"private export {path.name} must keep public_write_allowed=false")
            insight = candidate.get("insight") or {}
            if insight.get("status") != "review":
                errors.append(f"private export {path.name} must stop at insight status=review")
            if not isinstance(candidate.get("redaction"), dict):
                errors.append(f"private export {path.name} must include redaction metadata")

    return errors


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".local").mkdir(parents=True)
        (root / ".gitignore").write_text(".local/\n", encoding="utf-8")
        scripts = root / "scripts"
        scripts.mkdir()
        for builder in PUBLIC_BUILDERS:
            (scripts / builder.name).write_text("# public-only fixture builder\n", encoding="utf-8")
        data = root / "data"
        data.mkdir()
        for name, payload in {
            "sources.json": {"sources": []},
            "insights.json": {"insights": []},
            "knowledge-graph.json": {"concepts": [], "relations": []},
            "inbox.json": {"items": []},
            "claim-evidence.json": {"records": []},
            "knowledge-deltas.json": {"records": []},
            "knowledge-reviews.json": {"reviews": []},
            "prerequisite-maps.json": {"records": []},
            "learning-prompts.json": {"records": []},
            "knowledge-history.json": {"entities": []},
            "reanalysis-events.json": {"events": []},
            "source-revisions.json": {"sources": []},
            "source-decisions.json": {"records": []},
            "syntheses.json": {"records": []},
        }.items():
            (data / name).write_text(json.dumps(payload), encoding="utf-8")

        private_root = root / ".local" / "private"
        private_data = private_root / "data"
        (private_data / "research-bundles").mkdir(parents=True)
        sentinel_source = "private-src-leak-sentinel"
        sentinel_insight = "private-insight-leak-sentinel"
        sentinel_concept = "private-concept-leak-sentinel"
        (private_data / "inbox.json").write_text(json.dumps({"items": [{
            "id": "private-intake", "source_url": "https://private.invalid/x", "status": "review",
            "source_id": sentinel_source, "insight_id": sentinel_insight
        }]}), encoding="utf-8")
        (private_data / "sources.json").write_text(json.dumps({"sources": [{
            "id": sentinel_source, "canonical_url": "https://private.invalid/x"
        }]}), encoding="utf-8")
        (private_data / "insights.json").write_text(json.dumps({"insights": [{
            "id": sentinel_insight, "source_id": sentinel_source, "status": "review", "title": "Private"
        }]}), encoding="utf-8")
        (private_data / "knowledge-graph.json").write_text(json.dumps({"concepts": [{
            "id": sentinel_concept, "label": "Private", "summary": "Private", "coverage": "introduced",
            "insight_ids": [sentinel_insight]
        }], "relations": []}), encoding="utf-8")
        (private_data / "research-bundles" / "private-intake.json").write_text(json.dumps({
            "intake_id": "private-intake", "source": {"canonical_url": "https://private.invalid/x"},
            "inspection": {"full_content_committed": False}
        }), encoding="utf-8")

        errors = validate_overlay(private_root, root)
        if errors:
            print("Private overlay self-test failed on safe fixture:")
            for error in errors:
                print(f"- {error}")
            return 1

        (data / "knowledge-graph.json").write_text(json.dumps({
            "concepts": [{"id": "public", "summary": sentinel_concept}], "relations": []
        }), encoding="utf-8")
        leaked = validate_overlay(private_root, root)
        if not any("private-only ids" in error or "public graph depends" in error for error in leaked):
            print("Private overlay self-test failed: public graph leak was not detected")
            return 1

        (data / "knowledge-graph.json").write_text(json.dumps({"concepts": [], "relations": []}), encoding="utf-8")
        (scripts / "build.py").write_text("from private_overlay import combined_context\n", encoding="utf-8")
        coupled = validate_overlay(private_root, root)
        if not any("references private overlay" in error for error in coupled):
            print("Private overlay self-test failed: public builder/private overlay coupling was accepted")
            return 1

    print("Private overlay validation self-test passed; private-only IDs and builder coupling cannot reach public projections.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    try:
        errors = validate_overlay(args.private_root)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Private overlay validation failed: {exc}")
        return 1
    if errors:
        print(f"Private overlay validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    state = "overlay present and isolated" if args.private_root.exists() else "no private overlay present; static isolation guards verified"
    print(f"Private overlay validation passed: {state}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
