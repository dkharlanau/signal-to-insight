# Signal to Insight

[![Validate knowledge contracts](https://github.com/dkharlanau/signal-to-insight/actions/workflows/validate.yml/badge.svg)](https://github.com/dkharlanau/signal-to-insight/actions/workflows/validate.yml)
[![Deploy Pages](https://github.com/dkharlanau/signal-to-insight/actions/workflows/pages.yml/badge.svg)](https://github.com/dkharlanau/signal-to-insight/actions/workflows/pages.yml)

[Live knowledge site](https://dkharlanau.github.io/signal-to-insight/) · [Golden walkthrough](https://dkharlanau.github.io/signal-to-insight/walkthrough/) · [Knowledge graph](https://dkharlanau.github.io/signal-to-insight/knowledge/)

**An evidence-backed source-to-understanding engine with cumulative concept memory.**

Current source release: **v0.1.1**.

Give it a useful source — video, article, paper, documentation, repository, tool or system — and turn it into a coherent mental model of what is worth understanding, what changed relative to prior knowledge, whether the original is still worth your time, and what to learn or try next.

Signal to Insight is **not a generic summarizer**. The durable output is a versioned knowledge model with provenance, evidence boundaries and review state — not a pile of disconnected summaries.

## 30-second proof

```bash
python scripts/validate_public_surface.py
```

Expected result: `Public surface validation passed: 6 primary routes, 1 published explainer(s), 19 protected review preview(s).`

[Open the public golden walkthrough](https://dkharlanau.github.io/signal-to-insight/walkthrough/) to inspect the validated path from source provenance through Knowledge Delta and Source Decision to the published explainer and pending reconstruction checkpoint. This proof validates the committed public surface and review isolation; it does not process a new source, measure learning, or establish external adoption.

**Validation evidence:** [20-source cohort report](docs/COHORT_20_REPORT.md) — 20 real sources across five source types, with structural coverage and dogfood failures recorded rather than hidden.

> Map the whole source first. Then compress it without breaking the model.
>
> Check what is already known before creating something new.
>
> Show what the source actually changes — and reject attractive false connections.

## The product loop

```text
source + provenance
        ↓
prior-knowledge retrieval
        ↓
whole-source map
        ↓
verification / enrichment
        ↓
coherent mental model
        ↓
Knowledge Delta
        ↓
claim evidence + prerequisites
        ↓
Source Decision
        ↓
review preview
        ↓
explicit human publication
        ↓
published explainer + library + concept graph
        ↓
delayed reconstruction / transfer check
```

The five product questions are:

1. **What did this source actually change in the existing model?**
2. **Why should that change be trusted?**
3. **Do I still need the original source?**
4. **Can I reconstruct and apply the model later?**
5. **What should I learn, test or investigate next?**

## What works today

The repository has a deterministic, validated foundation for the full source-to-review lifecycle:

- URL/source intake with stable IDs and provenance;
- normalized research bundles without committed third-party full text;
- whole-source mapping before selection/compression;
- cumulative concept graph with typed evidence-backed relations;
- prior-knowledge retrieval with cohort-derived regression tests;
- curated **Knowledge Delta** records separating source evidence, prior evidence and project interpretation;
- claim-level evidence traces;
- prerequisite maps;
- evidence-backed **Source Decision**: `consume / skim selected parts / explainer is enough / skip for now`;
- authored delayed-reconstruction and transfer prompts;
- visual explainer generation from structured knowledge;
- review previews with `noindex,nofollow`;
- explicit owner-confirmed `review → published` lifecycle;
- public concept projections that cannot leak review-only evidence;
- private/local personal baseline and sensitive-source overlay;
- living-source freshness and knowledge-evolution support;
- local action/outcome and learning-utility stores;
- generated library, knowledge graph, concept pages, sitemap and discovery bundle;
- reusable local-first starter and repo-local CLI;
- CI contracts for source, evidence, knowledge, publication, privacy and generated-output drift.

## What still requires an external research agent

The repository is the stable knowledge and product layer. It does **not** embed a universal browser, YouTube transcription service, PDF extractor or LLM runtime.

A capable research agent currently performs source inspection and additional verification, then writes the normalized repository contracts. This is intentional: source-specific extraction is kept behind stable inputs so the core model does not depend on one provider.

Provider adapters are a later expansion only when repeated dogfood proves they remove meaningful friction.

## What is still experimental or human-gated

These are deliberately not represented as solved:

- **Delayed reconstruction + transfer benchmark (#19):** prompts and local measurement format exist; real delayed human results are still required.
- **Curated public proof corpus (#38):** review cases stay private-to-review until a person explicitly approves publication.
- **Source Decision calibration (#39):** deterministic decision contracts exist; trustworthiness must still be tested against real full-source consumption.
- **Dogfood utility metrics (#40):** structural 20-source cohort is complete; subjective utility, elapsed work and human learning measurements remain private/human evidence.

## 20-source validation cohort

The frozen validation cohort is now **20/20 processed**:

| Source type | Count |
| --- | ---: |
| Documentation | 7 |
| Repository | 4 |
| Paper | 4 |
| Article | 4 |
| Video | 1 |

Current publication state: **1 published + 19 review**. This is intentional; output volume is not treated as publication quality.

The cohort exposed real product failures, including:

- semantic retrieval precision/recall errors;
- evidence-boundary mismatches in transfer prompts, prerequisites and skim locators;
- mixed published/review concept projection risk;
- stale-branch materialization races under parallel agent loops;
- visual-primitive overreach;
- publication self-test assumptions that broke as the cumulative graph grew.

Those failures produced concrete validators, CI fixes and retrieval regressions. See [`docs/COHORT_20_REPORT.md`](docs/COHORT_20_REPORT.md).

## Knowledge model

`data/knowledge-graph.json` is the cumulative memory between source runs.

A concept has a stable ID, definition, domain, aliases, tags, coverage and supporting insight IDs. Relations are explicit and typed:

```text
depends_on
enables
realized_by
refines
related_to
```

Before research, prior concepts are retrieved:

```bash
python scripts/graph_context.py "durable workflow retry"
```

The new source is then classified against prior knowledge as:

```text
reinforcement
refinement
contradiction
new knowledge
not relevant
```

`not relevant` matches are kept out of the graph. Review-only knowledge can help future research internally, while public concept pages remain backed only by published evidence.

## Knowledge Delta

`data/knowledge-deltas.json` is the curated comparison layer.

Each meaningful delta separates:

- what the current source establishes;
- what prior project evidence established;
- how the project interprets the change.

The first published reference case establishes `controlled-execution` and `execution-history`. Later sources can refine those stable concepts instead of creating new pages just because terminology differs.

## Source Decision

Every review-ready insight gets a decision only after whole-source mapping and evidence exist:

```text
consume
skim_selected_parts
explainer_is_enough
skip_for_now
```

For `skim_selected_parts`, every recommended locator is tied back to claim evidence. The decision is a product hypothesis until the human calibration loop in #39 confirms that it reliably saves time.

## Delayed reconstruction

Every review/published insight has an authored prompt designed to test whether the mental model survives after reading.

Example from the published reference case:

> Without looking back, reconstruct why a capable AI agent still needs a controlled execution substrate: state the production failure mode, the surrounding mechanism, the operational result, and one boundary where that model is still insufficient.

The prompt is implemented. A real delayed score is **not** claimed until the human benchmark in #19 is performed.

## Start a source

Requirements: Python 3.9 or newer. The core pipeline uses the standard library and does
not require a package installation.

Using the repo-local CLI:

```bash
python sti.py intake "https://example.com/source" --type article --focus "What should I learn or try?"
python sti.py scaffold <intake-id>
python sti.py validate
```

Or use the owner-only GitHub source Issue Form. New source issues are normalized, deduplicated and scaffolded with a snapshot of relevant prior knowledge.

For agent-driven work, give the agent access to this repository and tell it to follow [`AGENTS.md`](AGENTS.md).

## Publication lifecycle

Research output stops at `review` by default.

Publishing requires an explicit confirmation and review note:

```bash
python scripts/publish_reviewed.py \
  --insight <insight-id> \
  --confirm PUBLISH:<insight-id> \
  --reviewed-by <reviewer> \
  --review-note "What was checked"
```

Published content can be returned to review or archived without losing provenance. Review patches cannot silently downgrade or overwrite a published insight.

## Privacy boundary

Private personalization and sensitive-source context live under `.local/` and are excluded from public builders.

The committed graph may store stable public/review knowledge, but local personal beliefs, active goals, learning results and private source contents are protected by explicit boundary validators.

## Public surfaces

The repository already contains the static public surface:

- `/` — product/method page;
- `/walkthrough/` — golden proof path;
- `/library/` — generated searchable explainer library;
- `/knowledge/` — public concept graph and learning path;
- `/knowledge/concepts/<id>/` — published-evidence concept pages;
- `/explainers/<slug>/` — published explainers;
- `/previews/<slug>/` — review-only `noindex,nofollow` previews;
- `/data/*.json` — machine-readable source/insight/graph contracts.
- `/contracts/research-evidence-handoff.schema.json` — portable public research-evidence contract.

Published insights can cross into a separate review workflow as a deterministic, digest-protected [research evidence handoff](https://dkharlanau.github.io/signal-to-insight/docs/research-evidence-handoff/). The packet remains external research context: it cannot authorize execution or represent production incident evidence. The [Markdown source](docs/PORTABLE_EVIDENCE_HANDOFF.md) is kept in the repository for review.

The live Pages URL is:

```text
https://dkharlanau.github.io/signal-to-insight/
```

The repository uses GitHub Actions as its Pages source. `.github/workflows/pages.yml`
validates the knowledge contracts, regenerates the deterministic surfaces, checks public
routes and review privacy, and deploys after changes reach `main`. Review previews remain
`noindex,nofollow` and are excluded from the sitemap and public discovery bundle.

## Public proof path

The first published case is based on the AI Engineer World's Fair 2026 talk **“Why Your Enterprise Tech Stack Isn't Ready for AI Agents — And What to Build Instead”** by Christopher Lovejoy and Saul Howard.

Use the [Golden walkthrough](walkthrough/index.html) to see how the project turns that source into:

```text
provenance
→ whole-source mental model
→ Knowledge Delta
→ Source Decision
→ published visual explainer
→ delayed reconstruction checkpoint
```

The walkthrough explicitly marks the delayed outcome as pending rather than inventing a result.

## Repository map

```text
AGENTS.md                         agent operating contract
config/                           research profiles and starter configuration
data/
  inbox.json                      source queue
  sources.json                    canonical source registry
  research-bundles/               whole-source maps + prior-knowledge snapshot
  insights.json                   structured insights and publication status
  knowledge-deltas.json           curated source-vs-prior changes
  claim-evidence.json             important claims + provenance
  prerequisite-maps.json          prerequisite resolution
  learning-prompts.json           reconstruction + transfer prompts
  source-decisions.json           evidence-backed source consumption decision
  knowledge-graph.json            cumulative concepts + typed relations
  cohorts/validation-20.json      frozen dogfood cohort evidence
scripts/                          validators, builders, lifecycle and local loops
explainers/                       generated published pages
previews/                         generated review-only pages
library/                          generated collection
knowledge/                        generated public concept surfaces
walkthrough/                      golden product proof path
docs/                             architecture, visual grammar, cohort report
```

## Core checks

```bash
python sti.py validate
python scripts/benchmark_retrieval.py
python scripts/cohort_audit.py --check --check-report docs/COHORT_20_REPORT.md
python scripts/build_sitemap.py --check
python scripts/publish_reviewed.py --self-test
python -m unittest discover -s tests -p "test_*.py" -v
```

See [`ROADMAP.md`](ROADMAP.md) and the GitHub backlog for the remaining validation-first loops.

## Release resources

- [v0.1.1 release notes](release/v0.1.1.md)
- [release and compatibility policy](docs/RELEASES.md)
- [golden quickstart](docs/GOLDEN_QUICKSTART_RELEASE.md)
- [15-minute external usability test](docs/USABILITY_TEST_15_MIN.md)
- [contributing and privacy-safe feedback](CONTRIBUTING.md)
- [changelog](CHANGELOG.md)

## Related projects

- [SAP Agentic Operations](https://github.com/dkharlanau/sap-agentic-operations) validates this project's portable evidence handoff and can render a human review card without treating research as operational authority.
- [dkharlanau-datasets](https://github.com/dkharlanau/dkharlanau-datasets) provides citable public records that may be considered as source material; each record still needs normal provenance and verification review before use.
- [Agent-Ready Web Profile](https://github.com/dkharlanau/agent-ready-web-profile) explores machine-readable discovery and interoperability for public knowledge surfaces; it is not a runtime dependency of Signal to Insight.

MIT licensed. See [`LICENSE`](LICENSE).

## About the author

Created and maintained by **Dzmitryi Kharlanau**, an SAP consultant and system analyst working across enterprise architecture, data, integration, operations, and practical AI.

- [Website and knowledge base](https://dkharlanau.github.io/)
- [LinkedIn](https://www.linkedin.com/in/dkharlanau/)
