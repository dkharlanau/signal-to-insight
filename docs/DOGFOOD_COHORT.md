# 20-source dogfood cohort — structural findings

Status: **20 / 20 real sources structurally processed** as of 2026-08-27.

This report records what the repository itself can prove from the cohort. It deliberately does **not** reconstruct or invent private timing, delayed-recall, transfer or Source Decision calibration results. Those observations belong in `.local/` and remain a separate human evidence gate for issue #40.

## What was exercised

The cohort spans at least five source types and multiple domains:

- video;
- documentation;
- repository/tool;
- research paper/framework;
- article/book chapter.

The final inbox contains one intentionally published reference case and nineteen review cases. Every source has a canonical source record, structured insight, Knowledge Delta, claim evidence, prerequisite map, authored reconstruction/transfer prompt and Source Decision. The review/public boundary remains explicit.

Representative new cases include Kubernetes reconciliation, SQLite WAL, PostgreSQL MVCC, DuckDB, LangGraph, Docker build cache, NIST AI RMF, the original Transformer paper, MapReduce, Idempotent Receiver, Pydantic AI, Terraform state, OpenTelemetry tracing, Google SRE monitoring and Twelve-Factor processes.

## What the cohort actually found

### 1. Prior retrieval is useful but concept identity must stay strict

Several sources produced plausible-looking prior matches that were semantically wrong:

- Kubernetes controller reconciliation was not treated as Temporal durable workflow execution;
- SQLite WAL was not treated as application execution history simply because both are log-like;
- PostgreSQL MVCC snapshots were kept separate from SQLite WAL reader snapshots;
- Transformer research rejected unrelated retrieval-practice, policy and agent-control matches;
- OpenTelemetry tracing was separated from authoritative execution history and controlled execution.

The `not_relevant` classification is therefore not an edge case. It is a necessary part of cumulative knowledge quality.

### 2. Scaffold-time context can become stale before analysis starts

Queued sources were often scaffolded before earlier cohort cases finished. The knowledge graph changed while the source waited.

The clearest case was DuckDB: its original scaffold predated the PostgreSQL MVCC case, so analysis-time knowledge contained a real overlap the scaffold could not represent. The same pattern appeared while reviewing later queued cases.

Decision: the source-run pipeline should refresh prior context at **analysis start**, but only while the bundle is still untouched. Once inspection/mapping/classification starts, the snapshot becomes evidence and must not drift automatically.

### 3. Atomic review contracts materially reduced partial-state failures

A mature case now moves through one review transaction:

```text
source + insight + graph
+ Knowledge Delta
+ claim evidence
+ prerequisites
+ learning prompt
+ Source Decision
```

Before the companion contract layer, adding a new review insight could temporarily make mandatory registries inconsistent. The case-patch + case-contract materializer makes the whole review state testable before it reaches `main`.

### 4. Strict evidence provenance caught real authoring mistakes

CI rejected several apparently harmless shortcuts:

- a DuckDB verification claim used the wrong evidence kind;
- NIST evidence referenced an official URL that was not registered in source provenance;
- OpenTelemetry claims derived from specification/context pages had to be labeled as verification rather than canonical-source claims;
- Source Decision skim locators had to resolve to the same claim-evidence trace.

This friction is useful. The product promise depends on keeping source fact, verification, prior knowledge and project interpretation distinct.

### 5. Public knowledge needs an explicit freeze when review evidence extends a published concept

OpenTelemetry refined the already-public `observability` concept. Without a curated public projection, the graph correctly failed closed because the concept now mixed published and review evidence.

The materializer now freezes the last published-only projection when a previously published-only concept receives its first review evidence. Already-mixed concepts still fail closed rather than guessing what is safe to expose.

### 6. Visual grammar should remain constrained

The PostgreSQL MVCC case initially tried to use a three-way base `comparison`. CI rejected it because the primitive intentionally represents exactly two sides.

The case was redesigned instead of weakening the grammar. This is the right product behavior: visual primitives should have semantic meaning rather than act as arbitrary layout containers.

### 7. Long-running agent work exposed branch-race behavior

Parallel cohort branches exposed a stale-branch materialization bug: a PR created before another case landed could interpret newer main-only files incorrectly during patch discovery.

The workflow now uses the merge-base/triple-dot changed-file view and filters to added/modified/copied/renamed case files, preventing unrelated main changes from being treated as work owned by the stale branch.

## Three product changes justified by the cohort

### A. Refresh prior context at actual research start — implement now

Status: **implemented in the dogfood follow-up**.

`run_source.py` refreshes `prior_knowledge` only while a bundle is still metadata-only, unmapped and unclassified. This closes the gap between queue time and analysis time without rewriting historical research evidence.

### B. Add a one-command pre-PR case preflight

The remaining authoring failures were usually cross-contract mistakes that CI caught only after pushing a PR: evidence origin/kind, source provenance, Source Decision locators or visual grammar.

A useful next tool should materialize a candidate patch + companion contract in an isolated temporary workspace and run the same semantic validators before the branch is pushed. The goal is not weaker CI; it is faster local feedback with the same contracts.

### C. Turn repeated `not_relevant` classifications into measured retrieval feedback

The cohort provides real negative examples for prior retrieval. The next retrieval experiment should test whether domain-aware penalties or curated negative feedback reduce repeated cross-domain false positives **without losing useful graph-neighbor recall**.

Do not jump directly to embeddings/vector infrastructure. Extend the current gold benchmark first and compare precision/recall before and after any ranking change.

## What 20 / 20 does not prove

Structural completion is not product-market or learning validation.

Still required:

- real local per-run time/manual-intervention records;
- delayed reconstruction and transfer results (#19);
- Source Decision calibration against consuming the original source (#39);
- intentional human review/publication of a proof corpus (#38);
- evidence that the product saves time while preserving or improving retained understanding.

Do not backfill these results retrospectively. Future real use should record them at the time they occur.

## Current conclusion

The cohort supports continuing the product, but it changes the engineering priority.

The core representation is already rich enough. The strongest next work is **validation and friction reduction**:

1. make each new research run use the right current prior context;
2. catch cross-contract authoring errors before PR round-trips;
3. measure retrieval noise, Source Decision accuracy and delayed understanding with real use.

More platform breadth should remain secondary until those measurements exist.
