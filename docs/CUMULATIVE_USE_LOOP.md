# Cumulative use loop

Signal to Insight should become more useful after knowledge is consumed, tested and revised. This layer closes three gaps without adding a backend.

## 1. Insight → action → outcome

`data/insights.json` remains source-backed public knowledge. Personal experiments do not become source evidence.

Use the private local store:

```bash
python scripts/action_outcomes.py add \
  --insight <insight-id> \
  --action "Try the mechanism in one bounded workflow" \
  --hypothesis "It should reduce manual recovery work" \
  --intended-outcome "Fewer manual interventions" \
  --concepts "durable-execution;idempotency-under-retry"
```

Then record the outcome:

```bash
python scripts/action_outcomes.py finish \
  --id <outcome-id> \
  --status adopted \
  --result "Observed result"
```

Allowed resolved states are `adopted`, `rejected`, `inconclusive` and `superseded`; `tried` can represent an experiment that ran but has not produced a stable decision yet.

The default store is `.local/action-outcomes.json`, which is gitignored. Personal experience may influence later practical relevance, but it must never be presented as if an external source established it.

## 2. Knowledge evolution without rewriting history

Knowledge Delta already records how one source changes the prior model. Knowledge review records already preserve scope decisions and evidence. `scripts/knowledge_history.py` turns those durable records into a queryable temporal view without introducing a second editable source of truth.

```bash
python scripts/knowledge_history.py controlled-execution
python scripts/knowledge_history.py controlled-execution --json
```

The timeline vocabulary includes:

- `established`
- `reinforced`
- `refined`
- `narrowed`
- `contradicted`
- `reconsidered`

The current graph can continue to show the active reviewed model while this timeline preserves how that model emerged. A new source must not erase an older interpretation merely because the newer one is preferred.

## 3. Gaps → next research question

The project should not generate an engagement feed. It should identify only research targets that follow from explicit missing knowledge.

```bash
python scripts/next_research.py
python scripts/next_research.py --json
```

Candidates currently come from:

- unresolved prerequisite gaps;
- unresolved multi-source synthesis gaps;
- contradiction/refinement reviews that need more evidence.

Each target contains its origin, reason and a research question. If an already queued source appears to address the question, its intake ID is shown. Otherwise the output is a research brief — not an invented source recommendation.

## Decision boundary

These three loops deliberately keep different epistemic roles separate:

```text
external source evidence
        ↓
reviewed insight / concept model
        ↓
private action experiment
        ↓
personal outcome evidence
        ↓
future practical relevance

new external evidence
        ↓
Knowledge Delta / review
        ↓
concept evolution timeline
        ↓
remaining explicit gap
        ↓
next research question
```

The public knowledge model is evidence-backed. Personal outcomes are useful context. They are not interchangeable.
