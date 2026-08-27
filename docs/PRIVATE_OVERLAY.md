# Private/local overlay

Signal to Insight can use sensitive personal or internal sources without placing those records in the public repository.

The safety boundary is physical, not a `private: true` flag inside public JSON:

```text
public repository
  data/...
  explainers/...
  library/...
  knowledge/...

.local/private/                ← gitignored boundary
  data/inbox.json
  data/sources.json
  data/insights.json
  data/knowledge-graph.json
  data/research-bundles/
  run-context/
  exports/
```

Public builders do not read `.local/private/`. This reduces the risk that one forgotten filter exposes a sensitive record through GitHub Pages.

## Threat model

This layer protects against the main accidental-publication failures in a local-first repository workflow:

- committing sensitive source, insight or graph records by mistake;
- allowing a public graph relation to depend on a private-only concept/insight;
- making a public generator read the private store;
- treating private experience/internal material as public source evidence;
- exporting a private insight straight into `published` state;
- carrying private URLs into an export without explicitly choosing to retain them.

It does **not** make the local computer or external research provider confidential by itself. Sensitive raw content still needs appropriate device, provider and access controls. Full third-party/internal source text should remain transient research input where possible; `full_content_committed` remains false even inside the overlay.

## Initialize

```bash
python scripts/private_overlay.py init
```

The default root is `.local/private`. A different root may be supplied with `--root`, but the repository validator only considers an overlay safe for normal operation when it remains under `.local/`.

## Queue a sensitive source

```bash
python scripts/private_overlay.py queue \
  "https://internal.example/source" \
  --type documentation \
  --focus "What changes my current model?" \
  --note "Internal source — do not publish"
```

The intake record is written only to `.local/private/data/inbox.json`.

## Scaffold the research bundle

```bash
python scripts/private_overlay.py scaffold <private-intake-id>
```

The normalized bundle uses the same source-safe bundle shape as the public pipeline where possible. It includes the normal public prior-knowledge snapshot.

Private cumulative knowledge is intentionally **not** merged into that bundle. Instead the command writes a local `run-context/<intake-id>.json` sidecar with two clearly separated sets:

```text
public_matches   → public graph evidence/context
private_matches  → local relevance/context only
```

A private match may reduce redundant explanation, highlight an internal dependency or influence practical relevance. It is never source evidence for a public claim merely because the local agent used it.

## Private source / insight / graph records

The overlay stores source, insight and graph objects in separate local registries. Reuse the public record shapes where applicable so research agents do not need a second conceptual model.

Additional rules are stricter than the public pipeline:

- a private insight may be `review` or `archived`, never `published`;
- private source/insight/concept/relation IDs must not collide with public registry IDs;
- private graph nodes may depend on public concepts/insights as read-only evidence/context;
- public graph nodes may never depend on private-only IDs;
- private records do not carry a `public` projection block;
- normalized research bundles still require `full_content_committed: false`.

## Query combined context

```bash
python scripts/private_overlay.py context \
  "policy decision enforcement" \
  --limit 5 \
  --json
```

The result labels every match with provenance (`public_graph` or `private_overlay`). Keep that separation visible throughout analysis.

## Export / redaction path

A private insight that becomes safe to share must not be copied directly into `data/insights.json`.

Create a local review candidate:

```bash
python scripts/private_overlay.py export \
  --insight <private-insight-id> \
  --confirm EXPORT:<private-insight-id>
```

Default export behavior:

- writes only to `.local/private/exports/`;
- strips overlay/public-projection metadata;
- forces the insight back to `review`;
- removes URL fields by default;
- sets `public_write_allowed: false`;
- includes a manual redaction/provenance checklist.

Use `--keep-urls` only when those URLs are independently safe to expose.

The export is **not** publication. After manual redaction, recreate or import the safe material through the normal public source/case contracts, establish canonical public provenance, run the normal validators, and use the explicit human review/publish workflow.

## Accidental-commit and leak guards

`.gitignore` contains the exact `.local/` rule.

Run:

```bash
python scripts/private_overlay.py self-test
python scripts/validate_private_overlay.py
python scripts/validate_private_overlay.py --self-test
python scripts/validate_private_boundary.py
```

`validate_private_overlay.py` checks an existing overlay and also provides fixture-driven leak tests. It rejects:

- private overlay roots outside `.local/`;
- private `published` status;
- dangling private source/insight/bundle/graph references;
- public/private ID collisions;
- private graph `public` projection blocks;
- private-only IDs appearing in versioned/public data or generated surfaces;
- public graph dependency on private-only IDs;
- public builders importing or referencing the private overlay;
- export candidates that do not stop at `review` with `public_write_allowed: false`.

`validate_private_boundary.py` additionally asserts that **all** public builders stay independent from `.local/` storage, including graph, library, synthesis, history, sitemap, preview and re-analysis generation.

The CI self-test injects a private sentinel into a fake public graph and couples a fake public builder to `private_overlay`; both must be rejected.

## Design rule

Private knowledge can make the next private analysis better. It must never become public evidence by inference.

The promotion boundary is always explicit:

```text
private source / experience
        ↓
private analysis
        ↓
redacted local export candidate
        ↓
human review + safe public provenance
        ↓
normal public review pipeline
        ↓
explicit publication
```
