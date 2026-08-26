# Signal to Insight

A personalized source-to-understanding engine.

Give it a useful source — video, article, paper, podcast, documentation, repository, tool or system — and turn that source into a coherent, visual, actionable explanation tailored to what is worth learning, trying, using, building or simply knowing.

The project is intentionally **not domain-locked**. AI, agents, developer tools, custom systems, architecture, automation, data, enterprise software and unfamiliar but high-leverage concepts are all valid inputs.

## The core loop

```text
Source
  ↓
Capture source + dates
  ↓
Map the whole material
  ↓
Apply personal research profile
  ↓
Select the coherent core
  ↓
Verify + enrich
  ↓
Build a mental model
  ↓
Map to use / try / learn / build / watch
  ↓
Design visual explainer
  ↓
Review → publish
```

The goal is not to create a shorter copy of the source. The goal is to preserve everything necessary for understanding while removing repetition, promotion and low-value detail.

## What the system should answer

Every finished explainer should make these questions easy to answer:

1. Why does this matter?
2. What is the complete mental model I need?
3. Which concepts are prerequisites?
4. How does the mechanism actually work?
5. Which tools or systems are worth knowing?
6. Where is the source incomplete, overstated or uncertain?
7. What can I use or try now?
8. What should I learn, build, watch or ignore for now?
9. What was the original source, when was it published/event-held, and when was this analysis produced?

## Personalization

`config/research-profile.json` defines the current selection and explanation preferences.

The profile deliberately favors:

- conceptual leverage over topic popularity;
- coherent understanding over isolated insights;
- practical tools and systems when they help;
- mechanisms and examples over marketing language;
- useful adjacent research when the original source is incomplete;
- breadth: no requirement to force every source into SAP or enterprise use cases.

## Agent contract

The detailed workflow is documented in [`docs/PIPELINE.md`](docs/PIPELINE.md).

The most important rule is:

> **Select all that is necessary for a coherent model, not merely the most exciting fragments.**

A long source can become a short page, but the page should still explain the idea end-to-end.

## Source and date policy

Every record must include provenance. At minimum:

- canonical source link or identifier;
- source title and creator/publisher when known;
- source publication date when verifiable;
- event date when relevant;
- date captured/analyzed by this project;
- supporting or contradictory sources used for verification.

Unknown dates must remain unknown rather than being guessed.

Full third-party transcripts, copied articles and source media are not stored in the public repository.

## Output model

A source can produce several connected outputs:

```text
Source
├─ source record
├─ concept map
├─ derived insight
├─ tool/system map
├─ action map
├─ visual landing page
└─ machine-readable JSON
```

A good landing page normally contains:

`why this matters → mental model → key concepts → mechanism → tools/systems → examples → limitations → what this changes → next actions → sources & dates`

## Repository structure

```text
config/
  research-profile.json    Personalization and selection rules
content/
  explainers/              Human-readable deep dives
  sources/                 Provenance policy
  TEMPLATE.md              Explainer template
data/
  insights.json            Machine-readable insight records
  insight.schema.json      Record contract
docs/
  PIPELINE.md              Agent workflow and quality gate
ROADMAP.md                 Product evolution
index.html                 GitHub Pages experience
styles.css                 Visual system
app.js                     Lightweight interaction
llms.txt                   Machine-readable project overview
```

## First case

The first explainer analyzes the AI Engineer World's Fair 2026 talk **“Why Your Enterprise Tech Stack Isn't Ready for AI Agents — And What to Build Instead”** by Christopher Lovejoy and Saul Howard.

It is one example of the engine, not the scope of the project. The same pipeline should work for a new AI tool, a GitHub repository, a research paper, a custom architecture, a productivity system or another high-value source.

## Publishing principle

Public output should contain original analysis, independently created diagrams, structured concepts and links to sources. Ingestion creates a reviewable draft; it does not silently publish source-derived material.

---

Maintained by [Dzmitryi Kharlanau](https://github.com/dkharlanau).
