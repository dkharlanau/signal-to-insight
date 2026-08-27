# Real-case visual extensions

The stable explainer grammar remains intentionally small. New visual forms are added only when a real source exposes a comprehension problem that the existing causal-chain / sequence / layers / comparison / decision primitives do not express well enough.

`data/visual-extensions.json` is the experimental extension layer. It does not silently change the base `visual_plan` contract for every insight.

## Rule

A visual extension must answer two questions explicitly:

1. **Why is the existing visual insufficient for this source?**
2. **What relationship becomes easier to understand with the new form?**

If the answer is only “this looks better”, do not add the extension.

Every record therefore requires a human-readable `reason` and a semantic text fallback.

## Decision tree

Use when one explicit decision produces materially different downstream behavior.

The real acceptance case is Open Policy Agent:

```text
application reaches protected action
              ↓
       query OPA / PDP
          ↙         ↘
       allow        deny
         ↓            ↓
application       application
executes          blocks/changes
```

This visual is more useful than a pure layered diagram for one specific point: **OPA returns a decision; the application still owns enforcement on both branches.**

The validator requires:

- exactly one root;
- every other node has one incoming edge;
- every node is reachable;
- no cycle;
- at least one node marked `decision` owns a real branch with two or more outcomes.

## State transition

Use when the useful idea is a change of state, especially recovery/return behavior that a linear sequence hides.

The real acceptance case is Temporal durable execution:

```text
Workflow active
      ↓
Task ready → Worker running ─────────→ progress recorded → Workflow active
                  │
                  └─ failure → Worker lost → reconstruct from Event History → Task ready
```

The core learning is that losing a Worker changes the executor, not the durable Workflow Execution identity/progress.

The validator requires:

- a valid initial state;
- every state reachable from it;
- at least one recovery state;
- at least one directed return/recovery cycle.

A linear flow is not accepted as a state-transition extension merely because it is drawn differently.

## Source-owned real figure

Use an original source figure only when it communicates structure that would be weakened by redrawing it.

The real acceptance case is ReAct. The authors' project diagram compares:

- reason-only;
- act-only;
- ReAct combining reasoning traces with actions and observations.

Signal to Insight does **not** copy the asset into this repository. The visual record points to the source-hosted author asset and to its recorded source page, with attribution, alt text and a text fallback.

Rules:

- HTTPS only;
- image host must match the recorded source-page host;
- source page must already exist in the insight's provenance;
- `copy_policy` stays `remote_source_owned`;
- no local mirrored image file;
- attribution and rights/copy-boundary note are mandatory;
- if the remote image fails, the page falls back to a semantic text description.

This is deliberately different from generated imagery. No image is generated merely because an explainer has a hero area available.

## Runtime safety

`visual-extensions.js` is progressive enhancement.

```text
base generated visual
        ↓
extension data available + valid runtime path?
        ├─ no → keep base visual
        └─ yes
            ├─ decision/state extension → replace base dominant visual
            └─ source figure → keep base visual + add original figure
```

If the extension JSON, JavaScript or remote figure is unavailable, the explainer remains readable.

Each extension includes a `<details>` text fallback. The source-figure fallback is automatically exposed if the remote image fails to load.

## Responsive behavior

Decision-tree layers and state grids collapse to a single reading column on narrow screens. Branch labels remain textual rather than relying on connector lines alone.

The source-owned figure preserves its intrinsic aspect ratio. On small screens, a large source figure may scroll horizontally rather than being shrunk until labels become unreadable.

## Validation

```bash
python scripts/validate_visual_extensions.py
python scripts/validate_visual_extensions.py --self-test
node --check visual-extensions.js
```

The self-test deliberately breaks:

- a decision tree by adding a cycle;
- a state machine by removing the recovery/return structure;
- a source figure by moving it to an unrelated image host.

All three mutations must be rejected.

## Relationship to the base grammar

The base grammar in `docs/VISUAL_GRAMMAR.md` remains the default contract.

Use the extension layer only after a real review-ready insight demonstrates that one of these richer forms improves comprehension. Once a primitive proves useful across multiple independent sources, it can later graduate into the stable `visual_plan` schema rather than remaining an extension.
