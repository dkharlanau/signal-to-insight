# Source adapter contracts

Adapters describe what the research agent should capture from different source types before analysis. They do not require one extraction library or provider. The normalized output is a research bundle defined by `schemas/research-bundle.schema.json`.

The adapter boundary is:

```text
source-specific input
        ↓
adapter / research tools
        ↓
normalized metadata + content map
        ↓
research bundle
        ↓
personalized analysis
```

Full third-party content may be used transiently when permitted and available, but it is not part of the committed bundle.

## Common output

Every adapter should establish, when available:

- canonical URL or stable identifier;
- source type;
- title;
- creators / organization;
- publication or event date;
- version / release / commit when relevant;
- language;
- source structure;
- content map;
- provenance of extracted facts;
- unresolved metadata or extraction gaps.

Never infer a precise date from weak clues. Unknown stays unknown.

## Video / YouTube

Capture:

- canonical video URL without timestamps or tracking parameters;
- title, channel/publisher, speakers when distinguishable;
- publication date when independently available;
- event date separately when the recording comes from an event;
- duration;
- chapters/timestamps when they improve navigation;
- transcript availability and method used to inspect it.

Map:

- opening problem;
- thesis;
- major sections;
- named concepts/tools;
- demonstrations/examples;
- claims/evidence;
- assumptions/limitations;
- conclusion / open questions.

Transcript rule: a full transcript is analysis input. Do not commit it. The research bundle stores only derived maps and optional short source locators such as timestamps.

## Web article / documentation

Capture:

- canonical URL (`rel=canonical` when reliable);
- page title;
- author / organization;
- published and modified dates when explicitly provided;
- product/version context for documentation;
- important outbound primary references.

Map headings and the logical argument rather than copying paragraphs. Documentation pages should additionally capture prerequisites, API/tool names, configuration objects and version-specific caveats.

## Paper / PDF

Capture:

- stable paper URL / DOI / arXiv ID when available;
- title and authors;
- publication venue/date;
- paper version;
- abstract-level question;
- study/design type.

Map:

- research question;
- method;
- population/data;
- key results;
- effect sizes/uncertainty when material;
- limitations;
- practical implications;
- conflicts with other evidence worth checking.

Figures/tables can be referenced by number or page. Do not copy the PDF into the public repository.

## GitHub repository

Capture:

- canonical `owner/repo` URL;
- repository description;
- default branch;
- license;
- latest relevant release/tag and date when useful;
- README/docs entry points;
- important directories/files;
- language/runtime/build context.

Map the repository as a system:

- what problem it solves;
- core abstraction;
- architecture/components;
- setup path;
- extension points;
- dependencies;
- operational model;
- limitations/maturity signals;
- smallest useful experiment for the reader.

Do not treat star count as technical evidence. Prefer README, docs, releases, code structure, tests and maintainership signals.

## Tool / product / system

When the source itself is a tool or product rather than an article about it, capture official docs plus one concrete usage path.

The explainer should answer:

- what category is this in;
- what does it replace or complement;
- its core abstraction;
- smallest useful setup;
- where it becomes useful;
- important constraints/cost/hosting/security considerations when relevant;
- whether the reader should use, try, learn, watch or ignore it.

## Extraction confidence

For each research bundle record the inspection method and confidence:

- `direct` — primary source content inspected directly;
- `metadata_only` — only metadata was accessible;
- `secondary` — important source content was reconstructed from trustworthy secondary evidence;
- `mixed` — combination of direct and secondary inspection.

A bundle with critical extraction gaps may proceed to `researching`, but it should not become `published` without making those gaps visible.
