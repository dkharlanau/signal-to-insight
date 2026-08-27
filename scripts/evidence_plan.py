#!/usr/bin/env python3
"""Plan the next real human/private validation evidence without fabricating outcomes.

This command is read-only. It combines the existing public/review contracts with the three
existing local evidence stores and answers: what should be measured next for #19, #39 and #40?
It never writes subjective observations and never creates a fourth evidence schema.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from dogfood import DEFAULT_STORE as DOGFOOD_STORE
from dogfood import load_store as load_dogfood_store
from dogfood import record_run as record_dogfood_run
from dogfood import summarize as summarize_dogfood
from dogfood import write_store as write_dogfood_store
from learning_utility import DEFAULT_STORE as LEARNING_STORE
from learning_utility import load_store as load_learning_store
from learning_utility import record_delayed, record_immediate
from source_decision_benchmark import DEFAULT_STORE as DECISION_STORE
from source_decision_benchmark import add_record as add_decision_record
from source_decision_benchmark import load_store as load_decision_store
from source_decision_benchmark import write_store as write_decision_store

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox.json"
SOURCES = ROOT / "data" / "sources.json"
INSIGHTS = ROOT / "data" / "insights.json"
PROMPTS = ROOT / "data" / "learning-prompts.json"
DECISIONS = ROOT / "data" / "source-decisions.json"

CALIBRATION_GROUPS = ["video", "documentation", "repository_tool", "paper", "article"]
GROUP_LABELS = {
    "video": "video",
    "documentation": "documentation",
    "repository_tool": "repository/tool",
    "paper": "paper",
    "article": "article",
}
DECISION_ORDER = {
    "explainer_is_enough": 0,
    "skim_selected_parts": 1,
    "consume": 2,
    "skip_for_now": 3,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def calibration_group(source_type: str) -> str | None:
    if source_type in {"repository", "tool", "product"}:
        return "repository_tool"
    if source_type in {"video", "documentation", "paper", "article"}:
        return source_type
    return None


def build_catalog() -> list[dict]:
    inbox_data = load_json(INBOX)
    source_data = load_json(SOURCES)
    insight_data = load_json(INSIGHTS)
    prompt_data = load_json(PROMPTS)
    decision_data = load_json(DECISIONS)

    sources = {item["id"]: item for item in source_data.get("sources", []) if item.get("id")}
    prompts = {item["insight_id"]: item for item in prompt_data.get("records", []) if item.get("insight_id")}
    decisions = {item["insight_id"]: item for item in decision_data.get("records", []) if item.get("insight_id")}
    intake_by_insight = {
        item.get("insight_id"): item
        for item in inbox_data.get("items", [])
        if item.get("insight_id")
    }

    catalog: list[dict] = []
    for insight in insight_data.get("insights", []):
        if insight.get("status") not in {"review", "published"}:
            continue
        insight_id = insight.get("id")
        source = sources.get(insight.get("source_id"))
        prompt = prompts.get(insight_id)
        decision = decisions.get(insight_id)
        intake = intake_by_insight.get(insight_id)
        if not insight_id or source is None or prompt is None or decision is None or intake is None:
            continue
        source_type = source.get("type") or intake.get("source_type") or "unknown"
        transfer = prompt.get("transfer_prompt")
        catalog.append({
            "insight_id": insight_id,
            "title": insight.get("title"),
            "status": insight.get("status"),
            "slug": insight.get("slug"),
            "source_id": source.get("id"),
            "source_type": source_type,
            "calibration_group": calibration_group(source_type),
            "source_url": source.get("canonical_url"),
            "intake_id": intake.get("id"),
            "retention_prompt": prompt.get("retention_prompt"),
            "transfer_prompt": transfer.get("prompt") if isinstance(transfer, dict) else None,
            "transfer_expected_concepts": transfer.get("expected_concept_ids", []) if isinstance(transfer, dict) else [],
            "predicted_decision": decision.get("decision"),
            "source_decision_rationale": decision.get("rationale"),
            "selected_parts": decision.get("selected_parts", []),
        })
    return sorted(catalog, key=lambda item: (item["source_type"], item["title"] or item["insight_id"]))


def completed_learning_by_insight(store: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for record in store.get("records", []):
        if record.get("delayed") is None:
            continue
        result.setdefault(record.get("insight_id"), []).append(record)
    return result


def completed_calibration_by_insight(store: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for record in store.get("records", []):
        result.setdefault(record.get("insight_id"), []).append(record)
    return result


def case_sort_key(item: dict) -> tuple:
    return (
        0 if item.get("status") == "published" else 1,
        DECISION_ORDER.get(item.get("predicted_decision"), 9),
        item.get("title") or item.get("insight_id"),
    )


def learning_command(item: dict) -> str:
    return (
        "python scripts/learning_utility.py record "
        f"--insight {item['insight_id']} "
        "--source-minutes <actual_or_estimated_source_minutes> "
        "--explainer-minutes <actual_explainer_minutes> "
        "--immediate <yes|partial|no> "
        "--decision <use_now|try|learn|build|watch|ignore_for_now>"
    )


def delayed_command() -> str:
    return (
        "python scripts/learning_utility.py delayed "
        "--record-id <learning_record_id> --days <actual_delay_days> "
        "--reconstruction <complete|partial|failed> "
        "--recalled '<model-piece;labels>' --missed '<model-piece;labels>' "
        "--transfer <applied|partial|failed|not_tested>"
    )


def calibration_command(item: dict) -> str:
    skim = (
        "<all|partial|none>"
        if item.get("predicted_decision") == "skim_selected_parts"
        else "not_applicable"
    )
    return (
        "python scripts/source_decision_benchmark.py record "
        f"--insight {item['insight_id']} "
        f"--source-type {item['source_type']} "
        f"--predicted {item['predicted_decision']} "
        "--missed <none|minor|major> "
        "--verdict <correct|too_optimistic|too_conservative> "
        f"--skim-targets {skim}"
    )


def dogfood_command() -> str:
    return (
        "python scripts/dogfood.py record "
        "--intake <new_intake_id> --insight <new_insight_id> "
        "--source-type <actual_source_type> --domain <actual_domain> "
        "--minutes <actual_elapsed_work_minutes> --agent <actual_agent_or_provider> "
        "--manual-interventions <n> --validation-failures <n> --structural-rewrites <n> "
        "--publication <publish|keep_review|archive|not_ready> "
        "--delta-false-positives <n> --trivial-deltas <n> --prerequisite-misses <n> "
        "--retrieval-noise <n> --retrieval-saved-repetition <yes|no|unknown> "
        "--source-decision-outcome <correct|too_optimistic|too_conservative|not_checked>"
    )


def choose_learning_cases(catalog: list[dict], completed: dict[str, list[dict]], count: int = 3) -> list[dict]:
    available = [
        item for item in catalog
        if item["insight_id"] not in completed and item.get("retention_prompt")
    ]
    selected: list[dict] = []
    used_types: set[str] = set()
    for item in sorted(available, key=case_sort_key):
        if item["source_type"] in used_types:
            continue
        selected.append(item)
        used_types.add(item["source_type"])
        if len(selected) >= count:
            return selected
    for item in sorted(available, key=case_sort_key):
        if item in selected:
            continue
        selected.append(item)
        if len(selected) >= count:
            break
    return selected


def choose_calibration_cases(catalog: list[dict], completed: dict[str, list[dict]]) -> list[dict]:
    selected: list[dict] = []
    for group in CALIBRATION_GROUPS:
        candidates = [
            item for item in catalog
            if item.get("calibration_group") == group and item["insight_id"] not in completed
        ]
        if not candidates:
            continue
        # Prefer a decision type not already selected in this plan to increase calibration diversity.
        existing_decisions = {item.get("predicted_decision") for item in selected}
        candidates.sort(
            key=lambda item: (
                0 if item.get("predicted_decision") not in existing_decisions else 1,
                *case_sort_key(item),
            )
        )
        selected.append(candidates[0])
    return selected


def build_plan(
    learning_store_path: Path = LEARNING_STORE,
    decision_store_path: Path = DECISION_STORE,
    dogfood_store_path: Path = DOGFOOD_STORE,
) -> dict:
    catalog = build_catalog()
    learning_store = load_learning_store(learning_store_path)
    decision_store = load_decision_store(decision_store_path)
    dogfood_store = load_dogfood_store(dogfood_store_path)

    learning_completed = completed_learning_by_insight(learning_store)
    calibration_completed = completed_calibration_by_insight(decision_store)
    catalog_by_id = {item["insight_id"]: item for item in catalog}

    delayed_records = [
        record
        for records in learning_completed.values()
        for record in records
    ]
    delayed_types = {
        catalog_by_id[record["insight_id"]]["source_type"]
        for record in delayed_records
        if record.get("insight_id") in catalog_by_id
    }
    transfer_records = [record for record in delayed_records if record.get("transfer") != "not_tested"]

    calibration_groups_completed = {
        catalog_by_id[insight_id]["calibration_group"]
        for insight_id in calibration_completed
        if insight_id in catalog_by_id and catalog_by_id[insight_id].get("calibration_group")
    }

    inbox = load_json(INBOX)
    structural_items = [
        item for item in inbox.get("items", [])
        if item.get("status") in {"review", "published"} and item.get("insight_id")
    ]
    structural_types = {item.get("source_type") for item in structural_items if item.get("source_type")}
    dogfood_report = summarize_dogfood(dogfood_store)

    learning_recommendations = choose_learning_cases(catalog, learning_completed, count=3)
    calibration_recommendations = choose_calibration_cases(catalog, calibration_completed)

    return {
        "generated_from": {
            "catalog_cases": len(catalog),
            "learning_store": str(learning_store_path),
            "source_decision_store": str(decision_store_path),
            "dogfood_store": str(dogfood_store_path),
        },
        "issue_19_delayed_reconstruction": {
            "human_evidence_required": True,
            "delayed_cases": len({record["insight_id"] for record in delayed_records}),
            "distinct_source_types": sorted(delayed_types),
            "transfer_cases": len({record["insight_id"] for record in transfer_records}),
            "minimum_structural_target": {"cases": 3, "distinct_source_types": 3},
            "structural_evidence_ready": (
                len({record["insight_id"] for record in delayed_records}) >= 3
                and len(delayed_types) >= 3
            ),
            "next_cases": [
                {
                    "insight_id": item["insight_id"],
                    "title": item["title"],
                    "source_type": item["source_type"],
                    "source_url": item["source_url"],
                    "retention_prompt": item["retention_prompt"],
                    "transfer_prompt": item["transfer_prompt"],
                    "record_immediate_command": learning_command(item),
                    "record_delayed_command": delayed_command(),
                }
                for item in learning_recommendations
            ],
            "note": "Do not record recalled/missed results until a real delayed attempt happens. Free-text answers are intentionally not stored.",
        },
        "issue_39_source_decision_calibration": {
            "human_evidence_required": True,
            "cases_recorded": len(decision_store.get("records", [])),
            "source_groups_completed": sorted(calibration_groups_completed),
            "required_groups": CALIBRATION_GROUPS,
            "balanced_sample_ready": set(CALIBRATION_GROUPS) <= calibration_groups_completed,
            "next_cases": [
                {
                    "insight_id": item["insight_id"],
                    "title": item["title"],
                    "source_type": item["source_type"],
                    "source_group": item["calibration_group"],
                    "source_url": item["source_url"],
                    "predicted_decision": item["predicted_decision"],
                    "selected_parts": item["selected_parts"],
                    "record_command": calibration_command(item),
                }
                for item in calibration_recommendations
            ],
            "note": "Consume the original source before recording calibration. The planner never infers verdicts from Git history or the explainer itself.",
        },
        "issue_40_dogfood_reliability": {
            "human_evidence_required": True,
            "structural_sources": len(structural_items),
            "structural_source_types": len(structural_types),
            "structural_20_source_target_met": len(structural_items) >= 20 and len(structural_types) >= 5,
            "local_observed_sources": dogfood_report.get("unique_intakes", 0),
            "local_observed_source_types": len(dogfood_report.get("source_types", {})),
            "local_cohort_ready": bool(dogfood_report.get("cohort_ready")),
            "local_failure_modes": dogfood_report.get("top_failure_modes", []),
            "next_record_command": dogfood_command(),
            "note": "Structural 20/20 must not be backfilled into the local dogfood store. Record the next newly processed real source at run time with actual observations.",
        },
        "next_human_action": next_human_action(
            learning_recommendations,
            calibration_recommendations,
            delayed_records,
            delayed_types,
            calibration_groups_completed,
            dogfood_report,
        ),
    }


def next_human_action(
    learning_recommendations: list[dict],
    calibration_recommendations: list[dict],
    delayed_records: list[dict],
    delayed_types: set[str],
    calibration_groups_completed: set[str],
    dogfood_report: dict,
) -> dict:
    delayed_insights = {record["insight_id"] for record in delayed_records}
    if len(delayed_insights) < 3 or len(delayed_types) < 3:
        if learning_recommendations:
            item = learning_recommendations[0]
            return {
                "gate": "#19 delayed reconstruction",
                "insight_id": item["insight_id"],
                "reason": "Delayed reconstruction/transfer is the strongest missing evidence for the product promise.",
                "command": learning_command(item),
                "after_delay": delayed_command(),
            }
    if not set(CALIBRATION_GROUPS) <= calibration_groups_completed:
        if calibration_recommendations:
            item = calibration_recommendations[0]
            return {
                "gate": "#39 Source Decision calibration",
                "insight_id": item["insight_id"],
                "reason": f"Balanced calibration is still missing the {GROUP_LABELS[item['calibration_group']]} source group.",
                "command": calibration_command(item),
            }
    if not dogfood_report.get("cohort_ready"):
        return {
            "gate": "#40 local dogfood evidence",
            "insight_id": None,
            "reason": "Structural 20/20 exists, but local real-use reliability observations must be collected prospectively.",
            "command": dogfood_command(),
        }
    return {
        "gate": "manual review of evidence quality",
        "insight_id": None,
        "reason": "The detectable quantitative gates are populated; inspect failures and decide product changes before adding platform breadth.",
        "command": "python scripts/learning_utility.py report && python scripts/source_decision_benchmark.py report && python scripts/dogfood.py report",
    }


def print_case(item: dict, prefix: str = "") -> None:
    print(f"{prefix}{item['title']} [{item['source_type']}] · {item['insight_id']}")
    print(f"{prefix}  source: {item['source_url']}")


def print_plan(plan: dict) -> None:
    learning = plan["issue_19_delayed_reconstruction"]
    calibration = plan["issue_39_source_decision_calibration"]
    dogfood = plan["issue_40_dogfood_reliability"]

    print("Evidence readiness")
    print(
        f"#19 delayed reconstruction: {learning['delayed_cases']} cases / "
        f"{len(learning['distinct_source_types'])} source types; transfer cases={learning['transfer_cases']}"
    )
    if not learning["structural_evidence_ready"]:
        print("  Recommended next cases:")
        for item in learning["next_cases"]:
            print_case(item, "  - ")
            print(f"      prompt: {item['retention_prompt']}")
            if item.get("transfer_prompt"):
                print(f"      transfer: {item['transfer_prompt']}")
            print(f"      record: {item['record_immediate_command']}")

    print(
        f"#39 Source Decision calibration: {calibration['cases_recorded']} cases; "
        f"groups={','.join(calibration['source_groups_completed']) or 'none'}"
    )
    missing_groups = [group for group in CALIBRATION_GROUPS if group not in set(calibration["source_groups_completed"])]
    if missing_groups:
        print("  Missing groups: " + ", ".join(GROUP_LABELS[group] for group in missing_groups))
        for item in calibration["next_cases"]:
            print_case(item, "  - ")
            print(f"      predicted: {item['predicted_decision']}")
            if item.get("selected_parts"):
                for part in item["selected_parts"]:
                    print(f"      skim: {part.get('label')} → {part.get('locator')}")
            print(f"      after consuming original: {item['record_command']}")

    print(
        f"#40 dogfood: structural={dogfood['structural_sources']} sources / "
        f"{dogfood['structural_source_types']} types; local observed={dogfood['local_observed_sources']} / "
        f"{dogfood['local_observed_source_types']} types"
    )
    if not dogfood["local_cohort_ready"]:
        print("  Do not backfill the structural cohort. For the next new real source, record actual observations with:")
        print("  " + dogfood["next_record_command"])

    action = plan["next_human_action"]
    print("\nNext human validation action")
    print(f"- gate: {action['gate']}")
    if action.get("insight_id"):
        print(f"- insight: {action['insight_id']}")
    print(f"- why: {action['reason']}")
    print(f"- command: {action['command']}")
    if action.get("after_delay"):
        print(f"- later: {action['after_delay']}")


def self_test() -> int:
    catalog = build_catalog()
    if len(catalog) < 5:
        print("evidence planner self-test requires the real review catalog")
        return 1
    groups = {item.get("calibration_group") for item in catalog}
    if not set(CALIBRATION_GROUPS) <= groups:
        print(f"evidence planner self-test missing calibration source groups: {sorted(set(CALIBRATION_GROUPS) - groups)}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        learning_path = root / "learning.json"
        decision_path = root / "decision.json"
        dogfood_path = root / "dogfood.json"

        empty = build_plan(learning_path, decision_path, dogfood_path)
        if len(empty["issue_19_delayed_reconstruction"]["next_cases"]) < 3:
            print("evidence planner self-test failed: expected three delayed-learning recommendations")
            return 1
        calibration_cases = empty["issue_39_source_decision_calibration"]["next_cases"]
        if {item["source_group"] for item in calibration_cases} != set(CALIBRATION_GROUPS):
            print("evidence planner self-test failed: calibration recommendations are not balanced across required groups")
            return 1
        if not empty["issue_40_dogfood_reliability"]["structural_20_source_target_met"]:
            print("evidence planner self-test failed: repository structural 20/20 should already be true")
            return 1
        if empty["issue_40_dogfood_reliability"]["local_observed_sources"] != 0:
            print("evidence planner self-test failed: empty local store should not infer observations from Git")
            return 1

        first = empty["issue_19_delayed_reconstruction"]["next_cases"][0]
        learning_record = record_immediate(
            learning_path,
            first["insight_id"],
            source_minutes=20,
            explainer_minutes=5,
            immediate_model="yes",
            decision="learn",
            record_id="planner-learning",
        )
        record_delayed(
            learning_path,
            learning_record["id"],
            delay_days=2,
            reconstruction="partial",
            recalled=["problem", "mechanism"],
            missed=["boundary"],
            transfer="partial",
        )

        calibration_item = calibration_cases[0]
        decision_store = load_decision_store(decision_path)
        add_decision_record(
            decision_store,
            record_id="planner-calibration",
            insight_id=calibration_item["insight_id"],
            source_type=calibration_item["source_type"],
            predicted_decision=calibration_item["predicted_decision"],
            missed_meaningful_info="none",
            verdict="correct",
            skim_targets_verified=("all" if calibration_item["predicted_decision"] == "skim_selected_parts" else "not_applicable"),
        )
        write_decision_store(decision_path, decision_store)

        dogfood_store = load_dogfood_store(dogfood_path)
        candidate = catalog[0]
        record_dogfood_run(
            dogfood_store,
            record_id="planner-dogfood",
            intake_id=candidate["intake_id"],
            insight_id=candidate["insight_id"],
            source_type=candidate["source_type"],
            domain="self-test",
            elapsed_work_minutes=10,
            agent_provider="fixture-agent",
            manual_interventions=0,
            validation_failures=0,
            structural_rewrites=0,
            publication_decision="keep_review",
            knowledge_delta_false_positives=0,
            trivial_deltas=0,
            prerequisite_misses=0,
            retrieval_noise=0,
            retrieval_saved_repetition="unknown",
            source_decision_outcome="not_checked",
            learning_record_id=learning_record["id"],
            note=None,
        )
        write_dogfood_store(dogfood_path, dogfood_store)

        populated = build_plan(learning_path, decision_path, dogfood_path)
        if populated["issue_19_delayed_reconstruction"]["delayed_cases"] != 1:
            print("evidence planner self-test failed: delayed local evidence was not recognized")
            return 1
        if populated["issue_39_source_decision_calibration"]["cases_recorded"] != 1:
            print("evidence planner self-test failed: calibration local evidence was not recognized")
            return 1
        if populated["issue_40_dogfood_reliability"]["local_observed_sources"] != 1:
            print("evidence planner self-test failed: dogfood local evidence was not recognized")
            return 1

    print("evidence planner self-test passed: public contracts + three existing private stores produce a read-only next-evidence plan.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learning-store", type=Path, default=LEARNING_STORE)
    parser.add_argument("--decision-store", type=Path, default=DECISION_STORE)
    parser.add_argument("--dogfood-store", type=Path, default=DOGFOOD_STORE)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    try:
        plan = build_plan(args.learning_store, args.decision_store, args.dogfood_store)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"evidence planner error: {exc}")
        return 2

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print_plan(plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
