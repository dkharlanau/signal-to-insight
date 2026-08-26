#!/usr/bin/env python3
"""Validate authored reconstruction/transfer prompts against insight and graph evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "data" / "learning-prompts.json"
INSIGHTS = ROOT / "data" / "insights.json"
GRAPH = ROOT / "data" / "knowledge-graph.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    prompt_data = load(PROMPTS)
    insight_data = load(INSIGHTS)
    graph_data = load(GRAPH)

    insights = {item["id"]: item for item in insight_data.get("insights", [])}
    concepts = {item["id"]: item for item in graph_data.get("concepts", [])}
    records: dict[str, dict] = {}

    for index, record in enumerate(prompt_data.get("records", [])):
        where = f"data/learning-prompts.json records[{index}]"
        insight_id = record.get("insight_id")
        if not isinstance(insight_id, str) or not insight_id:
            errors.append(f"{where}: insight_id is required")
            continue
        if insight_id in records:
            errors.append(f"{where}: duplicate insight_id '{insight_id}'")
            continue
        records[insight_id] = record

        insight = insights.get(insight_id)
        if insight is None:
            errors.append(f"{where}: unknown insight '{insight_id}'")
            continue
        if insight.get("status") not in {"review", "published"}:
            errors.append(f"{where}: prompts should only exist for review/published insights")

        prompt = record.get("retention_prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"{where}.retention_prompt: expected non-empty authored prompt")
        elif len(prompt.split()) < 12:
            errors.append(f"{where}.retention_prompt: too short to specify a model reconstruction task")

        answer = record.get("answer_key")
        if not isinstance(answer, dict):
            errors.append(f"{where}.answer_key: expected object")
            continue
        if answer.get("problem_from") != "whole_source_map.problem":
            errors.append(f"{where}.answer_key.problem_from must reference whole_source_map.problem")
        if answer.get("mechanism_from") != "whole_source_map.thesis":
            errors.append(f"{where}.answer_key.mechanism_from must reference whole_source_map.thesis")

        limitation_index = answer.get("boundary_limitation_index")
        limitations = insight.get("limitations", [])
        if not isinstance(limitation_index, int) or isinstance(limitation_index, bool):
            errors.append(f"{where}.answer_key.boundary_limitation_index: expected integer")
        elif limitation_index < 0 or limitation_index >= len(limitations):
            errors.append(f"{where}.answer_key.boundary_limitation_index: outside insight limitations")

        anchors = answer.get("anchor_concept_ids")
        if not isinstance(anchors, list) or not anchors:
            errors.append(f"{where}.answer_key.anchor_concept_ids: expected non-empty list")
            anchors = []
        if len(set(anchors)) != len(anchors):
            errors.append(f"{where}.answer_key.anchor_concept_ids: duplicate concept IDs")
        for concept_id in anchors:
            concept = concepts.get(concept_id)
            if concept is None:
                errors.append(f"{where}: unknown anchor concept '{concept_id}'")
            elif insight_id not in concept.get("insight_ids", []):
                errors.append(f"{where}: anchor concept '{concept_id}' is not evidenced by this insight")

        transfer = record.get("transfer_prompt")
        if transfer is not None:
            if not isinstance(transfer, dict):
                errors.append(f"{where}.transfer_prompt: expected object or null")
            else:
                text = transfer.get("prompt")
                if not isinstance(text, str) or len(text.split()) < 10:
                    errors.append(f"{where}.transfer_prompt.prompt: expected substantive application question")
                expected = transfer.get("expected_concept_ids")
                if not isinstance(expected, list) or not expected:
                    errors.append(f"{where}.transfer_prompt.expected_concept_ids: expected non-empty list")
                    expected = []
                if len(set(expected)) != len(expected):
                    errors.append(f"{where}.transfer_prompt.expected_concept_ids: duplicate concept IDs")
                for concept_id in expected:
                    concept = concepts.get(concept_id)
                    if concept is None:
                        errors.append(f"{where}: unknown transfer concept '{concept_id}'")
                    elif insight_id not in concept.get("insight_ids", []):
                        errors.append(f"{where}: transfer concept '{concept_id}' is not evidenced by this insight")

    required = {
        item["id"]
        for item in insights.values()
        if item.get("status") in {"review", "published"}
    }
    missing = sorted(required - set(records))
    if missing:
        errors.append(f"missing learning prompt record(s): {missing}")

    if errors:
        print(f"Learning prompt validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Learning prompt validation passed: {len(records)} review/published insight(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
