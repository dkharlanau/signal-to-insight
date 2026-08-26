# Personalized source-to-understanding pipeline

Signal to Insight is designed around one user action: provide a source. The system should do the analytical work needed to turn that source into a useful mental model, connect it to prior knowledge, and produce a reviewable visual explainer.

```text
SOURCE
  ↓
1. CAPTURE
  ↓
2. LOAD PRIOR KNOWLEDGE
  ↓
3. MAP THE WHOLE SOURCE
  ↓
4. APPLY RESEARCH PROFILE
  ↓
5. SELECT A COHERENT CORE
  ↓
6. VERIFY + ENRICH
  ↓
7. BUILD THE MENTAL MODEL
  ↓
8. MERGE INTO KNOWLEDGE GRAPH
  ↓
9. MAP TO ACTION
  ↓
10. DESIGN THE EXPLAINER
  ↓
11. QUALITY GATE
  ↓
REVIEWED LANDING PAGE + STRUCTURED DATA + CUMULATIVE KNOWLEDGE
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

## 2. Load prior knowledge

Before interpreting a new source, query `data/knowledge-graph.json` for concepts already known around the topic.

```bash
python scripts/graph_context.py "durable workflow retry"
```

The retrieval result should include relevant concepts, neighboring relations and the insights that currently support them. Treat it as prior knowledge, not as a conclusion about the new source.

For every important idea in the new source, classify the relationship to existing knowledge as one of:

- **reinforcement** — adds evidence or another example without changing the model;
- **refinement** — makes an existing concept more precise or concrete;
- **contradiction** — conflicts with an existing model and needs explicit resolution;
- **new knowledge** — introduces a genuinely new concept or relation.

Do not create a new concept merely because a source uses different wording. Prefer stable concept IDs and aliases when the underlying idea is the same.

## 3. Map the whole source

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

## 4. Apply the research profile

Use `config/research-profile.json` as the personalization layer. Score candidate material on:

- relevance;
- novelty;
- conceptual leverage;
- practical applicability;
- tool/system value;
- evidence strength;
- connection to existing knowledge.

Topic match alone is not enough. A concept outside the usual domains can be retained when it has high learning or practical value.

## 5. Select a coherent core

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

## 6. Verify and enrich

Research beyond the source when needed to:

- verify consequential claims;
- define unfamiliar prerequisites;
- compare a tool with its category or alternatives;
- find official documentation;
- identify where the source oversimplifies;
- add a better practical example.

Prefer primary and official sources for technical facts. Store supporting links and access dates in the structured record.

## 7. Build the mental model

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

## 8. Merge into the knowledge graph

Update `data/knowledge-graph.json` only after the coherent model exists.

For each retained concept:

- reuse an existing concept ID when the meaning is already represented;
- add the current insight ID as evidence when it reinforces or deepens that concept;
- improve a summary only when the new evidence materially improves the definition;
- move coverage from `introduced` → `explained` → `applied` only when evidence justifies it;
- add a new concept when it is genuinely distinct;
- add typed relations only when a rationale and shared evidence can be stated explicitly.

Allowed relation types are `depends_on`, `enables`, `realized_by`, `refines`, and `related_to`.

`review` knowledge may exist in the machine-readable graph so the agent can use it in later research. The public `/knowledge/` page filters out concepts with no published supporting insight, so adding graph memory must never bypass human publication review.

Run:

```bash
python scripts/validate_graph.py
python scripts/graph_context.py --self-test
python scripts/build_graph.py
```

## 9. Map to action

Every explainer should finish with an explicit personal action map:

- **Use now** — immediately applicable idea or pattern.
- **Try** — small experiment or tool worth testing.
- **Learn** — prerequisite or concept worth deeper study.
- **Build** — project or automation seed.
- **Watch** — important development with no current action.
- **Ignore for now** — low-value or premature branch.

Do not force every bucket to contain an item.

## 10. Design the explainer

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

## 11. Quality gate

A page is ready for review only when all are true:

- The source and dates are recorded.
- Prior knowledge was checked before analysis.
- The central idea can be explained in one sentence.
- Necessary prerequisites are present.
- The page is coherent from problem to action.
- Source claims and derived interpretation are distinguishable.
- Important limitations are visible.
- New concepts and relations have been merged or explicitly classified as not worth retaining.
- At least one useful application, learning path or monitoring decision exists.
- Visuals improve understanding rather than only appearance.
- The reader can understand the topic without first watching or reading the source.

Publication remains a review step; ingestion should not silently publish third-party-derived material.
