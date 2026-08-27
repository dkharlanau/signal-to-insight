# Source Decision calibration

The Source Decision card is valuable only if its `consume / skim selected parts / explainer is enough / skip for now` recommendation can be trusted to save time.

`python scripts/source_decision_benchmark.py` records private calibration evidence after the original source has actually been consumed.

## Benchmark method

Use a balanced sample across video, documentation, repository/tool, paper and article sources.

For each case:

1. finish whole-source mapping and generate the Source Decision normally;
2. record the predicted recommendation before using the original as the benchmark;
3. consume the original source;
4. judge whether meaningful information was missed (`none / minor / major`);
5. classify the recommendation as `correct / too_optimistic / too_conservative`;
6. for `skim_selected_parts`, verify whether the recommended sections/timestamps really contained the promised additional value.

Example:

```bash
python scripts/source_decision_benchmark.py record \
  --insight temporal-durable-execution-mental-model \
  --source-type documentation \
  --predicted skim_selected_parts \
  --missed none \
  --verdict correct \
  --skim-targets all
```

Report:

```bash
python scripts/source_decision_benchmark.py report
python scripts/source_decision_benchmark.py report --json
```

## Metrics

The report surfaces:

- overall verdict accuracy;
- false `explainer is enough` decisions;
- unnecessary `consume` recommendations;
- major information-miss rate;
- accuracy of `skim selected parts` locators.

False `explainer is enough` is especially important: it means the system recommended saving time when the compressed artifact still omitted useful material.

## What belongs in CI

Subjective benchmark judgments do not become deterministic CI gates. CI only checks the store contract and aggregation code with fixtures. Product rules/schema/prompts may later gain deterministic tests after repeated failures expose a stable rule.

```bash
python scripts/source_decision_benchmark.py self-test
```
