# P0 validation loop

This increment turns the validation-first backlog into executable product infrastructure without pretending that human evidence already exists.

## Completed in code

### Zero-backend capture

`/capture/` accepts a URL, infers a likely source type, carries optional focus/note, and opens the existing owner GitHub source-intake issue. The canonical queue workflow remains responsible for normalization, deduplication and repository writes. No write credential is shipped to the browser.

### Explicit private personal baseline

`.local/personal-baseline.json` can record explicit `known`, `partially_known`, `uncertain` or `unknown` concepts, with user-assertion/experience origin and active goals/projects/questions. `run_personalized.py` selects relevant private context for a source run.

The versioned run manifest receives reproducibility metadata only: baseline version, revision, fingerprint, selected-entry count and the gitignored sidecar path. Private concept/note content remains in `.local/` and is not public evidence.

### Dogfood and calibration evidence stores

Two local-first tools make product validation repeatable:

- `scripts/dogfood.py` records the 20-source reliability cohort and aggregates recurring failure modes;
- `scripts/source_decision_benchmark.py` records post-consumption calibration of `consume / skim / explainer is enough / skip` decisions.

These tools deliberately do not convert subjective human outcomes into CI fixtures.

### Public proof surface

The repository now includes:

- an explicit MIT license;
- a golden product walkthrough;
- a static capture surface;
- a GitHub Pages deployment workflow kept manual until Pages is enabled at repository level;
- refreshed generated sitemap metadata.

## What remains human evidence, not code

The following issues must remain open after this increment:

- delayed reconstruction/transfer benchmark: requires delayed human recall;
- curated proof corpus: publication requires explicit owner review;
- Source Decision calibration: requires consuming originals after predictions;
- 20-source dogfood cohort: requires twenty real source runs;
- public repository readiness: description/topics and GitHub Pages enablement are repository-level settings, and the public corpus still needs explicit review.

## CI contract

The validation workflow now tests:

- baseline store behavior;
- personalized private-sidecar leak boundary;
- dogfood evidence-store contract and aggregation;
- Source Decision benchmark-store contract and aggregation;
- capture URL normalization/type inference/issue construction;
- all pre-existing knowledge, provenance, publication and generated-output checks.

The decision rule remains: new architecture should follow observed repeated failure, not precede it.
