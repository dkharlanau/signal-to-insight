# Curated proof-corpus review

Issue #38 is a human publication gate, not a content-generation task. The repository can assemble everything a reviewer needs, but it must not decide that its own output deserves publication.

`data/publication-review-plan.json` fixes the first review chain so candidates are not selected after seeing which ones are easiest to approve.

## Fixed review chain

The already-published enterprise-agent reference case is the baseline.

Three remaining source insights are reviewed next because together they are the dependencies of the first multi-source synthesis and span different source types:

1. documentation — `temporal-durable-execution-mental-model`;
2. repository — `open-policy-agent-decision-enforcement-model`;
3. paper — `react-reason-act-observe-loop`.

Then review:

4. synthesis — `agent-production-control-stack`.

This means the synthesis cannot be published merely because it looks coherent. Its source-insight publication dependencies must first pass their own human reviews.

## Validate the review plan

```bash
python scripts/publication_review.py validate-plan
python scripts/publication_review.py self-test
```

The self-test uses only a temporary local review store and never runs a publish command.

## Review one source insight

Show the complete review card:

```bash
python scripts/publication_review.py card \
  --kind insight \
  --candidate temporal-durable-execution-mental-model
```

The card puts the required evidence in one place:

- central problem / thesis / causal chain;
- claim origin, status and evidence locators;
- limitations and open gaps;
- Knowledge Delta including suppressed prior matches;
- prerequisite resolution;
- Source Decision;
- dominant visual plan and image decision;
- structural blockers such as unclassified prior knowledge.

Open the printed preview path and inspect the actual generated page before approving `visual_usefulness`.

### Required source-insight checks

```text
central_model
claim_provenance
limitations
knowledge_delta
source_decision
visual_usefulness
```

Record a human disposition locally:

```bash
python scripts/publication_review.py record \
  --kind insight \
  --candidate temporal-durable-execution-mental-model \
  --verdict approve \
  --checks all \
  --note "Verified central model, source boundaries, limitations, Delta, decision and visual."
```

`approve` is rejected unless all six checks are present and the note is non-empty.

`hold` and `do_not_publish` also require a note, so intentional non-publication has an explicit reason instead of silently disappearing from the corpus.

## Get — but do not execute automatically — the publish command

After an `approve` record exists:

```bash
python scripts/publication_review.py publish-command \
  --kind insight \
  --candidate temporal-durable-execution-mental-model \
  --reviewed-by <reviewer>
```

The runner prints the existing `publish_reviewed.py` command with:

- exact `PUBLISH:<insight-id>` confirmation;
- reviewer identity;
- the human review note.

It does **not** execute it. Publication remains a separate explicit action.

## Review the synthesis

Show the synthesis card:

```bash
python scripts/publication_review.py card \
  --kind synthesis \
  --candidate agent-production-control-stack
```

### Required synthesis checks

```text
central_model
source_evidence
false_contradictions
unresolved_gaps
visual_usefulness
```

The synthesis card also lists every source-insight dependency and its current repository publication status.

Record the disposition locally:

```bash
python scripts/publication_review.py record \
  --kind synthesis \
  --candidate agent-production-control-stack \
  --verdict approve \
  --checks all \
  --note "Verified layer model, contribution evidence, false contradictions, gaps and visual."
```

Even after local approval, `publish-command` refuses to emit the synthesis command until every source insight in the synthesis is actually `published` in `data/insights.json`.

Only then:

```bash
python scripts/publication_review.py publish-command \
  --kind synthesis \
  --candidate agent-production-control-stack \
  --reviewed-by <reviewer>
```

prints the explicit `publish_synthesis.py` command.

## Review status

```bash
python scripts/publication_review.py status
```

This shows repository status and local human verdict for all fixed candidates.

## Evidence boundary

This kit deliberately does not:

- convert a review record to published;
- auto-approve based on validator scores;
- treat a coherent synthesis as permission to publish unpublished source evidence;
- commit human review notes by default;
- put review previews into public discovery;
- claim that two source types were reviewed merely because the structural card passed CI.

Issue #38 should close only after the human reviews and explicit publication transitions are actually performed, and any intentional non-publication is documented.
