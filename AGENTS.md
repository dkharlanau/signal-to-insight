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
4. Which concepts are prerequisites?
5. Which tools/systems are actually worth knowing?
6. Where does the model break or become incomplete?
7. What is source content vs project enrichment?
8. What changed relative to prior knowledge, and why?
9. What should I do with this knowledge?
10. Where did it come from and when?

If the reader still needs to consume the original source to understand the main model, the explainer is not ready.

## Repository outputs

A processed source may update:

- `data/inbox.json`
- `data/sources.json`
- `data/research-bundles/<intake-id>.json`
- `data/insights.json`
- `data/knowledge-deltas.json`
- `data/knowledge-graph.json`
- `content/explainers/*.md`
- generated `explainers/<slug>/index.html`
- generated `previews/<slug>/index.html`
- `sitemap.xml`

Do not edit generated explainer HTML by hand. Change the structured source/insight/delta record or generator and rebuild.

## Required checks

Before considering a change complete:

```bash
python scripts/validate.py
python scripts/validate_knowledge_deltas.py
python scripts/validate_graph.py
python scripts/validate_bundles.py
python scripts/build.py
python scripts/build.py --check
python scripts/build_previews.py
python scripts/build_previews.py --check
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q scripts tests
```

Generated files must be committed or synchronized by their dedicated workflows. CI must be green.

## Publication boundary

The agent may autonomously prepare research and a review-ready explainer. `published` is a reviewed state. Do not silently publish newly ingested third-party-derived content.

Publication requires the explicit owner workflow and exact `PUBLISH:<insight-id>` confirmation. A published insight may be explicitly returned to `review` or `archived`; retraction keeps provenance and removes the item from public generated surfaces after rebuild.
