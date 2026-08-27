# Living-source freshness and re-analysis

Documentation, repositories, tools and systems are not frozen sources. Signal to Insight therefore treats a later upstream revision as a new evidence event, not as permission to silently overwrite an existing insight.

## Core rule

```text
analyzed revision
      ↓
upstream changes
      ↓
change evidence
      ↓
mental-model impact classification
      ↓
human review
      ↓
keep current model / separately update / archive
```

A changed GitHub branch is not automatically a changed mental model. File and commit movement is only the trigger for review.

## Revision baselines

`data/source-revisions.json` records the version/revision that corresponds to the analysis.

A baseline can be:

- `direct` — the revision/version was captured during the original analysis;
- `reconstructed` — the original analysis preserved the access/review time but not the exact revision, so the best defensible upstream revision is reconstructed and the basis is recorded explicitly.

Do not present a reconstructed SHA as if it had been captured directly.

The first tracked sources are:

- Temporal documentation → official `temporalio/documentation` repository;
- Open Policy Agent → official `open-policy-agent/opa` repository, with the directly captured `v1.19.1` release marker and a reconstructed main-branch baseline.

## Detect a change

For a GitHub-backed source:

```bash
python scripts/source_freshness.py check --source src-open-policy-agent-opa-2026
```

The command resolves the configured upstream revision and compares it with the analyzed baseline. It prints a candidate event containing:

- from/to revision;
- commit count;
- changed files;
- compare URL;
- an intentionally `unknown` mental-model impact.

To persist a detected event:

```bash
python scripts/source_freshness.py check \
  --source src-open-policy-agent-opa-2026 \
  --write
```

This writes provenance only. It never edits `data/insights.json`, the graph or public explainers.

## Classify the impact

After inspecting the diff:

```bash
python scripts/source_freshness.py classify \
  --event <event-id> \
  --impact stable \
  --still-valid "The policy decision/enforcement boundary remains valid." \
  --unresolved "Recheck version-specific bundle/logging guidance before publication."
```

Allowed impact classes:

- `stable` — upstream changed but the central model remains valid;
- `refine` — the model remains useful but needs narrower or richer wording;
- `contradict` — new evidence conflicts with a material current statement;
- `supersede` — the old model should no longer be the active interpretation.

`stable` must name what remains valid. `refine/contradict/supersede` must name the changed model statements.

## Human finalization

Classification still is not publication authority. Finalization requires a reviewer, note and exact confirmation token.

Keep the current model:

```bash
python scripts/source_freshness.py finalize \
  --event <event-id> \
  --decision keep_current_model \
  --reviewed-by <reviewer> \
  --note "Reviewed changed files; central model is unaffected." \
  --confirm KEEP:<event-id>
```

Approve a separate model update:

```bash
python scripts/source_freshness.py finalize \
  --event <event-id> \
  --decision update_model \
  --reviewed-by <reviewer> \
  --note "New evidence requires the following reviewed model update." \
  --confirm UPDATE:<event-id>
```

An `update_model` decision still does **not** mutate the insight automatically. The reviewed knowledge change is applied separately so the diff, evidence and publication transition remain inspectable.

Archive uses `ARCHIVE:<event-id>`.

## Review previews

`python scripts/build_reanalysis.py` creates noindex pages under:

```text
/previews/reanalysis/<event-id>/
```

Each page shows:

- what changed upstream;
- revision evidence;
- model impact;
- changed and still-valid statements;
- unresolved questions;
- human-review state.

These pages are review surfaces, not canonical knowledge pages.

## First re-analysis observations

On 2026-08-27 the two existing living-source cases were checked against defensible analysis-time baselines.

### Temporal documentation

The official documentation repository advanced after the original analysis, but the observed changed files were in Cloud onboarding/pricing, AI guidance, SDK-version metadata and repository tooling. None of the core evidence paths used for the durable-execution mental model changed in that diff. The event is therefore classified `stable` but remains human-review pending.

### Open Policy Agent

OPA `main` advanced after the analysis while the latest release marker remained `v1.19.1`. The observed changes included parser/formatter/compiler internals and some bundle/decision-log implementation files. The high-level decision-engine versus enforcement-owner model is still supported; version-specific operational guidance should be rechecked before publication. This event also remains human-review pending.

## Safety properties

- source movement never auto-updates knowledge;
- every model-changing event retains from/to revision evidence;
- reconstructed baselines are labeled as such;
- human review is mandatory before accepting a re-analysis decision;
- `update_model` is authorization for a separate reviewed change, not an automatic mutation;
- public knowledge and review provenance remain separate.
