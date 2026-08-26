# Personalized source-to-understanding pipeline

Signal to Insight is designed around one user action: provide a source. The system should do the rest of the analytical work needed to turn that source into a useful mental model and a reviewable visual explainer.

```text
SOURCE
  ↓
1. CAPTURE
  ↓
2. MAP THE WHOLE SOURCE
  ↓
3. APPLY RESEARCH PROFILE
  ↓
4. SELECT A COHERENT CORE
  ↓
5. VERIFY + ENRICH
  ↓
6. BUILD THE MENTAL MODEL
  ↓
7. MAP TO ACTION
  ↓
8. DESIGN THE EXPLAINER
  ↓
9. QUALITY GATE
  ↓
REVIEWED LANDING PAGE + STRUCTURED DATA
```

## 1. Capture

Record before analysis:

- canonical source URL or stable identifier;
- source type;
- title;
- author / speaker / organization;
- publication date when verifiable;
- event date when relevant;
- date captured by Signal to Insight;
- date analyzed / reviewed;
- language and duration when useful.

Never invent a missing publication date. Use `null` plus a date note when it cannot be verified.

## 2. Map the whole source

Build a content map before deciding what to keep:

- central problem;
- thesis;
- concepts;
- mechanisms;
- tools and systems;
- examples;
- evidence and claims;
- assumptions;
- limitations;
- unresolved questions.

This prevents the system from extracting attractive fragments while losing the logic connecting them.

## 3. Apply the research profile

Use `config/research-profile.json` as the personalization layer. Score candidate material on:

- relevance;
- novelty;
- conceptual leverage;
- practical applicability;
- tool/system value;
- evidence strength;
- connection to existing knowledge.

Topic match alone is not enough. A concept outside the usual domains can be retained when it has high learning or practical value.

## 4. Select a coherent core

The output is not a ranked list of disconnected insights.

Keep:

- the main causal chain;
- prerequisites required to understand it;
- concepts that materially change the model;
- tools or systems worth knowing;
- useful examples and counterexamples;
- constraints that prevent misuse.

Drop:

- repeated points;
- promotional framing;
- anecdotes that add no mechanism;
- detail that does not improve understanding or action.

The compression target is: **less material, same or better understanding**.

## 5. Verify and enrich

Research beyond the source when needed to:

- verify consequential claims;
- define unfamiliar prerequisites;
- compare a tool with its category or alternatives;
- find official documentation;
- identify where the source oversimplifies;
- add a better practical example.

Prefer primary and official sources for technical facts. Store supporting links and access dates in the structured record.

## 6. Build the mental model

Before writing prose, produce a model that answers:

1. What problem exists?
2. Why does it exist?
3. What are the important components?
4. How do those components interact?
5. What changes if one component is missing?
6. Where does the model stop being valid?

Preferred visual forms:

- causal chain;
- architecture map;
- sequence;
- comparison;
- state transition;
- layered system;
- decision tree;
- annotated object or UI.

## 7. Map to action

Every explainer should finish with an explicit personal action map:

- **Use now** — immediately applicable idea or pattern.
- **Try** — small experiment or tool worth testing.
- **Learn** — prerequisite or concept worth deeper study.
- **Build** — project or automation seed.
- **Watch** — important development with no current action.
- **Ignore for now** — low-value or premature branch.

Do not force every bucket to contain an item.

## 8. Design the explainer

The landing page should be understandable without consuming the original source first.

Default narrative:

```text
Why this matters
→ the mental model
→ concepts you need
→ how it works
→ tool/system map
→ concrete example
→ limitations / missing context
→ what this changes for you
→ next learning / action
→ sources + dates
```

Visuals must have explanatory work to do. Prefer a clean diagram over a decorative generated image when the diagram teaches more.

## 9. Quality gate

A page is ready for review only when all are true:

- The source and dates are recorded.
- The central idea can be explained in one sentence.
- Necessary prerequisites are present.
- The page is coherent from problem to action.
- Source claims and derived interpretation are distinguishable.
- Important limitations are visible.
- At least one useful application, learning path or monitoring decision exists.
- Visuals improve understanding rather than only appearance.
- The reader can understand the topic without first watching or reading the source.

Publication remains a review step; ingestion should not silently publish third-party-derived material.
