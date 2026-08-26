# Explainer visual grammar

The visual system exists to reduce explanation time. A visual component must show a mechanism, relationship, contrast, sequence, state, decision or concrete object. Decorative imagery is secondary.

Do not force every explainer into the same page composition. Choose visuals from the structure of the idea.

## Primitive selection

### Causal chain

Use when the insight answers **why A produces B**.

```text
problem → mechanism → consequence
```

Best for:
- architectural reasoning;
- system failures;
- causal explanations;
- strategic implications.

CSS primitive: `.visual-chain` or the primary `.model-flow`.

### Sequence

Use when order matters.

```text
request → authorize → execute → verify
```

Best for:
- workflows;
- protocols;
- setup paths;
- lifecycle explanations.

CSS primitive: `.visual-sequence`.

### Layered system

Use when components sit above/below or wrap one another.

```text
experience
──────────
orchestration
──────────
data / infrastructure
```

Best for:
- architectures;
- abstractions;
- tool stacks;
- system boundaries.

CSS primitive: `.visual-layers`.

### Comparison

Use when the key learning comes from a changed assumption or trade-off.

```text
before | after
POC    | production
A      | B
```

Best for:
- alternatives;
- old/new models;
- category comparisons;
- misconception correction.

CSS primitive: `.visual-compare`.

### Decision

Use when the reader needs to choose what to do.

```text
condition
├─ use
├─ try
└─ ignore
```

Best for:
- selection guides;
- tool adoption;
- operational rules;
- troubleshooting.

CSS primitive: `.visual-decision`.

## Supporting components

Every explainer may also use:

- concept cards — prerequisites and vocabulary;
- tool cards — concrete tools/systems, with explicit source/enrichment relationship;
- example cards — transfer the model into another domain;
- limitation list — conditions where the simplified model is incomplete;
- action map — use / try / learn / build / watch / ignore;
- source panel — canonical source, creators, dates and verification/enrichment sources.

## Visual density

A page should have one dominant explanatory visual per major idea. Avoid grids of tiny diagrams. Prefer one readable model followed by supporting text/cards.

Large screens may use horizontal flows. Mobile layouts must collapse into a meaningful vertical reading order.

## Generated images

Generated illustrations are optional. Add one only when it does explanatory work that CSS/SVG diagrams cannot do efficiently, for example:

- spatial or physical systems;
- annotated device/product views;
- conceptual scenes where spatial metaphor improves comprehension.

Do not use generated images simply as headers or decoration. Source imagery should only be used when licensing/provenance is clear and it materially helps understanding.

## Variation without inconsistency

Keep stable:

- typography;
- spacing rhythm;
- source/date treatment;
- action vocabulary;
- provenance rules;
- component semantics.

Vary:

- dominant primitive;
- section ordering when the source requires it;
- number of concept/tool/example cards;
- diagrams and relationships;
- whether a tool section exists at all.

The goal is a recognizable system, not identical pages.
