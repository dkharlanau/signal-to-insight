# Knowledge evolution and supersession

Signal to Insight keeps stable concept and relation IDs while preserving how reviewed understanding changes over time.

The graph answers **what is the active model now**. `data/knowledge-history.json` answers **how did that model get here**.

## Do not version wording for its own sake

A new source can change knowledge in two different ways:

1. it can strengthen, narrow or clarify the interpretation without changing the active graph state;
2. it can materially change the definition, scope or relation represented by the graph.

These must not be treated as the same thing.

```text
new reviewed evidence
       ↓
compare with active state
       ↓
┌───────────────────────────────┬─────────────────────────────────┐
│ no material state change      │ material state change           │
│                               │                                 │
│ reviewed observation          │ new immutable state             │
│ reinforced / refined /        │ + reviewed transition           │
│ narrowed / etc.               │                                 │
└───────────────────────────────┴─────────────────────────────────┘
```

A cosmetic rewrite, better sentence or extra example is not a new state.

## Stable entities

History tracks the same IDs used by `data/knowledge-graph.json`:

- concept IDs such as `controlled-execution`;
- relation IDs such as `rel-controlled-execution-depends-on-policy-as-code`.

A state never creates a replacement concept ID merely because the interpretation became more precise.

## States

A state is a reviewed material interpretation of one concept or relation.

Concept state snapshots preserve:

```text
summary
domain
coverage
```

Relation state snapshots preserve:

```text
from
to
type
rationale
```

The active reviewed state must match the current graph projection exactly. This makes `knowledge-history.json` an auditable history, not a competing source of current truth.

`public_state_id` is separate from `active_state_id`. Review-only knowledge can therefore exist internally without leaking into the published graph.

## Material transitions

A transition connects two different reviewed states. Supported transition semantics are:

- `refined` — the model becomes more precise or complete;
- `narrowed` — the valid scope becomes smaller or more explicit;
- `contradicted` — reviewed evidence materially conflicts with the prior state;
- `superseded` — the prior state should no longer be the active interpretation;
- `restored_reconsidered` — an older direction becomes valid again after new review, represented as a new state rather than mutating history.

A material transition requires evidence plus a review that actually authorizes a model change. A resolved review with `model_change: none` cannot create a new state.

Circular supersession/state transitions are rejected.

## Reviewed observations

An observation records important evidence about an entity when the active state does not need to change.

Observation semantics additionally include:

- `reinforced`;
- `refined`;
- `narrowed`;
- `contradicted`;
- `superseded`;
- `restored_reconsidered`.

The wording describes what the evidence did to our understanding. It does **not** imply that a new graph state exists.

The current seed case is deliberate:

### Controlled execution

The published enterprise-agent source establishes the active concept state.

OPA is retained as a reviewed refinement observation: it shows that policy decision-making is one narrower control primitive while the integrating application still owns enforcement and execution.

ReAct is retained as a reviewed narrowing observation: it separates a model-level reasoning/action loop from the production substrate that authorizes, records and verifies consequential work.

Both human reviews explicitly concluded that no concept-definition rewrite was required. The history therefore has one state and two observations — not three invented versions.

## Source revisions are not independent evidence

`data/reanalysis-events.json` records changes to living sources. A later commit or documentation revision is provenance about the same source, not automatically a new independent source of evidence.

History evidence therefore records an `independence` class:

- `independent` — evidence comes from an independent insight/review and no source-revision event is being counted;
- `source_revision` — the evidence is a new revision of an already-known living source;
- `mixed` — independent evidence and source-revision evidence participate together.

A source revision cannot be labeled independent. A `stable` re-analysis event cannot authorize a material graph state change.

If a reviewed living-source event concludes `update_model`, that decision authorizes a separate reviewed model update; the re-analysis event itself still does not rewrite the graph automatically.

## Public projection

`knowledge/history.json` is generated from `data/knowledge-history.json` using published evidence only.

Review-only OPA/ReAct observations therefore remain queryable in the repository but do not appear in the public feed until their supporting insights are intentionally published.

A timeline is exposed only when an entity has more than one meaningful visible state. One baseline state does not render a fake timeline merely to make the product look dynamic.

## Query history

Internal/review-aware view:

```bash
python scripts/knowledge_history.py controlled-execution
```

Machine-readable:

```bash
python scripts/knowledge_history.py controlled-execution --json
```

Published-evidence-only projection:

```bash
python scripts/knowledge_history.py controlled-execution --public --json
```

The command reports:

- current state;
- material state timeline only when one exists;
- reviewed observations that did not rewrite the state.

## Generate the public feed

```bash
python scripts/build_history.py
python scripts/build_history.py --check
```

The feed is written to:

```text
knowledge/history.json
```

## Validation

```bash
python scripts/validate_knowledge_history.py
python scripts/validate_knowledge_history.py --self-test
python scripts/knowledge_history.py --self-test
python scripts/build_history.py --self-test
```

The validator rejects, among other things:

- history for missing graph entities;
- active states that differ from the graph;
- public states backed only by unpublished insights;
- cosmetic duplicate states;
- material transitions authorized only by a `model_change: none` review;
- stable source revisions used as material state changes;
- source revisions mislabeled as independent evidence;
- multiple incoming state transitions;
- circular supersession/state history.

## Applying a real future model change

When evidence genuinely changes a concept or relation:

1. complete the knowledge/re-analysis review and make the model change explicit;
2. preserve the current state in `data/knowledge-history.json`;
3. append a new state with the reviewed new snapshot;
4. append exactly one transition from the prior active state;
5. update `active_state_id`;
6. update the same stable entity in `data/knowledge-graph.json` to the new reviewed snapshot;
7. update `public_state_id` only if the new state is backed by published evidence;
8. rebuild/validate the public graph and history feed together.

Never delete or overwrite the old state because the newer interpretation is preferred.
