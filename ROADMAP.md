# Roadmap

## Product goal

Turn one supplied source into a personalized, coherent learning artifact that is faster to consume than the source while preserving the mental model needed to understand and use it.

The product is source-driven, not domain-driven.

## Current state — foundation complete

The stable source-to-output contracts are now implemented:

- intake queue + normalized URLs;
- source/date provenance model;
- research profile;
- source adapter contracts;
- normalized research bundle;
- insight model;
- validators + cross-reference checks;
- public explainer generator;
- review-only noindex previews;
- reusable visual grammar;
- generated searchable library;
- end-to-end acceptance test;
- CI checks for knowledge integrity and generated-output drift.

This means the next work should focus on **research intelligence and real source throughput**, not adding more repository scaffolding.

## Loop 1 — Real extraction adapters

Goal: make common source types easy for an agent to inspect with consistent provenance.

Build/test concrete processing paths for:

- YouTube/video metadata + transcript/subtitle inspection when available;
- web articles/documentation;
- PDF/research papers;
- GitHub repositories;
- tool/product documentation.

Requirements:

- source-specific extraction can change without changing the research-bundle schema;
- full third-party text stays transient/private;
- extraction method/confidence/gaps are recorded;
- dates and versions come from trustworthy metadata;
- the adapter may fail visibly rather than invent content.

Success test: process at least one real example of each major source type through the same normalized bundle contract.

## Loop 2 — Research orchestrator

Goal: reduce `queued URL → review-ready explainer` to one agent task.

The orchestrator should perform:

```text
pick queued source
→ capture
→ map whole source
→ score with research profile
→ select coherent core
→ identify missing prerequisites
→ verify consequential claims
→ research useful adjacent tools/systems
→ create/update source registry
→ create insight record
→ choose visual plan
→ generate preview
→ run quality gates
→ leave for review
```

No automatic publication.

The preferred first implementation is an agent playbook/command that works with existing research tools. A custom backend is not required until repeated runs prove it is useful.

## Loop 3 — Coherence engine

Goal: make the output reliably better than a normal summary.

Add explicit checks for:

- central causal/mechanical chain;
- concept dependency graph;
- missing prerequisites;
- selected-detail contribution to the model;
- contradictions between retained claims;
- source claim vs project interpretation;
- completeness: can the reader explain the topic end-to-end?

Possible structured scores:

- coherence;
- prerequisite completeness;
- evidence confidence;
- novelty;
- practical leverage;
- tool/system relevance;
- explanation completeness.

Scores should guide review, not replace judgment.

## Loop 4 — Visual planning + explanatory assets

Goal: make the visual output adapt to the idea rather than merely apply one template.

Add a structured `visual_plan` to each insight:

- dominant primitive: chain / sequence / layers / comparison / decision / state / annotated object;
- supporting primitives;
- key labels/relationships;
- whether an image is useful;
- why the image teaches something a diagram cannot;
- source/rights notes for non-generated assets.

Then update the generator to select page composition from that plan.

Generated images should be optional. Prefer CSS/SVG diagrams for mechanisms; use generated imagery for spatial, physical or conceptual scenes where it materially improves understanding.

## Loop 5 — Accumulating personal knowledge graph

Goal: make every source improve future source analysis.

Model:

- concepts and aliases;
- concept → prerequisite;
- source → concept;
- insight → pattern;
- tool → concept;
- tool → category/alternative;
- evidence supports / contradicts;
- first-seen / last-verified dates;
- `known`, `needs_refresh`, `new_to_learn` state.

Use the graph to avoid re-explaining familiar basics while still surfacing genuinely new connections.

## Loop 6 — Better intake surfaces

Goal: make supplying a source effortless.

Possible surfaces:

- ChatGPT / connected GitHub agent;
- GitHub Issue Form with URL + optional focus;
- CLI;
- lightweight web intake page;
- browser share/bookmark action;
- API endpoint only if needed later.

All surfaces should create the same `data/inbox.json` contract.

## Loop 7 — Publishing and discovery

Goal: make useful public explainers discoverable without turning the project into a content farm.

Improve:

- generated library organization;
- related explainers;
- concept/tool pages;
- canonical metadata + structured data;
- RSS/Atom;
- `llms.txt` / machine-readable discovery;
- OpenGraph cards;
- sitemap generation from published records;
- cross-links from source → concept → tool → explainer.

Quality remains more important than volume.

## Loop 8 — Services / MCP

Only after the content model is proven across multiple real sources:

- versioned JSON feed;
- `get_insight(slug)`;
- `search_insights(query)`;
- `get_concept(name)`;
- `get_tools_for_concept(name)`;
- MCP wrapper for agent access;
- optional private profile/context service;
- optional automated PR creation for review-ready explainers.

## Loop 9 — Evaluation

Measure learning utility rather than output count.

Candidate metrics:

- time saved vs source duration/read time;
- `I understand this now` rating;
- prerequisite gaps found during review;
- percentage of explainers producing a useful action/learning decision;
- number of useful cross-source connections;
- percentage of drafts requiring structural rewrite;
- source/date completeness;
- stale-tool detection;
- later recall of the central model.

## Next acceptance milestone

Process **five genuinely different real sources**:

1. video;
2. GitHub repository/tool;
3. research paper/PDF;
4. technical documentation/article;
5. source outside the usual AI/enterprise domain with high conceptual leverage.

For each one, require:

`intake → bundle → verification → insight → visual plan → preview → review → published explainer → library`

After those five, reassess the schemas and only then introduce more backend/service complexity.

## Non-goals

- AI-news aggregation;
- mass production of generic summaries;
- forcing every idea into SAP or enterprise context;
- isolated quotes / “top takeaways” as the main product;
- storing full third-party transcripts/content;
- decorative image generation without explanatory value;
- automatic publication without review;
- backend infrastructure before repeated real-source runs prove the need.
