#!/usr/bin/env python3
"""Generate published-only Atom, llms.txt and machine-readable discovery surfaces."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
INSIGHTS = ROOT / "data" / "insights.json"
SOURCES = ROOT / "data" / "sources.json"
ATOM = ROOT / "atom.xml"
LLMS = ROOT / "llms.txt"
DISCOVERY = ROOT / "discovery.json"
SITE_BASE = "https://dkharlanau.github.io/signal-to-insight"
REPO_URL = "https://github.com/dkharlanau/signal-to-insight"
HANDOFF_SCHEMA = SITE_BASE + "/contracts/research-evidence-handoff.schema.json"
HANDOFF_DOCS = REPO_URL + "/blob/main/docs/PORTABLE_EVIDENCE_HANDOFF.md"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def reviewed_date(insight: dict) -> str:
    return str((insight.get("provenance") or {}).get("reviewed_at") or "1970-01-01")


def atom_time(day: str) -> str:
    return f"{day}T00:00:00Z"


def published_records(insights_data: dict | None = None, sources_data: dict | None = None) -> list[dict]:
    insights_data = insights_data or load(INSIGHTS)
    sources_data = sources_data or load(SOURCES)
    sources = {item.get("id"): item for item in sources_data.get("sources", []) if item.get("id")}
    records: list[dict] = []
    for insight in insights_data.get("insights", []):
        if insight.get("status") != "published":
            continue
        source = sources.get(insight.get("source_id"))
        if source is None:
            raise ValueError(f"published insight {insight.get('id')} has no registered source")
        slug = insight.get("slug")
        if not slug:
            raise ValueError(f"published insight {insight.get('id')} has no slug")
        records.append({
            "id": insight["id"],
            "title": insight["title"],
            "summary": insight.get("one_liner") or "",
            "url": f"{SITE_BASE}/explainers/{slug}/",
            "reviewed_at": reviewed_date(insight),
            "tags": sorted(insight.get("tags") or []),
            "source": {
                "id": source["id"],
                "title": source.get("title") or source.get("canonical_url"),
                "url": source.get("canonical_url"),
                "type": source.get("type"),
            },
        })
    records.sort(key=lambda item: (item["reviewed_at"], item["title"].casefold(), item["id"]), reverse=True)
    return records


def discovery_payload(records: list[dict]) -> dict:
    return {
        "version": "1.0.0",
        "projection": "published-evidence-only",
        "site": SITE_BASE + "/",
        "repository": REPO_URL,
        "atom": SITE_BASE + "/atom.xml",
        "concept_index": SITE_BASE + "/knowledge/concepts/index.json",
        "knowledge_history": SITE_BASE + "/knowledge/history.json",
        "research_evidence_handoff": {
            "schema": HANDOFF_SCHEMA,
            "documentation": HANDOFF_DOCS,
            "trust_level": "external_research_context",
        },
        "records": records,
    }


def render_atom(records: list[dict]) -> str:
    updated = atom_time(max((item["reviewed_at"] for item in records), default="1970-01-01"))
    entries: list[str] = []
    for item in records:
        tags = "".join(f'<category term="{html.escape(tag, quote=True)}"/>' for tag in item["tags"])
        source_link = ""
        if item["source"].get("url"):
            source_link = f'<link rel="via" href="{html.escape(item["source"]["url"], quote=True)}"/>'
        entries.append(
            "  <entry>\n"
            f"    <title>{xml_escape(item['title'])}</title>\n"
            f"    <id>{xml_escape(item['url'])}</id>\n"
            f"    <updated>{atom_time(item['reviewed_at'])}</updated>\n"
            f"    <link rel=\"alternate\" href=\"{html.escape(item['url'], quote=True)}\"/>\n"
            f"    {source_link}\n"
            f"    <summary>{xml_escape(item['summary'])}</summary>\n"
            f"    {tags}\n"
            "  </entry>"
        )
    entry_text = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        '  <title>Signal to Insight</title>\n'
        '  <subtitle>Reviewed source-to-understanding explainers only.</subtitle>\n'
        f'  <id>{SITE_BASE}/</id>\n'
        f'  <updated>{updated}</updated>\n'
        f'  <link rel="self" type="application/atom+xml" href="{SITE_BASE}/atom.xml"/>\n'
        f'  <link rel="alternate" href="{SITE_BASE}/"/>\n'
        '  <author><name>Dzmitryi Kharlanau</name></author>\n'
        f'{entry_text}\n'
        '</feed>\n'
    )


def render_llms(records: list[dict]) -> str:
    lines = [
        "# Signal to Insight",
        "",
        "> A source-to-understanding engine that maps the whole source, shows what changed relative to prior knowledge, preserves evidence boundaries and turns reviewed understanding into visual explainers.",
        "",
        f"Canonical site: {SITE_BASE}/",
        f"Repository: {REPO_URL}",
        f"Published-only discovery JSON: {SITE_BASE}/discovery.json",
        f"Atom feed: {SITE_BASE}/atom.xml",
        f"Explainer library: {SITE_BASE}/library/",
        f"Public knowledge graph: {SITE_BASE}/knowledge/",
        f"Published concept index: {SITE_BASE}/knowledge/concepts/index.json",
        f"Published knowledge history: {SITE_BASE}/knowledge/history.json",
        f"Research evidence handoff schema: {HANDOFF_SCHEMA}",
        f"Research evidence handoff documentation: {HANDOFF_DOCS}",
        "",
        "## Product contract",
        "",
        "Signal to Insight is not a generic summarizer. Public material is intentionally human-reviewed. Review previews, private/local context and unpublished insight records are excluded from this discovery bundle.",
        "",
        "Core loop: source → whole-source map → prior-knowledge comparison → verification → mental model → Knowledge Delta → source decision → review → published explainer.",
        "",
        "A published insight can be exported as a digest-protected research evidence handoff. The packet is external research context only: it requires human review and cannot authorize execution or stand in for production incident evidence.",
        "",
        "## Published explainers",
        "",
    ]
    if not records:
        lines.append("No reviewed explainers are currently published.")
    else:
        for item in records:
            lines.append(f"- [{item['title']}]({item['url']}) — {item['summary']}")
            source = item["source"]
            if source.get("url"):
                lines.append(f"  Source: {source.get('title') or 'Original source'} — {source['url']}")
    lines.extend([
        "",
        "## Discovery boundary",
        "",
        "Only `status=published` insights are enumerated here. Do not treat repository review previews, local/private overlays or working knowledge as published claims.",
        "",
    ])
    return "\n".join(lines)


def expected() -> dict[Path, str]:
    records = published_records()
    return {
        ATOM: render_atom(records),
        LLMS: render_llms(records),
        DISCOVERY: json.dumps(discovery_payload(records), ensure_ascii=False, indent=2) + "\n",
    }


def build(check: bool = False) -> int:
    failures: list[str] = []
    for path, content in expected().items():
        if check:
            if not path.exists():
                failures.append(f"missing discovery output: {path.relative_to(ROOT)}")
            elif path.read_text(encoding="utf-8") != content:
                failures.append(f"stale discovery output: {path.relative_to(ROOT)}")
        else:
            path.write_text(content, encoding="utf-8")
            print(f"generated {path.relative_to(ROOT)}")
    if failures:
        print("Discovery bundle check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Discovery bundle check passed." if check else "Discovery bundle generated.")
    return 0


def self_test() -> int:
    fixture_insights = {
        "insights": [
            {"id": "pub", "source_id": "s1", "slug": "published", "status": "published", "title": "Published", "one_liner": "Visible", "tags": ["z"], "provenance": {"reviewed_at": "2026-08-27"}},
            {"id": "review", "source_id": "s2", "slug": "secret-review", "status": "review", "title": "Review", "one_liner": "Must not leak", "tags": [], "provenance": {"reviewed_at": None}},
        ]
    }
    fixture_sources = {"sources": [
        {"id": "s1", "title": "Public source", "canonical_url": "https://example.com/public", "type": "article"},
        {"id": "s2", "title": "Review source", "canonical_url": "https://example.com/review", "type": "article"},
    ]}
    records = published_records(fixture_insights, fixture_sources)
    atom = render_atom(records)
    llms = render_llms(records)
    discovery = json.dumps(discovery_payload(records))
    combined = atom + llms + discovery
    if len(records) != 1 or records[0]["id"] != "pub":
        print("Discovery self-test failed: published projection is wrong.")
        return 1
    for forbidden in ("secret-review", "Review source", "example.com/review", "Must not leak"):
        if forbidden in combined:
            print(f"Discovery self-test failed: review-only marker leaked: {forbidden}")
            return 1
    if "example.com/public" not in atom or "Published" not in llms:
        print("Discovery self-test failed: published source/prose missing.")
        return 1
    print("Discovery self-test passed; review-only records are excluded from Atom, llms.txt and discovery JSON.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    try:
        return build(check=args.check)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Discovery build failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
