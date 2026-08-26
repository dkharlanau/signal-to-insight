# 001 — Why enterprise AI agents fail after the POC

Source: [Why Your Enterprise Tech Stack Isn't Ready for AI Agents](https://www.youtube.com/watch?v=mav15aW9lLM) — Christopher Lovejoy and Saul Howard, AI Engineer.

## Signal

A proof of concept can demonstrate that an AI system is accurate, fast and useful while proving almost nothing about whether the organization can safely run it in production.

## Insight

The important architectural object is not the agent alone. It is the **execution substrate around the agent**: the mechanisms that determine who may act, what context may be accessed, how work is recorded, when a person must intervene, and whether a past case can be reconstructed.

A useful production test is therefore not only:

> Can the model do the task?

It is also:

> Can the organization explain, control, interrupt, reproduce and evaluate the task after the model has done it?

## Pattern 1 — Immutable execution history

Treat execution history as part of the system model rather than as optional debugging output.

A useful record captures references to the request, identity, authority, context, decision, approval, action and verification. This makes later reconstruction possible and creates a better foundation for audit and evaluation.

## Pattern 2 — Separate execution from protected data

Observability should not require every operator or developer to see the underlying business data.

Keep orchestration events and data references separate from protected objects. Grant access to the actual object only when the task and identity require it.

The deeper principle is:

**Being able to observe work is not the same as being entitled to see every datum used by that work.**

## Pattern 3 — Model the task independently from the executor

Instead of building one AI path and a second human exception path, define the business task once and allow different executors to perform it.

```text
approve_change(context)
        │
   ┌────┴────┐
   AI      Human
```

The downstream process should care about the validated result and authority, not whether the executor was an LLM or a person.

## Pattern 4 — Replay as an evaluation primitive

If historical state can be reconstructed, the same case can be replayed with a changed model, prompt, policy or tool.

That turns production history into a useful evaluation asset and helps distinguish the effect of a specific change from general noise.

## Application — SAP customer master

Consider a customer-master change proposed by an agent.

```text
Change request
      ↓
Identity + authority
      ↓
Agent proposal
      ↓
Policy evaluation
      ↓
AI execution / Human approval
      ↓
SAP or MDG update
      ↓
Verification + execution history
```

Months later, the architecture should still support a concrete question:

**Why was this customer changed, under whose authority, with which context, policy and approval?**

That question is a stronger production-readiness test than whether the original demo produced the correct field value.

## Where the idea needs more engineering

The patterns are useful, but none is sufficient by itself.

- An immutable history still needs identity evidence, versioned policies, meaningful event semantics, retention and tamper protection.
- Data-plane separation reduces exposure but does not eliminate injection or exfiltration risk.
- Human/agent equivalence still needs ownership, locking, idempotency, approval authority, timeout and recovery rules.
- Replay is only useful when the reconstructed context and evaluation criteria are trustworthy.

## Durable takeaway

Do not start with an AI demo and attach enterprise controls later. Start with the constraints of controlled enterprise work, then let AI operate inside that environment.

## Related concepts

- event sourcing
- zero trust
- policy-as-code
- human-in-the-loop
- agent evaluation
- enterprise observability
