# Source intake

The smallest useful input to Signal to Insight is a source URL. Everything else can be enriched later, but the system must preserve the original request and never lose provenance.

## Queue

New work lives in `data/inbox.json`.

Each item has:

- stable intake ID;
- canonical or submitted source URL;
- source type;
- submission date;
- optional requested focus / note;
- processing status;
- source and insight IDs once created.

## Status lifecycle

```text
queued
  ↓
capturing
  ↓
mapping
  ↓
researching
  ↓
drafting
  ↓
review
  ↓
published
```

A published insight can later be explicitly retracted:

```text
published → review
published → archived
```

Both transitions require a human note and exact confirmation. Retraction removes the insight from public generated surfaces after the same transaction rebuilds explainers, library, public knowledge and sitemap. Publication history remains in provenance.

Alternative terminal/interruption states:

- `archived` — previously processed material intentionally removed from active/public use while provenance is retained;
- `blocked` — source cannot currently be processed or verified;
- `rejected` — not worth converting into an explainer.

The queue records workflow state; it does not contain full third-party transcripts.

## Stable identifiers

Intake IDs use:

```text
intake-YYYY-MM-DD-short-source-key
```

Registered sources use:

```text
src-short-source-key-year
```

Insight IDs are semantic and source-independent where possible:

```text
enterprise-agents-production-substrate
```

A source may create more than one insight later. An insight may eventually connect to more than one source.

## Deduplication

Before a new queue item is added:

1. normalize obvious URL noise such as timestamps when it does not identify a different source;
2. compare against `data/inbox.json` and `data/sources.json`;
3. reuse the existing source record when the canonical source already exists;
4. add a new intake item only when the new request has a materially different requested focus or represents new source material.

## Publication boundary

`queued` through `review` are working states. Only `published` content is intended for the public explainer library.

The agent may prepare a draft autonomously. Publication remains an explicit review decision. The owner workflow requires `PUBLISH:<insight-id>` plus a human review note. Retraction requires `REVIEW:<insight-id>` or `ARCHIVE:<insight-id>` plus a reason.
