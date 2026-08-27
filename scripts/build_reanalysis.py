#!/usr/bin/env python3
"""Generate noindex review pages for living-source reanalysis events."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "data" / "reanalysis-events.json"
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"
OUTPUT = ROOT / "previews" / "reanalysis"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def list_items(values: list[str], empty: str) -> str:
    if not values:
        return f'<p class="empty">{e(empty)}</p>'
    return "<ul>" + "".join(f"<li>{e(value)}</li>" for value in values) + "</ul>"


def render(event: dict, source: dict, insight: dict) -> str:
    change = event["source_change"]
    model = event["mental_model"]
    review = event["review"]
    evidence = "".join(
        f'<li><a href="{e(url)}" target="_blank" rel="noreferrer">{e(url)}</a></li>'
        for url in change.get("evidence_urls", [])
    )
    files = list_items(change.get("changed_files", []), "No changed-file list was required for this observation.")
    model_changed = list_items(model.get("changed", []), "No mental-model change is currently identified.")
    model_stable = list_items(model.get("still_valid", []), "Still-valid statements have not been classified yet.")
    unresolved = list_items(model.get("unresolved", []), "No unresolved review questions recorded.")
    review_state = (
        "Human review pending"
        if review.get("decision") == "pending"
        else f"{review.get('decision')} · {review.get('reviewed_by')} · {review.get('reviewed_at')}"
    )

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>[REANALYSIS] {e(source['title'])} — Signal to Insight</title>
  <style>
    :root {{ font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #171713; background: #f3f1eb; }}
    * {{ box-sizing: border-box; }} body {{ margin: 0; }} main {{ width: min(1000px, calc(100% - 32px)); margin: 0 auto; padding: 44px 0 80px; }}
    .banner {{ border: 1px solid currentColor; padding: 10px 12px; font: 700 11px ui-monospace, monospace; letter-spacing: .08em; }}
    header {{ padding: 64px 0 42px; border-bottom: 1px solid #aaa69c; }} .eyebrow {{ font: 700 11px ui-monospace, monospace; letter-spacing: .12em; }}
    h1 {{ max-width: 850px; font-size: clamp(40px, 7vw, 74px); line-height: .96; letter-spacing: -.05em; margin: 12px 0 22px; }}
    .lede {{ max-width: 780px; font-size: 18px; line-height: 1.55; }} .meta {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 1px; background: #aaa69c; border: 1px solid #aaa69c; margin-top: 34px; }}
    .meta div {{ background: #f3f1eb; padding: 16px; }} dt {{ font: 700 10px ui-monospace, monospace; text-transform: uppercase; }} dd {{ margin: 6px 0 0; overflow-wrap: anywhere; }}
    section {{ padding: 42px 0; border-bottom: 1px solid #aaa69c; }} h2 {{ font-size: 30px; margin: 0 0 18px; }} h3 {{ font-size: 16px; margin: 28px 0 10px; }}
    p, li {{ line-height: 1.55; }} code {{ font-size: .88em; }} .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 36px; }}
    .impact {{ display: inline-block; border: 1px solid currentColor; padding: 7px 9px; font: 700 11px ui-monospace, monospace; text-transform: uppercase; }}
    .pending {{ background: #fff1a8; }} .empty {{ opacity: .55; }} a {{ color: inherit; }}
    @media (max-width: 760px) {{ .meta,.grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
<main>
  <div class="banner">REANALYSIS REVIEW · NOINDEX · NO AUTOMATIC PUBLIC KNOWLEDGE CHANGE</div>
  <header>
    <p class="eyebrow">LIVING SOURCE · {e(event['status'])}</p>
    <h1>{e(source['title'])}</h1>
    <p class="lede">{e(change['summary'])}</p>
    <dl class="meta">
      <div><dt>Insight</dt><dd>{e(insight['title'])}</dd></div>
      <div><dt>From</dt><dd><code>{e(event['from_revision']['id'])}</code></dd></div>
      <div><dt>To</dt><dd><code>{e(event['to_revision']['id'])}</code></dd></div>
      <div><dt>Checked</dt><dd>{e(event['checked_at'])}</dd></div>
    </dl>
  </header>

  <section>
    <h2>What changed upstream</h2>
    <p>{e(change['commit_count'])} commit(s) · {e(len(change.get('changed_files', [])))} changed file(s).</p>
    <details><summary>Changed files</summary>{files}</details>
    <h3>Diff evidence</h3><ul>{evidence}</ul>
  </section>

  <section>
    <h2>Mental-model impact</h2>
    <p><span class="impact">{e(model['impact'])}</span></p>
    <div class="grid">
      <div><h3>Changed</h3>{model_changed}</div>
      <div><h3>Still valid</h3>{model_stable}</div>
    </div>
    <h3>Unresolved</h3>{unresolved}
  </section>

  <section>
    <h2>Publication boundary</h2>
    <p class="{'pending' if review.get('decision') == 'pending' else ''}">{e(review_state)}</p>
    <p>This event is provenance about source evolution. It does not mutate the existing insight, graph or public explainer. A model-changing decision must first be human-reviewed, then applied as a separate reviewed knowledge change.</p>
    {f'<p>{e(review.get("note"))}</p>' if review.get('note') else ''}
  </section>
</main>
</body>
</html>'''


def expected_pages() -> dict[str, str]:
    events = load(EVENTS)
    sources = {item["id"]: item for item in load(SOURCES).get("sources", [])}
    insights = {item["id"]: item for item in load(INSIGHTS).get("insights", [])}
    output: dict[str, str] = {}
    for event in events.get("events", []):
        source = sources.get(event.get("source_id"))
        insight = insights.get(event.get("insight_id"))
        if source is None or insight is None:
            raise ValueError(f"{event.get('id')}: source/insight not found")
        output[event["id"]] = render(event, source, insight) + "\n"
    return output


def build(check: bool = False) -> int:
    try:
        expected = expected_pages()
    except ValueError as exc:
        print(f"Reanalysis preview build failed: {exc}")
        return 1
    existing = {path.parent.name: path for path in OUTPUT.glob("*/index.html")} if OUTPUT.exists() else {}
    failures: list[str] = []
    if check:
        for event_id, content in expected.items():
            target = OUTPUT / event_id / "index.html"
            if not target.exists():
                failures.append(f"missing reanalysis preview: {target.relative_to(ROOT)}")
            elif target.read_text(encoding="utf-8") != content:
                failures.append(f"stale reanalysis preview: {target.relative_to(ROOT)}")
        for event_id, path in existing.items():
            if event_id not in expected:
                failures.append(f"stale reanalysis preview: {path.relative_to(ROOT)}")
    else:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for event_id, path in existing.items():
            if event_id not in expected:
                shutil.rmtree(path.parent)
                print(f"removed {path.parent.relative_to(ROOT)}")
        for event_id, content in expected.items():
            target = OUTPUT / event_id / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            print(f"generated {target.relative_to(ROOT)}")
    if failures:
        print("Reanalysis preview check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Reanalysis preview {'check ' if check else ''}passed: {len(expected)} page(s).")
    return 0


def self_test() -> int:
    pages = expected_pages()
    if not pages:
        print("Reanalysis preview self-test requires at least one event.")
        return 1
    rendered = next(iter(pages.values()))
    checks = {
        "noindex": 'name="robots" content="noindex,nofollow"' in rendered,
        "review boundary": "NO AUTOMATIC PUBLIC KNOWLEDGE CHANGE" in rendered,
        "source change": "What changed upstream" in rendered,
        "mental model": "Mental-model impact" in rendered,
        "publication boundary": "Publication boundary" in rendered,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("Reanalysis preview self-test failed: " + ", ".join(failed))
        return 1
    print("Reanalysis preview self-test passed.")
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
