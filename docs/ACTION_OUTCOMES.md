# Insight → action → outcome

Signal to Insight should remember whether an idea actually worked in the user's context, not only whether the source looked useful.

Personal outcome evidence is private. It may influence future practical relevance and action recommendations, but it never becomes external/source evidence.

## Start an action

```bash
python scripts/action_outcomes.py start \
  --insight open-policy-agent-decision-enforcement-model \
  --action try \
  --hypothesis "Moving authorization rules out of application branching will make policy review clearer" \
  --outcome "Prototype one decision boundary and compare change/review effort" \
  --concepts "policy-as-code;policy-decision-enforcement-separation"
```

Optional `--review-at` can hold an ISO date/datetime. This is a review point, not a task-management backend.

## Record what happened

Statuses:

```text
planned → tried → adopted
                ↘ rejected
                ↘ inconclusive
                ↘ superseded
```

Example:

```bash
python scripts/action_outcomes.py update \
  --id action-open-policy-agent-decision-enforcement-model \
  --status adopted \
  --result "The explicit decision boundary reduced hidden branching in the prototype."
```

Final statuses require a result summary.

## Reuse the outcome later

```bash
python scripts/action_outcomes.py context --query "policy authorization"
```

`run_personalized.py` automatically selects relevant prior outcomes into the private run sidecar. The versioned manifest receives only an outcome-store fingerprint and selected-count metadata.

An `adopted` outcome can make a similar recommendation more practically relevant. A `rejected` outcome can warn the next analysis that the idea already failed in this context. Neither outcome proves or disproves the source claim itself.

## Report

```bash
python scripts/action_outcomes.py report
```

The aggregate is intentionally small: status counts, number of insights with outcomes and adoption rate among resolved experiments.

## Privacy boundary

Default store:

```text
.local/action-outcomes.json
```

It is included in portable local-state export/import, not public builds.

```bash
python scripts/action_outcomes.py self-test
python scripts/validate_private_boundary.py
```
