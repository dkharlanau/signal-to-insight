# Golden quickstart — v0.1.1

This walkthrough validates the released public knowledge state without processing or publishing a new source.

Requirements: Git, Python 3.9+, and Node.js.

```bash
git clone --branch v0.1.1 --depth 1 \
  https://github.com/dkharlanau/signal-to-insight.git
cd signal-to-insight

python sti.py validate > /tmp/signal-to-insight-v0.1.1.txt
python scripts/benchmark_retrieval.py
python scripts/build.py --check
python scripts/build_previews.py --check
python -m unittest discover -s tests -p 'test_*.py' -v
```

Verify the deterministic validation summary:

```bash
python - <<'PY'
from hashlib import sha256
from pathlib import Path

path = Path('/tmp/signal-to-insight-v0.1.1.txt')
actual = sha256(path.read_bytes()).hexdigest()
expected = 'a6c497e9d3778c2ab45c8ecd9cafd5df5fd331fa6be4132764c42b4fb0739986'
assert actual == expected, (actual, expected)
print(f'verified {actual}')
PY
```

Open `walkthrough/index.html` to inspect the already-published proof path. Do not change an insight from `review` to `published`; publication requires the explicit owner confirmation described in `AGENTS.md`.

A matching digest proves the released public contracts and fixture state. It is not a human learning outcome, external usability result, or approval of review-only material.
