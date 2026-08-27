# Validation cohort — 20 sources

Structural readiness: **YES**

This report audits committed source/knowledge contracts only. It deliberately does not claim human learning utility, delayed recall, elapsed work time or Source Decision calibration unless those measurements actually exist.

## Coverage

- Cohort members: 20 / 20
- Sources linked: 20
- Insights linked: 20
- Research bundles: 20
- Statuses: published=1, review=19

| Source type | Count |
| --- | ---: |
| article | 4 |
| documentation | 7 |
| paper | 4 |
| repository | 4 |
| video | 1 |

## Structured knowledge evidence

| Contract | Count |
| --- | ---: |
| Knowledge Delta records | 20 |
| Claim-evidence records | 20 |
| Important claims | 85 |
| Prerequisite maps | 20 |
| Prerequisites | 73 |
| Learning prompts | 20 |
| Source Decisions | 20 |
| Graph concepts (total graph) | 76 |
| Graph relations (total graph) | 68 |
| Review case patches | 17 |
| Companion case contracts | 15 |

## Failure modes exposed by dogfood

### retrieval-semantic-precision-recall

Prior retrieval produced attractive but irrelevant cross-layer matches for Kubernetes and SQLite, while the SRE monitoring query missed the broader existing observability model.

Resolution: Cohort-derived retrieval benchmark probes plus query-relevant bridge expansion; PR #94.

Status: `resolved_with_regression`

### evidence-boundary-mismatch

Draft review records occasionally referenced concepts, prerequisite explainers or skim locators that were not evidenced by the current source boundary.

Resolution: Existing semantic validators blocked materialization; authored records were corrected rather than weakening the gates.

Status: `resolved_by_contract`

### mixed-public-review-evidence

A concept that began with published evidence later accumulated review-only refinements, requiring the public projection to remain frozen on reviewed public evidence.

Resolution: Materializer freezes the pre-review published concept projection before adding the first review evidence; main commit 48b6ab4.

Status: `resolved_by_contract`

### stale-pr-materialization-diff

Parallel agent loops advanced main after a case branch was created, causing two-point diff logic to misclassify main-only patches as changes owned by a stale PR.

Resolution: Pull-request materialization now uses merge-base/triple-dot diff with added/modified filters; PR #86.

Status: `resolved_with_ci_fix`

### visual-primitive-overreach

A PostgreSQL isolation model tried to use a two-sided comparison primitive for three isolation levels.

Resolution: Kept the visual grammar small and changed the case to a sequence instead of expanding the DSL for one source.

Status: `resolved_by_content_change`

### publication-self-test-order-dependence

Publication self-test assumed the first review insight was publishable and failed once cumulative review evidence made that assumption invalid.

Resolution: Self-test now searches for a valid positive dry-run candidate while retaining fail-closed publication rules; PR #74.

Status: `resolved_with_test_fix`

## What this cohort still does not prove

- Per-run elapsed work, manual interventions and subjective utility remain private in .local dogfood records and were not fabricated for this structural audit.
- Delayed reconstruction and transfer outcomes require a real human delay and remain tracked by issue #19.
- Source Decision calibration against full-source consumption requires actual consumption checks and remains tracked by issue #39.
- Publication of the curated proof corpus requires explicit human review and remains tracked by issue #38.
