#!/usr/bin/env python3
"""Generate sitemap.xml from the published Signal to Insight surfaces."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from build_concepts import build_records

ROOT = Path(__file__).resolve().parents[1]
INSIGHTS = ROOT / "data" / "insights.json"
TARGET = ROOT / "sitemap.xml"
BASE = "https://dkharlanau.github.io/signal-to-insight"

# Sitemap generation is a checked-in deterministic build. Do not use date.today()
# here: that makes an unchanged repository fail `--check` every new calendar day.
# This baseline is the last intentional structural revision of the public surface;
# dated published evidence can move individual routes forward independently.
PUBLIC_SURFACE_BASELINE = "2026-08-27"


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


def published_date(insight: dict) -> str:
    provenance = insight.get("provenance", {})
    return (
        provenance.get("publication_review", {}).get("approved_at")
        or provenance.get("reviewed_at")
        or PUBLIC_SURFACE_BASELINE
    )


def render() -> str:
    data = load(INSIGHTS)
    published = [item for item in data.get("insights", []) if item.get("status") == "published"]
    published.sort(key=lambda item: item.get("slug", ""))
    concepts = build_records()

    blocks = [
        url_block(f"{BASE}/", PUBLIC_SURFACE_BASELINE, "weekly", "1.0"),
        url_block(f"{BASE}/walkthrough/", PUBLIC_SURFACE_BASELINE, "monthly", "0.95"),
        url_block(f"{BASE}/library/", PUBLIC_SURFACE_BASELINE, "weekly", "0.9"),
        url_block(f"{BASE}/knowledge/", PUBLIC_SURFACE_BASELINE, "weekly", "0.9"),
    ]
    for insight in published:
        blocks.append(
            url_block(
                f"{BASE}/explainers/{insight['slug']}/",
                published_date(insight),
                "monthly",
                "0.9",
            )
        )

    published_by_id = {item.get("id"): item for item in published}
    for concept in concepts:
        # Concept pages are generated only from published evidence + meaningful graph
        # relations, so they are safe to expose as normal discoverable routes.
        supporting_dates = [
            published_date(published_by_id[insight_id])
            for insight_id in concept.get("supporting_insight_ids", [])
            if insight_id in published_by_id
        ]
        lastmod = max(supporting_dates) if supporting_dates else PUBLIC_SURFACE_BASELINE
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
