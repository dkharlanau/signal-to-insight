#!/usr/bin/env python3
"""Generate the public explainer library from structured published records."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSIGHTS = ROOT / "data" / "insights.json"
SOURCES = ROOT / "data" / "sources.json"
TARGET = ROOT / "library" / "index.html"
SITE_BASE = "https://dkharlanau.github.io/signal-to-insight"


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def source_date(source: dict) -> str:
    return source.get("published_at") or source.get("event_date") or "date unknown"


def render() -> str:
    insight_data = load(INSIGHTS)
    source_data = load(SOURCES)
    sources = {item["id"]: item for item in source_data.get("sources", [])}
    published = [item for item in insight_data.get("insights", []) if item.get("status") == "published"]
    published.sort(key=lambda item: (item.get("provenance", {}).get("reviewed_at", ""), item.get("title", "")), reverse=True)

    all_tags = sorted({tag for item in published for tag in item.get("tags", [])})
    tag_buttons = "".join(
        f'<button type="button" class="filter-chip" data-filter="{e(tag)}">{e(tag)}</button>'
        for tag in all_tags
    )

    cards = []
    for item in published:
        source = sources.get(item.get("source_id"), {})
        tags = item.get("tags", [])
        search_text = " ".join([
            item.get("title", ""),
            item.get("one_liner", ""),
            " ".join(tags),
            source.get("title", ""),
            source.get("type", ""),
            " ".join(source.get("creators", [])),
            " ".join(item.get("connections", [])),
        ]).lower()
        tag_markup = "".join(f"<span>{e(tag)}</span>" for tag in tags)
        cards.append(f'''<article class="library-card" data-search="{e(search_text)}" data-tags="{e(' '.join(tags))}">
          <div class="library-card-meta"><span>{e(source.get('type', 'source'))}</span><span>{e(source_date(source))}</span></div>
          <h2><a href="../explainers/{e(item['slug'])}/">{e(item['title'])}</a></h2>
          <p>{e(item['one_liner'])}</p>
          <div class="library-tags">{tag_markup}</div>
          <footer>
            <span>{e(source.get('publisher') or ', '.join(source.get('creators', [])) or 'Source')}</span>
            <a href="../explainers/{e(item['slug'])}/">Open explainer →</a>
          </footer>
        </article>''')

    collection_ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Signal to Insight Library",
        "description": "Visual, source-backed explainers generated from the Signal to Insight knowledge layer.",
        "url": f"{SITE_BASE}/library/",
        "hasPart": [
            {
                "@type": "TechArticle",
                "headline": item["title"],
                "url": f"{SITE_BASE}/explainers/{item['slug']}/"
            }
            for item in published
        ]
    }

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Library — Signal to Insight</title>
  <meta name="description" content="Browse source-backed visual explainers of concepts, tools, systems and practical applications.">
  <link rel="canonical" href="{SITE_BASE}/library/">
  <link rel="stylesheet" href="../styles.css">
  <link rel="stylesheet" href="../library.css">
  <script type="application/ld+json">{json.dumps(collection_ld, ensure_ascii=False).replace('</', '<\\/')}</script>
</head>
<body class="library-page">
  <div class="progress" aria-hidden="true"><span id="progressBar"></span></div>
  <header class="site-header wrap">
    <a class="brand" href="../"><span class="brand-mark">S→I</span><span>Signal to Insight</span></a>
    <nav aria-label="Library navigation"><a href="../">Engine</a><a href="../data/insights.json">Data</a><a href="../data/sources.json">Sources</a></nav>
  </header>

  <main>
    <section class="library-hero wrap">
      <p class="eyebrow">KNOWLEDGE LIBRARY / {len(published):03d}</p>
      <h1>Models worth<br><em>remembering.</em></h1>
      <p>Browse reviewed explainers built from videos, papers, tools, repositories, documentation and other high-signal sources.</p>
    </section>

    <section class="library-controls wrap" aria-label="Library filters">
      <label class="library-search"><span>Search</span><input id="librarySearch" type="search" placeholder="concept, tool, source, tag…" autocomplete="off"></label>
      <div class="library-filters"><button type="button" class="filter-chip is-active" data-filter="all">all</button>{tag_buttons}</div>
      <p id="libraryCount" aria-live="polite">{len(published)} explainer{'s' if len(published) != 1 else ''}</p>
    </section>

    <section class="library-grid wrap" id="libraryGrid">
      {''.join(cards) if cards else '<p class="library-empty">No published explainers yet.</p>'}
    </section>
  </main>

  <footer class="site-footer wrap"><span>Signal to Insight</span><span>Generated from structured records</span><span>{len(published)} published</span></footer>
  <script src="../app.js"></script>
  <script src="../library.js"></script>
</body>
</html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if the committed library page is stale")
    args = parser.parse_args()
    content = render() + "\n"

    if args.check:
        if not TARGET.exists():
            print(f"missing generated library: {TARGET.relative_to(ROOT)}")
            return 1
        if TARGET.read_text(encoding="utf-8") != content:
            print(f"stale generated library: {TARGET.relative_to(ROOT)} (run python scripts/build_library.py)")
            return 1
        print("Library build check passed.")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    print(f"generated {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
