#!/usr/bin/env python3
"""Build deterministic review/public pages for multi-source synthesis records."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "data" / "syntheses.json"
INSIGHTS = ROOT / "data" / "insights.json"
CLAIMS = ROOT / "data" / "claim-evidence.json"
REVIEWS = ROOT / "data" / "knowledge-reviews.json"
PREVIEWS = ROOT / "synthesis-previews"
PUBLIC = ROOT / "syntheses"
SITE_BASE = "https://dkharlanau.github.io/signal-to-insight"


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def indexes() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    insight_data = load(INSIGHTS)
    claim_data = load(CLAIMS)
    review_data = load(REVIEWS)
    insights = {item["id"]: item for item in insight_data.get("insights", [])}
    claims: dict[str, dict] = {}
    for record in claim_data.get("records", []):
        owner = record.get("insight_id")
        for claim in record.get("claims", []):
            claims[claim["id"]] = {"owner": owner, "claim": claim}
    reviews = {item["id"]: item for item in review_data.get("reviews", [])}
    return insights, claims, reviews


def insight_href(insight: dict) -> str | None:
    if insight.get("status") == "published":
        return f"../../explainers/{e(insight['slug'])}/"
    if insight.get("status") == "review":
        return f"../../previews/{e(insight['slug'])}/"
    return None


def evidence_href(item: dict, insights: dict[str, dict]) -> str | None:
    if item.get("kind") == "prior_insight":
        prior = insights.get(item.get("insight_id"))
        return insight_href(prior) if prior else None
    return item.get("url")


def render_claim_refs(refs: list[str], insights: dict[str, dict], claims: dict[str, dict]) -> str:
    items: list[str] = []
    for claim_id in refs:
        entry = claims[claim_id]
        claim = entry["claim"]
        owner = insights[entry["owner"]]
        evidence = claim.get("evidence", [])
        locators: list[str] = []
        for source in evidence:
            href = evidence_href(source, insights)
            locator = e(source.get("locator"))
            if href:
                external = href.startswith("http://") or href.startswith("https://")
                attrs = ' target="_blank" rel="noreferrer"' if external else ""
                locators.append(f'<a href="{e(href)}"{attrs}>{locator}</a>')
            else:
                locators.append(locator)
        locator_text = " · ".join(locators) or "Evidence locator unavailable"
        items.append(
            f'<li><strong>{e(owner["title"])}</strong> · {e(claim.get("origin"))}<br>'
            f'{e(claim.get("text"))}<br><span>{locator_text}</span></li>'
        )
    return '<div class="synthesis-evidence"><span class="synthesis-evidence-label">Claim-level evidence</span><ul>' + "".join(items) + "</ul></div>"


def render_page(synthesis: dict, insights: dict[str, dict], claims: dict[str, dict], reviews: dict[str, dict]) -> str:
    is_review = synthesis["status"] == "review"
    robots = '<meta name="robots" content="noindex,nofollow">' if is_review else ""
    canonical = "" if is_review else f'<link rel="canonical" href="{SITE_BASE}/syntheses/{e(synthesis["slug"])}/">'
    banner = (
        '<div class="synthesis-review-banner">Review-only synthesis · may use review-state evidence · not public canonical knowledge</div>'
        if is_review
        else '<div class="synthesis-review-banner">Published synthesis · published evidence only</div>'
    )

    consensus = "".join(
        f'<article><span class="synthesis-badge">Agreement across sources</span>'
        f'<h3>{e(item["statement"])}</h3>{render_claim_refs(item["claim_refs"], insights, claims)}</article>'
        for item in synthesis.get("consensus", [])
    )

    layers = "".join(
        f'''<article class="synthesis-layer">
          <span class="synthesis-layer-index">{int(layer["order"]):02d}</span>
          <div><span class="synthesis-badge">{e(layer["role"])}</span><h3>{e(layer["name"])}</h3><p class="synthesis-layer-role">{e(insights[layer["source_insight_id"]]["title"])}</p></div>
          <p class="synthesis-do"><strong>Does:</strong> {e(layer["does"])}</p>
          <div><p class="synthesis-do-not"><strong>Does not:</strong> {e(layer["does_not"])}</p>{render_claim_refs(layer["claim_refs"], insights, claims)}</div>
        </article>'''
        for layer in sorted(synthesis.get("layers", []), key=lambda item: item["order"])
    )

    disagreements = "".join(
        f'''<article class="synthesis-disagreement">
          <span class="synthesis-badge">Resolved: {e(reviews[item["review_id"]]["resolution"])}</span>
          <h3>{e(item["why_it_matters"])}</h3>
          <p>{e(reviews[item["review_id"]]["scope_check"]["explanation"])}</p>
          <p class="synthesis-layer-role">{e(reviews[item["review_id"]]["rationale"])}</p>
        </article>'''
        for item in synthesis.get("reviewed_disagreements", [])
    )

    gaps = "".join(
        f'<article class="synthesis-gap"><span class="synthesis-badge">Unresolved gap</span>'
        f'<h3>{e(item["statement"])}</h3>{render_claim_refs(item["claim_refs"], insights, claims)}</article>'
        for item in synthesis.get("unresolved_gaps", [])
    )

    source_cards: list[str] = []
    for insight_id in synthesis.get("source_insight_ids", []):
        insight = insights[insight_id]
        href = insight_href(insight)
        title = e(insight["title"])
        title_markup = f'<a href="{href}">{title}</a>' if href else title
        source_cards.append(
            f'<article class="synthesis-source"><span class="synthesis-source-status">{e(insight["status"])}</span>'
            f'<h3>{title_markup}</h3><p>{e(insight["one_liner"])}</p></article>'
        )

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(synthesis['title'])} — Signal to Insight</title>
  <meta name="description" content="{e(synthesis['one_liner'])}">
  {robots}
  {canonical}
  <link rel="stylesheet" href="../../styles.css">
  <link rel="stylesheet" href="../../synthesis.css">
</head>
<body class="synthesis-page">
  <header class="synthesis-header synthesis-wrap"><a href="../../">Signal to Insight</a><span>Multi-source synthesis · {e(synthesis['status'])}</span></header>
  <div class="synthesis-wrap">{banner}</div>
  <main>
    <section class="synthesis-hero synthesis-wrap">
      <div><p class="synthesis-kicker">QUESTION-DRIVEN SYNTHESIS</p><p class="synthesis-question">{e(synthesis['question'])}</p></div>
      <div><h1>{e(synthesis['title'])}</h1><p class="synthesis-question">{e(synthesis['one_liner'])}</p></div>
    </section>

    <section class="synthesis-wrap"><p class="synthesis-thesis">{e(synthesis['thesis'])}</p></section>

    <section class="synthesis-section synthesis-wrap">
      <div class="synthesis-section-head"><p class="synthesis-kicker">CONSENSUS</p><div><h2>Where independent sources line up.</h2><p>Each synthesis statement below requires claim-level evidence from at least two source insights.</p></div></div>
      <div class="synthesis-consensus">{consensus}</div>
    </section>

    <section class="synthesis-section synthesis-wrap">
      <div class="synthesis-section-head"><p class="synthesis-kicker">LAYERED MODEL</p><div><h2>{e(synthesis['visual_plan']['title'])}</h2><p>{e(synthesis['visual_plan']['caption'])}</p></div></div>
      <div class="synthesis-layers">{layers}</div>
    </section>

    <section class="synthesis-section synthesis-wrap">
      <div class="synthesis-section-head"><p class="synthesis-kicker">SCOPE REVIEWS</p><div><h2>Apparent conflicts that were checked.</h2><p>Different layers or narrower responsibilities are not automatically contradictory evidence.</p></div></div>
      <div class="synthesis-review-grid">{disagreements or '<p>No reviewed disagreements are needed for this synthesis.</p>'}</div>
    </section>

    <section class="synthesis-section synthesis-wrap">
      <div class="synthesis-section-head"><p class="synthesis-kicker">UNRESOLVED</p><div><h2>What the combined evidence still does not establish.</h2><p>Synthesis should expose missing evidence instead of turning composition into certainty.</p></div></div>
      <div class="synthesis-gap-grid">{gaps}</div>
    </section>

    <section class="synthesis-section synthesis-wrap">
      <div class="synthesis-section-head"><p class="synthesis-kicker">SOURCE INSIGHTS</p><div><h2>Four inputs, one question.</h2><p>Review synthesis may use review-state source insights; public synthesis is constrained to published evidence only.</p></div></div>
      <div class="synthesis-source-grid">{''.join(source_cards)}</div>
    </section>
  </main>
  <footer class="synthesis-footer synthesis-wrap"><span>Synthesis: {e(synthesis['id'])}</span><span>Created {e(synthesis['provenance']['created_at'])}</span><span>Project synthesis is explicitly separated from source-authored claims.</span></footer>
</body>
</html>'''


def build(check: bool = False) -> int:
    data = load(SYN)
    insights, claims, reviews = indexes()
    failures: list[str] = []
    known_slugs = {item["slug"] for item in data.get("records", [])}
    review_slugs = {item["slug"] for item in data.get("records", []) if item.get("status") == "review"}
    public_slugs = {item["slug"] for item in data.get("records", []) if item.get("status") == "published"}

    for synthesis in data.get("records", []):
        if synthesis.get("status") not in {"review", "published"}:
            continue
        base = PREVIEWS if synthesis["status"] == "review" else PUBLIC
        target = base / synthesis["slug"] / "index.html"
        content = render_page(synthesis, insights, claims, reviews) + "\n"
        if check:
            if not target.exists():
                failures.append(f"missing synthesis page: {target.relative_to(ROOT)}")
            elif target.read_text(encoding="utf-8") != content:
                failures.append(f"stale synthesis page: {target.relative_to(ROOT)}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            print(f"generated {target.relative_to(ROOT)}")

    cleanup = [
        (PREVIEWS, review_slugs, "review"),
        (PUBLIC, public_slugs, "published"),
    ]
    for base, active, label in cleanup:
        for slug in known_slugs - active:
            stale = base / slug
            if not stale.exists():
                continue
            if check:
                failures.append(f"stale {label} synthesis page: {stale.relative_to(ROOT)}")
            else:
                shutil.rmtree(stale)
                print(f"removed {stale.relative_to(ROOT)}")

    if failures:
        print("Synthesis build check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Synthesis build {'check ' if check else ''}passed: {len(review_slugs)} review, {len(public_slugs)} published.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return build(check=args.check)


if __name__ == "__main__":
    sys.exit(main())
