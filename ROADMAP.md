# Roadmap

## Product goal

Turn one supplied source into a personalized, coherent learning artifact that is faster to consume than the source while preserving the mental model needed to understand, use and later reconstruct it.

The product is source-driven, not domain-driven.

## Current state — five-source foundation proven

The first product milestone has been reached through **review-ready output** across five genuinely different real sources:

1. **video** — enterprise agent production architecture;
2. **technical documentation** — Temporal durable execution;
3. **GitHub repository / tool** — Open Policy Agent;
4. **research paper / PDF** — ReAct;
5. **outside-domain research article** — retrieval practice / delayed retention.

This proves that one stable knowledge model can handle source types with very different structures. Four newer cases remain deliberately in `review`; publication is a separate explicit decision rather than an automatic consequence of research completion.

Implemented end-to-end capabilities now include:

- owner Issue + CLI intake with normalized URL deduplication;
- graph-aware research-bundle scaffolding;
- whole-source mapping and source-safe provenance;
- explicit prior-knowledge classification before review;
- direct research paths for video, documentation, GitHub repositories, PDF/papers and web research articles;
- coherent-core and prerequisite checks;
- structured visual planning with chain / sequence / layers / comparison / decision primitives;
- atomic researched case patches instead of manual edits to large shared registries;
- review-only case materialization with CI-enforced no-auto-publish boundary;
- generated `noindex,nofollow` review previews;
- cumulative typed knowledge graph;
- strict published-only public graph projection;
- searchable public library and Knowledge surface;
- lexical + graph prior-knowledge retrieval with noise guards;
- local-first delayed reconstruction UI on generated explainers;
- CI for schemas, research bundles, graph integrity, case patches, generated outputs and browser JavaScript.

The main risk has therefore changed. It is no longer “can the repository represent and render different sources?” It is now **whether the system measurably improves understanding and retention enough to justify continued use**.

## Next milestone — prove learning utility

Do not add a backend or more source abstractions yet. Prove three things with the current system.

### 1. Review and publish intentionally

Take at least two current review explainers through a real human review:

- Temporal;
- Open Policy Agent;
- ReAct;
- retrieval practice.

For each review, check:

- central model is correct;
- important source claims have visible provenance;
- project interpretation is distinguishable from source claims;
- limitations are strong enough to prevent misuse;
- visual structure teaches rather than decorates;
- prior-knowledge graph changes are appropriate;
- publication would improve the public library rather than merely increase volume.

Only then perform a separate explicit `review → published` transition.

### 2. Test the retention loop

Use delayed recall on at least three explainers.

The minimal experiment is:

```text
read explainer
→ leave it
→ reconstruct problem / mechanism / result / boundary from memory
→ reveal compact answer key
→ record recalled / missed pieces locally
→ optionally repeat later
```

Measure whether the recall prompt captures the **mental model**, not trivia.

Do not infer an optimized spacing algorithm from the 2006 retrieval-practice study. Before becoming prescriptive about scheduling, add evidence on:

- spacing;
- feedback after failed retrieval;
- transfer / application rather than recall alone.

### 3. Test cumulative knowledge quality

For several new sources, record whether prior-knowledge retrieval:

- finds genuinely relevant concepts;
- avoids false connections across domains;
- reduces repeated explanation of known basics;
- surfaces useful contradictions/refinements;
- keeps review-only knowledge out of the public projection.

A good graph is not the one with the most nodes. It is the one that improves the next analysis.

## Near-term product work

### Review workflow

Build a safe explicit review/publish command or PR workflow that:

- can only publish an existing `review` insight;
- requires a human-supplied review decision;
- validates source/date/coherence/public projection before transition;
- updates intake, explainer, library, sitemap and public knowledge atomically;
- supports reverting a published insight to review/archived without losing provenance.

Do not auto-approve review from CI or an agent run.

### Retention model

Current implementation is intentionally small and local-first:

- one reconstruction prompt per explainer;
- compact answer key derived from the model;
- optional 2-day / 1-week local reminder state;
- recalled / missed-pieces result;
- no account;
- no backend;
- no saved free-text answer;
- no gamification.

Next additions should be evidence-driven. Candidate structured fields after the experiment proves useful:

- explicit `retention_prompt` authored with the insight rather than DOM-derived;
- application/transfer prompt for concepts where recall is insufficient;
- local review history export/import;
- concept-level due state only if it improves navigation.

### Retrieval quality

Continue hardening prior-knowledge retrieval with real cases. Prefer:

- exact concept/alias evidence;
- multiple independent topical matches;
- typed graph neighbors after a strong seed;
- transparent matched terms and relationship path.

Avoid embedding-heavy infrastructure until lexical + graph retrieval has a documented failure mode it cannot solve.

### Visual quality

The visual grammar has now been exercised on multiple structures. Improve visual components only when a real explainer exposes a comprehension or layout problem.

Useful next tests:

- decision tree source;
- state-transition source;
- a source where one real image/figure teaches more than a CSS diagram.

Do not add generated imagery by default.

## Later — publishing and discovery

After review flow and learning utility are proven:

- related explainers generated from public graph edges;
- concept pages backed only by published evidence;
- RSS/Atom;
- generated sitemap from published records;
- OpenGraph cards;
- `llms.txt` / machine-readable discovery;
- cross-links from source → concept → tool → explainer.

Quality remains more important than volume.

## Later — services / MCP

Only if repeated use shows that external access is useful:

- versioned JSON feed;
- `get_insight(slug)`;
- `search_insights(query)`;
- `get_concept(name)`;
- `get_tools_for_concept(name)`;
- MCP wrapper;
- optional private retention/context service.

The static/local-first architecture remains preferable until a service solves a demonstrated problem.

## Evaluation

The project should optimize learning utility, not output count.

Core metrics / review questions:

- time saved versus consuming the original source;
- `I can explain the central model now`;
- delayed `I can reconstruct the central model`;
- prerequisite gaps found during review;
- percentage of explainers producing a useful action/learning decision;
- useful cross-source connections versus false-positive connections;
- percentage of drafts requiring structural rewrite;
- source/date completeness;
- later ability to apply the model to a new example.

## Non-goals

- AI-news aggregation;
- mass production of generic summaries;
- forcing every idea into SAP or enterprise context;
- isolated quotes / “top takeaways” as the main product;
- storing full third-party transcripts/content;
- decorative image generation without explanatory value;
- automatic publication without human review;
- quiz banks, streaks or gamification as the product;
- sophisticated spaced repetition before a minimal delayed-recall loop proves useful;
- backend infrastructure before repeated real use proves the need.
