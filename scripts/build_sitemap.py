#!/usr/bin/env python3
"""Generate sitemap.xml from the published Signal to Insight surfaces."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

from build_concepts import build_records

ROOT = Path(__file__).resolve().parents[1]
INSIGHTS = ROOT / "data" / "insights.json"
TARGET = ROOT / "sitemap.xml"
BASE = "https://dkharlanau.github.io/signal-to-insight"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def e(value: str) -> str:
    return html.escape(value, quote=True)


def url_block(loc: str, lastmod: str, changefreq: str, priority: str) -> str:
    return (
        "  <url>\n"
        f"    <loc>{e(loc)}</loc>\n"
        f"    <lastmod>{e(lastmod)}</lastmod>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        "  </url>"
    )


def render() -> str:
    data = load(INSIGHTS)
    published = [item for item in data.get("insights", []) if item.get("status") == "published"]
    published.sort(key=lambda item: item.get("slug", ""))
    concepts = build_records()
    today = date.today().isoformat()

    blocks = [
        url_block(f"{BASE}/", today, "weekly", "1.0"),
        url_block(f"{BASE}/walkthrough/", today, "monthly", "0.95"),
        url_block(f"{BASE}/library/", today, "weekly", "0.9"),
        url_block(f"{BASE}/knowledge/", today, "weekly", "0.9"),
    ]
    for insight in published:
        reviewed = insight.get("provenance", {}).get("publication_review", {}).get("approved_at")
        lastmod = reviewed or insight.get("provenance", {}).get("reviewed_at") or today
        blocks.append(
            url_block(
                f"{BASE}/explainers/{insight['slug']}/",
                lastmod,
                "monthly",
                "0.9",
            )
        )

    for concept in concepts:
        # Concept pages are generated only from published evidence + meaningful graph
        # relations, so they are safe to expose as normal discoverable routes.
        supporting_dates = []
        for insight_id in concept.get("supporting_insight_ids", []):
            insight = next((item for item in published if item.get("id") == insight_id), None)
            if insight:
                supporting_dates.append(
                    insight.get("provenance", {}).get("publication_review", {}).get("approved_at")
                    or insight.get("provenance", {}).get("reviewed_at")
                    or today
                )
        lastmod = max(supporting_dates) if supporting_dates else today
        blocks.append(
            url_block(
                f"{BASE}/knowledge/concepts/{concept['id']}/",
                lastmod,
                "monthly",
                "0.7",
            )
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(blocks)
        + "\n</urlset>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render()

    if args.check:
        if not TARGET.exists():
            print("missing sitemap.xml")
            return 1
        if TARGET.read_text(encoding="utf-8") != content:
            print("stale sitemap.xml (run python scripts/build_sitemap.py)")
            return 1
        print("Sitemap build check passed.")
        return 0

    TARGET.write_text(content, encoding="utf-8")
    print(f"generated {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
