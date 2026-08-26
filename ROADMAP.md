# Roadmap

## Product goal

Turn one supplied source into a personalized, coherent learning artifact that is faster to consume than the source but preserves the mental model needed to understand and use it.

The product is source-driven, not domain-driven.

## Phase 1 — Prove the learning format

Goal: make each explainer genuinely useful before automating ingestion.

- Publish 5–10 explainers across different source types and domains.
- Include at least one tool/repository explainer, one research source, one video and one custom/system architecture.
- Test whether a reader can understand the subject without first consuming the source.
- Establish visual patterns for architecture, sequence, comparison, state, decision and tool maps.
- Keep `data/insights.json` aligned with every published explainer.
- Record canonical source metadata and dates for every item.
- Add explicit `use / try / learn / build / watch / ignore` outcomes.

## Phase 2 — Personalized intake agent

Goal: reduce a supplied URL/source to a high-quality reviewable draft.

```text
URL / file / repo / tool
        ↓
source + date capture
        ↓
whole-source content map
        ↓
research profile scoring
        ↓
coherent-core selection
        ↓
verification + prerequisite research
        ↓
mental model
        ↓
action map
        ↓
visual explainer draft
        ↓
human review
```

Capabilities:

- YouTube transcript/subtitle extraction when legally and technically available;
- webpage/article parsing;
- PDF/paper analysis;
- GitHub repository inspection;
- documentation/tool research;
- source metadata capture;
- supporting-source search;
- automatic prerequisite detection;
- relevance and novelty scoring against `config/research-profile.json`.

Important constraint: intake creates a draft, never silently publishes third-party-derived content.

## Phase 3 — Coherence and quality engine

Goal: prevent the common failure mode of producing disconnected bullet points.

- Build a concept dependency graph for each source.
- Detect missing prerequisites.
- Identify the source's main causal/mechanical chain.
- Remove repeated or non-contributing detail.
- Check that selected concepts remain understandable together.
- Add a completeness score: can the reader explain the topic end-to-end?
- Add a visual-utility gate: every diagram/image must teach something.

## Phase 4 — Accumulating knowledge graph

Goal: make every new source improve future analysis.

- concepts and aliases;
- concept → prerequisite relationships;
- source → concept relationships;
- insight → pattern relationships;
- tool → concept relationships;
- tool → alternative/category relationships;
- supporting and contradictory evidence;
- confidence and review state;
- dates and freshness;
- reusable visual models;
- `already_known` vs `new_to_learn` signals.

Future agents should use this graph to avoid re-explaining familiar basics while detecting genuinely new connections.

## Phase 5 — Visual explainer generator

Goal: generate a polished landing page from the semantic model rather than directly from raw transcript text.

- choose page narrative based on source type;
- select diagram type from the mental model;
- create meaningful visual assets when diagrams are insufficient;
- create tool/system cards with primary documentation links;
- show source + date visibly;
- add mobile-first reading mode;
- keep pages static and GitHub Pages-friendly where possible.

## Phase 6 — Services

Only after the content and quality models are stable:

- versioned JSON feed;
- source intake endpoint;
- search endpoint;
- RSS / Atom;
- `get_insight(slug)`;
- `search_insights(query)`;
- `get_concept(name)`;
- `get_tools_for_concept(name)`;
- MCP wrapper for agent access;
- optional private profile/context service;
- optional GitHub Action that opens generated explainers as PRs for review.

## Phase 7 — Evaluation

Measure the product on learning utility rather than output volume.

Potential metrics:

- time saved vs source duration/read time;
- concept recall after reading;
- percentage of explainers that produce a useful action/learning decision;
- number of useful cross-source connections discovered;
- percentage of generated drafts requiring major restructuring;
- source/date completeness;
- stale-tool detection rate;
- user rating: `I understand this now`.

## Non-goals

- AI-news aggregation;
- mass production of generic summaries;
- forcing every idea into SAP or enterprise context;
- collecting isolated quotes or “top 10 takeaways”;
- storing full third-party transcripts;
- decorative image generation without explanatory value;
- automatic publication without review;
- backend infrastructure before the learning format proves valuable.
