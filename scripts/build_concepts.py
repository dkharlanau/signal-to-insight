#!/usr/bin/env python3
"""Generate public concept pages and graph-derived related-explainer navigation."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from public_projection import ProjectionError, public_graph

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources.json"
OUTPUT = ROOT / "knowledge" / "concepts"
INDEX = OUTPUT / "index.json"
SITE_BASE = "https://dkharlanau.github.io/signal-to-insight"
RELATION_LABELS = {
    "depends_on": "depends on",
    "enables": "enables",
    "realized_by": "realized by",
    "refines": "refines",
    "related_to": "related to",
}


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def public_model() -> tuple[list[dict], list[dict], dict[str, dict], dict[str, dict]]:
    concepts, relations, insights, _, _ = public_graph()
    sources = {item["id"]: item for item in load(SOURCES).get("sources", [])}
    relation_count: dict[str, int] = defaultdict(int)
    for relation in relations:
        relation_count[relation["from"]] += 1
        relation_count[relation["to"]] += 1

    # A page is intentionally not created for a thin or isolated node. Published support,
    # meaningful definition text and at least one public graph relation are all required.
    eligible = [
        item for item in concepts
        if item.get("published_support")
        and len(str(item.get("summary") or "").strip()) >= 40
        and relation_count[item["id"]] > 0
    ]
    return eligible, relations, insights, sources


def relation_view(concept_id: str, relation: dict, concept_map: dict[str, dict]) -> dict:
    if relation["from"] == concept_id:
        neighbor_id = relation["to"]
        direction = "out"
    else:
        neighbor_id = relation["from"]
        direction = "in"
    neighbor = concept_map[neighbor_id]
    return {
        "relation_id": relation["id"],
        "type": relation["type"],
        "label": RELATION_LABELS.get(relation["type"], relation["type"]),
        "direction": direction,
        "neighbor_id": neighbor_id,
        "neighbor_label": neighbor["label"],
        "rationale": relation["rationale"],
    }


def learning_label(concept_id: str, relation: dict) -> str:
    relation_type = relation["type"]
    outgoing = relation["from"] == concept_id
    if relation_type == "depends_on":
        return "Learn before" if outgoing else "Then explore"
    if relation_type == "enables":
        return "Then explore" if outgoing else "Learn before"
    if relation_type == "refines":
        return "Deeper refinement" if outgoing else "Then explore refinement"
    if relation_type == "realized_by":
        return "Concrete realization" if outgoing else "Concept behind this"
    return "Related concept"


def related_explainers(
    concept: dict,
    relations: list[dict],
    concept_map: dict[str, dict],
    insights: dict[str, dict],
) -> list[dict]:
    own = set(concept.get("published_support", []))
    scored: dict[str, dict] = {}
    for relation in relations:
        if concept["id"] not in {relation["from"], relation["to"]}:
            continue
        neighbor_id = relation["to"] if relation["from"] == concept["id"] else relation["from"]
        neighbor = concept_map[neighbor_id]
        for insight_id in neighbor.get("published_support", []):
            if insight_id in own:
                continue
            insight = insights[insight_id]
            entry = scored.setdefault(insight_id, {
                "insight_id": insight_id,
                "title": insight["title"],
                "slug": insight["slug"],
                "score": 0,
                "via": [],
            })
            entry["score"] += 1
            entry["via"].append({
                "concept_id": neighbor_id,
                "concept_label": neighbor["label"],
                "relation_id": relation["id"],
                "relation_type": relation["type"],
            })
    ordered = sorted(scored.values(), key=lambda item: (-item["score"], item["title"].lower()))
    for item in ordered:
        item.pop("score", None)
    return ordered[:6]


def boundaries(concept: dict, insights: dict[str, dict]) -> list[dict]:
    output: list[dict] = []
    seen: set[str] = set()
    for insight_id in concept.get("published_support", []):
        insight = insights[insight_id]
        for text in insight.get("limitations", []):
            normalized = " ".join(str(text).split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            output.append({
                "text": normalized,
                "insight_id": insight_id,
                "insight_title": insight["title"],
                "insight_slug": insight["slug"],
            })
            if len(output) >= 6:
                return output
    return output


def concept_record(
    concept: dict,
    concepts: list[dict],
    relations: list[dict],
    insights: dict[str, dict],
    sources: dict[str, dict],
) -> dict:
    concept_map = {item["id"]: item for item in concepts}
    relation_items = [
        relation_view(concept["id"], relation, concept_map)
        for relation in relations
        if concept["id"] in {relation["from"], relation["to"]}
        and relation["from"] in concept_map
        and relation["to"] in concept_map
    ]
    relation_items.sort(key=lambda item: (item["neighbor_label"].lower(), item["type"], item["relation_id"]))

    learning_items: list[dict] = []
    for relation in relations:
        if concept["id"] not in {relation["from"], relation["to"]}:
            continue
        neighbor_id = relation["to"] if relation["from"] == concept["id"] else relation["from"]
        if neighbor_id not in concept_map:
            continue
        learning_items.append({
            "kind": learning_label(concept["id"], relation),
            "concept_id": neighbor_id,
            "label": concept_map[neighbor_id]["label"],
            "relation_id": relation["id"],
        })
    learning_items.sort(key=lambda item: (item["kind"], item["label"].lower()))

    supporting = []
    for insight_id in concept.get("published_support", []):
        insight = insights[insight_id]
        source = sources.get(insight.get("source_id"), {})
        supporting.append({
            "insight_id": insight_id,
            "title": insight["title"],
            "slug": insight["slug"],
            "one_liner": insight.get("one_liner", ""),
            "source_title": source.get("title"),
            "source_url": source.get("canonical_url"),
        })
    supporting.sort(key=lambda item: item["title"].lower())

    return {
        "id": concept["id"],
        "label": concept["label"],
        "summary": concept["summary"],
        "domain": concept["domain"],
        "coverage": concept["coverage"],
        "tags": sorted(concept.get("tags", [])),
        "supporting_explainers": supporting,
        "supporting_insight_ids": [item["insight_id"] for item in supporting],
        "relations": relation_items,
        "learning_next": learning_items,
        "limitations": boundaries(concept, insights),
        "related_explainers": related_explainers(concept, relations, concept_map, insights),
        "canonical": f"{SITE_BASE}/knowledge/concepts/{concept['id']}/",
    }


def build_records() -> list[dict]:
    concepts, relations, insights, sources = public_model()
    eligible_ids = {item["id"] for item in concepts}
    # Only relations between concepts that are themselves substantial enough for pages are
    # exposed in page-to-page navigation. The main graph can still show other public nodes.
    page_relations = [
        item for item in relations
        if item["from"] in eligible_ids and item["to"] in eligible_ids
    ]
    records = [concept_record(item, concepts, page_relations, insights, sources) for item in concepts]
    records.sort(key=lambda item: item["label"].lower())
    return records


def render_page(record: dict) -> str:
    support = "".join(
        f'''<article class="support-card">
          <p class="meta">PUBLISHED EXPLAINER</p>
          <h3><a href="../../../explainers/{e(item['slug'])}/">{e(item['title'])}</a></h3>
          <p>{e(item['one_liner'])}</p>
          <div class="source-link">Source: <a href="{e(item['source_url'])}" target="_blank" rel="noreferrer">{e(item['source_title'] or 'Original source')} ↗</a></div>
        </article>'''
        for item in record["supporting_explainers"]
    )
    relations = "".join(
        f'''<article class="relation-card">
          <p class="meta">{e(item['label']).upper()}</p>
          <h3><a href="../{e(item['neighbor_id'])}/">{e(item['neighbor_label'])}</a></h3>
          <p>{e(item['rationale'])}</p>
        </article>'''
        for item in record["relations"]
    )
    limitations = "".join(
        f'''<li><span>{e(item['text'])}</span><a href="../../../explainers/{e(item['insight_slug'])}/">Evidence →</a></li>'''
        for item in record["limitations"]
    )
    learning = "".join(
        f'''<li><span class="learning-kind">{e(item['kind'])}</span><a href="../{e(item['concept_id'])}/">{e(item['label'])}</a></li>'''
        for item in record["learning_next"]
    )
    related = "".join(
        f'''<article class="related-card">
          <p class="meta">RELATED EXPLAINER · GRAPH-DERIVED</p>
          <h3><a href="../../../explainers/{e(item['slug'])}/">{e(item['title'])}</a></h3>
          <p>Connected through {e(', '.join(sorted({via['concept_label'] for via in item['via']})))}.</p>
        </article>'''
        for item in record["related_explainers"]
    )
    related_section = f'''<section>
      <div class="section-head"><p class="meta">RELATED EXPLAINERS</p><h2>Only graph-backed connections.</h2></div>
      <div class="card-grid">{related}</div>
    </section>''' if related else ""
    tags = "".join(f"<span>{e(tag)}</span>" for tag in record["tags"])
    defined_term_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "DefinedTerm",
            "name": record["label"],
            "description": record["summary"],
            "url": record["canonical"],
            "inDefinedTermSet": f"{SITE_BASE}/knowledge/",
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(record['label'])} — Signal to Insight</title>
  <meta name="description" content="{e(record['summary'])}">
  <meta property="og:title" content="{e(record['label'])} — Signal to Insight">
  <meta property="og:description" content="{e(record['summary'])}">
  <meta property="og:type" content="article">
  <link rel="canonical" href="{e(record['canonical'])}">
  <link rel="stylesheet" href="../../../styles.css">
  <script type="application/ld+json">{defined_term_ld}</script>
  <style>
    body{{background:#f3f0e9;color:#111}}.wrap{{width:min(1080px,calc(100% - 36px));margin:auto}}header{{padding:34px 0;border-bottom:1px solid #aaa69c;display:flex;justify-content:space-between;gap:20px}}header a{{color:inherit;font-weight:700}}
    main{{padding-bottom:90px}}.hero{{padding:88px 0 58px;border-bottom:1px solid #aaa69c}}.meta{{font:700 10px ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:#5f5b55}}h1{{font-size:clamp(48px,9vw,96px);line-height:.9;letter-spacing:-.06em;margin:.12em 0 .28em;max-width:10ch}}.lede{{font-size:20px;line-height:1.55;max-width:780px}}
    .tags{{display:flex;flex-wrap:wrap;gap:7px;margin-top:24px}}.tags span{{border:1px solid #111;padding:7px 9px;font:700 10px ui-monospace,monospace}}section{{padding:54px 0;border-bottom:1px solid #aaa69c}}.section-head{{display:grid;grid-template-columns:.42fr 1.58fr;gap:30px;align-items:end;margin-bottom:24px}}h2{{font-size:clamp(30px,5vw,52px);letter-spacing:-.045em;margin:0}}h3{{font-size:21px;margin:8px 0 12px}}p,li{{line-height:1.55}}a{{color:inherit;text-underline-offset:3px}}
    .card-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}.support-card,.relation-card,.related-card{{border:1px solid #111;padding:22px;min-height:220px;display:flex;flex-direction:column}}.source-link{{margin-top:auto;padding-top:20px;font-size:13px}}.relation-card p:last-child{{margin-top:auto}}.boundary-list,.learning-list{{list-style:none;padding:0;margin:0;border-top:1px solid #111}}.boundary-list li,.learning-list li{{display:grid;grid-template-columns:1fr auto;gap:18px;padding:16px 0;border-bottom:1px solid #aaa69c}}.learning-list li{{grid-template-columns:160px 1fr}}.learning-kind{{font:700 10px ui-monospace,monospace;text-transform:uppercase}}
    footer{{padding:30px 0 50px;font:700 10px ui-monospace,monospace;display:flex;justify-content:space-between;gap:20px}}@media(max-width:720px){{.section-head,.card-grid{{grid-template-columns:1fr}}.boundary-list li,.learning-list li{{grid-template-columns:1fr}}header,footer{{flex-direction:column}}}}
  </style>
</head>
<body>
<header class="wrap"><a href="../../../knowledge/">← Knowledge graph</a><a href="../../../library/">Explainer library</a></header>
<main>
  <section class="hero"><div class="wrap"><p class="meta">CONCEPT · {e(record['domain'])} · {e(record['coverage'])}</p><h1>{e(record['label'])}</h1><p class="lede">{e(record['summary'])}</p><div class="tags">{tags}</div></div></section>
  <div class="wrap">
    <section><div class="section-head"><p class="meta">EVIDENCE</p><h2>Why this concept exists here.</h2></div><div class="card-grid">{support}</div></section>
    <section><div class="section-head"><p class="meta">RELATIONS</p><h2>What it depends on and connects to.</h2></div><div class="card-grid">{relations}</div></section>
    <section><div class="section-head"><p class="meta">BOUNDARIES</p><h2>Where supporting models are incomplete.</h2></div><ul class="boundary-list">{limitations}</ul></section>
    <section><div class="section-head"><p class="meta">LEARN NEXT</p><h2>Navigate by graph semantics.</h2></div><ul class="learning-list">{learning}</ul></section>
    {related_section}
  </div>
</main>
<footer class="wrap"><span>Signal to Insight</span><span>Concept: {e(record['id'])}</span></footer>
</body>
</html>'''


def expected() -> tuple[dict[str, str], str]:
    records = build_records()
    pages = {record["id"]: render_page(record) + "\n" for record in records}
    index_payload = {
        "version": "1.0.0",
        "projection": "published-evidence-only",
        "records": records,
    }
    return pages, json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n"


def build(check: bool = False) -> int:
    try:
        pages, index_content = expected()
    except ProjectionError as exc:
        print(f"Concept build blocked by public projection: {exc}")
        return 1

    existing = {
        path.parent.name: path
        for path in OUTPUT.glob("*/index.html")
        if path.parent.name != "index"
    } if OUTPUT.exists() else {}
    failures: list[str] = []

    if check:
        if not INDEX.exists():
            failures.append(f"missing concept index: {INDEX.relative_to(ROOT)}")
        elif INDEX.read_text(encoding="utf-8") != index_content:
            failures.append(f"stale concept index: {INDEX.relative_to(ROOT)}")
        for concept_id, content in pages.items():
            target = OUTPUT / concept_id / "index.html"
            if not target.exists():
                failures.append(f"missing concept page: {target.relative_to(ROOT)}")
            elif target.read_text(encoding="utf-8") != content:
                failures.append(f"stale concept page: {target.relative_to(ROOT)}")
        for concept_id, path in existing.items():
            if concept_id not in pages:
                failures.append(f"stale concept page: {path.relative_to(ROOT)}")
    else:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for concept_id, path in existing.items():
            if concept_id not in pages:
                shutil.rmtree(path.parent)
                print(f"removed stale concept page {path.parent.relative_to(ROOT)}")
        for concept_id, content in pages.items():
            target = OUTPUT / concept_id / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            print(f"generated {target.relative_to(ROOT)}")
        INDEX.write_text(index_content, encoding="utf-8")
        print(f"generated {INDEX.relative_to(ROOT)}")

    if failures:
        print("Concept page build check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Concept page build {'check ' if check else ''}passed: {len(pages)} page(s).")
    return 0


def self_test() -> int:
    records = build_records()
    if not records:
        print("Concept page self-test failed: no eligible published concept pages.")
        return 1
    for record in records:
        if not record["supporting_explainers"]:
            print(f"Concept page self-test failed: {record['id']} has no public evidence.")
            return 1
        if not record["relations"]:
            print(f"Concept page self-test failed: {record['id']} is a thin isolated page.")
            return 1
        if any(not item.get("source_url") for item in record["supporting_explainers"]):
            print(f"Concept page self-test failed: {record['id']} lost source provenance.")
            return 1
        own = set(record["supporting_insight_ids"])
        if any(item["insight_id"] in own for item in record["related_explainers"]):
            print(f"Concept page self-test failed: {record['id']} recommends its own supporting explainer as related.")
            return 1
    print(f"Concept page self-test passed: {len(records)} evidence-backed page(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    return build(check=args.check)


if __name__ == "__main__":
    sys.exit(main())
