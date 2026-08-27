#!/usr/bin/env python3
"""Prepare human publication review cards without publishing automatically.

Issue #38 is intentionally human-gated. This runner fixes the candidate chain, assembles the
existing evidence into one review surface, stores human dispositions only under `.local/`, and
prints the existing explicit publish commands only after a local `approve` record exists.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data" / "publication-review-plan.json"
INBOX = ROOT / "data" / "inbox.json"
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"
SYNTHeses = ROOT / "data" / "syntheses.json"
DELTAS = ROOT / "data" / "knowledge-deltas.json"
CLAIMS = ROOT / "data" / "claim-evidence.json"
PREREQS = ROOT / "data" / "prerequisite-maps.json"
DECISIONS = ROOT / "data" / "source-decisions.json"
BUNDLES = ROOT / "data" / "research-bundles"
DEFAULT_STORE = ROOT / ".local" / "publication-review.json"
STORE_VERSION = "1.0.0"
VERDICTS = {"approve", "hold", "do_not_publish"}
INSIGHT_CHECKS = {
    "central_model",
    "claim_provenance",
    "limitations",
    "knowledge_delta",
    "source_decision",
    "visual_usefulness",
}
SYNTHESIS_CHECKS = {
    "central_model",
    "source_evidence",
    "false_contradictions",
    "unresolved_gaps",
    "visual_usefulness",
}


class PublicationReviewError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def records_by(path: Path, key: str) -> dict[str, dict]:
    return {
        item[key]: item
        for item in load(path).get("records", [])
        if isinstance(item, dict) and isinstance(item.get(key), str)
    }


def insight_registry() -> dict:
    inbox = {
        item.get("insight_id"): item
        for item in load(INBOX).get("items", [])
        if isinstance(item, dict) and item.get("insight_id")
    }
    return {
        "inbox": inbox,
        "sources": {
            item.get("id"): item
            for item in load(SOURCES).get("sources", [])
            if isinstance(item, dict) and item.get("id")
        },
        "insights": {
            item.get("id"): item
            for item in load(INSIGHTS).get("insights", [])
            if isinstance(item, dict) and item.get("id")
        },
        "deltas": records_by(DELTAS, "insight_id"),
        "claims": records_by(CLAIMS, "insight_id"),
        "prereqs": records_by(PREREQS, "insight_id"),
        "decisions": records_by(DECISIONS, "insight_id"),
    }


def synthesis_records() -> dict[str, dict]:
    data = load(SYNTHeses)
    values = data.get("records")
    if not isinstance(values, list):
        values = data.get("syntheses", [])
    return {
        item.get("id"): item
        for item in values
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def synthesis_dependencies(record: dict) -> list[str]:
    for key in ("source_insight_ids", "insight_ids", "source_insights"):
        values = record.get(key)
        if isinstance(values, list) and all(isinstance(item, str) for item in values):
            return values
    sources = record.get("sources")
    if isinstance(sources, list):
        result = []
        for item in sources:
            if isinstance(item, dict) and isinstance(item.get("insight_id"), str):
                result.append(item["insight_id"])
        if result:
            return result
    return []


def insight_surface(insight: dict) -> Path:
    slug = insight.get("slug")
    if not isinstance(slug, str) or not slug:
        raise PublicationReviewError(f"insight has no slug: {insight.get('id')}")
    if insight.get("status") == "published":
        path = ROOT / "explainers" / slug / "index.html"
    else:
        path = ROOT / "previews" / slug / "index.html"
    if not path.exists():
        raise PublicationReviewError(f"review surface missing: {path.relative_to(ROOT)}")
    return path


def synthesis_surface(record: dict) -> Path | None:
    slug = record.get("slug") or record.get("id")
    if not isinstance(slug, str) or not slug:
        return None
    candidates = [
        ROOT / "syntheses" / slug / "index.html",
        ROOT / "previews" / "syntheses" / slug / "index.html",
        ROOT / "previews" / slug / "index.html",
    ]
    for path in candidates:
        if path.exists():
            return path
    # Keep the lookup deterministic but tolerant of a different generated root.
    matches = sorted(
        path
        for path in ROOT.glob(f"*/{slug}/index.html")
        if ".local" not in path.parts
    )
    return matches[0] if matches else None


def unresolved_prior(insight_id: str, state: dict) -> list[str]:
    intake = state["inbox"].get(insight_id)
    if not intake:
        return []
    bundle_path = BUNDLES / f"{intake['id']}.json"
    if not bundle_path.exists():
        return ["research_bundle_missing"]
    bundle = load(bundle_path)
    prior = bundle.get("prior_knowledge")
    if not isinstance(prior, dict) or prior.get("classification_required") is not True:
        return []
    return [
        str(item.get("concept_id"))
        for item in prior.get("matches", [])
        if item.get("relationship_to_source") == "unclassified"
    ]


def validate_plan() -> dict:
    plan = load(PLAN)
    errors: list[str] = []
    if plan.get("version") != "1.0.0":
        errors.append(f"unsupported plan version: {plan.get('version')!r}")
    state = insight_registry()
    syntheses = synthesis_records()

    insight_ids = plan.get("insight_candidates")
    if not isinstance(insight_ids, list) or len(insight_ids) < 2:
        errors.append("publication review plan requires at least two insight candidates")
        insight_ids = []
    source_types: set[str] = set()
    for insight_id in insight_ids:
        insight = state["insights"].get(insight_id)
        intake = state["inbox"].get(insight_id)
        if insight is None or intake is None:
            errors.append(f"unknown insight candidate: {insight_id}")
            continue
        if insight.get("status") != "review":
            errors.append(f"insight candidate must be review: {insight_id} ({insight.get('status')})")
        source_type = intake.get("source_type")
        if isinstance(source_type, str):
            source_types.add(source_type)
        for label, registry in (
            ("Knowledge Delta", state["deltas"]),
            ("claim evidence", state["claims"]),
            ("prerequisite map", state["prereqs"]),
            ("Source Decision", state["decisions"]),
        ):
            if insight_id not in registry:
                errors.append(f"{insight_id}: missing {label}")
        if not insight.get("limitations"):
            errors.append(f"{insight_id}: no limitations to review")
        visual = insight.get("visual_plan") or {}
        if not isinstance(visual.get("dominant"), dict):
            errors.append(f"{insight_id}: no dominant visual plan to review")
        try:
            insight_surface(insight)
        except PublicationReviewError as exc:
            errors.append(str(exc))
        unresolved = unresolved_prior(insight_id, state)
        if unresolved:
            errors.append(f"{insight_id}: unclassified prior knowledge {unresolved}")
    if len(source_types) < 2:
        errors.append(f"insight proof corpus must span at least two source types, found {sorted(source_types)}")

    synthesis_ids = plan.get("synthesis_candidates")
    if not isinstance(synthesis_ids, list) or not synthesis_ids:
        errors.append("publication review plan requires at least one synthesis candidate")
        synthesis_ids = []
    synthesis_dependencies_by_id: dict[str, list[str]] = {}
    for synthesis_id in synthesis_ids:
        record = syntheses.get(synthesis_id)
        if record is None:
            errors.append(f"unknown synthesis candidate: {synthesis_id}")
            continue
        if record.get("status") != "review":
            errors.append(f"synthesis candidate must be review: {synthesis_id} ({record.get('status')})")
        deps = synthesis_dependencies(record)
        synthesis_dependencies_by_id[synthesis_id] = deps
        if not deps:
            errors.append(f"{synthesis_id}: source insight dependencies are not explicit")
        if not isinstance(record.get("visual_plan"), dict):
            errors.append(f"{synthesis_id}: no synthesis visual plan to review")
        # A missing generated synthesis surface is a review warning rather than a plan error;
        # the structured record can still be reviewed, but publish_synthesis will keep failing
        # until its normal generated-page preflight is satisfied.

    if errors:
        raise PublicationReviewError("\n".join(errors))
    return {
        "insight_candidates": len(insight_ids),
        "source_types": sorted(source_types),
        "synthesis_candidates": len(synthesis_ids),
        "synthesis_dependencies": synthesis_dependencies_by_id,
    }


def load_store(path: Path) -> dict:
    if not path.exists():
        return {"version": STORE_VERSION, "records": []}
    data = load(path)
    if data.get("version") != STORE_VERSION or not isinstance(data.get("records"), list):
        raise PublicationReviewError(f"unsupported publication review store: {path}")
    return data


def write_store(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def required_checks(kind: str) -> set[str]:
    if kind == "insight":
        return INSIGHT_CHECKS
    if kind == "synthesis":
        return SYNTHESIS_CHECKS
    raise PublicationReviewError("candidate kind must be insight or synthesis")


def parse_checks(raw: str) -> list[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if values == ["all"]:
        return []
    return values


def record_review(
    path: Path,
    kind: str,
    candidate_id: str,
    verdict: str,
    checks_raw: str,
    note: str,
) -> dict:
    validate_plan()
    if verdict not in VERDICTS:
        raise PublicationReviewError(f"verdict must be one of {sorted(VERDICTS)}")
    if not note.strip():
        raise PublicationReviewError("human review note is required")
    required = required_checks(kind)
    raw = [item.strip() for item in checks_raw.split(",") if item.strip()]
    checks = sorted(required) if raw == ["all"] else sorted(set(raw))
    unknown = set(checks) - required
    if unknown:
        raise PublicationReviewError(f"unknown review checks for {kind}: {sorted(unknown)}")
    if verdict == "approve" and set(checks) != required:
        missing = sorted(required - set(checks))
        raise PublicationReviewError(f"approve requires all review checks; missing {missing}")

    plan = load(PLAN)
    allowed = set(plan["insight_candidates"] if kind == "insight" else plan["synthesis_candidates"])
    if candidate_id not in allowed:
        raise PublicationReviewError(f"candidate is not in committed publication review plan: {candidate_id}")

    store = load_store(path)
    record_id = f"{kind}:{candidate_id}"
    item = {
        "id": record_id,
        "kind": kind,
        "candidate_id": candidate_id,
        "verdict": verdict,
        "checks": checks,
        "note": note.strip(),
        "reviewed_at": now_iso(),
    }
    existing = next((row for row in store["records"] if row.get("id") == record_id), None)
    if existing is None:
        store["records"].append(item)
    else:
        existing.update(item)
    write_store(path, store)
    return item


def latest_review(path: Path, kind: str, candidate_id: str) -> dict | None:
    store = load_store(path)
    record_id = f"{kind}:{candidate_id}"
    return next((item for item in store["records"] if item.get("id") == record_id), None)


def evidence_lines(claim_record: dict) -> list[str]:
    rows = []
    for claim in claim_record.get("claims", []):
        origins = []
        for evidence in claim.get("evidence", []):
            if evidence.get("kind") == "prior_insight":
                origins.append(f"prior:{evidence.get('insight_id')} @ {evidence.get('locator')}")
            else:
                origins.append(f"{evidence.get('kind')} @ {evidence.get('locator')}")
        rows.append(
            f"- {claim.get('id')} [{claim.get('origin')}/{claim.get('status')}]: {claim.get('text')}"
            + (" | " + "; ".join(origins) if origins else "")
        )
    return rows


def show_insight_card(insight_id: str) -> None:
    state = insight_registry()
    insight = state["insights"].get(insight_id)
    intake = state["inbox"].get(insight_id)
    if insight is None or intake is None:
        raise PublicationReviewError(f"unknown insight: {insight_id}")
    if insight_id not in load(PLAN).get("insight_candidates", []):
        raise PublicationReviewError(f"insight is not in publication review plan: {insight_id}")
    delta = state["deltas"][insight_id]
    claims = state["claims"][insight_id]
    prereq = state["prereqs"][insight_id]
    decision = state["decisions"][insight_id]
    source = state["sources"].get(insight.get("source_id"), {})
    model = insight.get("whole_source_map") or {}
    coherence = insight.get("coherence_review") or {}
    visual = insight.get("visual_plan") or {}
    surface = insight_surface(insight)

    print(f"PUBLICATION REVIEW — {insight['title']}")
    print(f"ID: {insight_id} | status={insight.get('status')} | type={intake.get('source_type')}")
    print(f"Preview: {surface.relative_to(ROOT)}")
    print(f"Source: {source.get('canonical_url') or intake.get('source_url')}")
    print("\nCENTRAL MODEL")
    print(f"Problem: {model.get('problem')}")
    print(f"Thesis: {model.get('thesis')}")
    for step in coherence.get("central_chain", []):
        print(f"- {step}")
    print("\nCLAIM PROVENANCE")
    for line in evidence_lines(claims):
        print(line)
    print("\nLIMITATIONS / OPEN GAPS")
    for item in insight.get("limitations", []):
        print(f"- {item}")
    for item in coherence.get("open_gaps", []):
        print(f"- OPEN: {item}")
    print("\nKNOWLEDGE DELTA")
    print(delta.get("summary"))
    for item in delta.get("items", []):
        print(f"- {item.get('relationship')} · {item.get('concept_id')}: {item.get('interpretation')}")
    if delta.get("suppressed_prior_matches"):
        print("Suppressed prior matches: " + ", ".join(delta["suppressed_prior_matches"]))
    print("\nPREREQUISITES")
    print(prereq.get("summary"))
    for item in prereq.get("items", []):
        print(f"- {item.get('priority')} · {item.get('concept_id')} · {item.get('state')}")
    print("\nSOURCE DECISION")
    print(f"{decision.get('decision')}: {decision.get('rationale')}")
    print("\nVISUAL")
    dominant = visual.get("dominant") or {}
    print(f"Dominant: {dominant.get('type')} · {dominant.get('title')}")
    print(f"Image: {(visual.get('image') or {}).get('needed')} · {(visual.get('image') or {}).get('reason')}")
    unresolved = unresolved_prior(insight_id, state)
    print("\nSTRUCTURAL BLOCKERS")
    print("- none" if not unresolved else "- unclassified prior knowledge: " + ", ".join(unresolved))
    print("\nApproval requires checks: " + ", ".join(sorted(INSIGHT_CHECKS)))


def show_synthesis_card(synthesis_id: str) -> None:
    record = synthesis_records().get(synthesis_id)
    if record is None:
        raise PublicationReviewError(f"unknown synthesis: {synthesis_id}")
    if synthesis_id not in load(PLAN).get("synthesis_candidates", []):
        raise PublicationReviewError(f"synthesis is not in publication review plan: {synthesis_id}")
    deps = synthesis_dependencies(record)
    statuses = {
        item.get("id"): item.get("status")
        for item in load(INSIGHTS).get("insights", [])
        if isinstance(item, dict)
    }
    surface = synthesis_surface(record)
    print(f"SYNTHESIS PUBLICATION REVIEW — {record.get('title')}")
    print(f"ID: {synthesis_id} | status={record.get('status')}")
    print(f"Surface: {surface.relative_to(ROOT) if surface else 'not generated / structured review only'}")
    print("\nSOURCE DEPENDENCIES")
    for insight_id in deps:
        print(f"- {insight_id}: {statuses.get(insight_id)}")
    print("\nCENTRAL MODEL")
    print(record.get("one_liner") or record.get("summary") or record.get("thesis"))
    for key in ("layer_model", "consensus", "core_model", "architecture"):
        value = record.get(key)
        if value:
            print(f"{key}: {json.dumps(value, ensure_ascii=False, indent=2)}")
    print("\nSOURCE CONTRIBUTION / EVIDENCE")
    for key in ("source_contributions", "contribution_evidence", "evidence", "claim_evidence"):
        value = record.get(key)
        if value:
            print(f"{key}: {json.dumps(value, ensure_ascii=False, indent=2)}")
    print("\nFALSE CONTRADICTIONS")
    print(json.dumps(record.get("false_contradictions", []), ensure_ascii=False, indent=2))
    print("\nUNRESOLVED GAPS")
    print(json.dumps(record.get("unresolved_gaps", []), ensure_ascii=False, indent=2))
    print("\nVISUAL")
    print(json.dumps(record.get("visual_plan", {}), ensure_ascii=False, indent=2))
    blockers = [insight_id for insight_id in deps if statuses.get(insight_id) != "published"]
    print("\nPUBLISH BLOCKERS")
    if blockers:
        print("- source insights not published: " + ", ".join(blockers))
    else:
        print("- none from source insight status")
    print("\nApproval requires checks: " + ", ".join(sorted(SYNTHESIS_CHECKS)))


def publish_command(kind: str, candidate_id: str, reviewed_by: str, store_path: Path) -> str:
    if not reviewed_by.strip():
        raise PublicationReviewError("--reviewed-by is required to produce a publish command")
    review = latest_review(store_path, kind, candidate_id)
    if review is None or review.get("verdict") != "approve":
        raise PublicationReviewError("local human review must have verdict=approve before a publish command is produced")
    checks = set(review.get("checks", []))
    missing = required_checks(kind) - checks
    if missing:
        raise PublicationReviewError(f"approved review is missing checks: {sorted(missing)}")
    note = review["note"]
    if kind == "insight":
        insight = insight_registry()["insights"].get(candidate_id)
        if insight is None or insight.get("status") != "review":
            raise PublicationReviewError(f"insight must still be review before publication: {candidate_id}")
        return (
            "python scripts/publish_reviewed.py "
            f"--insight {shlex.quote(candidate_id)} "
            f"--confirm {shlex.quote('PUBLISH:' + candidate_id)} "
            f"--reviewed-by {shlex.quote(reviewed_by)} "
            f"--review-note {shlex.quote(note)}"
        )

    record = synthesis_records().get(candidate_id)
    if record is None or record.get("status") != "review":
        raise PublicationReviewError(f"synthesis must still be review before publication: {candidate_id}")
    deps = synthesis_dependencies(record)
    statuses = {
        item.get("id"): item.get("status")
        for item in load(INSIGHTS).get("insights", [])
        if isinstance(item, dict)
    }
    blockers = [insight_id for insight_id in deps if statuses.get(insight_id) != "published"]
    if blockers:
        raise PublicationReviewError(
            "synthesis publish command is blocked until source insights are published: " + ", ".join(blockers)
        )
    return (
        "python scripts/publish_synthesis.py "
        f"--synthesis {shlex.quote(candidate_id)} "
        f"--confirm {shlex.quote('PUBLISH_SYNTHESIS:' + candidate_id)} "
        f"--reviewed-by {shlex.quote(reviewed_by)} "
        f"--review-note {shlex.quote(note)}"
    )


def status(store_path: Path) -> dict:
    plan = load(PLAN)
    store = load_store(store_path)
    by_id = {item.get("id"): item for item in store.get("records", [])}
    state = insight_registry()
    syntheses = synthesis_records()
    rows = []
    for insight_id in plan.get("insight_candidates", []):
        review = by_id.get(f"insight:{insight_id}")
        rows.append(
            {
                "kind": "insight",
                "candidate_id": insight_id,
                "repository_status": (state["insights"].get(insight_id) or {}).get("status"),
                "review_verdict": review.get("verdict") if review else "not_reviewed",
            }
        )
    for synthesis_id in plan.get("synthesis_candidates", []):
        review = by_id.get(f"synthesis:{synthesis_id}")
        rows.append(
            {
                "kind": "synthesis",
                "candidate_id": synthesis_id,
                "repository_status": (syntheses.get(synthesis_id) or {}).get("status"),
                "review_verdict": review.get("verdict") if review else "not_reviewed",
            }
        )
    return {"issue": plan.get("issue"), "candidates": rows}


def self_test() -> int:
    try:
        summary = validate_plan()
    except PublicationReviewError as exc:
        print(f"publication review self-test failed: {exc}")
        return 1
    if summary["insight_candidates"] < 2 or len(summary["source_types"]) < 2:
        print("publication review self-test failed: proof corpus insight sample is not diverse")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "review.json"
        candidate = load(PLAN)["insight_candidates"][0]
        try:
            record_review(store, "insight", candidate, "approve", "central_model", "synthetic")
        except PublicationReviewError:
            pass
        else:
            print("publication review self-test failed: approve accepted incomplete checks")
            return 1
        item = record_review(store, "insight", candidate, "approve", "all", "synthetic review")
        if set(item["checks"]) != INSIGHT_CHECKS:
            print("publication review self-test failed: approve did not persist all checks")
            return 1
        command = publish_command("insight", candidate, "self-test", store)
        if f"PUBLISH:{candidate}" not in command or "publish_reviewed.py" not in command:
            print("publication review self-test failed: approved insight did not produce explicit publish command")
            return 1

        synthesis_id = load(PLAN)["synthesis_candidates"][0]
        record_review(store, "synthesis", synthesis_id, "approve", "all", "synthetic synthesis review")
        try:
            publish_command("synthesis", synthesis_id, "self-test", store)
        except PublicationReviewError as exc:
            # This is the current expected state: source insights are still review. The test
            # proves an approval record cannot bypass repository publication dependencies.
            if "source insights are published" not in str(exc):
                print(f"publication review self-test failed with unexpected synthesis blocker: {exc}")
                return 1
        else:
            print("publication review self-test failed: synthesis command bypassed review-source publication dependencies")
            return 1

    print(
        "publication review self-test passed; fixed diverse candidates, complete-check approval, "
        "local-only dispositions and explicit dependency-gated publish commands work."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-plan")
    validate.add_argument("--json", action="store_true")

    card = sub.add_parser("card")
    card.add_argument("--kind", choices=["insight", "synthesis"], required=True)
    card.add_argument("--candidate", required=True)

    review = sub.add_parser("record")
    review.add_argument("--kind", choices=["insight", "synthesis"], required=True)
    review.add_argument("--candidate", required=True)
    review.add_argument("--verdict", choices=sorted(VERDICTS), required=True)
    review.add_argument("--checks", required=True, help="Comma-separated checks or 'all'")
    review.add_argument("--note", required=True)
    review.add_argument("--store", type=Path, default=DEFAULT_STORE)

    command = sub.add_parser("publish-command")
    command.add_argument("--kind", choices=["insight", "synthesis"], required=True)
    command.add_argument("--candidate", required=True)
    command.add_argument("--reviewed-by", required=True)
    command.add_argument("--store", type=Path, default=DEFAULT_STORE)

    stat = sub.add_parser("status")
    stat.add_argument("--store", type=Path, default=DEFAULT_STORE)
    stat.add_argument("--json", action="store_true")

    sub.add_parser("self-test")

    args = parser.parse_args()
    try:
        if args.command == "self-test":
            return self_test()
        if args.command == "validate-plan":
            result = validate_plan()
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(
                    "Publication review plan passed: "
                    f"{result['insight_candidates']} insights / {len(result['source_types'])} source types / "
                    f"{result['synthesis_candidates']} synthesis candidate(s)."
                )
            return 0
        if args.command == "card":
            validate_plan()
            if args.kind == "insight":
                show_insight_card(args.candidate)
            else:
                show_synthesis_card(args.candidate)
            return 0
        if args.command == "record":
            item = record_review(
                args.store,
                args.kind,
                args.candidate,
                args.verdict,
                args.checks,
                args.note,
            )
            print(json.dumps(item, ensure_ascii=False, indent=2))
            return 0
        if args.command == "publish-command":
            print(publish_command(args.kind, args.candidate, args.reviewed_by, args.store))
            return 0
        if args.command == "status":
            result = status(args.store)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Publication review issue #{result['issue']}")
                for item in result["candidates"]:
                    print(
                        f"- {item['kind']} · {item['candidate_id']} · "
                        f"repo={item['repository_status']} · review={item['review_verdict']}"
                    )
            return 0
    except (PublicationReviewError, json.JSONDecodeError, OSError) as exc:
        print(f"publication review error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
