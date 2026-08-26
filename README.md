# Signal to Insight

Turn high-signal AI and enterprise sources into practical explanations, patterns, and applications.

This repository is not a transcript archive or an AI-news feed. It is a structured knowledge system for converting talks, papers, articles, podcasts, documentation, and repositories into durable insights.

## The loop

```text
Signal → Extract → Challenge → Connect → Apply → Explain → Publish
```

Each published insight should answer six questions:

1. What is the signal?
2. What is the underlying idea?
3. Why does it matter?
4. Where does it break or get oversimplified?
5. How can it be applied in enterprise work?
6. What should be explored next?

## Content model

- **Signal** — a source worth examining.
- **Insight** — a non-obvious conclusion extracted from one or more signals.
- **Pattern** — an idea that repeats across sources and contexts.
- **Explainer** — a visual, practical explanation of a concept.
- **Application** — how the idea changes architecture, delivery, product, or operating practice.
- **Project seed** — a buildable idea that follows from the insight.

## Repository structure

```text
content/
  explainers/       Human-readable deep dives
  sources/          Source notes and provenance rules
data/
  insights.json     Machine-readable knowledge layer
index.html           GitHub Pages entry point
styles.css           Visual system
app.js               Lightweight interaction
```

## First explainer

**Why enterprise AI agents fail after the POC** — based on the AI Engineer talk *Why Your Enterprise Tech Stack Isn't Ready for AI Agents* by Christopher Lovejoy and Saul Howard.

The page focuses on four reusable architectural primitives:

- immutable execution history;
- separated data and orchestration planes;
- human/agent task equivalence;
- replayable production evaluation.

## Publishing principle

The repository stores original analysis, diagrams, structured insights, and links to sources. It does **not** store full third-party transcripts or reproduce source material beyond what is necessary for commentary and attribution.

## Goal

Build a small, useful knowledge base that works in two directions:

- **for people:** concise visual explainers with practical enterprise examples;
- **for machines:** structured JSON that can later support search, feeds, APIs, or MCP tools.

---

Maintained by [Dzmitryi Kharlanau](https://github.com/dkharlanau).