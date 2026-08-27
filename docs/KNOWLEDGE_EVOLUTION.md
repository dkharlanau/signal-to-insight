# Knowledge evolution

The cumulative graph is the current reviewed interpretation. `data/knowledge-evolution.json` preserves how selected concepts and relations reached that interpretation when evidence materially changes or meaningfully challenges the model.

The goal is not to version wording. The goal is to prevent cumulative knowledge from looking timeless or silently rewriting earlier understanding.

## Two different things

A new source can matter without creating a new semantic state.

```text
new evidence
   ↓
reviewed effect
   ├─ reinforcement / reconsideration / boundary refinement
   │      → record an evolution event
   │      → active semantic state stays the same
   │
   └─ material definition / scope / relation change
          → preserve old state
          → create a new state
          → record reviewed transition
          → new state becomes the active graph projection
```

This distinction is important. The current OPA and ReAct reviews both refine the boundary of `controlled-execution`, but each review explicitly concluded that the existing definition already expressed the correct production-layer boundary. They are therefore recorded as `refined` events with `material_state_change=false`; no invented v2 exists.

## Transition vocabulary

The ledger supports:

- `reinforced` — independent evidence strengthens the current state without changing it;
- `refined` — evidence makes a boundary more precise; it may or may not require a new state;
- `narrowed` — the valid scope becomes materially smaller;
- `contradicted` — comparable evidence conflicts with the current model and requires review;
- `superseded` — a reviewed newer state replaces the old active interpretation;
- `restored` — a later review returns to an earlier semantic position, but as a new state rather than by pointing history backward;
- `reconsidered` — the model was explicitly rechecked, commonly after a living-source revision, and remained valid.

A restored state is a new state whose snapshot may resemble an older one. State transitions remain acyclic; history is never rewritten into a loop.

## Evidence lineage

Every event declares why it exists:

- `independent_source` — another processed source contributed evidence;
- `same_source_revision` — a living source changed and was re-analyzed;
- `review_resolution` — a human review resolved a previously open interpretation.

A re-analysis of the same source is not counted as independent corroboration. `record-reanalysis` only accepts a human-finalized re-analysis event. Stable re-analysis is recorded as `reconsidered`; a material update requires the re-analysis decision `update_model`.

## Active projection contract

For every tracked subject, exactly one state is active. Its semantic snapshot must equal the corresponding current object in `data/knowledge-graph.json`.

Concept snapshots contain:

```json
{"summary": "...", "coverage": "explained"}
```

Relation snapshots contain:

```json
{"from": "...", "to": "...", "type": "depends_on", "rationale": "..."}
```

`python scripts/validate_knowledge_evolution.py` rejects:

- active ledger state diverging from the graph;
- dangling insight, claim, review or re-analysis provenance;
- material changes backed by unresolved review;
- same-source re-analysis presented as independent evidence;
- a `superseded`/`restored` event without a new state;
- `reinforced`/`reconsidered` creating unnecessary states;
- circular state history;
- superseded states with no reviewed outgoing transition.

## Working with the ledger

Inspect a tracked subject:

```bash
python scripts/knowledge_evolution.py show \
  --type concept \
  --subject controlled-execution
```

Record a resolved review that does not change the active state:

```bash
python scripts/knowledge_evolution.py record-review \
  --type concept \
  --subject controlled-execution \
  --review <review-id> \
  --kind refined \
  --reason "Why the boundary became clearer without changing the definition"
```

For a material reviewed graph change, first apply the reviewed graph update in the same change set, then register the transition:

```bash
python scripts/knowledge_evolution.py record-review \
  --type concept \
  --subject <concept-id> \
  --review <review-id> \
  --kind refined \
  --material \
  --reason "What materially changed" \
  --confirm EVOLVE:<concept-id>
```

The command captures the current graph snapshot as the new state, preserves the previous active state, and records the provenance transition. It refuses a material transition when the referenced knowledge review explicitly says `model_change=none`.

Living-source updates use `record-reanalysis`; accepted stable revisions use `reconsidered`, while accepted `update_model` decisions can create a material state.

## Public timeline

`python scripts/build_evolution.py` generates a public timeline only when a subject has at least two meaningful semantic states and every exposed state is supported by published evidence.

Review-only states or events are not projected publicly. A one-state subject does not get a thin timeline page just to create content. Internal history remains queryable from the ledger and CLI.

This keeps temporal knowledge useful without turning the project into a cosmetic document-versioning system.
