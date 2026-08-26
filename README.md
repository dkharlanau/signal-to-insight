# Signal to Insight

A personalized source-to-understanding engine with cumulative concept memory.

Give the agent a useful source — video, article, paper, podcast, documentation, repository, tool or system — and turn it into a coherent, visual, actionable explanation of what is worth understanding, learning, trying, using, building or simply tracking.

This is **not a summarizer** and it is **not domain-locked**. The system preserves the minimum complete mental model behind a source rather than extracting disconnected highlights. New sources are also compared with prior knowledge so repeated ideas reinforce or refine the existing model instead of becoming isolated pages.

## Product loop

```text
source
  ↓
intake + provenance
  ↓
prior-knowledge lookup
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
mental model
  ↓
merge concepts + relations into knowledge graph
  ↓
structured insight
  ↓
review preview
  ↓
review
  ↓
published visual explainer + library + public knowledge graph
```

The strongest rules in the project are:

> **Map the whole source first. Then compress it without breaking the model.**
>
> **Check what is already known before creating something new.**

## What is implemented

The repository now has a working deterministic foundation for the complete source-to-page lifecycle:

- source intake queue and URL normalization;
- owner-only GitHub Issue intake that can queue a source and scaffold its research bundle in one workflow;
- stable intake/source/insight identifiers;
- provenance and source-date rules;
- personalized research profile;
- source adapter contracts for video, article/docs, paper/PDF, GitHub repository and tools/systems;
- normalized research bundles that never commit full third-party source text;
- automatic prior-knowledge snapshot in newly scaffolded bundles;
- cumulative concept graph with stable concept IDs and typed evidence-backed relations;
- prior-knowledge retrieval with neighboring concepts and supporting insights;
- machine-readable insight records;
- schema/semantic validation and cross-reference checks;
- generated visual explainer pages;
- `review` previews with `noindex,nofollow` and no public canonical/JSON-LD;
- reusable explainer visual grammar;
- generated searchable library with tag filters;
- generated public knowledge graph and relation-derived learning path;
- end-to-end fixture-driven acceptance tests;
- GitHub Actions checks for structured data and generated-output drift;
- auto-sync workflows for review previews, the public knowledge graph and the generated library.

## Cumulative knowledge model

`data/knowledge-graph.json` is the durable memory layer between source-specific research runs.

A concept has a stable ID, short definition, domain, aliases, tags, coverage and supporting insight IDs. Relations are explicit and typed:

```text
depends_on
 enables
 realized_by
 refines
 related_to
```

Every relation needs a rationale and shared evidence. The graph validator rejects dangling concepts, dangling insights, duplicate semantic edges, self-relations, unsupported relations and isolated nodes.

Before researching a new source, query prior knowledge:

```bash
python scripts/graph_context.py "durable workflow retry"
```

The agent then classifies overlap as:

```text
reinforcement
refinement
contradiction
new knowledge
not relevant
```

Review-only concepts may exist in machine-readable memory so later research can use them. The public `/knowledge/` page exposes only concepts backed by at least one published insight, so cumulative memory cannot bypass human publication review.

## Current operating model

A capable research agent is currently the intelligence/extraction layer. It reads [`AGENTS.md`](AGENTS.md), the research profile, prior concept graph and pipeline, inspects the supplied source using the tools available to it, performs additional research when needed, and writes the normalized repository artifacts.

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

New bundles include a snapshot of relevant graph concepts. Those matches begin as `unclassified`; the research step must decide whether the new source reinforces, refines, contradicts or adds knowledge.

The owner-only GitHub Issue Form removes the second manual command: a new `[source]` issue is normalized, deduplicated and, when newly queued, committed together with its graph-aware research bundle.

For agent-driven work, simply provide the source to an agent that can edit this repository and tell it to follow `AGENTS.md`.

## Required processing behavior

Before selecting insights, the agent maps:

- prior concepts and neighboring relations;
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

After the coherent model exists, reusable concepts and relations are merged into `data/knowledge-graph.json`. Different wording is not enough to create a new concept; prefer a stable concept ID plus aliases when the meaning is already represented.

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

The knowledge graph is a different visualization: its layout is generated from reusable concepts and typed relations, while its learning path is derived from relation semantics rather than manually curated ordering.

## Repository structure

```text
AGENTS.md                         agent operating contract
config/research-profile.json      personalization rules
content/                          human-readable source/explainer notes
data/
  inbox.json                      source queue
  sources.json                    canonical source registry
  research-bundles/               normalized source maps + prior-knowledge snapshots
  insights.json                   publishable knowledge model
  knowledge-graph.json            cumulative concepts + typed relations
schemas/                          machine-readable contracts
docs/
  PIPELINE.md                     graph-aware source-to-understanding workflow
  INTAKE.md                       lifecycle and IDs
  SOURCE_ADAPTERS.md              source-specific capture rules
  VISUAL_GRAMMAR.md               explanatory visual system
scripts/
  new_source.py                   queue a URL
  scaffold_bundle.py              create graph-aware research bundle
  graph_context.py                retrieve relevant prior concepts
  validate.py                     knowledge validation
  validate_bundles.py             research-bundle safety + prior-knowledge checks
  validate_graph.py               concept/relation/evidence validation
  build.py                        public explainer generator
  build_previews.py               review-preview generator
  build_library.py                library generator
  build_graph.py                  public graph + learning-path generator
explainers/                       generated published pages
previews/                         generated review pages
library/                          generated browsable collection
knowledge/                        generated public concept graph
tests/                            end-to-end acceptance fixtures
```

## Checks

```bash
python scripts/validate.py
python scripts/validate_graph.py
python scripts/validate_bundles.py
python scripts/graph_context.py --self-test
python scripts/scaffold_bundle.py --self-test
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/build.py
python scripts/build_previews.py
python scripts/build_library.py
python scripts/build_graph.py
```

Core CI runs graph validation and prior-knowledge self-tests. Generated pages are also checked or synchronized by dedicated workflows so adding a new generated file cannot silently pass because it is untracked.

## Reference cases

The first published case uses the AI Engineer World's Fair 2026 talk **“Why Your Enterprise Tech Stack Isn't Ready for AI Agents — And What to Build Instead”** by Christopher Lovejoy and Saul Howard.

A second real source — Temporal documentation — is held in `review` and exercises a different source adapter and visual structure. Its concepts already participate in machine-readable cumulative memory but remain withheld from the public graph until publication.

These are reference cases only. The same contracts are designed for new tools, repositories, papers, custom architectures, productivity systems and other high-value sources.

## Public surfaces

When GitHub Pages is enabled from `main` / repository root:

- `/` — product/method page;
- `/library/` — generated searchable explainer library;
- `/knowledge/` — generated public concept graph + learning path;
- `/explainers/<slug>/` — published explainers;
- `/previews/<slug>/` — review-only noindex pages;
- `/data/insights.json` and `/data/sources.json` — machine-readable knowledge/provenance;
- `/data/knowledge-graph.json` — complete cumulative concept memory, including review-supported concepts.

See [`ROADMAP.md`](ROADMAP.md) for the next development loops.

---

Maintained by [Dzmitryi Kharlanau](https://github.com/dkharlanau).
