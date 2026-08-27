# Portable private local state

Personal learning/context should survive browser/device moves without requiring an account or backend.

`local_state.py` packages supported `.local` stores into one versioned JSON bundle:

- explicit personal baseline;
- learning-utility history;
- insight/action outcomes;
- dogfood cohort evidence;
- Source Decision calibration evidence.

## Export

```bash
python scripts/local_state.py export --out ~/signal-to-insight-state.json
```

The export contains private derived/user evidence only. It does not read or mirror source transcripts/articles/PDF text/repository contents.

## Inspect before import

```bash
python scripts/local_state.py inspect --in ~/signal-to-insight-state.json
```

## Import / merge

```bash
python scripts/local_state.py import --in ~/signal-to-insight-state.json
```

Merge rules are conflict-safe:

- new record IDs are added;
- identical records are deduplicated;
- records with distinct timestamps keep the newer version;
- delayed learning evidence can replace the same immediate record when it is clearly a later completion;
- ambiguous same-ID/same-time differences fail instead of silently overwriting;
- personal baseline active goals/projects/questions are unioned;
- baseline revision is advanced after merge.

## Source-content guard

Both export and import recursively reject fields such as:

```text
transcript
full_text
raw_content
source_text
pdf_text
repository_contents
```

This is defense in depth: the normal project contracts already avoid committing full third-party content, and the portability layer should not become an accidental archive for it.

## Privacy

The resulting JSON is portable but still private. Treat it as personal data and store it accordingly. It is never consumed by public builders.

```bash
python scripts/local_state.py self-test
python scripts/validate_private_boundary.py
```
