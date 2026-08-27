# Private/local overlay

Some high-value sources cannot be committed to a public repository. Signal to Insight therefore treats private evidence as a separate local projection, not as a hidden flag inside public JSON.

## Storage boundary

Initialize the overlay:

```bash
python scripts/private_overlay.py init
```

The default location is:

```text
.local/private/overlay.json
```

`.local/` is gitignored. Private source, insight and concept IDs must start with `private-`, which makes accidental cross-projection references detectable.

## Threat model

The main accidental-leak risks are:

1. a private source or concept ID is referenced from a committed public knowledge record;
2. an agent treats private experience/internal evidence as if it were a public source claim;
3. a private insight is copied into a public explainer without rebuilding provenance;
4. a local export is accidentally committed.

The overlay addresses these risks by separation rather than by encryption. It is **not** a secure secrets vault. Do not store passwords, credentials or material that requires cryptographic protection.

## Local context

Private concepts can assist a local research run:

```bash
python scripts/private_overlay.py context "workflow recovery policy"
```

The result is explicitly tagged `private_local_not_public_evidence`. It may change explanation depth, relevance or practical recommendations. It may not become public claim evidence automatically.

## Leak check

Run:

```bash
python scripts/private_overlay.py leak-check
```

The command scans committed public knowledge stores for private IDs. CI also runs an isolated self-test proving that a synthetic private ID is detected when inserted into a public fixture.

## Redaction/export boundary

A private insight can produce only a redaction scaffold:

```bash
python scripts/private_overlay.py redact-export \
  --insight private-insight-example \
  --out .local/redaction-candidate.json
```

The scaffold deliberately remains `redaction_required`. Before anything can become public, it must receive publishable provenance, public stable IDs, rebuilt claim evidence and the normal human review/publish transition.

## Public graph rule

The public graph must never depend on private-only evidence. Private knowledge may help local analysis, but a public relation/concept requires public/review-allowed evidence under the normal repository contracts.
