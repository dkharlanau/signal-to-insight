#!/usr/bin/env python3
"""Create a sanitized local-first Signal to Insight starter from the current clone.

The command never resets the current repository in place. It creates a new target directory,
keeps reusable contracts/runtime code, removes reference-case data and generated public content,
and installs a generic research profile plus minimal CI.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_EXAMPLE = ROOT / "config" / "research-profile.example.json"

RESET_KEYS = {
    "inbox.json": ["items"],
    "sources.json": ["sources"],
    "insights.json": ["insights"],
    "claim-evidence.json": ["records"],
    "knowledge-deltas.json": ["records"],
    "knowledge-graph.json": ["concepts", "relations"],
    "knowledge-reviews.json": ["reviews"],
    "learning-prompts.json": ["records"],
    "prerequisite-maps.json": ["records"],
    "source-decisions.json": ["records"],
    "syntheses.json": ["records"],
    "knowledge-history.json": ["entities"],
    "source-revisions.json": ["sources"],
    "reanalysis-events.json": ["events"],
}

ROOT_FILES = [
    ".gitignore",
    "LICENSE",
    "AGENTS.md",
    "sti.py",
    "app.js",
    "evidence.js",
    "library.js",
    "capture.js",
    "styles.css",
    "explainer.css",
    "preview.css",
    "evidence.css",
    "library.css",
    "decision.css",
    "retention.css",
    "synthesis.css",
    "visual-plan.css",
    "capture.css",
]


class BootstrapError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_empty_target(target: Path) -> None:
    if target.resolve() == ROOT.resolve():
        raise BootstrapError("refusing to bootstrap over the current repository")
    if target.exists() and any(target.iterdir()):
        raise BootstrapError(f"target must be empty or absent: {target}")
    target.mkdir(parents=True, exist_ok=True)


def copy_tree_if_exists(source: Path, target: Path) -> None:
    if not source.exists():
        return
    shutil.copytree(
        source,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def sanitized_data(target: Path) -> None:
    data_target = target / "data"
    data_target.mkdir(parents=True, exist_ok=True)
    for filename, keys in RESET_KEYS.items():
        source = ROOT / "data" / filename
        if source.exists():
            payload = load(source)
        else:
            payload = {}
        for key in keys:
            payload[key] = []
        if filename == "knowledge-graph.json":
            payload["updated_at"] = date.today().isoformat()
        dump(data_target / filename, payload)

    for directory in ("research-bundles", "case-patches", "run-manifests"):
        (data_target / directory).mkdir(parents=True, exist_ok=True)
        (data_target / directory / ".gitkeep").write_text("", encoding="utf-8")


def starter_readme() -> str:
    return """# Signal to Insight — local-first starter

This workspace was generated from the Signal to Insight repository without its reference-case knowledge.

## Start

```bash
python sti.py intake \"https://example.com/source\" --type article --focus \"What should I understand?\"
python sti.py scaffold <intake-id>
python sti.py context \"topic or mechanism\"
```

At that point an external capable research agent/provider must inspect the real source and write the normalized artifacts described by `AGENTS.md`. The repository intentionally does not embed a universal transcription/scraping/LLM runtime.

Validate and build deterministic surfaces:

```bash
python sti.py validate
python sti.py build
```

Publication remains human-controlled:

```bash
python sti.py publish \\
  --insight <insight-id> \\
  --confirm PUBLISH:<insight-id> \\
  --reviewed-by <name> \\
  --review-note \"What was checked\"
```

GitHub Pages is optional. The local data/contracts/CLI work without it.

See `docs/STARTER.md` for the full bootstrap and operating boundary.
"""


def starter_index() -> str:
    return """<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Signal to Insight</title><meta name=\"description\" content=\"Local-first source-to-understanding workspace.\"><link rel=\"stylesheet\" href=\"styles.css\"></head>
<body><main class=\"wrap\" style=\"padding:8vh 0\"><p class=\"eyebrow\">SIGNAL TO INSIGHT</p><h1>Source → understanding.</h1><p>Empty local-first starter. Queue a source with <code>python sti.py intake …</code>, then follow <code>AGENTS.md</code>.</p><p><a href=\"library/\">Library</a> · <a href=\"knowledge/\">Knowledge</a></p></main></body></html>
"""


def starter_workflow() -> str:
    return """name: Validate starter workspace

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: \"3.12\"
      - name: Core validation
        run: python sti.py validate
      - name: Synthetic end-to-end contract
        run: python -m unittest tests.test_e2e -v
      - name: Bootstrap portability self-test
        run: python scripts/bootstrap_starter.py --self-test
      - name: Compile Python
        run: python -m compileall -q sti.py scripts tests
"""


def create_starter(target: Path) -> None:
    ensure_empty_target(target)

    # Runtime contracts and deterministic tools.
    copy_tree_if_exists(ROOT / "scripts", target / "scripts")
    copy_tree_if_exists(ROOT / "schemas", target / "schemas")
    copy_tree_if_exists(ROOT / "docs", target / "docs")

    # Only synthetic acceptance fixtures/tests are required in the generated starter.
    (target / "tests" / "fixtures").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tests" / "fixtures" / "e2e.json", target / "tests" / "fixtures" / "e2e.json")
    shutil.copy2(ROOT / "tests" / "test_e2e.py", target / "tests" / "test_e2e.py")
    (target / "tests" / "__init__.py").write_text("", encoding="utf-8")

    for filename in ROOT_FILES:
        source = ROOT / filename
        if source.exists():
            shutil.copy2(source, target / filename)

    # Generic configuration, not the maintainer's personal research priorities.
    (target / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROFILE_EXAMPLE, target / "config" / "research-profile.json")
    shutil.copy2(PROFILE_EXAMPLE, target / "config" / "research-profile.example.json")

    sanitized_data(target)

    # Keep source handling guidance but not reference-case content.
    source_readme = ROOT / "content" / "sources" / "README.md"
    if source_readme.exists():
        (target / "content" / "sources").mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_readme, target / "content" / "sources" / "README.md")

    # Owner issue intake can be reused without copying the maintainer's full workflow set.
    issue_template = ROOT / ".github" / "ISSUE_TEMPLATE" / "source.yml"
    if issue_template.exists():
        destination = target / ".github" / "ISSUE_TEMPLATE" / "source.yml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(issue_template, destination)
    workflow = target / ".github" / "workflows" / "validate.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(starter_workflow(), encoding="utf-8")

    (target / "README.md").write_text(starter_readme(), encoding="utf-8")
    (target / "index.html").write_text(starter_index(), encoding="utf-8")

    # Generated directories start empty and are rebuilt locally as needed.
    for directory in ("explainers", "previews", "library", "knowledge", "syntheses"):
        path = target / directory
        path.mkdir(parents=True, exist_ok=True)
        (path / ".gitkeep").write_text("", encoding="utf-8")

    # Generate safe empty discovery/sitemap surfaces from the sanitized records.
    for script in ("build_sitemap.py", "build_discovery.py"):
        completed = subprocess.run([sys.executable, str(target / "scripts" / script)], cwd=target, text=True, capture_output=True)
        if completed.returncode:
            raise BootstrapError(f"starter generation failed in {script}: {(completed.stdout + completed.stderr).strip()}")


def run_checked(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    output = (completed.stdout + completed.stderr).strip()
    if completed.returncode:
        raise BootstrapError(f"command failed ({' '.join(command)}):\n{output}")
    return output


def self_test() -> int:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "starter"
            create_starter(target)

            profile = load(target / "config" / "research-profile.json")
            if profile.get("scope", {}).get("priority_areas") != []:
                raise BootstrapError("starter profile contains maintainer-specific priority areas")
            insights = load(target / "data" / "insights.json").get("insights", [])
            sources = load(target / "data" / "sources.json").get("sources", [])
            graph = load(target / "data" / "knowledge-graph.json")
            if insights or sources or graph.get("concepts") or graph.get("relations"):
                raise BootstrapError("starter data was not reset to an empty knowledge workspace")

            run_checked([
                sys.executable, "sti.py", "intake", "https://example.com/starter-fixture?utm_source=test",
                "--type", "article", "--focus", "Understand the fixture mechanism",
            ], target)
            inbox = load(target / "data" / "inbox.json").get("items", [])
            if len(inbox) != 1 or "utm_source" in inbox[0].get("source_url", ""):
                raise BootstrapError("starter CLI intake did not normalize/queue the fixture source")
            intake_id = inbox[0]["id"]
            run_checked([sys.executable, "sti.py", "scaffold", intake_id], target)
            bundle = target / "data" / "research-bundles" / f"{intake_id}.json"
            if not bundle.exists():
                raise BootstrapError("starter CLI scaffold did not create a research bundle")
            if load(bundle).get("inspection", {}).get("full_content_committed") is not False:
                raise BootstrapError("starter bundle violated raw-content boundary")

            run_checked([sys.executable, "sti.py", "validate"], target)
            run_checked([sys.executable, "-m", "unittest", "tests.test_e2e", "-v"], target)
            run_checked([sys.executable, "sti.py", "build"], target)

            if not (target / "atom.xml").exists() or not (target / "sitemap.xml").exists():
                raise BootstrapError("starter deterministic build did not produce discovery/sitemap surfaces")
    except (BootstrapError, OSError, json.JSONDecodeError) as exc:
        print(f"Starter bootstrap self-test failed: {exc}")
        return 1
    print("Starter bootstrap self-test passed: sanitized copy completed intake → scaffold → validate → synthetic E2E → build.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, help="Empty/absent target directory")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.target is None:
        parser.error("target is required unless --self-test is used")
    try:
        create_starter(args.target)
    except (BootstrapError, OSError, json.JSONDecodeError) as exc:
        print(f"Starter bootstrap failed: {exc}")
        return 1
    print(f"created sanitized Signal to Insight starter: {args.target}")
    print(f"next: cd {args.target} && python sti.py intake https://example.com/source --type article")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
