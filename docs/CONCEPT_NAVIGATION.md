# Public concept navigation

The public knowledge graph is a navigation layer, not a reason to manufacture pages for every internal node.

## Page eligibility

`python scripts/build_concepts.py` generates a concept page only when all of these are true:

1. the concept has at least one **published** supporting insight;
2. its public-safe definition is meaningful rather than a placeholder;
3. it participates in at least one meaningful **published** graph relation.

Review-only concepts and relations never qualify through this path. Isolated nodes are deliberately not turned into thin SEO pages.

The generator uses `scripts/public_projection.py`, so concepts that mix published and review evidence must first have an explicit curated public projection.

## Concept page contents

Generated pages live under:

```text
/knowledge/concepts/<stable-concept-id>/
```

Each page contains:

- the public definition/domain/coverage;
- supporting published explainers;
- the original source behind each supporting explainer;
- important public graph relations;
- boundaries inherited from supporting explainers;
- graph-semantic learn-before / learn-next links;
- related explainers only when a different published explainer is reachable through meaningful public graph relations.

The machine-readable public index is:

```text
/knowledge/concepts/index.json
```

## Related explainers

Related explainers are **not** selected by tag similarity.

For one concept page, the generator:

1. takes the concept's public graph neighbors;
2. reads published support of those neighboring concepts;
3. excludes the explainer(s) already supporting the current concept;
4. ranks remaining explainers by the number of public graph connections that reach them;
5. stores the exact concepts/relations used for the connection.

If no different published explainer exists yet, the related-explainers section is omitted. Empty recommendations are better than invented relevance.

## Explainer cross-links

`concept-links.js` progressively enhances generated explainers:

- concept cards matching public concept labels receive an `Open concept →` link;
- when genuinely related published explainers exist, an additional related-explainers section is generated from the same public concept index.

The module is loaded through the generated-page enhancement shell and does not modify generated explainer HTML by hand.

The navigation chain is therefore:

```text
original source
    ↕
explainer
    ↓
concept page
    ↓
graph relation
    ↓
related concept / related published explainer
```

## SEO boundary

Concept pages are normal indexable pages only because their inputs are already published evidence.

They include:

- one canonical URL;
- a meaningful description from the public concept definition;
- OpenGraph title/description;
- `DefinedTerm` JSON-LD;
- sitemap inclusion only after the same page-eligibility test passes.

Review previews, review-only concepts and internal graph state do not receive concept routes or sitemap entries.

## Deterministic generation

```bash
python scripts/build_concepts.py
python scripts/build_concepts.py --check
python scripts/build_concepts.py --self-test
```

The generator removes stale concept directories when an entity stops qualifying. CI checks the page content, machine-readable index and JavaScript syntax.

Knowledge graph/history/concept surfaces are synchronized together by `.github/workflows/knowledge-graph.yml`.
