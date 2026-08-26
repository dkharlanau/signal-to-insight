# Signal to Insight — Agent Operating Contract

This repository is a source-to-understanding system. The agent's job is not to summarize a source. Its job is to turn a supplied source into a coherent, personalized, verified learning artifact and a reviewable visual explainer.

## Read first

Before processing any source, read:

1. `config/research-profile.json` — what is useful and how explanations should be shaped.
2. `docs/PIPELINE.md` — required reasoning and publication flow.
3. `docs/INTAKE.md` — intake lifecycle and stable identifiers.
4. `docs/SOURCE_ADAPTERS.md` — source-specific capture rules.
5. `content/sources/README.md` — provenance and copyright boundary.

## Core rule

**Map the whole source before selecting what to keep.**

Do not produce a collection of attractive fragments. Preserve the minimum complete model needed to understand the source: problem → mechanism → components → relationships → constraints → implications.

## Processing loop

For each queued item in `data/inbox.json`:

```text
queued
  ↓
capture source metadata
  ↓
create normalized research bundle
  ↓
retrieve prior knowledge
  ↓
map the whole source
  ↓
apply research profile
  ↓
verify + enrich where useful
  ↓
classify what changed vs prior knowledge
  ↓
create / update source registry
  ↓
create structured insight + curated Knowledge Delta
  ↓
review contradiction/refinement candidates
  ↓
trace important claims to evidence
  ↓
resolve prerequisite path / gaps
  ↓
author reconstruction / transfer prompts
  ↓
generate explainer
  ↓
validate + review
```

Use status transitions from `docs/INTAKE.md`. Never jump directly from `queued` to `published`.

## Source handling

- Prefer canonical URLs and official metadata.
- Record source date when verifiable, plus capture and analysis dates.
- Never invent a missing publication date. Use `null` with a `date_note`.
- Full third-party transcripts, articles, PDFs or copied repository content are working input, not public project data.
- If a full transcript/text is used during analysis, treat it as ephemeral/private and do not commit it.
- Store derived maps, paraphrased concepts, short necessary quotations, references and provenance only.

## Research behavior

Research beyond the supplied source when it materially improves understanding. Typical reasons:

- verify an important claim;
- resolve a missing prerequisite;
- open official documentation for a named tool or system;
- compare a tool with its category or an obvious alternative;
- identify a hidden limitation;
- confirm date, author, version, license or product status.

Prefer primary sources for technical facts: official docs, papers, repositories, standards, vendor documentation and original talks.

Distinguish every external addition from the original source. A tool discovered by project research must not be presented as if the source author recommended it.

## Claim-level evidence

Every insight that reaches `review` must have a compact evidence trace in `data/claim-evidence.json` for its important claims.

A claim must state its epistemic origin explicitly:

- `source` — paraphrase of what the supplied source establishes;
- `verification` — fact established by a separate verification source;
- `project_interpretation` — synthesis or boundary inferred by this project;
- `prior_knowledge` — claim carried from an earlier evidenced insight.

Each claim also has a support status:

- `supported`;
- `uncertain`;
- `unresolved`.

Rules:

1. High-impact supported claims require evidence.
2. Source-origin claims must point to the current registered source plus a meaningful locator.
3. Verification claims must point to a registered verification URL.
4. Prior-knowledge claims must identify the earlier insight.
5. Project interpretations must remain visibly labeled as interpretation and explain that boundary in `note`.
6. `uncertain` / `unresolved` claims must explain why confidence is limited.
7. Never invent timestamps, page numbers or sections. Use the best verified locator available; a structural source section is preferable to a fabricated precision marker.
8. Do not store copied paragraphs, transcript fragments or full source text in the evidence record. Store paraphrased claims, URLs and locators.

For a published insight, public claim evidence must not depend on review-only/private prior knowledge.

## Knowledge Delta

Every insight that reaches `review` must answer a second question beyond “what does the source say?”: **what does this source change in the existing model?**

Use the prior-knowledge snapshot in the research bundle and curate only meaningful changes into `data/knowledge-deltas.json`.

Allowed surfaced relationships are:

- `new` — a reusable concept or boundary that was not already represented;
- `reinforces` — independent evidence strengthens an existing model without materially changing it;
- `refines` — the source narrows, concretizes or changes the boundary of an existing model;
- `contradicts` — evidence is genuinely inconsistent within comparable scope and needs explicit review.

For every surfaced delta, keep three layers visibly separate:

1. **source basis** — what the current source establishes;
2. **prior basis** — what the project already represented and which prior insights support it;
3. **project interpretation** — why this difference matters to the cumulative model.

Do not surface a connection merely because retrieval found overlapping words. Candidates classified `not_relevant` should remain suppressed and may be recorded in `suppressed_prior_matches` as evidence that noise was deliberately rejected.

Never reinterpret a bundle `reinforcement`, `refinement` or `contradiction` as another relationship without revisiting the source evidence and changing the underlying classification too.

## Contradiction and refinement review

When a new source appears to challenge or narrow existing knowledge, use `data/knowledge-reviews.json` rather than silently changing the graph.

Before accepting `contradiction`, compare:

- whether both claims address the same subject;
- whether they operate at the same architectural/conceptual layer;
- whether their conditions and scope are comparable.

A true contradiction requires all three to match. A model-level reasoning loop and a production-control substrate, for example, may discuss the same agent action while still describing different layers.

Every resolved review must preserve:

- evidence from the new and prior claim traces;
- human-readable scope assessment and rationale;
- resolution (`refinement / contradiction / different_scope / not_conflict / needs_more_evidence`);
- any graph/concept change with explicit `before / after`;
- review history so superseded interpretations are not erased.

Do not optimize for finding disagreements. Optimize for correctly identifying where evidence changes the model.

## Prerequisite path

Every review-ready insight must have a compact prerequisite map in `data/prerequisite-maps.json`.

The map is not a reading list. Include only concepts whose absence materially harms comprehension of the central model, normally no more than five.

Classify priority as:

- `must_know_now` — required to understand the current model;
- `learn_next` — useful immediately after the core model;
- `optional_depth` — valuable context but not required.

Classify state as:

- `known_in_graph` — prior evidence already explains it;
- `explained_here` — the current explainer supplies enough context;
- `gap` — still unresolved.

Rules:

1. `known_in_graph` must be backed by another insight, not merely by a matching label.
2. `explained_here` must be evidenced by the current insight.
3. Prefer an existing published explainer or concept when it genuinely covers the prerequisite.
4. A `gap` must become an explicit `learning_target`; do not hide it inside prose.
5. A published insight may not contain an unresolved `must_know_now` gap.
6. If required prerequisites remain unresolved, `coherence_review.prerequisites_complete` cannot be true.
7. Do not inflate the list with generic domain foundations that the source does not depend on.

The generated prerequisite path should appear before the mental model so the reader knows what must be understood first.

## Personalization

Use `config/research-profile.json` as a filter, not as a topic prison.

Do not force SAP or enterprise examples. Use the clearest domain. Preserve unfamiliar concepts when they have high conceptual leverage or are prerequisites for understanding the main idea.

For every retained concept, decide whether the reader should:

- know it;
- learn it;
- try it;
- use it now;
- build with it;
- watch it;
- ignore it for now.

## Quality bar

A finished explainer must let the reader answer:

1. What problem is being solved?
2. Why does the problem exist?
3. What is the core mechanism?
4. Which concepts are prerequisites, and are any still missing?
5. Which tools/systems are actually worth knowing?
6. Where does the model break or become incomplete?
7. What is source content vs project enrichment?
8. What changed relative to prior knowledge, and why?
9. Which apparent contradictions were scope-reviewed rather than accepted mechanically?
10. Which important claims are source evidence versus project interpretation, and where can they be checked?
11. What should I do with this knowledge?
12. Where did it come from and when?

If the reader still needs to consume the original source to understand the main model, the explainer is not ready.

## Repository outputs

A processed source may update:

- `data/inbox.json`
- `data/sources.json`
- `data/research-bundles/<intake-id>.json`
- `data/insights.json`
- `data/claim-evidence.json`
- `data/knowledge-deltas.json`
- `data/knowledge-reviews.json`
- `data/prerequisite-maps.json`
- `data/learning-prompts.json`
- `data/knowledge-graph.json`
- `content/explainers/*.md`
- generated `explainers/<slug>/index.html`
- generated `previews/<slug>/index.html`
- `sitemap.xml`

Do not edit generated explainer HTML by hand. Change the structured source/insight/evidence/delta/review/prerequisite record or generator and rebuild.

## Required checks

Before considering a change complete:

```bash
python scripts/validate.py
python scripts/validate_claim_evidence.py
python scripts/validate_knowledge_deltas.py
python scripts/validate_knowledge_reviews.py
python scripts/validate_knowledge_reviews.py --self-test
python scripts/validate_prerequisites.py
python scripts/validate_learning_prompts.py
python scripts/validate_graph.py
python scripts/validate_bundles.py
python scripts/benchmark_retrieval.py
python scripts/build.py
python scripts/build.py --check
python scripts/build_previews.py
python scripts/build_previews.py --check
node --check app.js
node --check evidence.js
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q scripts tests
```

Generated files must be committed or synchronized by their dedicated workflows. CI must be green.

## Publication boundary

The agent may autonomously prepare research and a review-ready explainer. `published` is a reviewed state. Do not silently publish newly ingested third-party-derived content.

Publication requires the explicit owner workflow and exact `PUBLISH:<insight-id>` confirmation. A published insight may be explicitly returned to `review` or `archived`; retraction keeps provenance and removes the item from public generated surfaces after rebuild.
