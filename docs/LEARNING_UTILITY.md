# Learning utility

Signal to Insight should optimize retained, usable understanding rather than the number of generated pages.

The measurement loop is deliberately local-first. Personal review results live by default in:

```text
.local/learning-utility.json
```

`.local/` is gitignored. The public repository contains the schema and tooling, not the user's experiment history or free-text reconstruction answers.

## What is measured

One immediate record captures:

- estimated minutes required to consume the original source;
- minutes actually spent on the explainer;
- whether the central model can be explained immediately (`yes / partial / no`);
- the practical decision produced by the source (`use_now / try / learn / build / watch / ignore_for_now`).

A later review can attach:

- delay in days;
- whether the central model was reconstructed (`complete / partial / failed`);
- labels for model pieces recalled and missed;
- whether the model transferred to a new example (`applied / partial / failed / not_tested`).

Do not store the learner's full free-text reconstruction answer. Record only compact model-piece labels such as `problem`, `mechanism`, `result`, `boundary`, or a more specific authored label.

## Record an immediate result

```bash
python scripts/learning_utility.py record \
  --insight temporal-durable-execution-mental-model \
  --source-minutes 35 \
  --explainer-minutes 7 \
  --immediate yes \
  --decision learn
```

The command prints a local record ID. Keep that ID for the delayed review.

## Attach a delayed reconstruction result

```bash
python scripts/learning_utility.py delayed \
  --record-id <record-id> \
  --days 2 \
  --reconstruction partial \
  --recalled "problem;mechanism;result" \
  --missed "boundary" \
  --transfer partial
```

The command does not schedule the delay. It records an observation only after the review has actually happened.

## Aggregate report

```bash
python scripts/learning_utility.py report
```

or machine-readable output:

```bash
python scripts/learning_utility.py report --json
```

The report includes:

- attempts;
- estimated source minutes versus explainer minutes;
- estimated minutes saved and compression ratio;
- immediate can-explain rate;
- delayed complete-reconstruction rate;
- transfer-applied rate;
- action-decision distribution;
- most frequently missed model pieces.

## How the metrics guide product decisions

The metrics are diagnostic, not a score to optimize blindly.

- **Time saved is positive, but reconstruction fails** → the explainer may be over-compressed or structurally unclear.
- **Immediate understanding is high, delayed reconstruction is weak** → add a better reconstruction prompt, clearer causal structure or stronger boundary statement rather than more prose.
- **Recall is good, transfer is weak** → add an application example or transfer prompt; memorizing the model is not enough.
- **The same model piece is repeatedly missed** → revise the explainer component that teaches that piece.
- **Many sources end in `ignore_for_now`** → source selection or personalization is weak even if the generated pages look good.
- **Explainer time approaches source time** → the product is not compressing enough to justify itself unless the source is unusually difficult or the explainer adds substantial synthesis value.

Do not infer a universal spaced-repetition schedule from this log. Scheduling is a later evidence question.

## Privacy boundary

The schema is public so the local state remains portable and auditable. The actual local log is intentionally not part of generated pages, public JSON feeds, the knowledge graph or GitHub Actions artifacts.

The CLI self-test uses a temporary directory:

```bash
python scripts/learning_utility.py self-test
```

It verifies record creation, delayed update and aggregate reporting without writing personal state into the repository.
