# Public surface and repository settings

The static product surface is committed and validated in-repository. GitHub repository metadata and Pages enablement are repository-level settings and are intentionally listed separately from code so their state cannot be confused with a successful build.

## Intended repository metadata

Use these values for the GitHub repository settings:

**Description**

> Evidence-backed source-to-understanding engine: whole-source models, cumulative concept memory, Knowledge Delta, Source Decision and reconstruction checks.

**Homepage**

```text
https://dkharlanau.github.io/signal-to-insight/
```

**Topics**

```text
knowledge-management
research
learning
knowledge-graph
ai-agents
information-synthesis
provenance
local-first
static-site
```

The homepage value should be set only together with Pages enablement so GitHub does not advertise a dead route.

## Pages setting

The intended Pages configuration is:

```text
Settings → Pages → Build and deployment → Source: GitHub Actions
```

`.github/workflows/pages.yml` then performs:

1. knowledge/evidence validation;
2. deterministic regeneration of public and review surfaces;
3. static route + review-privacy validation;
4. Pages artifact upload;
5. deployment to the `github-pages` environment.

The workflow remains `workflow_dispatch` while the repository-level Pages setting is disabled. After Pages is enabled and the first manual deployment is verified, switching deployment to `push` on `main` can be considered separately.

## Expected public routes

```text
/
/walkthrough/
/library/
/knowledge/
/knowledge/concepts/<published-concept-id>/
/explainers/<published-slug>/
```

Review previews exist under `/previews/<slug>/` for repository review workflows, but they must remain `noindex,nofollow`, absent from the sitemap and free of public canonical/JSON-LD discovery metadata.

## Pre-deployment validation

Run:

```bash
python scripts/build_sitemap.py --check
python scripts/validate_public_surface.py
```

The same checks run in `.github/workflows/public-surface.yml` and again before any Pages deployment.

## Evidence boundary

The Golden walkthrough is based only on the already-published reference insight. It can show the authored delayed-reconstruction prompt, but it explicitly marks the delayed outcome as pending because issue #19 still requires a real human delayed-recall attempt.

The 20-source cohort report proves structural/reliability coverage. It does not substitute for human publication review (#38) or Source Decision calibration against full-source consumption (#39).
