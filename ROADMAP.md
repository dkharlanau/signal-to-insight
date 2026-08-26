# Roadmap

## Phase 1 — Prove the format

Goal: make the knowledge unit genuinely useful before automating ingestion.

- Publish 5–10 high-quality explainers.
- Establish a consistent visual grammar for mechanisms, contrasts, flows and limitations.
- Keep structured JSON aligned with every published explainer.
- Add related-insight navigation and tags.
- Measure which topics and page structures are actually worth continuing.

## Phase 2 — Personal intake loop

Goal: reduce the cost of turning an interesting source into a reviewable draft.

```text
URL / paper / repo
        ↓
source metadata
        ↓
claim + concept extraction
        ↓
challenge / connections
        ↓
personal application
        ↓
draft explainer
        ↓
human review
```

Important constraint: ingestion should create a draft, never silently publish source-derived content.

## Phase 3 — Knowledge graph

Goal: make insights accumulate instead of becoming isolated pages.

- concepts and aliases;
- source → insight relationships;
- insight → pattern relationships;
- related applications;
- contradictory evidence;
- confidence and review status;
- reusable visual models.

## Phase 4 — Services

Only after the content model is stable:

- `/insights.json` or versioned JSON feed;
- search endpoint;
- RSS / Atom;
- `get_insight(slug)` API;
- `search_insights(query)` API;
- MCP wrapper for agent access;
- optional private intake service for URLs and notes.

## Non-goals

- becoming an AI-news aggregator;
- mass-producing generic summaries;
- storing full third-party transcripts;
- publishing automatically without review;
- building backend infrastructure before the explanation format proves valuable.
