#!/usr/bin/env python3
"""Prepare and record human-only validation sessions without fabricating outcomes.

The committed plan fixes balanced samples for issues #19 and #39. Prepared sessions and all
human observations are local-only under `.local/`. This runner reuses the existing
`learning_utility.py` and `source_decision_benchmark.py` stores rather than creating a third
measurement system.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from learning_utility import (
    DECISIONS as LEARNING_DECISIONS,
    IMMEDIATE,
    RECONSTRUCTION,
    TRANSFER,
    LearningUtilityError,
    load_store as load_learning_store,
    record_delayed,
    record_immediate,
)
from source_decision_benchmark import (
    MISSED,
    SKIM,
    VERDICTS,
    BenchmarkError,
    add_record as add_decision_record,
    load_store as load_decision_store,
    write_store as write_decision_store,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data" / "human-validation-plan.json"
INBOX = ROOT / "data" / "inbox.json"
INSIGHTS = ROOT / "data" / "insights.json"
PROMPTS = ROOT / "data" / "learning-prompts.json"
DECISIONS = ROOT / "data" / "source-decisions.json"
DEFAULT_SESSION_DIR = ROOT / ".local" / "human-validation"
DEFAULT_LEARNING_STORE = ROOT / ".local" / "learning-utility.json"
DEFAULT_DECISION_STORE = ROOT / ".local" / "source-decision-benchmark.json"
SESSION_VERSION = "1.0.0"
KINDS = {"reconstruction", "source_decision"}


class HumanValidationError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def records_by_insight(path: Path) -> dict[str, dict]:
    return {
        item["insight_id"]: item
        for item in load(path).get("records", [])
        if isinstance(item, dict) and isinstance(item.get("insight_id"), str)
    }


def registry() -> dict:
    inbox = {
        item.get("insight_id"): item
        for item in load(INBOX).get("items", [])
        if isinstance(item, dict) and item.get("insight_id")
    }
    insights = {
        item.get("id"): item
        for item in load(INSIGHTS).get("insights", [])
        if isinstance(item, dict) and item.get("id")
    }
    return {
        "inbox": inbox,
        "insights": insights,
        "prompts": records_by_insight(PROMPTS),
        "decisions": records_by_insight(DECISIONS),
    }


def surface_for(insight: dict) -> str:
    slug = insight.get("slug")
    if not isinstance(slug, str) or not slug:
        raise HumanValidationError(f"insight has no slug: {insight.get('id')}")
    if insight.get("status") == "published":
        path = ROOT / "explainers" / slug / "index.html"
    elif insight.get("status") == "review":
        path = ROOT / "previews" / slug / "index.html"
    else:
        raise HumanValidationError(
            f"human benchmark requires review/published insight, found {insight.get('status')!r}: {insight.get('id')}"
        )
    if not path.exists():
        raise HumanValidationError(f"benchmark surface is missing: {path.relative_to(ROOT)}")
    return str(path.relative_to(ROOT))


def validate_plan(plan: dict | None = None) -> dict:
    plan = plan or load(PLAN)
    errors: list[str] = []
    if plan.get("version") != "1.0.0":
        errors.append(f"unsupported plan version: {plan.get('version')!r}")
    state = registry()

    reconstruction = plan.get("reconstruction") or {}
    reconstruction_cases = reconstruction.get("cases")
    if not isinstance(reconstruction_cases, list) or len(reconstruction_cases) < 3:
        errors.append("reconstruction plan requires at least three fixed cases")
        reconstruction_cases = []
    reconstruction_types: set[str] = set()
    for insight_id in reconstruction_cases:
        insight = state["insights"].get(insight_id)
        item = state["inbox"].get(insight_id)
        prompt = state["prompts"].get(insight_id)
        if insight is None or item is None:
            errors.append(f"reconstruction case is not linked to intake/insight: {insight_id}")
            continue
        if prompt is None:
            errors.append(f"reconstruction case has no authored learning prompt: {insight_id}")
        else:
            if not isinstance(prompt.get("retention_prompt"), str) or not prompt["retention_prompt"].strip():
                errors.append(f"reconstruction case has no retention prompt: {insight_id}")
            if not isinstance(prompt.get("transfer_prompt"), dict):
                errors.append(f"reconstruction case has no transfer prompt: {insight_id}")
        try:
            surface_for(insight)
        except HumanValidationError as exc:
            errors.append(str(exc))
        source_type = item.get("source_type")
        if isinstance(source_type, str):
            reconstruction_types.add(source_type)
    if len(reconstruction_types) < 3:
        errors.append(
            f"reconstruction sample must span at least three source types, found {sorted(reconstruction_types)}"
        )

    decision = plan.get("source_decision") or {}
    decision_cases = decision.get("cases")
    required_types = decision.get("required_source_types")
    if not isinstance(decision_cases, list) or not decision_cases:
        errors.append("source_decision plan requires fixed cases")
        decision_cases = []
    if not isinstance(required_types, list) or not required_types:
        errors.append("source_decision plan requires source-type coverage contract")
        required_types = []
    decision_types: list[str] = []
    for insight_id in decision_cases:
        insight = state["insights"].get(insight_id)
        item = state["inbox"].get(insight_id)
        prediction = state["decisions"].get(insight_id)
        if insight is None or item is None:
            errors.append(f"source-decision case is not linked to intake/insight: {insight_id}")
            continue
        if prediction is None:
            errors.append(f"source-decision case has no predicted decision: {insight_id}")
        source_type = item.get("source_type")
        if isinstance(source_type, str):
            decision_types.append(source_type)
    if set(decision_types) != set(required_types):
        errors.append(
            "source-decision sample must cover exactly the required source types: "
            f"found={sorted(set(decision_types))}, required={sorted(set(required_types))}"
        )
    if len(decision_types) != len(set(decision_types)):
        errors.append("source-decision sample must contain exactly one case per source type")

    if errors:
        raise HumanValidationError("\n".join(errors))
    return {
        "reconstruction_source_types": sorted(reconstruction_types),
        "source_decision_source_types": sorted(decision_types),
        "reconstruction_cases": len(reconstruction_cases),
        "source_decision_cases": len(decision_cases),
    }


def session_path(kind: str, directory: Path = DEFAULT_SESSION_DIR) -> Path:
    return directory / f"{kind}-{stamp()}.json"


def make_case(kind: str, insight_id: str, session_id: str, state: dict) -> dict:
    insight = state["insights"][insight_id]
    intake = state["inbox"][insight_id]
    case = {
        "insight_id": insight_id,
        "title": insight.get("title"),
        "status": insight.get("status"),
        "source_type": intake.get("source_type"),
        "source_url": intake.get("source_url"),
    }
    if kind == "reconstruction":
        prompt = state["prompts"][insight_id]
        case.update(
            {
                "surface": surface_for(insight),
                "retention_prompt": prompt["retention_prompt"],
                "transfer_prompt": prompt["transfer_prompt"]["prompt"],
                "learning_record_id": f"{session_id}-{insight_id}",
            }
        )
    else:
        prediction = state["decisions"][insight_id]
        case.update(
            {
                "predicted_decision": prediction["decision"],
                "rationale": prediction["rationale"],
                "selected_parts": prediction.get("selected_parts", []),
                "calibration_record_id": f"{session_id}-{insight_id}",
            }
        )
    return case


def prepare(kind: str, output: Path | None = None) -> tuple[Path, dict]:
    if kind not in KINDS:
        raise HumanValidationError(f"kind must be one of {sorted(KINDS)}")
    validate_plan()
    plan = load(PLAN)
    state = registry()
    session_id = f"validation-{kind.replace('_', '-')}-{stamp()}"
    section = plan[kind]
    payload = {
        "session_version": SESSION_VERSION,
        "session_id": session_id,
        "kind": kind,
        "prepared_at": now_iso(),
        "issue": section["issue"],
        "purpose": section["purpose"],
        "outcomes_recorded": False,
        "cases": [make_case(kind, insight_id, session_id, state) for insight_id in section["cases"]],
    }
    if kind == "reconstruction":
        payload["recommended_delay_days"] = section["recommended_delay_days"]
        payload["delay_note"] = section["delay_note"]
    target = output or session_path(kind)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise HumanValidationError(f"session already exists; choose another path: {target}")
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target, payload


def load_session(path: Path) -> dict:
    if not path.is_absolute():
        path = ROOT / path
    data = load(path)
    if data.get("session_version") != SESSION_VERSION:
        raise HumanValidationError(f"unsupported session version: {data.get('session_version')!r}")
    if data.get("kind") not in KINDS:
        raise HumanValidationError(f"invalid session kind: {data.get('kind')!r}")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise HumanValidationError("session has no cases")
    # A prepared session may contain prompts/predictions, but never outcome fields.
    forbidden = {
        "recalled_pieces",
        "missed_pieces",
        "reconstruction",
        "transfer_outcome",
        "missed_meaningful_info",
        "verdict",
        "original_consumed",
    }
    for index, item in enumerate(cases):
        leaked = forbidden & set(item)
        if leaked:
            raise HumanValidationError(f"session case {index} contains outcome fields: {sorted(leaked)}")
    return data


def find_case(session: dict, insight_id: str) -> dict:
    item = next((case for case in session["cases"] if case.get("insight_id") == insight_id), None)
    if item is None:
        raise HumanValidationError(f"insight is not in this session: {insight_id}")
    return item


def print_prepared(path: Path, session: dict) -> None:
    print(f"Prepared {session['kind']} session: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    print(f"Issue: #{session['issue']} | Cases: {len(session['cases'])}")
    if session["kind"] == "reconstruction":
        print(f"Recommended delay: {session['recommended_delay_days']} day(s)")
        print("Stage 1: read each explainer/review surface and record immediate/time evidence.")
        print("Stage 2 after the delay: run `prompt`, answer without reopening the source/surface, then run `scoring-guide`.")
    else:
        print("Read the predicted Source Decision first, then consume the original source as the benchmark requires.")
        print("Only after full-source consumption run `record-calibration --confirm-consumed`.")
    print("Cases:")
    for item in session["cases"]:
        print(f"- {item['source_type']} · {item['insight_id']} · {item['title']}")


def show_prompt(session: dict, insight_id: str) -> None:
    if session["kind"] != "reconstruction":
        raise HumanValidationError("prompt is only available for reconstruction sessions")
    case = find_case(session, insight_id)
    print(f"{case['title']} [{case['source_type']}; {case['status']}]")
    print(f"Surface used before delay: {case['surface']}")
    print("\nRetention prompt — answer without reopening source or surface:\n")
    print(case["retention_prompt"])
    print("\nTransfer prompt:\n")
    print(case["transfer_prompt"])
    print("\nAnswer-key anchors are intentionally hidden until `scoring-guide`.")


def show_scoring_guide(session: dict, insight_id: str) -> None:
    if session["kind"] != "reconstruction":
        raise HumanValidationError("scoring-guide is only available for reconstruction sessions")
    find_case(session, insight_id)
    prompt = registry()["prompts"][insight_id]
    answer_key = prompt.get("answer_key") or {}
    transfer = prompt.get("transfer_prompt") or {}
    print("Scoring guide — reveal only after the unaided attempt")
    print(f"Problem anchor: {answer_key.get('problem_from')}")
    print(f"Mechanism anchor: {answer_key.get('mechanism_from')}")
    print("Core model pieces: " + ", ".join(answer_key.get("anchor_concept_ids", [])))
    print(f"Boundary limitation index: {answer_key.get('boundary_limitation_index')}")
    print("Expected transfer concepts: " + ", ".join(transfer.get("expected_concept_ids", [])))
    print("Record only model-piece labels as recalled/missed; do not store the free-text answer.")


def show_decision(session: dict, insight_id: str) -> None:
    if session["kind"] != "source_decision":
        raise HumanValidationError("decision is only available for source_decision sessions")
    case = find_case(session, insight_id)
    print(f"{case['title']} [{case['source_type']}; {case['status']}]")
    print(f"Original source: {case['source_url']}")
    print(f"Predicted decision: {case['predicted_decision']}")
    print(f"Rationale: {case['rationale']}")
    if case["selected_parts"]:
        print("Selected parts:")
        for item in case["selected_parts"]:
            print(f"- {item.get('label')}: {item.get('locator')} — {item.get('why')}")
    else:
        print("Selected parts: none")
    print("\nBenchmark instruction: now consume the original source. Do not record calibration before that action is complete.")


def record_learning_immediate(
    session: dict,
    insight_id: str,
    source_minutes: float,
    explainer_minutes: float,
    immediate: str,
    decision: str,
    store: Path,
) -> dict:
    if session["kind"] != "reconstruction":
        raise HumanValidationError("learning records require a reconstruction session")
    case = find_case(session, insight_id)
    return record_immediate(
        store,
        insight_id,
        source_minutes,
        explainer_minutes,
        immediate,
        decision,
        note=f"Human validation session {session['session_id']} / issue #{session['issue']}",
        record_id=case["learning_record_id"],
    )


def record_learning_delayed(
    session: dict,
    insight_id: str,
    days: float,
    reconstruction: str,
    recalled: list[str],
    missed: list[str],
    transfer: str,
    store: Path,
) -> dict:
    if session["kind"] != "reconstruction":
        raise HumanValidationError("delayed learning records require a reconstruction session")
    case = find_case(session, insight_id)
    return record_delayed(
        store,
        case["learning_record_id"],
        days,
        reconstruction,
        recalled,
        missed,
        transfer,
    )


def record_calibration(
    session: dict,
    insight_id: str,
    confirm_consumed: bool,
    missed: str,
    verdict: str,
    skim_targets: str,
    note: str | None,
    store_path: Path,
) -> dict:
    if session["kind"] != "source_decision":
        raise HumanValidationError("calibration records require a source_decision session")
    if not confirm_consumed:
        raise HumanValidationError(
            "refusing to record calibration before explicit --confirm-consumed; issue #39 requires actual full-source consumption"
        )
    case = find_case(session, insight_id)
    predicted = case["predicted_decision"]
    if predicted != "skim_selected_parts":
        skim_targets = "not_applicable"
    elif skim_targets == "not_applicable":
        raise HumanValidationError("skim_selected_parts case requires --skim-targets all|partial|none")
    store = load_decision_store(store_path)
    item = add_decision_record(
        store,
        record_id=case["calibration_record_id"],
        insight_id=insight_id,
        source_type=case["source_type"],
        predicted_decision=predicted,
        missed_meaningful_info=missed,
        verdict=verdict,
        skim_targets_verified=skim_targets,
        note=note or f"Human validation session {session['session_id']} / issue #{session['issue']}",
    )
    write_decision_store(store_path, store)
    return item


def status(session: dict, learning_store: Path, decision_store: Path) -> dict:
    learning = load_learning_store(learning_store)
    decisions = load_decision_store(decision_store)
    learning_by_id = {item.get("id"): item for item in learning.get("records", [])}
    decision_by_id = {item.get("id"): item for item in decisions.get("records", [])}
    rows = []
    for case in session["cases"]:
        if session["kind"] == "reconstruction":
            record = learning_by_id.get(case["learning_record_id"])
            rows.append(
                {
                    "insight_id": case["insight_id"],
                    "immediate_recorded": record is not None,
                    "delayed_recorded": bool(record and record.get("delayed") is not None),
                    "transfer": record.get("transfer") if record else "not_recorded",
                }
            )
        else:
            rows.append(
                {
                    "insight_id": case["insight_id"],
                    "calibration_recorded": case["calibration_record_id"] in decision_by_id,
                }
            )
    return {"session_id": session["session_id"], "kind": session["kind"], "cases": rows}


def split_labels(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(";") if item.strip()]


def self_test() -> int:
    try:
        summary = validate_plan()
    except HumanValidationError as exc:
        print(f"human validation self-test failed: plan invalid: {exc}")
        return 1
    if summary["reconstruction_cases"] < 3 or len(summary["reconstruction_source_types"]) < 3:
        print("human validation self-test failed: reconstruction sample is not balanced")
        return 1
    if set(summary["source_decision_source_types"]) != {"video", "documentation", "repository", "paper", "article"}:
        print("human validation self-test failed: source decision sample does not cover five source types")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        reconstruction_path, reconstruction_session = prepare(
            "reconstruction", temp / "reconstruction.json"
        )
        decision_path, decision_session = prepare(
            "source_decision", temp / "source-decision.json"
        )
        # Prepared session must contain no human outcome fields and must reload through guards.
        load_session(reconstruction_path)
        load_session(decision_path)
        if any("answer_key" in case for case in reconstruction_session["cases"]):
            print("human validation self-test failed: reconstruction session leaked answer key")
            return 1

        learning_store = temp / "learning.json"
        first = reconstruction_session["cases"][0]
        record_learning_immediate(
            reconstruction_session,
            first["insight_id"],
            30,
            6,
            "yes",
            "learn",
            learning_store,
        )
        record_learning_delayed(
            reconstruction_session,
            first["insight_id"],
            2,
            "partial",
            ["problem", "mechanism"],
            ["boundary"],
            "partial",
            learning_store,
        )
        learning_status = status(reconstruction_session, learning_store, temp / "empty-decision.json")
        if not learning_status["cases"][0]["delayed_recorded"]:
            print("human validation self-test failed: delayed evidence did not attach")
            return 1

        calibration_store = temp / "calibration.json"
        selected = decision_session["cases"][0]
        try:
            record_calibration(
                decision_session,
                selected["insight_id"],
                False,
                "none",
                "correct",
                "all" if selected["predicted_decision"] == "skim_selected_parts" else "not_applicable",
                None,
                calibration_store,
            )
        except HumanValidationError:
            pass
        else:
            print("human validation self-test failed: calibration accepted without consumption confirmation")
            return 1
        record_calibration(
            decision_session,
            selected["insight_id"],
            True,
            "none",
            "correct",
            "all" if selected["predicted_decision"] == "skim_selected_parts" else "not_applicable",
            "synthetic self-test observation only",
            calibration_store,
        )
        calibration_status = status(decision_session, temp / "empty-learning.json", calibration_store)
        if not calibration_status["cases"][0]["calibration_recorded"]:
            print("human validation self-test failed: calibration evidence did not record")
            return 1

    print(
        "human validation self-test passed; fixed balanced samples, prompt-before-key ordering, "
        "local-only stores and explicit full-source confirmation work."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-plan")
    validate.add_argument("--json", action="store_true")

    prep = sub.add_parser("prepare")
    prep.add_argument("--kind", choices=sorted(KINDS), required=True)
    prep.add_argument("--output", type=Path)

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--session", type=Path, required=True)
    prompt.add_argument("--insight", required=True)

    guide = sub.add_parser("scoring-guide")
    guide.add_argument("--session", type=Path, required=True)
    guide.add_argument("--insight", required=True)

    decision = sub.add_parser("decision")
    decision.add_argument("--session", type=Path, required=True)
    decision.add_argument("--insight", required=True)

    immediate = sub.add_parser("record-immediate")
    immediate.add_argument("--session", type=Path, required=True)
    immediate.add_argument("--insight", required=True)
    immediate.add_argument("--source-minutes", type=float, required=True)
    immediate.add_argument("--explainer-minutes", type=float, required=True)
    immediate.add_argument("--immediate", choices=sorted(IMMEDIATE), required=True)
    immediate.add_argument("--decision", choices=sorted(LEARNING_DECISIONS), required=True)
    immediate.add_argument("--store", type=Path, default=DEFAULT_LEARNING_STORE)

    delayed = sub.add_parser("record-delayed")
    delayed.add_argument("--session", type=Path, required=True)
    delayed.add_argument("--insight", required=True)
    delayed.add_argument("--days", type=float, required=True)
    delayed.add_argument("--reconstruction", choices=sorted(RECONSTRUCTION), required=True)
    delayed.add_argument("--recalled", default="", help="Semicolon-separated model-piece labels")
    delayed.add_argument("--missed", default="", help="Semicolon-separated model-piece labels")
    delayed.add_argument("--transfer", choices=sorted(TRANSFER), default="not_tested")
    delayed.add_argument("--store", type=Path, default=DEFAULT_LEARNING_STORE)

    calibration = sub.add_parser("record-calibration")
    calibration.add_argument("--session", type=Path, required=True)
    calibration.add_argument("--insight", required=True)
    calibration.add_argument("--confirm-consumed", action="store_true")
    calibration.add_argument("--missed", choices=sorted(MISSED), required=True)
    calibration.add_argument("--verdict", choices=sorted(VERDICTS), required=True)
    calibration.add_argument("--skim-targets", choices=sorted(SKIM), default="not_applicable")
    calibration.add_argument("--note")
    calibration.add_argument("--store", type=Path, default=DEFAULT_DECISION_STORE)

    stat = sub.add_parser("status")
    stat.add_argument("--session", type=Path, required=True)
    stat.add_argument("--learning-store", type=Path, default=DEFAULT_LEARNING_STORE)
    stat.add_argument("--decision-store", type=Path, default=DEFAULT_DECISION_STORE)
    stat.add_argument("--json", action="store_true")

    sub.add_parser("self-test")

    args = parser.parse_args()
    try:
        if args.command == "self-test":
            return self_test()
        if args.command == "validate-plan":
            result = validate_plan()
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(
                    "Human validation plan passed: "
                    f"reconstruction={result['reconstruction_cases']} cases / {len(result['reconstruction_source_types'])} types; "
                    f"source_decision={result['source_decision_cases']} cases / {len(result['source_decision_source_types'])} types."
                )
            return 0
        if args.command == "prepare":
            path, session = prepare(args.kind, args.output)
            print_prepared(path, session)
            return 0

        session = load_session(args.session)
        if args.command == "prompt":
            show_prompt(session, args.insight)
        elif args.command == "scoring-guide":
            show_scoring_guide(session, args.insight)
        elif args.command == "decision":
            show_decision(session, args.insight)
        elif args.command == "record-immediate":
            item = record_learning_immediate(
                session,
                args.insight,
                args.source_minutes,
                args.explainer_minutes,
                args.immediate,
                args.decision,
                args.store,
            )
            print(json.dumps(item, ensure_ascii=False, indent=2))
        elif args.command == "record-delayed":
            item = record_learning_delayed(
                session,
                args.insight,
                args.days,
                args.reconstruction,
                split_labels(args.recalled),
                split_labels(args.missed),
                args.transfer,
                args.store,
            )
            print(json.dumps(item, ensure_ascii=False, indent=2))
        elif args.command == "record-calibration":
            item = record_calibration(
                session,
                args.insight,
                args.confirm_consumed,
                args.missed,
                args.verdict,
                args.skim_targets,
                args.note,
                args.store,
            )
            print(json.dumps(item, ensure_ascii=False, indent=2))
        elif args.command == "status":
            result = status(session, args.learning_store, args.decision_store)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Session {result['session_id']} [{result['kind']}]")
                for item in result["cases"]:
                    print("- " + json.dumps(item, sort_keys=True))
        return 0
    except (HumanValidationError, LearningUtilityError, BenchmarkError, json.JSONDecodeError, OSError) as exc:
        print(f"human validation error: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
