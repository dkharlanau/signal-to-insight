# Research case preflight

Use the case preflight before opening a PR for a researched source.

It answers one narrow question:

> Can this candidate case patch + companion contract materialize as a valid review case against the repository as it exists now?

## Command

```bash
python sti.py preflight data/case-patches/my-source.json
```

When the companion contract has the same filename, or can be matched uniquely by `intake_id` / `insight_id`, it is inferred automatically.

Otherwise pass it explicitly:

```bash
python sti.py preflight \
  data/case-patches/my-source.json \
  --contract data/case-contracts/my-source-contract.json
```

The direct script entry point is also available:

```bash
python scripts/preflight_case.py data/case-patches/my-source.json
```

Use `--json` for an agent/machine-readable result.

## What it does

The preflight creates a temporary copy of the repository, stages the candidate files there and then runs the same review materialization logic used by GitHub Actions:

```text
validate case-patch / case-contract structure
→ apply case patch
→ apply companion contract
→ validate structured knowledge + bundles
→ validate graph
→ validate Knowledge Delta
→ validate claim evidence / provenance
→ validate prerequisites
→ validate learning prompts
→ validate Source Decision
→ validate public projection
→ build review preview
→ build generated explainer/library/public graph/sitemap surfaces
```

The command stops on the first failing step and prints that contract's output. A successful preflight means the candidate can survive the current deterministic review contracts; GitHub Actions remains the final CI check.

## Isolation boundary

Preflight never applies the candidate to the working repository registries.

The candidate is materialized only inside a temporary workspace. The workspace is deleted after success or failure.

This protects at least:

- `data/inbox.json`;
- sources / insights / knowledge graph;
- Knowledge Delta / claim evidence / prerequisites / learning prompts / Source Decisions;
- previews and generated public surfaces.

The self-test fingerprints those mutable paths before and after both a successful and an intentionally failing preflight.

## Why this exists

The 20-source dogfood cohort found several real errors that were structurally small but required a push/CI/fix round-trip:

- source claim versus verification origin mismatch;
- unregistered verification provenance;
- Source Decision locators not backed by claim evidence;
- visual grammar violations;
- mixed published/review graph projection boundaries.

Those validators should stay strict. Preflight moves their feedback earlier rather than weakening them.

## Self-test

```bash
python scripts/preflight_case.py --self-test
```

The self-test:

1. selects an existing real review case and verifies a full isolated preflight succeeds;
2. creates an intentionally invalid companion contract and verifies semantic validation rejects it;
3. confirms the live registries and generated surfaces have the same fingerprints before and after both runs.

## Non-goals

Preflight does not:

- inspect or research the source;
- judge whether the insight is worth publishing;
- weaken or replace GitHub Actions;
- mutate publication state;
- create private learning or dogfood evidence.
