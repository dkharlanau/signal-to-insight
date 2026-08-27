# Knowledge gaps → next research

The system should recommend what to investigate next only when an explicit gap justifies it. This is not an engagement feed.

`next_research.py` derives candidates from:

- unresolved prerequisite maps;
- unresolved multi-source synthesis gaps;
- unresolved contradiction/refinement reviews;
- concepts that are only `introduced` and supported by a narrow evidence base.

It deliberately does **not** recommend generic graph neighbors.

## Show the current queue

```bash
python scripts/next_research.py show
```

With private personal context available, active goals/projects/questions add a transparent score boost when terms overlap. The output shows the matching terms rather than hiding personalization in a model score.

Each candidate includes:

- type (`learn_prerequisite`, `verify_claim`, `resolve_contradiction`, `update_living_source`, `explore_adjacent_leverage`);
- explicit target statement;
- why it exists;
- evidence refs;
- ranking score;
- matching personal-context terms;
- existing unprocessed inbox source when one genuinely matches;
- otherwise a research brief that asks for a primary/official/high-quality source without inventing a URL.

## Queue / defer / ignore

The local disposition store is:

```text
.local/next-research.json
```

Example:

```bash
python scripts/next_research.py set \
  --candidate next-verify-claim-xxxxxxxxxx \
  --status queued \
  --note "Use this after the current Temporal review."
```

Other statuses are `deferred`, `ignored` and `closed`.

Closing a target requires the intake that addressed it:

```bash
python scripts/next_research.py set \
  --candidate next-verify-claim-xxxxxxxxxx \
  --status closed \
  --closed-by-intake intake-2026-... \
  --materially-closed
```

This lets later evaluation measure whether recommended research actually closed the intended gap rather than merely producing another source.

## Design rule

A candidate must have a reason that can be traced to an explicit gap or low-coverage state. “This concept is related” is insufficient.

```bash
python scripts/next_research.py self-test
```
