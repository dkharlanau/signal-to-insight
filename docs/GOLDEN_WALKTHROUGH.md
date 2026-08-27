# Golden walkthrough — from source to changed understanding

This walkthrough uses the first published reference case to show the product loop without requiring a reader to understand the repository architecture first.

## 1. Start with a source, not a prompt

The reference source is the AI Engineer World's Fair 2026 talk **“Why Your Enterprise Tech Stack Isn't Ready for AI Agents — And What to Build Instead”** by Christopher Lovejoy and Saul Howard.

Signal to Insight preserves the canonical source, creator/date information when verifiable, capture/analysis dates and any verification sources. The source is not copied into the repository as a transcript.

## 2. Map the whole source before selecting highlights

The research bundle first reconstructs the source structure:

```text
problem
  ↓
why normal application assumptions fail for consequential agent work
  ↓
mechanisms / responsibilities required in production
  ↓
limitations and boundaries
  ↓
practical implications
```

This step is what prevents the output from becoming a collection of attractive but disconnected takeaways.

## 3. Ask what is already known

Before the explainer is finalized, the system retrieves relevant concepts from the cumulative graph and classifies every candidate as reinforcement, refinement, contradiction, new knowledge or not relevant.

The important rule is precision over graph density: a lexical match is not automatically a meaningful connection.

With the private personal-baseline layer enabled, the run can also know whether a concept is personally familiar or relevant to an active goal. That private context changes explanation depth/relevance; it never becomes external evidence.

## 4. Produce the Knowledge Delta

The explainer does not stop at “what the talk says.” Its Knowledge Delta separates three layers:

```text
current source basis
        +
prior evidence-backed model
        ↓
project interpretation of what changed
```

Only meaningful `new / reinforces / refines / contradicts` changes are surfaced. Attractive false connections are explicitly suppressible.

This is the central product distinction from a generic summarizer: the output is a change to an accumulated mental model, not another isolated document.

## 5. Make the time decision explicit

After whole-source mapping, Source Decision asks whether the original is still worth consuming:

```text
consume
skim selected parts
explainer is enough
skip for now
```

The recommendation considers novelty, source quality, practical leverage and information lost by compression. It is deliberately produced after source mapping, never from metadata alone.

The recommendation is not assumed to be correct. `scripts/source_decision_benchmark.py` exists specifically to calibrate it against later full-source consumption.

## 6. Render a coherent explainer

Structured knowledge is transformed into a visual explanation using a semantic primitive such as causal chain, sequence, layered system, comparison or decision structure.

The page must let the reader reconstruct:

```text
problem → mechanism → result → boundary
```

Claim-level evidence keeps source claims, external verification, prior knowledge and project interpretation distinguishable at the point where trust matters.

## 7. Test whether understanding survives

Immediate comprehension is not enough. The local retention loop asks the reader to reconstruct the central model later without reopening the source.

The repository stores only labels for recalled/missed model pieces, not the private free-text answer.

Example measurement loop:

```text
read explainer
→ leave it
→ reconstruct central model later
→ reveal compact answer key
→ record recalled / missed pieces
→ attempt transfer to a new example
```

`scripts/learning_utility.py` aggregates time saved, immediate can-explain rate, delayed reconstruction and transfer outcomes.

## 8. Let the next source start from the accumulated state

The durable result is not the generated page. It is the combination of:

- source provenance;
- evidenced claims;
- reusable concepts and typed relations;
- Knowledge Delta;
- contradiction/refinement history;
- prerequisites/gaps;
- private learning evidence;
- optional explicit personal context.

The next source therefore starts from an evolved model rather than from an empty chat window.

## What this walkthrough proves

It demonstrates the intended product mechanics and the evidence boundaries already encoded in the repository.

It does **not** yet prove that:

- Source Decision is calibrated well enough to trust broadly;
- delayed reconstruction is consistently better than reading the original;
- twenty diverse sources can pass through the workflow with low friction;
- the same personal baseline works equally well across every domain.

Those are the current validation loops, not claims the public product should make prematurely.

## The product promise to test

A successful Signal to Insight run should make four measurable improvements:

1. less time spent consuming low-value/redundant material;
2. clearer understanding of the central model and its boundaries;
3. better retained/reconstructable understanding later;
4. a higher-quality next learning or practical decision because new evidence was integrated with what was already known.
