# Release and compatibility policy

Signal to Insight uses Semantic Versioning for public source releases. Dataset/schema versions inside the repository remain independently declared where their contracts require it.

- Patch releases preserve the v0.1 public lifecycle and generated-surface contracts while fixing defects or evidence metadata.
- Minor releases may add optional source, insight, evidence, graph, or learning contracts. During `0.x`, review release notes before reusing automation.
- Major releases may change stable identity or publication-boundary contracts and require migration guidance.

## Supported release surface

The v0.1 release covers the repository-local Python/Node validation and build tools, public schemas, 20-source structural cohort, one published proof path, generated public surfaces, and research-evidence handoff v1.

GitHub Releases attach a deterministic source archive and `SHA256SUMS` built from the tagged commit. There is no package-registry distribution in v0.1.

## Compatibility and non-goals

- Review and published states are not interchangeable. A release tag never promotes content.
- Private/local overlays and full third-party source text are outside the public release.
- The portable research packet is human-reviewed context only; it cannot grant operational authority or become production incident evidence.
- External extraction/research agents are provider-independent collaborators, not part of the deterministic core.
- Delayed reconstruction, transfer, subjective utility, and external usability remain human evidence gaps unless real sessions are recorded.

See the [golden quickstart](GOLDEN_QUICKSTART_RELEASE.md) and [v0.1.0 release notes](../release/v0.1.0.md).
