#!/usr/bin/env python3
"""Generate compact public knowledge-evolution timelines only when 2+ reviewed states exist."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVOLUTION = ROOT / "data" / "knowledge-evolution.json"
INSIGHTS = ROOT / "data" / "insights.json"
REANALYSIS = ROOT / "data" / "reanalysis-events.json"
OUTPUT = ROOT / "knowledge" / "evolution"
BASE_URL = "https://dkharlanau.github.io/signal-to-insight"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def published_ids(insights: dict) -> set[str]:
    return {item.get("id") for item in insights.get("insights", []) if item.get("status") == "published" and item.get("id")}


def public_subjects(evolution: dict, insights: dict, reanalysis: dict) -> list[dict]:
    published = published_ids(insights)
    upstream = {item.get("id"): item for item in reanalysis.get("events", []) if item.get("id")}
    output: list[dict] = []
    for subject in evolution.get("subjects", []):
        states = subject.get("states", [])
        if len(states) < 2:
            continue
        # A public semantic state must have at least one published evidence insight and may not
        # depend on review/private-only evidence. Internal history remains queryable in JSON/CLI.
        if any(
            not state.get("evidence_insight_ids")
            or any(insight_id not in published for insight_id in state.get("evidence_insight_ids", []))
            for state in states
        ):
            continue
        visible_events: list[dict] = []
        for event in subject.get("events", []):
            trigger_insight = event.get("trigger_insight_id")
            trigger_reanalysis = event.get("trigger_reanalysis_event_id")
            if trigger_insight is not None:
                if trigger_insight not in published:
                    continue
            elif trigger_reanalysis is not None:
                source_event = upstream.get(trigger_reanalysis)
                if source_event is None or source_event.get("status") != "accepted" or source_event.get("insight_id") not in published:
                    continue
            else:
                continue
            visible_events.append(event)
        item = dict(subject)
        item["events"] = visible_events
        output.append(item)
    return output


def snapshot_text(subject_type: str, snapshot: dict) -> str:
    if subject_type == "concept":
        return str(snapshot.get("summary") or "")
    return f"{snapshot.get('from')} —{snapshot.get('type')}→ {snapshot.get('to')}: {snapshot.get('rationale')}"


def render(subject: dict) -> str:
    states = sorted(subject.get("states", []), key=lambda item: (item.get("recorded_at", ""), item.get("id", "")))
    events = sorted(subject.get("events", []), key=lambda item: (item.get("recorded_at", ""), item.get("id", "")))
    title = subject["subject_id"].replace("-", " ").title()
    canonical = f"{BASE_URL}/knowledge/evolution/{subject['subject_id']}/"
    state_html = "".join(
        f'''<article class="state {'active' if state['id'] == subject['active_state_id'] else ''}">
          <div class="date">{e(state['recorded_at'])}</div>
          <div><span class="status">{e(state['status'])}</span><h2>{e(snapshot_text(subject['subject_type'], state['snapshot']))}</h2></div>
        </article>'''
        for state in states
    )
    event_html = "".join(
        f'''<li><span>{e(event['recorded_at'])}</span><strong>{e(event['kind'])}</strong><p>{e(event['reason'])}</p></li>'''
        for event in events
    ) or '<li class="muted">No public intermediate evidence events between these semantic states.</li>'
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)} · Knowledge evolution · Signal to Insight</title>
  <meta name="description" content="Reviewed evolution of the {e(subject['subject_id'])} knowledge model over time.">
  <link rel="canonical" href="{e(canonical)}">
  <style>
    :root {{ font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #171713; background: #f3f1eb; }}
    * {{ box-sizing: border-box; }} body {{ margin: 0; }} main {{ width: min(980px, calc(100% - 32px)); margin: 0 auto; padding: 58px 0 90px; }}
    a {{ color: inherit; }} .eyebrow,.date,.status {{ font: 700 11px ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; }}
    h1 {{ font-size: clamp(46px, 8vw, 82px); line-height: .93; letter-spacing: -.055em; max-width: 900px; margin: 12px 0 22px; }}
    .lede {{ max-width: 720px; font-size: 18px; line-height: 1.55; }} .timeline {{ margin-top: 58px; border-top: 1px solid #aaa69c; }}
    .state {{ display: grid; grid-template-columns: 150px 1fr; gap: 30px; padding: 34px 0; border-bottom: 1px solid #aaa69c; }}
    .state h2 {{ font-size: clamp(22px, 4vw, 38px); line-height: 1.12; margin: 9px 0 0; letter-spacing: -.025em; }}
    .active .status {{ background: #171713; color: #f3f1eb; padding: 4px 6px; }}
    section {{ padding-top: 48px; }} section h2 {{ font-size: 30px; }} ul {{ padding: 0; list-style: none; }} li {{ padding: 18px 0; border-top: 1px solid #c8c4ba; }}
    li span {{ display: inline-block; min-width: 120px; font: 11px ui-monospace, monospace; }} li strong {{ text-transform: uppercase; font-size: 12px; }} li p {{ max-width: 760px; line-height: 1.55; }} .muted {{ opacity: .6; }}
    @media (max-width: 680px) {{ .state {{ grid-template-columns: 1fr; gap: 10px; }} }}
  </style>
</head>
<body>
<main>
  <p class="eyebrow"><a href="../../">Knowledge</a> / evolution</p>
  <h1>{e(title)}</h1>
  <p class="lede">Only material, reviewed semantic states are versioned here. Reinforcement or reconsideration can be recorded without inventing a new state. The current state is the one projected by the active knowledge graph.</p>
  <div class="timeline">{state_html}</div>
  <section><h2>Evidence events</h2><ul>{event_html}</ul></section>
</main>
</body>
</html>'''


def expected_pages(evolution: dict | None = None, insights: dict | None = None, reanalysis: dict | None = None) -> dict[str, str]:
    evolution = evolution or load(EVOLUTION)
    insights = insights or load(INSIGHTS)
    reanalysis = reanalysis or load(REANALYSIS)
    return {subject["subject_id"]: render(subject) + "\n" for subject in public_subjects(evolution, insights, reanalysis)}


def build(check: bool = False) -> int:
    expected = expected_pages()
    existing = {path.parent.name: path for path in OUTPUT.glob("*/index.html")} if OUTPUT.exists() else {}
    failures: list[str] = []
    if check:
        for subject_id, content in expected.items():
            target = OUTPUT / subject_id / "index.html"
            if not target.exists():
                failures.append(f"missing evolution page: {target.relative_to(ROOT)}")
            elif target.read_text(encoding="utf-8") != content:
                failures.append(f"stale evolution page: {target.relative_to(ROOT)}")
        for subject_id, path in existing.items():
            if subject_id not in expected:
                failures.append(f"stale evolution page: {path.relative_to(ROOT)}")
    else:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for subject_id, path in existing.items():
            if subject_id not in expected:
                shutil.rmtree(path.parent)
                print(f"removed {path.parent.relative_to(ROOT)}")
        for subject_id, content in expected.items():
            target = OUTPUT / subject_id / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            print(f"generated {target.relative_to(ROOT)}")
    if failures:
        print("Knowledge evolution page check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Knowledge evolution {'check ' if check else ''}passed: {len(expected)} public timeline page(s).")
    return 0


def self_test() -> int:
    fixture = {
        "version": "1.0.0",
        "subjects": [{
            "subject_type": "concept", "subject_id": "fixture", "active_state_id": "v2",
            "states": [
                {"id": "v1", "recorded_at": "2026-08-26", "status": "superseded", "snapshot": {"summary": "Old", "coverage": "introduced"}, "evidence_insight_ids": ["p1"], "review_ids": [], "reanalysis_event_ids": []},
                {"id": "v2", "recorded_at": "2026-08-27", "status": "active", "snapshot": {"summary": "New", "coverage": "explained"}, "evidence_insight_ids": ["p2"], "review_ids": [], "reanalysis_event_ids": []},
            ],
            "events": [{"id": "e", "kind": "refined", "recorded_at": "2026-08-27", "material_state_change": True, "from_state_id": "v1", "to_state_id": "v2", "evidence_lineage": "independent_source", "trigger_insight_id": "p2", "trigger_reanalysis_event_id": None, "review_ids": [], "evidence_claim_ids": [], "reason": "Published refinement."}]
        }]
    }
    insights = {"insights": [{"id": "p1", "status": "published"}, {"id": "p2", "status": "published"}]}
    pages = expected_pages(fixture, insights, {"events": []})
    rendered = pages.get("fixture", "")
    if "Old" not in rendered or "New" not in rendered or "Published refinement" not in rendered:
        print("Knowledge evolution renderer self-test failed: multi-state timeline was not rendered.")
        return 1
    private = json.loads(json.dumps(fixture))
    private["subjects"][0]["states"][1]["evidence_insight_ids"] = ["review-only"]
    if expected_pages(private, insights, {"events": []}):
        print("Knowledge evolution renderer self-test failed: review-only state leaked to public output.")
        return 1
    one_state = json.loads(json.dumps(fixture))
    one_state["subjects"][0]["states"] = [one_state["subjects"][0]["states"][1]]
    if expected_pages(one_state, insights, {"events": []}):
        print("Knowledge evolution renderer self-test failed: thin one-state timeline was generated.")
        return 1
    print("Knowledge evolution renderer self-test passed; only multi-state published history is exposed.")
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
