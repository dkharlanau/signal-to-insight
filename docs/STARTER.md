# Reusable local-first starter

Signal to Insight can be reused as a repository/workspace without turning it into a hosted service or requiring the original maintainer's knowledge corpus.

## Two ways to start

### 1. Fork/clone and keep the reference cases

Use the repository as-is when the existing examples are useful. The normal commands remain available individually or through the unified wrapper:

```bash
python sti.py intake "https://example.com/source" --type article
python sti.py scaffold <intake-id>
python sti.py context "topic"
python sti.py validate --all
python sti.py build
```

### 2. Generate an empty starter workspace

From a clone of this repository:

```bash
python scripts/bootstrap_starter.py ../my-signal-to-insight
cd ../my-signal-to-insight
```

The bootstrap command refuses to overwrite the current repository and refuses a non-empty target.

The generated workspace contains:

- schemas and deterministic processing/build scripts;
- `AGENTS.md` operating contract;
- `sti.py` unified CLI;
- a generic `config/research-profile.json` copied from `research-profile.example.json`;
- empty source/insight/graph/evidence/review/history/freshness stores;
- no reference-case research bundles or generated explainers;
- only the synthetic acceptance fixture/test;
- static CSS/JS required by generated pages;
- owner source Issue Form;
- a minimal validation workflow;
- an optional static landing page;
- empty/generated sitemap, Atom, discovery JSON and llms surfaces.

The maintainer's research priorities are not copied into the starter profile.

## Unified CLI

`sti.py` is deliberately a thin dispatcher over the existing scripts rather than a second implementation.

### Intake

```bash
python sti.py intake "https://example.com/source" \
  --type article \
  --focus "What should I understand or test?"
```

### Scaffold

```bash
python sti.py scaffold <intake-id>
```

This creates the normalized research bundle and prior-knowledge snapshot.

### Resume one source run

```bash
python sti.py run <intake-id>
```

The deterministic orchestrator reports the exact next blocker. It does not pretend to research the source by itself.

### Query accumulated knowledge

```bash
python sti.py context "durable workflow retry" --limit 5 --json
```

### Validate

```bash
python sti.py validate
python sti.py validate --all
```

The default runs the core structural/graph/bundle/private-boundary checks. `--all` adds evidence, delta, review, prerequisite, prompt, synthesis, freshness/history validation and acceptance tests.

### Build

```bash
python sti.py build
```

This regenerates published explainers, review previews, library, graph, concept pages, history, re-analysis views, sitemap and published-only discovery surfaces.

### Publish

```bash
python sti.py publish \
  --insight <insight-id> \
  --confirm PUBLISH:<insight-id> \
  --reviewed-by <name> \
  --review-note "What was checked"
```

The wrapper preserves the existing explicit human publication boundary. It does not add an automatic publication path.

## What still requires an external agent/provider

The repository owns stable contracts, cumulative memory, validation, generation and publication boundaries. It intentionally does **not** embed a universal runtime for:

- YouTube/video transcription;
- arbitrary web/article extraction;
- PDF text extraction;
- repository/tool inspection;
- LLM research/reasoning.

After intake/scaffold, a capable external research agent uses the source adapter rules and `AGENTS.md` to inspect the source, verify important claims and write normalized artifacts. Full third-party source text remains transient input and is not committed.

This separation avoids provider lock-in: the research agent/provider can change without changing the knowledge model.

## Bootstrap acceptance test

Run:

```bash
python scripts/bootstrap_starter.py --self-test
```

The test creates a temporary sanitized copy and verifies:

1. reference source/insight/graph data is empty;
2. research profile has no maintainer-specific priority areas;
3. `sti intake` queues and normalizes a synthetic source URL;
4. `sti scaffold` creates a safe bundle with `full_content_committed=false`;
5. `sti validate` passes in the clean workspace;
6. the synthetic E2E fixture proves identifier chain, raw-content boundary, deterministic public rendering and noindex review rendering;
7. `sti build` completes from the clean workspace and emits discovery/sitemap surfaces.

This is intentionally network-free. It verifies packaging/contracts, not the quality of an external research model.

## GitHub Pages

Pages is optional. The local CLI, data model, private overlay, learning state and validators work without it.

If the generated workspace is later published, enable Pages explicitly and keep the same review → publish boundary. Do not expose review previews or `.local/` data as public evidence.
