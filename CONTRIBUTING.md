# Contributing

Contributions should strengthen source provenance, evidence boundaries, cumulative knowledge quality, deterministic validation, public-surface safety, or adoption evidence.

Read `AGENTS.md` and the linked pipeline/source-handling documents before changing content contracts. Review content must not be silently published, and full third-party source text must not enter the public repository.

## Development checks

Run the required commands in `AGENTS.md`; the minimum first loop is:

```bash
python sti.py validate
python scripts/benchmark_retrieval.py
python scripts/build.py --check
python scripts/build_previews.py --check
python -m unittest discover -s tests -p 'test_*.py' -v
```

Generated public files must remain synchronized with their structured sources. Do not mark an insight `published` without the explicit owner workflow and exact confirmation.

## Feedback paths

- Use the [15-minute usability kit](docs/USABILITY_TEST_15_MIN.md) for a real first-use session.
- File a privacy-safe [usability report](https://github.com/dkharlanau/signal-to-insight/issues/new?template=usability-feedback.yml).
- Use a normal GitHub issue for a reproducible validation, retrieval, lifecycle, or public-surface defect.

Do not submit private profiles, personal reading history, unpublished notes, full source text, confidential URLs, or proprietary material.
