# Human evidence planner

The repository can now answer a practical question without fabricating subjective results:

> What real validation should I do next?

Run:

```bash
python sti.py evidence
```

or:

```bash
python scripts/evidence_plan.py
```

Use `--json` for machine-readable output.

## Why this exists

The structural product loop is much further ahead than the human evidence loop:

- 20 real sources have been structurally processed;
- every current source has the review/publish contracts required by the product;
- retrieval/preflight/public-boundary checks are automated;
- but delayed reconstruction, Source Decision calibration and local reliability observations are intentionally private human measurements.

Those measurements already have three separate local stores with different semantics:

- `.local/learning-utility.json`;
- `.local/source-decision-benchmark.json`;
- `.local/dogfood-cohort.json`.

The planner does **not** create a fourth evidence store. It reads the existing stores plus the public/review contracts and decides which missing experiment has the highest current value.

## What it plans

### #19 — delayed reconstruction + transfer

The planner counts real delayed records and their source-type diversity. If the minimum three-case / three-source-type structural target has not been reached, it recommends untested explainers from distinct source types and shows:

- the authored reconstruction prompt;
- the transfer prompt;
- the exact `learning_utility.py record` command template;
- the later `learning_utility.py delayed` template.

The command contains placeholders for actual time, reconstruction and transfer outcomes. The planner never fills those values itself.

### #39 — Source Decision calibration

The planner targets a balanced sample across:

- video;
- documentation;
- repository/tool;
- paper;
- article.

For each still-missing source group it selects a real uncalibrated insight and preserves:

- the predicted Source Decision;
- source URL;
- selected skim targets/locators when applicable;
- the exact local calibration command to run **after consuming the original source**.

This avoids choosing five convenient cases from one source type and calling the decision card calibrated.

### #40 — local dogfood reliability evidence

The planner displays two counts separately:

```text
structural sources processed
vs
sources with local real-use observations
```

This distinction is intentional. The 20 structurally processed sources in Git are not converted into local elapsed-time/manual-intervention/failure records after the fact.

If the local cohort is incomplete, the planner tells you to record the **next newly processed real source prospectively** and prints the `dogfood.py record` command template.

## Priority rule

The default next action is:

1. delayed reconstruction/transfer (#19) until the minimum diverse sample exists;
2. balanced Source Decision calibration (#39);
3. prospective dogfood observations (#40);
4. only then manual review of the accumulated evidence before adding more product/platform breadth.

This order reflects the product thesis: retained understanding and trustworthy time-saving decisions are more important than adding another integration surface.

## Privacy boundary

`evidence_plan.py` is read-only.

It does not:

- create subjective observations;
- infer recall from page content;
- infer Source Decision accuracy from Git history;
- backfill dogfood timing from commit timestamps;
- publish `.local` data;
- auto-close human-gated issues.

Only explicit future human measurements populate the existing local stores.

## Self-test

```bash
python scripts/evidence_plan.py --self-test
```

The self-test uses temporary local stores and verifies that:

- the real catalog contains the required source-type diversity;
- an empty local state recommends at least three diverse delayed-learning cases;
- an empty calibration store produces one recommendation for every required source group;
- the structural 20-source milestone is recognized while local observed sources remain zero;
- temporary learning, calibration and dogfood records are then recognized correctly.

No default `.local` store is touched by the self-test.
