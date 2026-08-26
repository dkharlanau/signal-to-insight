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
map the whole source
  ↓
apply research profile
  ↓
verify + enrich where useful
  ↓
create / update source registry
  ↓
create structured insight record
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
8. What should I do with this knowledge?
9. Where did it come from and when?

If the reader still needs to consume the original source to understand the main model, the explainer is not ready.

## Repository outputs

A processed source may update:

- `data/inbox.json`
- `data/sources.json`
- `data/research-bundles/<intake-id>.json`
- `data/insights.json`
- `content/explainers/*.md`
- generated `explainers/<slug>/index.html`
- `sitemap.xml`

Do not edit generated explainer HTML by hand. Change the structured source/insight record or generator and rebuild.

## Required checks

Before considering a change complete:

```bash
python scripts/validate.py
python scripts/build.py
python scripts/build.py --check
python -m compileall -q scripts
```

Generated files must be committed. CI must be green.

## Publication boundary

The agent may autonomously prepare research and a review-ready explainer. `published` is a reviewed state. Do not silently publish newly ingested third-party-derived content.
