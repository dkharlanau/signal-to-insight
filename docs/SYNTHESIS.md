# Multi-source synthesis

A source explainer answers: **what is the coherent model inside this source?**

A synthesis answers a different question: **what model emerges when several already-processed sources are compared against one explicit question?**

Do not create a synthesis merely to concatenate explainers.

## Contract

Structured synthesis records live in `data/syntheses.json`.

A synthesis must:

- start from a substantive question;
- name the source insight IDs it uses;
- preserve claim-level provenance through `claim_refs`;
- separate cross-source consensus from complementary responsibilities;
- reuse resolved knowledge-change reviews rather than inventing disagreements again;
- expose unresolved gaps explicitly;
- state that the combined model is project synthesis rather than a source-authored architecture.

## Evidence modes

`review_allowed` may use source insights in either `review` or `published` state. The generated page is review-only and carries `noindex,nofollow`.

`published_only` is required for a public synthesis. Every source insight must already be `published`.

A public synthesis therefore cannot promote review-only evidence into a public claim surface.

## First reference synthesis

The first synthesis asks:

> What does a production AI agent stack need beyond the model's own reasoning and tool-use loop?

It combines four existing insight models:

- ReAct — model-level reason / act / observe feedback;
- OPA — policy decision versus enforcement;
- Temporal — durable orchestration and retry boundaries;
- enterprise-agent production architecture — cross-cutting controlled execution and reconstructable evidence.

The resulting four-layer view is deliberately labelled as project synthesis. None of the source authors claims that these exact tools/components form a mandatory reference architecture.

## Build

```bash
python scripts/validate_syntheses.py
python scripts/build_syntheses.py
python scripts/build_syntheses.py --check
```

Review pages are generated under:

```text
synthesis-previews/<slug>/index.html
```

Published pages are generated under:

```text
syntheses/<slug>/index.html
```

## Publication

Publication is explicit:

```bash
python scripts/publish_synthesis.py \
  --synthesis <id> \
  --confirm PUBLISH_SYNTHESIS:<id> \
  --reviewed-by <reviewer> \
  --review-note "What was checked"
```

The command blocks publication if any source insight is not already published.

GitHub Actions exposes the same boundary through the owner-only `Publish reviewed synthesis` workflow.

## Non-goals

- concatenating source summaries;
- claiming consensus when only one source supports a statement;
- turning a useful composition into a vendor/tool recommendation;
- hiding review-only evidence behind a public synthesis;
- resolving uncertainty by removing gaps from the page.
