#!/usr/bin/env python3
"""Signal to Insight repo-local CLI.

This wrapper keeps the existing deterministic scripts as the implementation units while giving a
fresh clone one stable entry point. Research/extraction intelligence remains external by design.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"


class CliError(ValueError):
    pass


def run_script(name: str, args: list[str]) -> int:
    path = SCRIPTS / name
    if not path.exists():
        raise CliError(f"missing repository script: scripts/{name}")
    return subprocess.call([sys.executable, str(path), *args], cwd=ROOT)


def run_many(commands: list[tuple[str, list[str]]]) -> int:
    for name, args in commands:
        print(f"==> {name} {' '.join(args)}".rstrip())
        code = run_script(name, args)
        if code:
            return code
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sti",
        description="Repo-local Signal to Insight CLI. External research agent/provider is still required to inspect real sources.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    intake = sub.add_parser("intake", help="Queue a source URL")
    intake.add_argument("url")
    intake.add_argument("--type", dest="source_type", default="article")
    intake.add_argument("--focus", default="")
    intake.add_argument("--note", default="")

    scaffold = sub.add_parser("scaffold", help="Create the normalized research bundle for an intake")
    scaffold.add_argument("intake_id")

    run = sub.add_parser("run", help="Prepare/resume one source run and report the exact next blocker")
    run.add_argument("source")
    run.add_argument("--type", dest="source_type", default="article")
    run.add_argument("--focus", default="")
    run.add_argument("--note", default="")
    run.add_argument("--no-checks", action="store_true")
    run.add_argument("--json", action="store_true")

    context = sub.add_parser("context", help="Query cumulative public prior knowledge")
    context.add_argument("query")
    context.add_argument("--limit", type=int, default=5)
    context.add_argument("--json", action="store_true")

    preflight = sub.add_parser("preflight", help="Validate one researched review case in an isolated temporary workspace")
    preflight.add_argument("patch", help="Candidate data/case-patches/*.json path")
    preflight.add_argument("--contract", help="Companion case-contract path; inferred when omitted")
    preflight.add_argument("--json", action="store_true")

    evidence = sub.add_parser("evidence", help="Plan the next real human/private validation evidence")
    evidence.add_argument("--json", action="store_true")

    validate = sub.add_parser("validate", help="Run deterministic core repository validation")
    validate.add_argument("--all", action="store_true", help="Also run extended evidence/freshness/history validators and acceptance tests")

    sub.add_parser("build", help="Regenerate deterministic public/review static surfaces")

    publish = sub.add_parser("publish", help="Explicit human review → publish transition")
    publish.add_argument("--insight", required=True)
    publish.add_argument("--confirm", required=True)
    publish.add_argument("--reviewed-by", required=True)
    publish.add_argument("--review-note", required=True)

    args = parser.parse_args()
    try:
        if args.command == "intake":
            forwarded = [args.url, "--type", args.source_type]
            if args.focus:
                forwarded += ["--focus", args.focus]
            if args.note:
                forwarded += ["--note", args.note]
            return run_script("new_source.py", forwarded)

        if args.command == "scaffold":
            return run_script("scaffold_bundle.py", [args.intake_id])

        if args.command == "run":
            forwarded = [args.source, "--type", args.source_type]
            if args.focus:
                forwarded += ["--focus", args.focus]
            if args.note:
                forwarded += ["--note", args.note]
            if args.no_checks:
                forwarded.append("--no-checks")
            if args.json:
                forwarded.append("--json")
            return run_script("run_source.py", forwarded)

        if args.command == "context":
            forwarded = [args.query, "--limit", str(max(1, args.limit))]
            if args.json:
                forwarded.append("--json")
            return run_script("graph_context.py", forwarded)

        if args.command == "preflight":
            forwarded = [args.patch]
            if args.contract:
                forwarded += ["--contract", args.contract]
            if args.json:
                forwarded.append("--json")
            return run_script("preflight_case.py", forwarded)

        if args.command == "evidence":
            forwarded = ["--json"] if args.json else []
            return run_script("evidence_plan.py", forwarded)

        if args.command == "validate":
            core = [
                ("validate.py", []),
                ("validate_graph.py", []),
                ("validate_bundles.py", []),
                ("validate_private_boundary.py", []),
            ]
            if not args.all:
                return run_many(core)
            extended = [
                ("validate_claim_evidence.py", []),
                ("validate_knowledge_deltas.py", []),
                ("validate_knowledge_reviews.py", []),
                ("validate_prerequisites.py", []),
                ("validate_learning_prompts.py", []),
                ("validate_syntheses.py", []),
                ("validate_freshness.py", []),
                ("validate_knowledge_history.py", []),
            ]
            code = run_many(core + extended)
            if code:
                return code
            return subprocess.call(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
                cwd=ROOT,
            )

        if args.command == "build":
            commands = [
                ("build.py", []),
                ("build_previews.py", []),
                ("build_library.py", []),
                ("build_graph.py", []),
                ("build_concepts.py", []),
                ("build_history.py", []),
                ("build_reanalysis.py", []),
                ("build_sitemap.py", []),
                ("build_discovery.py", []),
            ]
            return run_many(commands)

        if args.command == "publish":
            return run_script("publish_reviewed.py", [
                "--insight", args.insight,
                "--confirm", args.confirm,
                "--reviewed-by", args.reviewed_by,
                "--review-note", args.review_note,
            ])
    except CliError as exc:
        print(f"sti: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
