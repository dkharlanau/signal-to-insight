# One-command source run

`run_source.py` is the deterministic entry point for starting or resuming one source-to-insight run.

It does not contain an LLM runtime, scraping service or publication agent. Its job is to prepare stable repository context, preserve the run's starting revision, detect what has already been completed and tell the external research agent the exact next blocking action.

## Start from a URL

```bash
python scripts/run_source.py \
  "https://example.com/source" \
  --type article \
  --focus "What should I understand, test or use from this?"
```

The command:

1. normalizes the URL;
2. reuses an equivalent intake when one already exists;
3. otherwise creates a new intake;
4. creates the graph-aware research bundle only when missing;
5. writes `data/run-manifests/<intake-id>.json`;
6. prints the exact next blocking action.

## Resume from an intake

```bash
python scripts/run_source.py intake-2026-08-26-example-source
```

The existing bundle is never overwritten just because the command was run again. The manifest preserves its original context snapshot and also records the currently observed profile/graph revision.

## Manifest

A manifest records:

- intake ID and canonical submitted URL;
- source type and requested focus;
- first-run and last-check timestamps;
- initial research-profile version;
- initial knowledge-graph version/date;
- current profile/graph revision on resume;
- research-bundle path;
- expected output paths;
- current pipeline state;
- exact next blocker;
- external-agent handoff contract;
- deterministic check results once the case is review-ready.

The manifest intentionally contains no full third-party source text and no hidden model state.

## Resume logic

The command checks the pipeline in order:

```text
source inspected + whole-source map
→ prior knowledge classified
→ source registered
→ insight linked + review-ready
→ Knowledge Delta present
→ authored learning prompt present
→ intake state synchronized
→ validators + generated-output checks
→ human review / explicit publication
```

It stops conceptually at the first missing requirement and reports that as `next_blocking_action`.

This lets a capable agent pick up an interrupted source without rereading the repository to rediscover the workflow.

## Mature-run checks

Once the case already has a review-ready insight, Knowledge Delta and learning prompt, the command runs deterministic checks including:

```text
validate.py
validate_knowledge_deltas.py
validate_learning_prompts.py
validate_graph.py
validate_bundles.py
build.py --check
build_previews.py --check
```

If a check fails, that exact check becomes the next blocker in the manifest. Use `--no-checks` only when another process will run the checks separately.

## Machine-readable output

```bash
python scripts/run_source.py <url-or-intake> --json
```

## Provider independence

The manifest handoff points to `AGENTS.md`. The research step may be performed by any capable agent/provider that can inspect the source and edit the repository according to the contracts.

Provider-specific extraction belongs behind source adapters later. The source-run command itself remains deterministic and provider-independent.

## Publication boundary

A successful source run ends at a reviewable artifact. Publication still requires the explicit owner-confirmed `PUBLISH:<insight-id>` workflow.

The source-run command never auto-publishes.

## Self-test

```bash
python scripts/run_source.py --self-test
```

The self-test checks that an existing mature case exposes a deterministic state and that a synthetic fresh bundle correctly reports source research as the first blocker without changing repository data.
