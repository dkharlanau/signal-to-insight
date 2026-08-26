#!/usr/bin/env python3
"""Explicitly publish one reviewed multi-source synthesis.

Publication is blocked unless every source insight is already published. This prevents a
review synthesis from promoting review-only evidence into a public claim surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "data" / "syntheses.json"
INSIGHTS = ROOT / "data" / "insights.json"


class PublishSynthesisError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight(synthesis_id: str, confirm: str, reviewed_by: str, review_note: str) -> tuple[dict, dict]:
    if confirm != f"PUBLISH_SYNTHESIS:{synthesis_id}":
        raise PublishSynthesisError(f"confirmation must exactly equal PUBLISH_SYNTHESIS:{synthesis_id}")
    if not reviewed_by.strip():
        raise PublishSynthesisError("reviewed_by is required")
    if not review_note.strip():
        raise PublishSynthesisError("review_note is required")

    data = load(SYN)
    insights = {item["id"]: item for item in load(INSIGHTS).get("insights", [])}
    synthesis = next((item for item in data.get("records", []) if item.get("id") == synthesis_id), None)
    if synthesis is None:
        raise PublishSynthesisError(f"synthesis not found: {synthesis_id}")
    if synthesis.get("status") != "review":
        raise PublishSynthesisError(f"synthesis must be in review, found {synthesis.get('status')!r}")

    missing: list[str] = []
    not_published: list[str] = []
    for insight_id in synthesis.get("source_insight_ids", []):
        insight = insights.get(insight_id)
        if insight is None:
            missing.append(insight_id)
        elif insight.get("status") != "published":
            not_published.append(f"{insight_id} ({insight.get('status')})")
    if missing:
        raise PublishSynthesisError(f"source insights missing: {missing}")
    if not_published:
        raise PublishSynthesisError(
            "all source insights must be published before synthesis publication; blocked by: "
            + ", ".join(not_published)
        )
    return data, synthesis


def publish(
    synthesis_id: str,
    confirm: str,
    reviewed_by: str,
    review_note: str,
    dry_run: bool = False,
) -> int:
    data, synthesis = preflight(synthesis_id, confirm, reviewed_by, review_note)
    if dry_run:
        print(f"Synthesis publication preflight passed for {synthesis_id}; no files changed.")
        return 0

    synthesis["status"] = "published"
    synthesis["evidence_mode"] = "published_only"
    provenance = synthesis.setdefault("provenance", {})
    provenance["reviewed_at"] = date.today().isoformat()
    provenance["reviewed_by"] = reviewed_by
    provenance["review_note"] = review_note
    dump(SYN, data)
    print(f"published synthesis data transition: {synthesis_id}")
    return 0


def self_test() -> int:
    data = load(SYN)
    review = next((item for item in data.get("records", []) if item.get("status") == "review"), None)
    if review is None:
        print("Synthesis publication self-test skipped: no review synthesis exists.")
        return 0
    synthesis_id = review["id"]

    try:
        preflight(synthesis_id, "WRONG", "self-test", "boundary test")
    except PublishSynthesisError:
        pass
    else:
        print("Synthesis publication self-test failed: incorrect confirmation was accepted.")
        return 1

    insights = {item["id"]: item for item in load(INSIGHTS).get("insights", [])}
    blockers = [
        insight_id
        for insight_id in review.get("source_insight_ids", [])
        if insights.get(insight_id, {}).get("status") != "published"
    ]
    if blockers:
        try:
            preflight(
                synthesis_id,
                f"PUBLISH_SYNTHESIS:{synthesis_id}",
                "self-test",
                "Verify review-only evidence cannot be promoted.",
            )
        except PublishSynthesisError as exc:
            if "all source insights must be published" not in str(exc):
                print(f"Synthesis publication self-test failed with unexpected blocker: {exc}")
                return 1
        else:
            print("Synthesis publication self-test failed: review-only source evidence was accepted.")
            return 1
    else:
        try:
            publish(
                synthesis_id,
                f"PUBLISH_SYNTHESIS:{synthesis_id}",
                "self-test",
                "Dry-run human publication boundary.",
                dry_run=True,
            )
        except PublishSynthesisError as exc:
            print(f"Synthesis publication self-test failed: {exc}")
            return 1

    print("Synthesis publication self-test passed; explicit confirmation and published-source boundaries hold.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthesis")
    parser.add_argument("--confirm")
    parser.add_argument("--reviewed-by", default="")
    parser.add_argument("--review-note", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.synthesis:
        parser.error("--synthesis is required unless --self-test is used")
    try:
        return publish(
            args.synthesis,
            args.confirm or "",
            args.reviewed_by,
            args.review_note,
            dry_run=args.dry_run,
        )
    except PublishSynthesisError as exc:
        print(f"Synthesis publication blocked: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
