#!/usr/bin/env python3
"""Validate the static public/review surface before a GitHub Pages deployment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSIGHTS = ROOT / "data" / "insights.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    required_routes = {
        "root": ROOT / "index.html",
        "walkthrough": ROOT / "walkthrough" / "index.html",
        "library": ROOT / "library" / "index.html",
        "knowledge": ROOT / "knowledge" / "index.html",
        "research evidence handoff schema": ROOT / "contracts" / "research-evidence-handoff.schema.json",
        "research evidence handoff guide": ROOT / "docs" / "research-evidence-handoff" / "index.html",
    }
    for label, path in required_routes.items():
        if not path.exists():
            errors.append(f"missing public route {label}: {path.relative_to(ROOT)}")

    readme = read(ROOT / "README.md")
    for required in (
        "Golden walkthrough",
        "20-source cohort report",
        "Live knowledge site",
        "https://dkharlanau.github.io/signal-to-insight/",
        "noindex,nofollow",
        "delayed reconstruction",
        "Source Decision",
        "research evidence handoff",
    ):
        if required.lower() not in readme.lower():
            errors.append(f"README is missing public-surface proof text: {required!r}")

    root_html = read(required_routes["root"]) if required_routes["root"].exists() else ""
    if "Signal to Insight" not in root_html:
        errors.append("root product page does not identify Signal to Insight")
    if 'name="robots" content="noindex' in root_html.lower():
        errors.append("root public page must not be noindex")

    handoff_guide = read(required_routes["research evidence handoff guide"]) if required_routes["research evidence handoff guide"].exists() else ""
    for required in (
        "external_research_context",
        "Human review is required",
        "cannot authorize execution",
        "SAP Agentic Operations",
        "research-evidence-handoff.schema.json",
    ):
        if required.lower() not in handoff_guide.lower():
            errors.append(f"research evidence handoff guide is missing boundary text: {required!r}")

    walkthrough = read(required_routes["walkthrough"]) if required_routes["walkthrough"].exists() else ""
    walkthrough_requirements = (
        "Knowledge Delta",
        "Source Decision",
        "published explainer",
        "Outcome pending human benchmark",
        "What is already proven",
    )
    for required in walkthrough_requirements:
        if required.lower() not in walkthrough.lower():
            errors.append(f"walkthrough is missing proof stage/boundary: {required!r}")
    if "no delayed-recall score is invented" not in walkthrough.lower():
        errors.append("walkthrough must explicitly refuse to invent delayed-recall evidence")

    data = json.loads(read(INSIGHTS))
    published = [item for item in data.get("insights", []) if item.get("status") == "published"]
    if not published:
        errors.append("public surface requires at least one explicitly published insight")
    for insight in published:
        slug = insight.get("slug")
        if not isinstance(slug, str) or not slug:
            errors.append(f"published insight missing slug: {insight.get('id')}")
            continue
        page = ROOT / "explainers" / slug / "index.html"
        if not page.exists():
            errors.append(f"published explainer route missing: {page.relative_to(ROOT)}")
            continue
        html = read(page).lower()
        if 'name="robots" content="noindex' in html:
            errors.append(f"published explainer must not be noindex: {page.relative_to(ROOT)}")

    previews = sorted((ROOT / "previews").glob("*/index.html")) if (ROOT / "previews").exists() else []
    for preview in previews:
        html = read(preview).lower().replace(" ", "")
        if 'name="robots"content="noindex,nofollow"' not in html:
            errors.append(f"review preview is not noindex,nofollow: {preview.relative_to(ROOT)}")
        if 'rel="canonical"' in html or 'application/ld+json' in html:
            errors.append(f"review preview exposes public discovery metadata: {preview.relative_to(ROOT)}")

    sitemap = read(ROOT / "sitemap.xml") if (ROOT / "sitemap.xml").exists() else ""
    for route in (
        "https://dkharlanau.github.io/signal-to-insight/",
        "https://dkharlanau.github.io/signal-to-insight/walkthrough/",
        "https://dkharlanau.github.io/signal-to-insight/library/",
        "https://dkharlanau.github.io/signal-to-insight/knowledge/",
        "https://dkharlanau.github.io/signal-to-insight/docs/research-evidence-handoff/",
    ):
        if f"<loc>{route}</loc>" not in sitemap:
            errors.append(f"sitemap missing intended public route: {route}")
    if "/previews/" in sitemap:
        errors.append("sitemap must never expose review preview routes")

    pages_workflow = ROOT / ".github" / "workflows" / "pages.yml"
    if not pages_workflow.exists():
        errors.append("GitHub Pages deployment workflow is missing")
    else:
        workflow = read(pages_workflow)
        for action in ("actions/configure-pages@", "actions/upload-pages-artifact@", "actions/deploy-pages@"):
            if action not in workflow:
                errors.append(f"Pages workflow missing deployment action: {action}")
        for trigger in ("push:", "branches: [main]", "workflow_dispatch:"):
            if trigger not in workflow:
                errors.append(f"Pages workflow missing publication trigger: {trigger}")

    if errors:
        print(f"Public surface validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "Public surface validation passed: "
        f"{len(required_routes)} primary routes, {len(published)} published explainer(s), "
        f"{len(previews)} protected review preview(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
