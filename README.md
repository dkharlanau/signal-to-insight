# Signal to Insight

A personalized source-to-understanding engine.

Give the agent a useful source — video, article, paper, podcast, documentation, repository, tool or system — and turn it into a coherent, visual, actionable explanation of what is worth understanding, learning, trying, using, building or simply tracking.

This is **not a summarizer** and it is **not domain-locked**. The system preserves the minimum complete mental model behind a source rather than extracting disconnected highlights.

## Product loop

```text
source
  ↓
intake + provenance
  ↓
whole-source map
  ↓
normalized research bundle
  ↓
personal research profile
  ↓
coherent-core selection
  ↓
verification + enrichment
  ↓
structured insight
  ↓
review preview
  ↓
review
  ↓
published visual explainer + library
```

The strongest rule in the project is:

> **Map the whole source first. Then compress it without breaking the model.**

## What is implemented

The repository now has a working deterministic foundation for the complete source-to-page lifecycle:

- source intake queue and URL normalization;
- stable intake/source/insight identifiers;
- provenance and source-date rules;
- personalized research profile;
- source adapter contracts for video, article/docs, paper/PDF, GitHub repository and tools/systems;
- normalized research bundles that never commit full third-party source text;
- machine-readable insight records;
- schema/semantic validation and cross-reference checks;
- generated visual explainer pages;
- `review` previews with `noindex,nofollow` and no public canonical/JSON-LD;
- reusable explainer visual grammar;
- generated searchable library with tag filters;
- end-to-end fixture-driven acceptance tests;
- GitHub Actions checks for structured data and generated-output drift.

## Current operating model

A capable research agent is currently the intelligence/extraction layer. It reads [`AGENTS.md`](AGENTS.md), the research profile and pipeline, inspects the supplied source using the tools available to it, performs additional research when needed, and writes the normalized repository artifacts.

The repository itself does **not** yet contain a universal YouTube/web/PDF transcription service or an embedded LLM runtime. That is intentional: source-specific extraction is separated from the stable research/output contracts so different agents/providers can be used without changing the knowledge model.

## Start a source

A URL can be queued locally with:

```bash
python scripts/new_source.py "https://example.com/source" --type article --focus "What should I learn or try from this?"
```

Then create the normalized working artifact:

```bash
python scripts/scaffold_bundle.py <intake-id>
```

For agent-driven work, simply provide the source to an agent that can edit this repository and tell it to follow `AGENTS.md`.

## Required processing behavior

Before selecting insights, the agent maps:

- problem and thesis;
- source structure;
- concepts and prerequisites;
- mechanisms and relationships;
- named tools/systems;
- examples;
- claims/evidence;
- assumptions;
- limitations;
- unresolved questions.

Then `config/research-profile.json` determines what deserves attention. Topic match alone is not enough: an unfamiliar tool or concept stays when it has high learning or practical leverage.

The final action vocabulary is deliberately small:

`use now / try / learn / build / watch / ignore for now`

## Source and date policy

Every published item must preserve:

- canonical source URL or stable identifier;
- creator/publisher when known;
- publication date when verifiable;
- event date separately when relevant;
- capture and analysis dates;
- supporting/verification sources and access dates.

A missing source date remains `null` with a note. It is never guessed.

Full third-party transcripts, copied articles, PDF text dumps or mirrored repository contents are not committed. They may be transient research input; public data stores derived maps, paraphrased analysis, safe locators and provenance.

## Visual output

The explainer is generated from structured knowledge, not directly from raw source text.

The visual grammar supports different idea structures:

```text
causal chain     problem → mechanism → result
sequence         A → B → C → D
layered system   experience / orchestration / data
comparison       A | B
 decision         condition → choices
```

See [`docs/VISUAL_GRAMMAR.md`](docs/VISUAL_GRAMMAR.md). Images are optional and should be used only when they explain more than a diagram can.

## Repository structure

```text
AGENTS.md                         agent operating contract
config/research-profile.json      personalization rules
content/                          human-readable source/explainer notes
data/
  inbox.json                      source queue
  sources.json                    canonical source registry
  research-bundles/               normalized source maps
  insights.json                   publishable knowledge model
schemas/                          machine-readable contracts
docs/
  PIPELINE.md                     source-to-understanding workflow
  INTAKE.md                       lifecycle and IDs
  SOURCE_ADAPTERS.md              source-specific capture rules
  VISUAL_GRAMMAR.md               explanatory visual system
scripts/
  new_source.py                   queue a URL
  scaffold_bundle.py              create normalized research bundle
  validate.py                     knowledge validation
  validate_bundles.py             research-bundle safety checks
  build.py                        public explainer generator
  build_previews.py               review-preview generator
  build_library.py                library generator
explainers/                       generated published pages
previews/                         generated review pages
library/                          generated browsable collection
tests/                            end-to-end acceptance fixtures
```

## Checks

```bash
python scripts/validate.py
python scripts/validate_bundles.py
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/build.py
python scripts/build_previews.py
python scripts/build_library.py
```

CI also verifies that generated pages committed to the repository match structured data.

## Reference case

The first case uses the AI Engineer World's Fair 2026 talk **“Why Your Enterprise Tech Stack Isn't Ready for AI Agents — And What to Build Instead”** by Christopher Lovejoy and Saul Howard.

It is only a reference case. The same contracts are designed for new tools, repositories, papers, custom architectures, productivity systems and other high-value sources.

## Public surfaces

When GitHub Pages is enabled from `main` / repository root:

- `/` — product/method page;
- `/library/` — generated searchable explainer library;
- `/explainers/<slug>/` — published explainers;
- `/previews/<slug>/` — review-only noindex pages;
- `/data/insights.json` and `/data/sources.json` — machine-readable knowledge/provenance.

See [`ROADMAP.md`](ROADMAP.md) for the next development loops.

---

Maintained by [Dzmitryi Kharlanau](https://github.com/dkharlanau).
