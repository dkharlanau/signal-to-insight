#!/usr/bin/env python3
"""Generate noindex visual previews for insights in review state."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from build import INSIGHTS, ROOT, SOURCES, load, render_page

OUTPUT = ROOT / "previews"


def render_preview(insight: dict, source: dict) -> str:
    page = render_page(insight, source)
    page = page.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n  <meta name="robots" content="noindex,nofollow">',
        1,
    )
    page = re.sub(r'\n  <link rel="canonical"[^>]+>', '', page, count=1)
    page = re.sub(r'\n  <script type="application/ld\+json">.*?</script>', '', page, count=1)
    page = page.replace('<title>', '<title>[PREVIEW] ', 1)
    page = page.replace('<body class="generated-page">', '<body class="generated-page preview-page">', 1)
    banner = '<div class="preview-banner">REVIEW PREVIEW · NOT INDEXED · NOT PUBLISHED</div>'
    page = page.replace('<main>', f'{banner}\n  <main>', 1)
    return page


def expected_previews() -> dict[str, str]:
    insight_data = load(INSIGHTS)
    source_data = load(SOURCES)
    sources = {item["id"]: item for item in source_data.get("sources", [])}
    output: dict[str, str] = {}

    for insight in insight_data.get("insights", []):
        if insight.get("status") != "review":
            continue
        source = sources.get(insight.get("source_id"))
        if source is None:
            raise ValueError(f"{insight.get('id')}: source_id not found")
        output[insight["slug"]] = render_preview(insight, source) + "\n"
    return output


def build(check: bool = False) -> int:
    try:
        expected = expected_previews()
    except ValueError as exc:
        print(f"Preview build failed: {exc}")
        return 1

    failures: list[str] = []
    existing = {
        path.parent.name: path
        for path in OUTPUT.glob("*/index.html")
    } if OUTPUT.exists() else {}

    if check:
        for slug, content in expected.items():
            target = OUTPUT / slug / "index.html"
            if not target.exists():
                failures.append(f"missing preview: {target.relative_to(ROOT)}")
            elif target.read_text(encoding="utf-8") != content:
                failures.append(f"stale preview: {target.relative_to(ROOT)}")
        for slug, path in existing.items():
            if slug not in expected:
                failures.append(f"stale preview for non-review insight: {path.relative_to(ROOT)}")
    else:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for slug, path in existing.items():
            if slug not in expected:
                shutil.rmtree(path.parent)
                print(f"removed stale preview {path.parent.relative_to(ROOT)}")
        for slug, content in expected.items():
            target = OUTPUT / slug / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            print(f"generated {target.relative_to(ROOT)}")

    if failures:
        print("Preview build check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Preview build {'check ' if check else ''}passed: {len(expected)} review page(s).")
    return 0


def self_test() -> int:
    insight_data = load(INSIGHTS)
    source_data = load(SOURCES)
    published = next((item for item in insight_data.get("insights", []) if item.get("status") == "published"), None)
    if published is None:
        print("Preview self-test requires one published fixture-like insight.")
        return 1
    source = next((item for item in source_data.get("sources", []) if item.get("id") == published.get("source_id")), None)
    if source is None:
        print("Preview self-test source not found.")
        return 1

    review = dict(published)
    review["status"] = "review"
    rendered = render_preview(review, source)
    assertions = {
        "robots noindex": '<meta name="robots" content="noindex,nofollow">' in rendered,
        "no canonical": 'rel="canonical"' not in rendered,
        "no structured article": 'application/ld+json' not in rendered,
        "preview banner": 'REVIEW PREVIEW · NOT INDEXED · NOT PUBLISHED' in rendered,
        "preview body class": 'preview-page' in rendered,
    }
    failed = [name for name, ok in assertions.items() if not ok]
    if failed:
        print("Preview self-test failed: " + ", ".join(failed))
        return 1
    print("Preview self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    return build(check=args.check)


if __name__ == "__main__":
    sys.exit(main())
