# Retrieval feedback experiment — cohort negative matches

Status: **measured, not adopted**.

The 20-source dogfood cohort produced several real `not_relevant` prior-knowledge matches. Instead of treating them as anecdotes, this experiment asked whether remembered negative matches should suppress concepts during future retrieval.

## Evidence set

`data/retrieval-negative-feedback.json` contains five source-time rejection sets from real research bundles:

- Kubernetes controllers rejected Temporal/workflow/control concepts;
- SQLite WAL rejected execution-history/control concepts;
- PostgreSQL MVCC rejected the SQLite WAL reader snapshot as concept identity;
- the original Transformer paper rejected unrelated learning/policy/control concepts;
- OpenTelemetry tracing rejected execution-history/control/durable-execution/OPA concepts.

Every feedback record is checked against the original research bundle. A stored negative is valid only when the captured prior snapshot actually contained that concept and the source analysis classified it `relationship_to_source = not_relevant`.

This is evidence-backed retrieval feedback, not a free-form blacklist.

## Gold set

The retrieval benchmark now contains **12 cases**. Four cohort-derived cases were added for:

- Kubernetes reconciliation versus workflow execution;
- PostgreSQL MVCC versus SQLite WAL snapshot semantics;
- Transformer architecture versus cross-domain vocabulary noise;
- OpenTelemetry tracing versus execution-history/control concepts.

The earlier SQLite and SRE regression probes remain as additional cohort-derived coverage.

Each case preserves:

- required concepts;
- acceptable context;
- forbidden concepts;
- minimum precision proxy;
- traceability through matched terms or an explicit graph path.

## Candidate tested

The baseline remained the normal deterministic `graph_context.rank()` behavior.

The experimental candidate added an **opt-in** suppression set. Historical negative feedback was activated only when the current query shared at least three searchable terms and at least 40% term coverage with a captured source-time query.

The candidate was intentionally conservative:

- no embeddings;
- no vector store;
- no hidden reranker;
- no global permanent blacklist;
- every suppressed concept came from validated historical evidence.

Production retrieval was not changed during the experiment.

## Measured result

CI comparison on the 12-case gold set:

| Metric | Baseline | Feedback-aware candidate |
| --- | ---: | ---: |
| Cases passed | 12 / 12 | 12 / 12 |
| Forbidden hits | 0 | 0 |
| Macro precision proxy | 0.950 | 0.950 |
| Macro required recall | 1.000 | 1.000 |
| Required-recall regressions | 0 | 0 |

The candidate was safe, but it produced **no measurable improvement**.

The benchmark decision was therefore:

```text
DO NOT ADOPT
candidate_safe = true
forbidden_improvement = false
precision_not_worse = true
recall_regressions = none
```

## Why the experiment did not improve retrieval

The current deterministic retrieval had already improved during the cohort:

- weak one-token lexical matches are rejected as seeds;
- graph expansion stays one hop by default;
- a second hop is allowed only through a query-relevant bridge;
- real cohort regressions are already part of the gold benchmark.

As a result, the historical false positives that motivated the experiment no longer appear in the measured baseline.

Examples from the final baseline:

- Kubernetes returns only reconciliation / desired-state / observed-state concepts;
- PostgreSQL returns the MVCC/isolation cluster and not `wal-reader-snapshot`;
- Transformer returns the self-attention/sequence cluster and no learning/policy/control noise;
- OpenTelemetry returns trace/context/span concepts and not execution-history/control concepts.

## Product decision

Do **not** make negative-feedback suppression part of production retrieval now.

Keep:

- the 12-case regression benchmark;
- the evidence-backed negative-feedback corpus;
- the manual `--compare-feedback` experiment for future regression analysis;
- the existing transparent lexical + graph-path retrieval contract.

Production CI should continue enforcing the ordinary baseline benchmark.

Re-run the comparison only when new real source work produces a false prior match that the baseline benchmark can reproduce. Adopt a feedback mechanism only if it reduces measured forbidden results without lowering required recall or precision.

## What this means for embeddings

This experiment is evidence against adding retrieval infrastructure for completeness alone.

The current deterministic approach reaches 1.000 required recall with zero forbidden hits on the measured 12-case set. That does not prove it will remain sufficient forever, but it means embeddings/vector infrastructure currently lacks a measured problem to solve.

A future retrieval architecture change should begin with a failing regression case, not with a new retrieval technology.
