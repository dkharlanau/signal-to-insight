# 20-source dogfood and reliability cohort

The next architecture investment should be justified by repeated observed friction, not by hypothetical completeness.

`python scripts/dogfood.py` records a private cohort under `.local/dogfood-cohort.json`.

## Cohort shape

Process at least 20 real sources across at least five source types and several domains. Do not choose sources only because they are easy for the current pipeline.

For each run, record:

- source type and domain;
- elapsed hands-on work time;
- agent/provider used;
- manual interventions;
- validation failures;
- structural rewrites;
- publication decision;
- Knowledge Delta false positives and trivial deltas;
- prerequisite misses;
- prior-knowledge retrieval noise;
- whether prior knowledge reduced repeated explanation;
- Source Decision calibration outcome when known;
- optional link to a private learning-utility record.

Example:

```bash
python scripts/dogfood.py record \
  --intake intake-2026-08-27-example \
  --insight example-insight \
  --source-type article \
  --domain architecture \
  --minutes 24 \
  --agent chatgpt \
  --manual-interventions 1 \
  --validation-failures 0 \
  --structural-rewrites 1 \
  --publication keep_review \
  --delta-false-positives 1 \
  --retrieval-noise 1 \
  --retrieval-saved-repetition yes \
  --source-decision-outcome not_checked
```

Report:

```bash
python scripts/dogfood.py report
python scripts/dogfood.py report --json
```

## Pair with learning evidence

For useful cases, also use `scripts/learning_utility.py` to record source-time estimate, explainer consumption time, immediate model understanding, delayed reconstruction and transfer. The dogfood cohort measures production friction/quality failure modes; the learning-utility store measures user benefit.

## Exit condition

The cohort is structurally complete when it contains at least:

- 20 unique intakes;
- five source types.

That alone is not product success. The report must identify the most frequent failure modes and the next three product changes justified by them.

Candidate architecture work such as extraction providers, embeddings, more visual primitives or a service backend should be promoted only when the cohort shows a repeated bottleneck they solve.

## Privacy

Dogfood observations are private local evidence. They may include subjective judgments and operational notes, so they are not stored in public repository data by default.

```bash
python scripts/dogfood.py self-test
```
