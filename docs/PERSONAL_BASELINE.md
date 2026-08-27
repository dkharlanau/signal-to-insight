# Private personal knowledge baseline

Signal to Insight has two different kinds of memory and they must not be conflated.

## 1. Evidence-backed project knowledge

`data/knowledge-graph.json`, claim evidence, Knowledge Delta and related public/project records represent knowledge derived from processed sources. They have provenance and may participate in public output according to review status.

## 2. Explicit private personal context

`.local/personal-baseline.json` represents what the user explicitly says they already know, partly know, are uncertain about, or do not know, plus current goals/projects/questions.

It is private input. It is not source evidence.

Allowed knowledge states:

- `known`
- `partially_known`
- `uncertain`
- `unknown`

Allowed origins:

- `user_assertion`
- `experience`

The tool deliberately does not infer a profile from clicks, reading history or opaque behavioral signals.

## Create and edit the baseline

```bash
python scripts/personal_baseline.py init

python scripts/personal_baseline.py set \
  --concept "Durable execution" \
  --state known \
  --origin experience \
  --tags "workflow,reliability"

python scripts/personal_baseline.py context-add \
  --kind goal \
  --text "Understand production agent control"
```

Inspect only metadata/fingerprint:

```bash
python scripts/personal_baseline.py show
```

Inspect the full local file only when deliberately needed:

```bash
python scripts/personal_baseline.py show --full
```

## Use it during a source run

```bash
python scripts/run_personalized.py <intake-id>
```

or:

```bash
python scripts/run_personalized.py "https://example.com/source" \
  --type article \
  --focus "What changes my current mental model?"
```

The wrapper writes a selected context snapshot to:

```text
.local/run-context/<intake-id>.json
```

The versioned run manifest stores only baseline version, revision, fingerprint, private sidecar path and selected-entry count. It does not copy private knowledge statements into the repository.

## How personalization may influence analysis

Private context may change:

- explanation depth;
- prerequisite emphasis;
- practical relevance;
- which unfamiliar concepts deserve attention;
- whether an idea is personally novel or already familiar.

It must **not**:

- become a source claim;
- become verification evidence;
- silently enter the public knowledge graph;
- be cited as if it came from an external source.

## Two different deltas

Keep these concepts separate:

**Evidence Knowledge Delta** answers: what does the current source change relative to prior evidence-backed project knowledge?

**Personal novelty/relevance** answers: what is new or useful relative to this user's explicit private baseline and active context?

The first may be public after review. The second is private personalization unless the user explicitly chooses otherwise.

## Safety check

`.local/` is gitignored. Public builders and validators should never depend on private baseline content. The personalized run wrapper passes only a fingerprint/revision into versioned manifests so a run can be reproduced as “used baseline revision N” without exposing its contents.

```bash
python scripts/personal_baseline.py self-test
```
