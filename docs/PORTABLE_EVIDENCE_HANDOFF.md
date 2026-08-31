# Portable research evidence handoff

Signal to Insight can export a reviewed, published insight as a compact JSON packet for a separate human review or control-design workflow.

This is a boundary-preserving handoff, not a generic data dump. It contains the public insight identity, source provenance, claim-level evidence and an explicit operational trust boundary. It never contains a transcript, copied article, PDF text, private overlay or review-only insight.

## Export a published insight

```bash
python sti.py handoff export \
  enterprise-agents-production-substrate \
  --output /tmp/enterprise-agent-evidence.json
```

Only `status=published` insights can cross this boundary. A review, draft or private insight is rejected even if its local structure is otherwise valid.

The committed reference packet is generated from the first published explainer:

- [`examples/research-evidence-handoff/enterprise-agents-production-substrate.json`](../examples/research-evidence-handoff/enterprise-agents-production-substrate.json)

## Validate before use

```bash
python sti.py handoff validate /tmp/enterprise-agent-evidence.json
```

Validation checks the contract version, publication state, required operational boundary, absence of raw-source fields and SHA-256 digest over the canonical payload.

The digest detects accidental or unauthorized mutation. It is not a digital signature and does not establish who transported the file.

## Trust boundary

Every packet declares:

```text
trust level: external_research_context
human review: required
```

Permitted uses include:

- human review;
- research traceability;
- control-design discussion;
- hypothesis formation.

The packet must not be used as:

- authorization;
- an execution instruction;
- evidence that a production incident occurred;
- an automatic policy change.

These restrictions are part of the machine-readable payload and its digest. A consumer should reject a packet that weakens or removes them.

## Use with SAP Agentic Operations

SAP Agentic Operations supports the same v1 contract as external research context:

```bash
sao research validate /tmp/enterprise-agent-evidence.json
sao research review /tmp/enterprise-agent-evidence.json \
  --output /tmp/enterprise-agent-review.md
```

The review card preserves claim origin and source links while repeating the non-operational boundary. It does not merge research claims into an Evidence Pack and cannot grant an agent capability.

## Contract and versioning

- Schema: [`contracts/research-evidence-handoff.schema.json`](../contracts/research-evidence-handoff.schema.json)
- Schema ID: `https://dkharlanau.github.io/signal-to-insight/contracts/research-evidence-handoff.schema.json`
- Current version: `1.0.0`

Compatible patch changes may clarify documentation or add stricter validation without changing the packet shape. New optional or required fields require a versioned contract update. Consumers should fail closed on an unknown schema or major version.

## Reproducibility check

The reference packet is deterministic and checked in CI:

```bash
python sti.py handoff export \
  enterprise-agents-production-substrate \
  --output examples/research-evidence-handoff/enterprise-agents-production-substrate.json \
  --check
```

If the published insight, source provenance or claim evidence changes, regenerate the packet intentionally and review the diff before publication.
