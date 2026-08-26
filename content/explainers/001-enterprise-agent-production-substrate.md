# 001 — Why enterprise AI agents fail after the POC

## Source record

- **Source:** [Why Your Enterprise Tech Stack Isn't Ready for AI Agents - And What to Build Instead](https://www.youtube.com/watch?v=mav15aW9lLM)
- **Speakers:** Christopher Lovejoy, Saul Howard
- **Publisher / event:** AI Engineer — AI Engineer World's Fair 2026
- **Source type:** video / conference talk
- **Event date:** 2026-07-02
- **YouTube publication date:** unknown / not independently verified
- **Captured:** 2026-08-26
- **Analyzed:** 2026-08-26
- **Duration:** ~19 minutes
- **Date verification:** [official AI Engineer World's Fair 2026 schedule](https://ai.engineer/worldsfair/schedule)

## Why this matters

The talk is useful because it reframes production AI-agent architecture. A successful agent demo can prove that the model can perform a task while proving very little about whether the surrounding system can safely authorize, observe, interrupt, reconstruct and evaluate that task.

This is not only an enterprise/SAP idea. The same question applies to a custom automation, support agent, coding agent, financial workflow, healthcare assistant or any system where an AI can take consequential actions.

## One-sentence model

**A production agent is not just a model with tools; it is a controlled execution system in which model calls, human actions, authority, data access, history and evaluation are part of one workflow.**

## The coherent core

Four ideas belong together:

1. execution history must be reconstructable;
2. observation of execution should be separable from access to protected data;
3. a task should be modeled independently from whether a human or AI executes it;
4. reconstructable history can become material for replay and evaluation.

Taken separately these are useful patterns. Taken together they form a stronger mental model: **controlled execution**.

```text
request
  ↓
identity + authority
  ↓
context / protected data access
  ↓
task
 ├─ AI executor
 └─ human executor
  ↓
action
  ↓
verification
  ↓
reconstructable history
  ↓
replay / evaluation
```

## Concept 1 — Execution history, not only developer logs

Treat execution history as part of the system model rather than optional debugging output.

A useful record captures references to the request, identity, authority, context, decision, approval, action, component versions and verification. Later, the system should be able to reconstruct what happened and why.

A related concept worth learning is **event sourcing / append-only history**: state can be understood from a sequence of recorded events rather than only from the latest mutable record.

## Concept 2 — Separate execution from protected data

Being able to observe work is not the same as being entitled to see every datum used by that work.

The talk's architectural direction is to separate orchestration history from the sensitive objects it references and grant access when the task and identity require it.

This matters far beyond healthcare. It is useful whenever developers, operators, AI agents and auditors need different levels of access to the same workflow.

## Concept 3 — Model the task independently from the executor

Instead of building an AI path plus a separate human-exception path, define the task once.

```text
approve_change(context)
        │
   ┌────┴────┐
   AI      Human
```

The workflow should care about the valid result, authority and state transition. The executor can change when confidence, policy or risk requires it.

This is a useful design idea for any custom workflow engine: human-in-the-loop becomes a normal execution mode rather than an emergency branch bolted onto the AI system.

## Concept 4 — Replay as an evaluation primitive

If historical context can be reconstructed, the same case can be replayed with one changed component:

```text
same case + old model    → result A
same case + new model    → result B
same case + new policy   → result C
same case + new prompt   → result D
```

This connects operational architecture directly to evaluation. Production history becomes more useful when it can be safely reconstructed and compared.

## Tools and systems worth learning around this concept

These are **adjacent project research**, not a claim that the speakers recommended these exact tools.

### Temporal — durable workflow execution

[Official documentation](https://docs.temporal.io/)

Why learn it: Temporal is a concrete system for understanding durable, long-running execution and recovery after process or infrastructure failures. It is useful as a reference point when thinking about agent workflows that must survive beyond a single request.

**Status:** learn.

### OpenTelemetry — observability model

[Official documentation](https://opentelemetry.io/docs/)

Why learn it: OpenTelemetry provides a vendor-neutral model for traces, metrics and logs. It is useful for understanding what standardized execution observability looks like, while remembering that telemetry alone is not the same as a complete business execution ledger.

**Status:** learn.

### Open Policy Agent — policy as code

[Official documentation](https://www.openpolicyagent.org/docs)

Why learn it: OPA is a concrete example of separating policy decisions from application logic. It gives a practical way to experiment with explicit authorization or decision rules around actions.

**Status:** try.

## Example — custom AI workflow

Suppose an agent can update a customer record, issue a refund, change an account setting or perform another consequential action.

A weak design is:

```text
prompt → model → API → done
```

A stronger test is:

```text
request
  ↓
identity + authority
  ↓
context access
  ↓
agent proposal
  ↓
policy / risk decision
  ↓
AI or human execution
  ↓
tool / API action
  ↓
verification + durable history
```

Months later, the important question is not only whether the result was correct. It is whether the system can explain **why the action happened, under whose authority, using which context and which version of the relevant policy/model/tool**.

SAP master-data change is one possible example of this model, but it is not the project scope.

## What the source gets right

The strongest contribution is the architecture-level reframing: controls, handoff, history and evaluation should not be treated as cleanup work after the model demo succeeds.

The four primitives also reinforce each other. Replay is more useful when history is trustworthy; human handoff is more useful when task state is durable; audit is more useful when data access and identity are explicit.

## What needs more engineering

The high-level model is useful, but none of the primitives solves production architecture alone.

- An append-only history still needs identity evidence, versioned policies/components, retention, meaningful event semantics and tamper resistance.
- Data-plane separation reduces exposure but does not eliminate injection or exfiltration risk.
- Human/agent equivalence still needs ownership, locking, idempotency, approval authority, timeout and recovery rules.
- Replay is only useful when reconstructed context and evaluation criteria are trustworthy.
- Observability, workflow durability and business audit history overlap, but they are not automatically the same system.

## What this changes for me

### Use now

When evaluating an agent design, ask: **Can I reconstruct and explain a consequential action later?** This is a stronger production-readiness test than asking only whether the model can perform the task.

### Try

- Model one workflow as an executor-independent task.
- Write one simple policy rule outside the application logic with Open Policy Agent.

### Learn

- durable execution and workflow engines;
- event sourcing / append-only histories;
- OpenTelemetry traces and context propagation;
- policy-as-code;
- replay-based agent evaluation.

### Build

A minimal agent execution-ledger prototype: request → authority → context references → executor → action → verification → replay.

### Watch

How emerging agent platforms standardize identity, permissions, durable state, human handoff and replay rather than leaving each application to invent these layers independently.

## Durable takeaway

**Do not judge an AI system only by whether the model can complete the work. Judge whether the surrounding execution system lets the work be controlled, transferred, reconstructed and evaluated.**

## Sources & dates

Primary source:

- Christopher Lovejoy & Saul Howard, *Why Your Enterprise Tech Stack Isn't Ready for AI Agents - And What to Build Instead*, AI Engineer World's Fair 2026. Event date: **2026-07-02**. Captured/analyzed: **2026-08-26**. [Video](https://www.youtube.com/watch?v=mav15aW9lLM).

Supporting project research, accessed **2026-08-26**:

- [AI Engineer World's Fair 2026 Schedule](https://ai.engineer/worldsfair/schedule) — event metadata/date.
- [Temporal documentation](https://docs.temporal.io/) — durable workflow execution context.
- [OpenTelemetry documentation](https://opentelemetry.io/docs/) — observability context.
- [Open Policy Agent documentation](https://www.openpolicyagent.org/docs) — policy-as-code context.
