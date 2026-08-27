#!/usr/bin/env python3
"""Generate evidence-dense public concept pages and related-explainer links from published graph evidence."""

from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "data" / "knowledge-graph.json"
INSIGHTS = ROOT / "data" / "insights.json"
OUT = ROOT / "concepts"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def published() -> dict[str, dict]:
    return {x["id"]: x for x in load(INSIGHTS).get("insights", []) if x.get("status") == "published"}


def public_evidence(concept: dict, pub: dict[str, dict]) -> list[str]:
    declared = (concept.get("public") or {}).get("evidence_insights") or concept.get("insight_ids") or []
    return [x for x in declared if x in pub]


def public_relations(graph: dict, concept_id: str, pub: dict[str, dict]) -> list[dict]:
    result = []
    for relation in graph.get("relations", []):
        if concept_id not in {relation.get("from"), relation.get("to")}:
            continue
        evidence = (relation.get("public") or {}).get("evidence_insights") or relation.get("evidence_insights") or []
        evidence = [x for x in evidence if x in pub]
        if evidence:
            result.append({**relation, "public_evidence": evidence})
    return result


def eligible(concept: dict, graph: dict, pub: dict[str, dict]) -> bool:
    evidence = public_evidence(concept, pub)
    relations = public_relations(graph, concept["id"], pub)
    # Avoid thin SEO pages: require two independent published insights, or one published
    # insight plus at least two evidence-backed relations that add explanatory structure.
    return len(set(evidence)) >= 2 or (len(set(evidence)) == 1 and len(relations) >= 2)


def related_insights(concept: dict, graph: dict, pub: dict[str, dict]) -> list[dict]:
    ids = set(public_evidence(concept, pub))
    for relation in public_relations(graph, concept["id"], pub):
        ids.update(relation["public_evidence"])
    return sorted((pub[x] for x in ids if x in pub), key=lambda x: x["title"])


def render(concept: dict, graph: dict, pub: dict[str, dict]) -> str:
    relations = public_relations(graph, concept["id"], pub)
    insights = related_insights(concept, graph, pub)
    relation_html = "".join(
        f"<li><strong>{html.escape(r['type'])}</strong> — {html.escape(r['from'])} → {html.escape(r['to'])}<br><span>{html.escape(r.get('rationale') or '')}</span></li>"
        for r in relations
    )
    insight_html = "".join(
        f"<li><a href=\"../explainers/{html.escape(i['slug'])}/\">{html.escape(i['title'])}</a></li>" for i in insights
    )
    aliases = ", ".join(concept.get("aliases") or [])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(concept['label'])} · Signal to Insight</title><meta name="description" content="{html.escape((concept.get('public') or {}).get('summary') or concept.get('summary') or '')}">
<link rel="canonical" href="https://dkharlanau.github.io/signal-to-insight/concepts/{html.escape(concept['id'])}/">
<style>body{{font-family:system-ui,sans-serif;max-width:780px;margin:0 auto;padding:48px 22px;line-height:1.55}}a{{color:inherit}}.eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-size:12px;opacity:.6}}h1{{font-size:clamp(38px,7vw,70px);line-height:1;letter-spacing:-.045em}}section{{margin-top:42px;border-top:1px solid #bbb;padding-top:22px}}li{{margin:12px 0}}span{{opacity:.72}}</style></head><body>
<p><a href="../knowledge/">← Knowledge</a></p><p class="eyebrow">Published concept</p><h1>{html.escape(concept['label'])}</h1>
<p>{html.escape((concept.get('public') or {}).get('summary') or concept.get('summary') or '')}</p>
<p><strong>Domain:</strong> {html.escape(concept.get('domain') or '—')}</p>{f'<p><strong>Also:</strong> {html.escape(aliases)}</p>' if aliases else ''}
<section><h2>Evidence-backed relations</h2><ul>{relation_html}</ul></section>
<section><h2>Supporting explainers</h2><ul>{insight_html}</ul></section>
<section><h2>Why this page exists</h2><p>This page is generated only when published evidence is dense enough to avoid a thin one-sentence concept page. Review-only/private evidence is excluded.</p></section>
</body></html>"""


def build(check: bool = False) -> tuple[int, list[str]]:
    graph = load(GRAPH)
    pub = published()
    outputs = {c["id"]: render(c, graph, pub) for c in graph.get("concepts", []) if eligible(c, graph, pub)}
    drift = []
    if check:
        existing = {p.parent.name: p.read_text(encoding="utf-8") for p in OUT.glob("*/index.html")} if OUT.exists() else {}
        for key in sorted(set(outputs) | set(existing)):
            if outputs.get(key) != existing.get(key):
                drift.append(key)
        return len(outputs), drift
    if OUT.exists():
        shutil.rmtree(OUT)
    for concept_id, text in outputs.items():
        target = OUT / concept_id / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    (OUT / "README.md").write_text("# Generated concept pages\n\nDo not edit generated HTML by hand.\n", encoding="utf-8")
    return len(outputs), []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        graph = load(GRAPH); pub = published()
        thin = [c["id"] for c in graph.get("concepts", []) if len(public_evidence(c, pub)) == 1 and not eligible(c, graph, pub)]
        if not thin:
            print("build_concepts self-test failed: expected at least one thin concept to remain suppressed")
            return 1
        print(f"build_concepts self-test passed; {len(thin)} thin concepts are suppressed until evidence grows.")
        return 0
    count, drift = build(args.check)
    if args.check and drift:
        print("Concept pages drift: " + ", ".join(drift))
        return 1
    print(f"Concept pages: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
