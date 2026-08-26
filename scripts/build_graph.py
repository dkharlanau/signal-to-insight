#!/usr/bin/env python3
"""Generate the public cumulative knowledge graph and a relation-derived learning path."""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"
TARGET = ROOT / "knowledge" / "index.html"
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


def public_graph() -> tuple[list[dict], list[dict], dict[str, dict], int, str]:
    graph = load(GRAPH)
    insight_data = load(INSIGHTS)
    insights = {item["id"]: item for item in insight_data.get("insights", [])}
    published_ids = {item_id for item_id, item in insights.items() if item.get("status") == "published"}

    visible: list[dict] = []
    hidden_count = 0
    for concept in graph.get("concepts", []):
        support = [item_id for item_id in concept.get("insight_ids", []) if item_id in published_ids]
        if not support:
            hidden_count += 1
            continue
        item = dict(concept)
        item["published_support"] = support
        visible.append(item)

    visible_ids = {item["id"] for item in visible}
    relations = [
        relation
        for relation in graph.get("relations", [])
        if relation.get("from") in visible_ids
        and relation.get("to") in visible_ids
        and any(item_id in published_ids for item_id in relation.get("evidence_insights", []))
    ]
    return visible, relations, insights, hidden_count, graph.get("graph_version", "0.0.0")


def layout(concepts: list[dict], relations: list[dict]) -> dict[str, tuple[float, float]]:
    if not concepts:
        return {}
    degree: Counter[str] = Counter()
    for relation in relations:
        degree[relation["from"]] += 1
        degree[relation["to"]] += 1
    ordered = sorted(concepts, key=lambda item: (-degree[item["id"]], item["label"].lower()))
    hub = ordered[0]
    positions = {hub["id"]: (600.0, 380.0)}
    outer = ordered[1:]
    count = max(1, len(outer))
    for index, concept in enumerate(outer):
        angle = -math.pi / 2 + (2 * math.pi * index / count)
        positions[concept["id"]] = (600 + 430 * math.cos(angle), 380 + 270 * math.sin(angle))
    return positions


def precedence_edges(relations: list[dict]) -> set[tuple[str, str]]:
    """Convert semantic relations into learn-before ordering edges."""
    edges: set[tuple[str, str]] = set()
    for relation in relations:
        source, target, relation_type = relation["from"], relation["to"], relation["type"]
        if relation_type == "depends_on":
            edges.add((target, source))
        elif relation_type == "enables":
            edges.add((source, target))
        elif relation_type == "refines":
            edges.add((target, source))
        elif relation_type == "realized_by":
            edges.add((source, target))
    return edges


def learning_order(concepts: list[dict], relations: list[dict]) -> tuple[list[str], dict[str, list[str]]]:
    """Stable topological order; unrelated concepts stay alphabetically deterministic."""
    concept_map = {item["id"]: item for item in concepts}
    edges = precedence_edges(relations)
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    indegree = {concept_id: 0 for concept_id in concept_map}
    for before, after in edges:
        if before not in concept_map or after not in concept_map or after in outgoing[before]:
            continue
        outgoing[before].add(after)
        incoming[after].add(before)
        indegree[after] += 1

    ready = sorted(
        [concept_id for concept_id, degree in indegree.items() if degree == 0],
        key=lambda concept_id: concept_map[concept_id]["label"].lower(),
    )
    order: list[str] = []
    queue = deque(ready)
    while queue:
        concept_id = queue.popleft()
        order.append(concept_id)
        newly_ready: list[str] = []
        for neighbor in sorted(outgoing.get(concept_id, set()), key=lambda item: concept_map[item]["label"].lower()):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                newly_ready.append(neighbor)
        if newly_ready:
            queue.extend(sorted(newly_ready, key=lambda item: concept_map[item]["label"].lower()))

    if len(order) != len(concept_map):
        remaining = sorted(set(concept_map) - set(order), key=lambda item: concept_map[item]["label"].lower())
        order.extend(remaining)
    prerequisites = {
        concept_id: sorted(incoming.get(concept_id, set()), key=lambda item: concept_map[item]["label"].lower())
        for concept_id in concept_map
    }
    return order, prerequisites


def render() -> str:
    concepts, relations, insights, hidden_count, graph_version = public_graph()
    positions = layout(concepts, relations)
    concept_map = {item["id"]: item for item in concepts}
    order, prerequisites = learning_order(concepts, relations)

    edge_markup: list[str] = []
    for relation in relations:
        x1, y1 = positions[relation["from"]]
        x2, y2 = positions[relation["to"]]
        dx, dy = x2 - x1, y2 - y1
        length = max(1.0, math.hypot(dx, dy))
        ux, uy = dx / length, dy / length
        start_x, start_y = x1 + ux * 98, y1 + uy * 50
        end_x, end_y = x2 - ux * 98, y2 - uy * 50
        mid_x, mid_y = (start_x + end_x) / 2, (start_y + end_y) / 2
        label = RELATION_LABELS.get(relation["type"], relation["type"])
        edge_markup.append(
            f'<g class="edge"><line x1="{start_x:.1f}" y1="{start_y:.1f}" x2="{end_x:.1f}" y2="{end_y:.1f}" marker-end="url(#arrow)"/>'
            f'<text x="{mid_x:.1f}" y="{mid_y - 7:.1f}" text-anchor="middle">{e(label)}</text></g>'
        )

    node_markup: list[str] = []
    for concept in concepts:
        x, y = positions[concept["id"]]
        insight = insights[concept["published_support"][0]]
        label = concept["label"]
        display = label if len(label) <= 25 else label[:22] + "…"
        node_markup.append(f'''<a class="node-link" href="../explainers/{e(insight['slug'])}/" aria-label="{e(label)} — open supporting explainer">
          <g class="node" transform="translate({x:.1f} {y:.1f})">
            <rect x="-112" y="-49" width="224" height="98" rx="18"/>
            <text class="node-title" x="0" y="-7" text-anchor="middle">{e(display)}</text>
            <text class="node-domain" x="0" y="18" text-anchor="middle">{e(concept['domain'])}</text>
            <text class="node-count" x="0" y="36" text-anchor="middle">{len(concept['published_support'])} public insight{'s' if len(concept['published_support']) != 1 else ''}</text>
          </g>
        </a>''')

    learning_cards: list[str] = []
    for index, concept_id in enumerate(order, start=1):
        concept = concept_map[concept_id]
        prereq_ids = prerequisites.get(concept_id, [])
        prereq = (
            "After: " + ", ".join(concept_map[item]["label"] for item in prereq_ids)
            if prereq_ids else "Foundation / no required public predecessor"
        )
        insight = insights[concept["published_support"][0]]
        learning_cards.append(f'''<li class="path-step">
          <span class="path-number">{index:02d}</span>
          <div><p class="path-meta">{e(prereq)}</p><h3>{e(concept['label'])}</h3><p>{e(concept['summary'])}</p><a href="../explainers/{e(insight['slug'])}/">Open evidence →</a></div>
        </li>''')

    concept_cards: list[str] = []
    for concept in sorted(concepts, key=lambda item: item["label"].lower()):
        public_insights = [insights[item_id] for item_id in concept["published_support"]]
        links = "".join(f'<a href="../explainers/{e(item["slug"])}/">{e(item["title"])}</a>' for item in public_insights)
        tags = "".join(f"<span>{e(tag)}</span>" for tag in concept.get("tags", []))
        concept_cards.append(f'''<article class="concept-card" id="concept-{e(concept['id'])}">
          <p class="concept-domain">{e(concept['domain'])}</p>
          <h2>{e(concept['label'])}</h2>
          <p>{e(concept['summary'])}</p>
          <div class="concept-tags">{tags}</div>
          <div class="concept-evidence"><strong>Public evidence</strong>{links}</div>
        </article>''')

    relation_rows = "".join(f'''<tr>
          <td><a href="#concept-{e(relation['from'])}">{e(concept_map[relation['from']]['label'])}</a></td>
          <td>{e(RELATION_LABELS.get(relation['type'], relation['type']))}</td>
          <td><a href="#concept-{e(relation['to'])}">{e(concept_map[relation['to']]['label'])}</a></td>
          <td>{e(relation['rationale'])}</td>
        </tr>''' for relation in relations)

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Knowledge Graph — Signal to Insight</title>
  <meta name="description" content="A cumulative concept graph showing how published Signal to Insight explainers connect and deepen one another.">
  <link rel="canonical" href="{SITE_BASE}/knowledge/">
  <link rel="stylesheet" href="../styles.css">
  <style>
    .kg-page {{ background:#f3f0e9; color:#111; }}
    .kg-wrap {{ width:min(1180px,calc(100% - 40px)); margin-inline:auto; }}
    .kg-hero {{ padding:96px 0 44px; border-bottom:1px solid rgba(0,0,0,.18); }}
    .kg-hero h1 {{ font-size:clamp(3.4rem,9vw,8.4rem); line-height:.82; letter-spacing:-.07em; margin:.14em 0 .24em; max-width:9ch; }}
    .kg-hero h1 em {{ font-family:Georgia,serif; font-weight:400; }}
    .kg-hero>p:last-child {{ max-width:720px; font-size:1.12rem; line-height:1.6; }}
    .kg-stats {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:24px; }}
    .kg-stats span {{ border:1px solid #111; padding:9px 12px; font:700 .72rem/1 monospace; text-transform:uppercase; letter-spacing:.06em; }}
    .graph-panel {{ margin:44px auto 0; background:#111; color:#f7f4ee; border-radius:28px; padding:18px; overflow:hidden; }}
    .graph-panel header {{ display:flex; justify-content:space-between; gap:16px; align-items:end; padding:12px 14px 4px; }}
    .graph-panel header p {{ max-width:620px; margin:0; color:#b9b7b1; }}
    .graph-panel svg {{ width:100%; height:auto; min-height:600px; display:block; }}
    .edge line {{ stroke:#74716a; stroke-width:1.5; }} .edge text {{ fill:#aaa69d; font:600 12px/1 monospace; }}
    .node rect {{ fill:#f3f0e9; stroke:#f3f0e9; transition:.15s ease; }}
    .node-title {{ fill:#111; font:700 14px/1.1 Arial,sans-serif; }} .node-domain,.node-count {{ fill:#66635d; font:600 10px/1 monospace; }}
    .node-link:hover rect,.node-link:focus rect {{ fill:#fff; stroke:#fff; transform:scale(1.03); transform-box:fill-box; transform-origin:center; }}
    .kg-section {{ padding:70px 0; }} .kg-section-head {{ display:flex; justify-content:space-between; gap:30px; align-items:end; margin-bottom:26px; }}
    .kg-section-head h2 {{ font-size:clamp(2rem,5vw,4rem); letter-spacing:-.05em; margin:0; }} .kg-section-head p {{ max-width:560px; margin:0; }}
    .learning-path {{ list-style:none; margin:0; padding:0; border-top:1px solid #111; }}
    .path-step {{ display:grid; grid-template-columns:90px 1fr; gap:20px; padding:24px 0; border-bottom:1px solid #111; }}
    .path-number {{ font:700 2.3rem/1 monospace; }} .path-step h3 {{ margin:.15em 0 .35em; font-size:1.7rem; }} .path-step p {{ max-width:760px; line-height:1.55; }}
    .path-meta {{ font:700 .68rem/1.4 monospace; text-transform:uppercase; letter-spacing:.05em; color:#65615a; }} .path-step a {{ color:inherit; font-weight:700; text-underline-offset:3px; }}
    .concept-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
    .concept-card {{ border:1px solid #111; padding:24px; min-height:260px; display:flex; flex-direction:column; }}
    .concept-domain {{ font:700 .7rem/1 monospace; text-transform:uppercase; letter-spacing:.08em; }} .concept-card h2 {{ font-size:1.8rem; margin:.45em 0 .35em; }}
    .concept-card>p:not(.concept-domain) {{ line-height:1.55; max-width:58ch; }}
    .concept-tags {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:auto; padding-top:20px; }} .concept-tags span {{ background:#111; color:#f7f4ee; padding:6px 8px; font:600 .68rem/1 monospace; }}
    .concept-evidence {{ border-top:1px solid rgba(0,0,0,.18); margin-top:18px; padding-top:14px; display:grid; gap:6px; }} .concept-evidence strong {{ font:700 .7rem/1 monospace; text-transform:uppercase; }}
    .concept-evidence a {{ color:inherit; text-decoration-thickness:1px; text-underline-offset:3px; }}
    .relation-table-wrap {{ overflow:auto; border:1px solid #111; }} table {{ border-collapse:collapse; width:100%; min-width:820px; }} th,td {{ padding:14px; border-bottom:1px solid rgba(0,0,0,.18); text-align:left; vertical-align:top; }} th {{ font:700 .7rem/1 monospace; text-transform:uppercase; }} td:nth-child(2) {{ font:700 .75rem/1.3 monospace; white-space:nowrap; }} td a {{ color:inherit; }}
    .kg-note {{ margin-top:18px; max-width:760px; font-size:.88rem; color:#5d5a54; }}
    @media(max-width:760px) {{ .concept-grid {{ grid-template-columns:1fr; }} .graph-panel {{ padding:8px; border-radius:18px; }} .graph-panel svg {{ min-height:440px; }} .edge text {{ display:none; }} .node-domain,.node-count {{ display:none; }} .kg-section-head {{ display:block; }} .kg-section-head p {{ margin-top:12px; }} .path-step {{ grid-template-columns:55px 1fr; }} }}
  </style>
</head>
<body class="kg-page">
  <header class="site-header kg-wrap">
    <a class="brand" href="../"><span class="brand-mark">S→I</span><span>Signal to Insight</span></a>
    <nav aria-label="Knowledge navigation"><a href="../library/">Library</a><a href="#learning-path">Learning path</a><a href="../data/knowledge-graph.json">Graph data</a></nav>
  </header>
  <main>
    <section class="kg-hero kg-wrap">
      <p class="eyebrow">CUMULATIVE KNOWLEDGE / GRAPH {e(graph_version)}</p>
      <h1>Ideas that <em>connect.</em></h1>
      <p>Each published explainer should change what the system already knows. This graph records reusable concepts and explicit relationships instead of treating every source as an isolated page.</p>
      <div class="kg-stats"><span>{len(concepts)} public concepts</span><span>{len(relations)} public relations</span><span>{hidden_count} review-only concepts withheld</span></div>
    </section>

    <section class="graph-panel kg-wrap" aria-labelledby="graph-title">
      <header><div><p class="eyebrow">PUBLIC GRAPH</p><h2 id="graph-title">Current mental model</h2></div><p>Only concepts backed by at least one published insight are rendered here. Review-only knowledge remains in structured memory but is withheld from the public view.</p></header>
      <svg viewBox="0 0 1200 760" role="img" aria-label="Concept relationship graph">
        <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#74716a"/></marker></defs>
        {''.join(edge_markup)}
        {''.join(node_markup)}
      </svg>
    </section>

    <section class="kg-section kg-wrap" id="learning-path">
      <div class="kg-section-head"><h2>Learning path</h2><p>This order is calculated from graph semantics. Prerequisites come before concepts that depend on them; enabling concepts come before what they enable; broad concepts come before refinements.</p></div>
      <ol class="learning-path">{''.join(learning_cards)}</ol>
    </section>

    <section class="kg-section kg-wrap">
      <div class="kg-section-head"><h2>Concept registry</h2><p>The registry is the durable memory layer: stable concept IDs, short definitions, tags and the published explainers that currently support each concept.</p></div>
      <div class="concept-grid">{''.join(concept_cards)}</div>
    </section>

    <section class="kg-section kg-wrap">
      <div class="kg-section-head"><h2>Why the edges exist</h2><p>Relations are typed and evidence-linked. The validator rejects dangling concepts, dangling insights, duplicate semantic edges and relations without shared evidence.</p></div>
      <div class="relation-table-wrap"><table><thead><tr><th>From</th><th>Relation</th><th>To</th><th>Rationale</th></tr></thead><tbody>{relation_rows}</tbody></table></div>
      <p class="kg-note">The complete machine-readable graph also contains concepts supported only by material still in review. Those nodes become public automatically when at least one linked insight is published.</p>
    </section>
  </main>
  <footer class="site-footer kg-wrap"><span>Signal to Insight</span><span>Cumulative concept memory</span><span>{len(concepts)} public / {hidden_count} withheld</span></footer>
</body>
</html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if the committed public graph page is stale")
    args = parser.parse_args()
    content = render() + "\n"
    if args.check:
        if not TARGET.exists():
            print(f"missing generated graph: {TARGET.relative_to(ROOT)}")
            return 1
        if TARGET.read_text(encoding="utf-8") != content:
            print(f"stale generated graph: {TARGET.relative_to(ROOT)} (run python scripts/build_graph.py)")
            return 1
        print("Knowledge graph build check passed.")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    print(f"generated {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
