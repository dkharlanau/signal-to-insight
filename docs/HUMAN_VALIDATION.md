# Human validation kit

Issues #19 and #39 require evidence that an agent cannot honestly generate for itself. This kit removes setup friction while keeping the actual observations human-only and local.

The committed sample is fixed in `data/human-validation-plan.json`. It contains **selection only** — never scores, elapsed time, recall results or calibration verdicts.

## Why the sample is fixed

A benchmark should not choose easier sources after seeing failures.

### Delayed reconstruction — issue #19

Three different source types:

- video — `enterprise-agents-production-substrate`;
- paper — `react-reason-act-observe-loop`;
- documentation — `sqlite-write-ahead-log-checkpointing`.

The project uses a repeatable two-day delay for this first benchmark. This is an experiment interval, **not** a claim that two days is an optimal learning schedule.

### Source Decision calibration — issue #39

Exactly one case from every source type in the validation cohort:

- video — `enterprise-agents-production-substrate`;
- documentation — `terraform-state-identity-binding`;
- repository — `duckdb-in-process-analytics`;
- paper — `transformer-self-attention-sequence-model`;
- article — `retrieval-practice-delayed-retention`.

## Validate the committed plan

```bash
python scripts/human_validation.py validate-plan
python scripts/human_validation.py self-test
```

The self-test uses temporary synthetic stores only. It does not create benchmark evidence.

## Issue #19 — delayed reconstruction

### 1. Prepare a local session

```bash
python scripts/human_validation.py prepare --kind reconstruction
```

The session is written under `.local/human-validation/` and is ignored by Git.

It contains:

- the three fixed cases;
- the explainer/review surface used before the delay;
- authored retention and transfer prompts;
- stable local record IDs.

It intentionally does **not** contain answer-key anchors or human outcomes.

### 2. Read the explainer and record immediate evidence

Open the `surface` printed for the case. Do not reopen the original source merely to make the immediate result look better.

Record actual time and immediate understanding:

```bash
python scripts/human_validation.py record-immediate \
  --session .local/human-validation/<session>.json \
  --insight <insight-id> \
  --source-minutes <actual-or-measured-source-minutes> \
  --explainer-minutes <actual-explainer-minutes> \
  --immediate yes \
  --decision learn
```

Use the real `yes / partial / no` result and the real action decision. Do not normalize results across cases.

### 3. After the delay, reconstruct without reopening anything

Show only the prompt:

```bash
python scripts/human_validation.py prompt \
  --session .local/human-validation/<session>.json \
  --insight <insight-id>
```

Answer it before looking at the explainer, source, graph or answer key.

The prompt includes a transfer question. Answer that in the same unaided attempt.

### 4. Only after the attempt, reveal the scoring anchors

```bash
python scripts/human_validation.py scoring-guide \
  --session .local/human-validation/<session>.json \
  --insight <insight-id>
```

The guide reveals:

- the problem/mechanism anchors;
- core concept IDs;
- the boundary limitation anchor;
- expected transfer concepts.

Do **not** store the free-text answer. Convert it into compact recalled/missed model-piece labels.

### 5. Record delayed evidence

```bash
python scripts/human_validation.py record-delayed \
  --session .local/human-validation/<session>.json \
  --insight <insight-id> \
  --days 2 \
  --reconstruction partial \
  --recalled "problem;mechanism" \
  --missed "boundary" \
  --transfer partial
```

Use semicolons between model-piece labels. The record goes into the existing `.local/learning-utility.json` store.

## Issue #39 — Source Decision calibration

### 1. Prepare the balanced five-type session

```bash
python scripts/human_validation.py prepare --kind source_decision
```

### 2. Read the prediction before consuming the original

```bash
python scripts/human_validation.py decision \
  --session .local/human-validation/<session>.json \
  --insight <insight-id>
```

This shows:

- original source URL;
- predicted decision;
- rationale;
- evidence-backed skim targets when applicable.

This order is intentional. The prediction must exist **before** the benchmark consumes the source.

### 3. Consume the original source

For this benchmark, consume the original even when the prediction says `explainer_is_enough` or `skip_for_now`. The point is to measure whether the decision was trustworthy.

For `skim_selected_parts`, verify whether the selected sections/timestamps actually contained the promised additional value, but still complete the full-source benchmark before recording the verdict.

### 4. Record calibration only after full consumption

```bash
python scripts/human_validation.py record-calibration \
  --session .local/human-validation/<session>.json \
  --insight <insight-id> \
  --confirm-consumed \
  --missed none \
  --verdict correct \
  --skim-targets all
```

The command refuses to write without `--confirm-consumed`.

For non-`skim_selected_parts` predictions, `--skim-targets` is automatically stored as `not_applicable`.

Use:

- missed meaningful info: `none / minor / major`;
- verdict: `correct / too_optimistic / too_conservative`;
- skim targets: `all / partial / none` only when the prediction was `skim_selected_parts`.

The record goes into the existing `.local/source-decision-benchmark.json` store.

## Check session progress

```bash
python scripts/human_validation.py status \
  --session .local/human-validation/<session>.json
```

This reports whether each fixed case has immediate/delayed evidence or a completed calibration record. It does not score or reinterpret the human result.

## What this kit does not do

It does not:

- generate a delayed recall score;
- simulate waiting;
- answer reconstruction prompts on the user's behalf;
- mark a Source Decision correct without full-source consumption;
- automatically publish any review insight;
- commit private benchmark evidence.

Completion of #19 and #39 still requires the actual human actions above. The kit only makes those experiments repeatable, balanced and difficult to accidentally contaminate.
