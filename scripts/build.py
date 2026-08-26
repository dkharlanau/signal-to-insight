#!/usr/bin/env python3
"""Generate reviewable static explainer pages from published insight records."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSIGHTS = ROOT / "data" / "insights.json"
SOURCES = ROOT / "data" / "sources.json"
KNOWLEDGE_DELTAS = ROOT / "data" / "knowledge-deltas.json"
OUTPUT = ROOT / "explainers"
SITE_BASE = "https://dkharlanau.github.io/signal-to-insight"

ACTION_LABELS = {
    "use_now": "Use now",
    "try": "Try",
    "learn": "Learn",
    "build": "Build",
    "watch": "Watch",
    "ignore_for_now": "Ignore for now",
}

DELTA_LABELS = {
    "new": "New",
    "reinforces": "Reinforces",
    "refines": "Refines",
    "contradicts": "Contradicts",
}

LIVING_SOURCE_TYPES = {"documentation", "repository", "tool", "product", "system"}


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def render_items(items: list[str], empty: str = "No action required.") -> str:
    if not items:
        return f'<p class="empty-note">{e(empty)}</p>'
    return "<ul>" + "".join(f"<li>{e(item)}</li>" for item in items) + "</ul>"


def source_date(source: dict) -> tuple[str, str]:
    if source.get("published_at"):
        return "Published", source["published_at"]
    if source.get("event_date"):
        return "Event date", source["event_date"]
    if source.get("type") in LIVING_SOURCE_TYPES:
        accessed = source.get("analyzed_at") or source.get("captured_at")
        if accessed:
            return "Source status", f"living source · accessed {accessed}"
    return "Source date", "not independently verified"


def json_ld(insight: dict, source: dict) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": insight["title"],
        "description": insight["one_liner"],
        "author": {
            "@type": "Person",
            "name": "Dzmitryi Kharlanau",
            "url": "https://github.com/dkharlanau",
        },
        "dateModified": insight["provenance"]["reviewed_at"],
        "isBasedOn": source["canonical_url"],
        "url": f"{SITE_BASE}/explainers/{insight['slug']}/",
        "keywords": insight.get("tags", []),
    }
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def render_dominant_visual(insight: dict) -> str:
    dominant = insight["visual_plan"]["dominant"]
    visual_type = dominant["type"]
    nodes = dominant["nodes"]

    if visual_type == "causal_chain":
        parts: list[str] = []
        for index, node in enumerate(nodes):
            if index:
                parts.append("        <b>→</b>")
            parts.append(f'        <article><span>{e(node["label"])}</span><p>{e(node["text"])}</p></article>')
        return '<div class="model-flow">\n' + "\n".join(parts) + '\n      </div>'

    css_class = {
        "sequence": "visual-sequence",
        "layers": "visual-layers",
        "comparison": "visual-compare",
        "decision": "visual-decision",
    }[visual_type]
    node_markup = "".join(
        f'''<article>
          <span>{e(node["label"])}</span>
          <h3>{e(node["title"])}</h3>
          <p>{e(node["text"])}</p>
        </article>'''
        for node in nodes
    )
    return f'<div class="{css_class}" aria-label="{e(dominant["title"])}">{node_markup}</div>'


def delta_record(insight_id: str) -> dict | None:
    if not KNOWLEDGE_DELTAS.exists():
        return None
    data = load(KNOWLEDGE_DELTAS)
    return next((item for item in data.get("records", []) if item.get("insight_id") == insight_id), None)


def render_delta_evidence(evidence_ids: list[str], current_status: str) -> str:
    if not evidence_ids:
        return '<span class="delta-baseline">No prior project evidence — baseline/new knowledge.</span>'

    insight_index = {item["id"]: item for item in load(INSIGHTS).get("insights", [])}
    parts: list[str] = []
    for evidence_id in evidence_ids:
        prior = insight_index.get(evidence_id)
        if prior is None:
            continue
        if prior.get("status") == "published":
            parts.append(f'<a href="../../explainers/{e(prior["slug"])}/">{e(prior["title"])}</a>')
        elif current_status != "published" and prior.get("status") == "review":
            parts.append(f'<a href="../../previews/{e(prior["slug"])}/">{e(prior["title"])}</a>')
        else:
            parts.append(e(prior["title"]))
    return ", ".join(parts) or '<span class="delta-baseline">Prior evidence is not publicly linked.</span>'


def render_knowledge_delta(insight: dict) -> str:
    record = delta_record(insight["id"])
    if record is None:
        return ""

    cards = "".join(
        f'''<article class="concept-card delta-card">
          <span>{e(DELTA_LABELS.get(item.get("relationship"), item.get("relationship")))}</span>
          <h3>{e(item.get("label"))}</h3>
          <p><strong>Source says:</strong> {e(item.get("source_basis"))}</p>
          <p><strong>Previously:</strong> {e(item.get("prior_basis"))}</p>
          <p><strong>Project interpretation:</strong> {e(item.get("interpretation"))}</p>
          <small>Prior evidence: {render_delta_evidence(item.get("evidence_insights", []), insight.get("status", "review"))}</small>
        </article>'''
        for item in record.get("items", [])
    )
    suppressed = record.get("suppressed_prior_matches", [])
    suppressed_note = ""
    if suppressed:
        suppressed_note = (
            '<p class="section-note"><strong>Noise rejected:</strong> prior concepts retrieved but deliberately classified as not relevant: '
            + e(", ".join(suppressed))
            + ".</p>"
        )

    return f'''<section id="delta" class="detail-section wrap knowledge-delta-section">
      <p class="kicker">KNOWLEDGE DELTA</p>
      <h2>What this source changes in the existing model.</h2>
      <p class="big-statement">{e(record.get("summary"))}</p>
      <div class="concept-grid">{cards}</div>
      {suppressed_note}
    </section>'''


def render_page(insight: dict, source: dict) -> str:
    date_label, date_value = source_date(source)
    creators = ", ".join(source.get("creators", [])) or "Unknown creator"
    concepts = "".join(
        f'''<article class="concept-card">
          <span>{e(concept.get("depth", "know"))}</span>
          <h3>{e(concept.get("name"))}</h3>
          <p>{e(concept.get("why_needed"))}</p>
        </article>'''
        for concept in insight.get("concepts", [])
    )

    tools = "".join(
        f'''<a class="tool-card" href="{e(tool.get('url'))}" target="_blank" rel="noreferrer">
          <span>{e(tool.get("status", "learn"))}</span>
          <strong>{e(tool.get("name"))}</strong>
          <p>{e(tool.get("why_explore"))}</p>
          <small>{e(tool.get("category"))} · {e(tool.get("relationship"))}</small>
        </a>'''
        for tool in insight.get("tool_map", [])
    )

    examples = "".join(
        f'''<article class="example-card">
          <span>{e(example.get("domain"))}</span>
          <h3>{e(example.get("scenario"))}</h3>
          <p>{e(example.get("question"))}</p>
        </article>'''
        for example in insight.get("examples", [])
    )

    limitations = "".join(f"<li>{e(item)}</li>" for item in insight.get("limitations", []))

    action_cards = "".join(
        f'''<article class="action-card action-{e(bucket)}">
          <span>{e(ACTION_LABELS[bucket])}</span>
          {render_items(insight.get("action_map", {}).get(bucket, []))}
        </article>'''
        for bucket in ACTION_LABELS
    )

    supporting = "".join(
        f'''<li>
          <a href="{e(item.get('url'))}" target="_blank" rel="noreferrer">{e(item.get("title"))}</a>
          <span>{e(item.get("purpose"))} · accessed {e(item.get("accessed_at"))}</span>
        </li>'''
        for item in insight.get("supporting_sources", [])
    )

    dominant_visual = render_dominant_visual(insight)
    knowledge_delta = render_knowledge_delta(insight)
    core_topics = "".join(f"<li>{e(topic)}</li>" for topic in insight.get("whole_source_map", {}).get("core_topics", []))

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(insight['title'])} — Signal to Insight</title>
  <meta name="description" content="{e(insight['one_liner'])}">
  <meta property="og:title" content="{e(insight['title'])}">
  <meta property="og:description" content="{e(insight['one_liner'])}">
  <meta property="og:type" content="article">
  <link rel="canonical" href="{SITE_BASE}/explainers/{e(insight['slug'])}/">
  <link rel="stylesheet" href="../../styles.css">
  <script type="application/ld+json">{json_ld(insight, source)}</script>
</head>
<body class="generated-page">
  <div class="progress" aria-hidden="true"><span id="progressBar"></span></div>
  <header class="site-header wrap">
    <a class="brand" href="../../"><span class="brand-mark">S→I</span><span>Signal to Insight</span></a>
    <nav aria-label="Explainer navigation">
      <a href="#delta">Delta</a><a href="#model">Model</a><a href="#concepts">Concepts</a><a href="#tools">Tools</a><a href="#actions">Actions</a><a href="#sources">Sources</a>
    </nav>
  </header>

  <main>
    <section class="detail-hero wrap">
      <a class="back-link" href="../../">← Research engine</a>
      <p class="eyebrow">EXPLAINER · {e(insight['status'])}</p>
      <h1>{e(insight['title'])}</h1>
      <div class="detail-lede">
        <p>{e(insight['one_liner'])}</p>
        <dl class="detail-meta">
          <div><dt>Original source</dt><dd><a href="{e(source['canonical_url'])}" target="_blank" rel="noreferrer">{e(source['title'])} ↗</a></dd></div>
          <div><dt>Creator</dt><dd>{e(creators)}</dd></div>
          <div><dt>{e(date_label)}</dt><dd>{e(date_value)}</dd></div>
          <div><dt>Captured</dt><dd>{e(source['captured_at'])}</dd></div>
          <div><dt>Analyzed</dt><dd>{e(source['analyzed_at'])}</dd></div>
        </dl>
      </div>
    </section>

    <section class="detail-section wrap">
      <p class="kicker">WHY THIS MATTERS</p>
      <p class="big-statement">{e(insight['why_this_matters'])}</p>
    </section>

    {knowledge_delta}

    <section id="model" class="detail-section wrap">
      <p class="kicker">MENTAL MODEL</p>
      {dominant_visual}
      <div class="core-map">
        <div><span>Source problem</span><p>{e(insight['whole_source_map']['problem'])}</p></div>
        <div><span>Source thesis</span><p>{e(insight['whole_source_map']['thesis'])}</p></div>
        <div><span>Core topics</span><ul>{core_topics}</ul></div>
      </div>
    </section>

    <section id="concepts" class="detail-section wrap">
      <p class="kicker">CONCEPTS TO KNOW</p>
      <h2>Learn only the prerequisites that preserve the model.</h2>
      <div class="concept-grid">{concepts}</div>
    </section>

    <section id="tools" class="detail-section wrap">
      <p class="kicker">TOOLS / SYSTEMS</p>
      <h2>Concrete systems worth knowing.</h2>
      <p class="section-note">Tool connections may be project enrichment rather than recommendations from the original source. Each card states the relationship.</p>
      <div class="tool-grid">{tools or '<p class="empty-note">No tool is required to understand this source.</p>'}</div>
    </section>

    <section class="detail-section wrap">
      <p class="kicker">EXAMPLES</p>
      <div class="example-grid">{examples}</div>
    </section>

    <section class="detail-section wrap limitation-section">
      <p class="kicker">WHERE THE MODEL BREAKS</p>
      <h2>Useful does not mean sufficient.</h2>
      <ol class="limitation-list">{limitations}</ol>
    </section>

    <section id="actions" class="detail-section wrap">
      <p class="kicker">PERSONAL ACTION MAP</p>
      <h2>Convert understanding into a decision.</h2>
      <div class="action-grid">{action_cards}</div>
    </section>

    <section id="sources" class="detail-section wrap source-section">
      <p class="kicker">SOURCES + DATES</p>
      <div class="source-grid">
        <div>
          <h3>Primary source</h3>
          <a href="{e(source['canonical_url'])}" target="_blank" rel="noreferrer">{e(source['title'])} ↗</a>
          <p>{e(creators)} · {e(date_label)}: {e(date_value)}</p>
          <p>{e(source.get('date_note'))}</p>
        </div>
        <div>
          <h3>Verification / enrichment</h3>
          <ul class="supporting-sources">{supporting}</ul>
        </div>
      </div>
      <p class="provenance-note">Analyzed {e(source['analyzed_at'])}. Full third-party transcript is not stored. Source claims and project enrichment are kept distinguishable.</p>
    </section>
  </main>

  <footer class="site-footer wrap">
    <span>Signal to Insight</span><span>Explainer: {e(insight['id'])}</span><span>Reviewed {e(insight['provenance']['reviewed_at'])}</span>
  </footer>
  <script src="../../app.js"></script>
</body>
</html>'''


def build(check: bool = False) -> int:
    insight_data = load(INSIGHTS)
    source_data = load(SOURCES)
    sources = {item["id"]: item for item in source_data.get("sources", [])}
    failures: list[str] = []
    generated = 0
    known_slugs = {
        item.get("slug")
        for item in insight_data.get("insights", [])
        if isinstance(item.get("slug"), str) and item.get("slug")
    }
    published_slugs: set[str] = set()

    for insight in insight_data.get("insights", []):
        if insight.get("status") != "published":
            continue
        published_slugs.add(insight["slug"])
        source = sources.get(insight.get("source_id"))
        if source is None:
            failures.append(f"{insight.get('id')}: source_id not found")
            continue

        target = OUTPUT / insight["slug"] / "index.html"
        content = render_page(insight, source) + "\n"
        generated += 1

        if check:
            if not target.exists():
                failures.append(f"missing generated page: {target.relative_to(ROOT)}")
            elif target.read_text(encoding="utf-8") != content:
                failures.append(f"stale generated page: {target.relative_to(ROOT)} (run python scripts/build.py)")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            print(f"generated {target.relative_to(ROOT)}")

    for slug in sorted(known_slugs - published_slugs):
        stale_dir = OUTPUT / slug
        if not stale_dir.exists():
            continue
        if check:
            failures.append(f"non-published insight still has public explainer: {stale_dir.relative_to(ROOT)}")
        else:
            shutil.rmtree(stale_dir)
            print(f"removed {stale_dir.relative_to(ROOT)}")

    if failures:
        print("Explainer build check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Explainer build {'check ' if check else ''}passed: {generated} published page(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if committed generated pages are missing or stale")
    args = parser.parse_args()
    return build(check=args.check)


if __name__ == "__main__":
    sys.exit(main())
