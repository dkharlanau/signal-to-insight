#!/usr/bin/env python3
"""Explicitly publish one human-reviewed insight after all safety gates pass."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"
BUNDLES = ROOT / "data" / "research-bundles"
PREVIEWS = ROOT / "previews"


class PublishError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bump_patch(version: str) -> str:
    try:
        major, minor, patch = [int(part) for part in version.split(".")]
    except (AttributeError, ValueError):
        raise PublishError(f"invalid graph version: {version!r}")
    return f"{major}.{minor}.{patch + 1}"


def unresolved_prior(bundle: dict) -> list[str]:
    prior = bundle.get("prior_knowledge")
    if not isinstance(prior, dict) or prior.get("classification_required") is not True:
        return []
    return [
        str(match.get("concept_id"))
        for match in prior.get("matches", [])
        if match.get("relationship_to_source") == "unclassified"
    ]


def preflight(
    insight_id: str,
    confirm: str,
    reviewed_by: str,
    review_note: str,
) -> tuple[dict, dict, dict, dict, dict, dict]:
    if confirm != f"PUBLISH:{insight_id}":
        raise PublishError(f"confirmation must exactly equal PUBLISH:{insight_id}")
    if not reviewed_by.strip():
        raise PublishError("reviewed_by is required")
    if not review_note.strip():
        raise PublishError("review_note is required; record what the human review established")

    inbox = load(INBOX)
    sources = load(SOURCES)
    insights = load(INSIGHTS)
    graph = load(GRAPH)

    insight = next((item for item in insights.get("insights", []) if item.get("id") == insight_id), None)
    if insight is None:
        raise PublishError(f"insight not found: {insight_id}")
    if insight.get("status") != "review":
        raise PublishError(f"insight must be in review, found {insight.get('status')!r}")

    source = next(
        (item for item in sources.get("sources", []) if item.get("id") == insight.get("source_id")),
        None,
    )
    if source is None:
        raise PublishError(f"source not found: {insight.get('source_id')}")
    if source.get("published_at") is None and source.get("event_date") is None and not source.get("date_note"):
        raise PublishError("source date is unresolved without date_note")

    intake = next(
        (item for item in inbox.get("items", []) if item.get("insight_id") == insight_id),
        None,
    )
    if intake is None:
        raise PublishError(f"intake not linked to insight: {insight_id}")
    if intake.get("status") != "review":
        raise PublishError(f"intake must be in review, found {intake.get('status')!r}")
    if intake.get("source_id") != source.get("id"):
        raise PublishError("intake source_id differs from insight source")

    coherence = insight.get("coherence_review") or {}
    if coherence.get("prerequisites_complete") is not True:
        raise PublishError("review cannot publish with incomplete prerequisites")
    if coherence.get("source_vs_enrichment_clear") is not True:
        raise PublishError("review cannot publish until source vs enrichment is clear")

    preview = PREVIEWS / str(insight.get("slug")) / "index.html"
    if not preview.exists():
        raise PublishError(f"review preview is missing: {preview.relative_to(ROOT)}")

    bundle_path = BUNDLES / f"{intake['id']}.json"
    if not bundle_path.exists():
        raise PublishError(f"research bundle is missing: {bundle_path.relative_to(ROOT)}")
    bundle = load(bundle_path)
    unresolved = unresolved_prior(bundle)
    if unresolved:
        raise PublishError(f"prior knowledge is still unclassified: {unresolved}")

    statuses = {item.get("id"): item.get("status") for item in insights.get("insights", [])}
    statuses[insight_id] = "published"
    published_after = {item_id for item_id, status in statuses.items() if status == "published"}

    # A mixed concept can become public only if it already has a curated public projection.
    for concept in graph.get("concepts", []):
        linked = list(concept.get("insight_ids", []))
        if insight_id not in linked:
            continue
        nonpublished_after = [item_id for item_id in linked if item_id not in published_after]
        if nonpublished_after and not isinstance(concept.get("public"), dict):
            raise PublishError(
                f"concept '{concept.get('id')}' would mix published and review evidence without a curated public projection"
            )

    # Same rule for a relation whose rationale/evidence is shared with still-unpublished material.
    for relation in graph.get("relations", []):
        evidence = list(relation.get("evidence_insights", []))
        if insight_id not in evidence:
            continue
        nonpublished_after = [item_id for item_id in evidence if item_id not in published_after]
        if nonpublished_after and not isinstance(relation.get("public"), dict):
            raise PublishError(
                f"relation '{relation.get('id')}' would mix published and review evidence without a curated public projection"
            )

    return inbox, sources, insights, graph, insight, intake


def publish(
    insight_id: str,
    confirm: str,
    reviewed_by: str,
    review_note: str,
    dry_run: bool = False,
) -> int:
    inbox, _, insights, graph, insight, intake = preflight(
        insight_id,
        confirm,
        reviewed_by,
        review_note,
    )

    if dry_run:
        print(f"Publish preflight passed for {insight_id}; no files changed.")
        return 0

    today = date.today().isoformat()
    insight["status"] = "published"
    provenance = insight.setdefault("provenance", {})
    provenance["publication_review"] = {
        "approved_by": reviewed_by,
        "approved_at": today,
        "note": review_note,
    }
    intake["status"] = "published"

    statuses = {item.get("id"): item.get("status") for item in insights.get("insights", [])}
    published_after = {item_id for item_id, status in statuses.items() if status == "published"}

    for concept in graph.get("concepts", []):
        linked = list(concept.get("insight_ids", []))
        if insight_id not in linked:
            continue
        nonpublished_after = [item_id for item_id in linked if item_id not in published_after]
        public = concept.get("public")
        if nonpublished_after and isinstance(public, dict):
            evidence = public.setdefault("evidence_insights", [])
            if insight_id not in evidence:
                evidence.append(insight_id)

    for relation in graph.get("relations", []):
        evidence = list(relation.get("evidence_insights", []))
        if insight_id not in evidence:
            continue
        nonpublished_after = [item_id for item_id in evidence if item_id not in published_after]
        public = relation.get("public")
        if nonpublished_after and isinstance(public, dict):
            public_evidence = public.setdefault("evidence_insights", [])
            if insight_id not in public_evidence:
                public_evidence.append(insight_id)

    graph["updated_at"] = today
    graph["graph_version"] = bump_patch(graph.get("graph_version", "0.0.0"))

    dump(INBOX, inbox)
    dump(INSIGHTS, insights)
    dump(GRAPH, graph)
    print(f"published {insight_id}; public artifacts must now be regenerated in the same transaction")
    return 0


def self_test() -> int:
    insights = load(INSIGHTS)
    reviews = [item for item in insights.get("insights", []) if item.get("status") == "review"]
    if not reviews:
        print("Publish self-test requires at least one review insight.")
        return 1

    # Wrong confirmation must always be rejected, independently of whether the selected
    # review item would otherwise pass all publication safety gates.
    first_id = reviews[0]["id"]
    try:
        preflight(first_id, "WRONG", "self-test", "self-test review")
    except PublishError:
        pass
    else:
        print("Publish self-test failed: incorrect confirmation was accepted.")
        return 1

    # Repository state can legitimately contain review items that are not publishable yet
    # (for example, a concept with mixed published/review evidence and no curated public
    # projection). Do not make the self-test depend on which review record appears first.
    blocked: list[str] = []
    for review in reviews:
        insight_id = review["id"]
        try:
            publish(
                insight_id,
                f"PUBLISH:{insight_id}",
                "self-test",
                "Validated source, model, limitations and public projection.",
                dry_run=True,
            )
        except PublishError as exc:
            blocked.append(f"{insight_id}: {exc}")
            continue

        print(
            "Publish self-test passed; wrong confirmation is rejected and at least one "
            f"review item ({insight_id}) passes all explicit publication safety gates."
        )
        return 0

    print("Publish self-test failed: no current review insight passes the positive dry-run path.")
    for item in blocked:
        print(f"- {item}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--insight")
    parser.add_argument("--confirm")
    parser.add_argument("--reviewed-by", default="")
    parser.add_argument("--review-note", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.insight:
        parser.error("--insight is required unless --self-test is used")

    try:
        return publish(
            args.insight,
            args.confirm or "",
            args.reviewed_by,
            args.review_note,
            dry_run=args.dry_run,
        )
    except PublishError as exc:
        print(f"Publish blocked: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
