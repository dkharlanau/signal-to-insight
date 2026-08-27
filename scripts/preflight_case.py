#!/usr/bin/env python3
"""Preflight one researched review case in an isolated copy of the repository.

The command stages a candidate case patch + companion contract into a temporary workspace,
materializes them there, runs the same semantic validators/build steps used by CI, and deletes
the workspace afterwards. The live repository registries and generated surfaces are never
mutated by the preflight itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH_DIR = ROOT / "data" / "case-patches"
CONTRACT_DIR = ROOT / "data" / "case-contracts"

MUTABLE_FILES = [
    "data/inbox.json",
    "data/sources.json",
    "data/insights.json",
    "data/knowledge-graph.json",
    "data/knowledge-deltas.json",
    "data/claim-evidence.json",
    "data/prerequisite-maps.json",
    "data/learning-prompts.json",
    "data/source-decisions.json",
    "sitemap.xml",
]
MUTABLE_DIRS = ["previews", "explainers", "library", "knowledge"]

STEPS: list[tuple[str, list[str]]] = [
    ("case-patch schema/preflight", ["scripts/validate_case_patches.py"]),
    ("case-contract schema/preflight", ["scripts/validate_case_contracts.py"]),
    ("apply case patch", ["scripts/apply_case_patch.py", "{patch}"]),
    ("apply companion contract", ["scripts/apply_case_contract.py", "{contract}"]),
    ("structured knowledge", ["scripts/validate.py"]),
    ("research bundles", ["scripts/validate_bundles.py"]),
    ("case patches", ["scripts/validate_case_patches.py"]),
    ("case contracts", ["scripts/validate_case_contracts.py"]),
    ("knowledge graph", ["scripts/validate_graph.py"]),
    ("Knowledge Delta", ["scripts/validate_knowledge_deltas.py"]),
    ("claim evidence", ["scripts/validate_claim_evidence.py"]),
    ("prerequisites", ["scripts/validate_prerequisites.py"]),
    ("learning prompts", ["scripts/validate_learning_prompts.py"]),
    ("Source Decision", ["scripts/validate_source_decisions.py"]),
    ("public projection", ["scripts/public_projection.py"]),
    ("preview safety self-test", ["scripts/build_previews.py", "--self-test"]),
    ("review previews", ["scripts/build_previews.py"]),
    ("generated explainers", ["scripts/build.py"]),
    ("library", ["scripts/build_library.py"]),
    ("public graph", ["scripts/build_public_graph.py"]),
    ("sitemap", ["scripts/build_sitemap.py"]),
]


class PreflightError(ValueError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_input(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise PreflightError(f"candidate file not found: {path}")
    return path


def infer_contract(patch_path: Path) -> Path:
    same_name = CONTRACT_DIR / patch_path.name
    if same_name.exists():
        return same_name.resolve()

    patch = load(patch_path)
    intake_id = patch.get("intake_id")
    insight_id = (patch.get("insight") or {}).get("id")
    matches: list[Path] = []
    for candidate in sorted(CONTRACT_DIR.glob("*.json")):
        try:
            data = load(candidate)
        except (OSError, json.JSONDecodeError):
            continue
        if (
            intake_id
            and data.get("intake_id") == intake_id
            or insight_id
            and data.get("insight_id") == insight_id
        ):
            matches.append(candidate)
    if len(matches) == 1:
        return matches[0].resolve()
    if not matches:
        raise PreflightError(
            "companion contract could not be inferred; pass --contract explicitly"
        )
    raise PreflightError(
        "multiple companion contracts matched the candidate; pass --contract explicitly: "
        + ", ".join(str(path.relative_to(ROOT)) for path in matches)
    )


def copy_workspace(destination: Path) -> None:
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".local",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            "*.pyc",
        ),
    )


def stage_candidate(source: Path, workspace: Path, kind: str) -> Path:
    if kind == "patch":
        target = workspace / "data" / "case-patches" / source.name
    elif kind == "contract":
        target = workspace / "data" / "case-contracts" / source.name
    else:
        raise PreflightError(f"unsupported candidate kind: {kind}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def command_for(workspace: Path, parts: list[str], patch: Path, contract: Path) -> list[str]:
    rendered = [
        str(patch.relative_to(workspace)) if part == "{patch}" else
        str(contract.relative_to(workspace)) if part == "{contract}" else
        part
        for part in parts
    ]
    return [sys.executable, *rendered]


def run_preflight(patch_source: Path, contract_source: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="sti-case-preflight-") as tmp:
        workspace = Path(tmp) / "repo"
        copy_workspace(workspace)
        patch = stage_candidate(patch_source, workspace, "patch")
        contract = stage_candidate(contract_source, workspace, "contract")

        results: list[dict] = []
        for label, parts in STEPS:
            command = command_for(workspace, parts, patch, contract)
            completed = subprocess.run(
                command,
                cwd=workspace,
                text=True,
                capture_output=True,
            )
            output = (completed.stdout + completed.stderr).strip()
            result = {
                "step": label,
                "ok": completed.returncode == 0,
                "returncode": completed.returncode,
                "command": " ".join(command[1:]),
                "output": output[-5000:],
            }
            results.append(result)
            if completed.returncode != 0:
                return {
                    "ok": False,
                    "patch": patch_source.name,
                    "contract": contract_source.name,
                    "failed_step": label,
                    "steps_completed": len(results) - 1,
                    "result": result,
                    "workspace_persisted": False,
                }

        return {
            "ok": True,
            "patch": patch_source.name,
            "contract": contract_source.name,
            "failed_step": None,
            "steps_completed": len(results),
            "result": results[-1] if results else None,
            "workspace_persisted": False,
        }


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint_mutable_state(root: Path = ROOT) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in MUTABLE_FILES:
        path = root / relative
        result[relative] = hash_file(path) if path.exists() else "<missing>"
    for relative in MUTABLE_DIRS:
        directory = root / relative
        if not directory.exists():
            result[relative] = "<missing>"
            continue
        digest = hashlib.sha256()
        files = sorted(path for path in directory.rglob("*") if path.is_file())
        for path in files:
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        result[relative] = digest.hexdigest()
    return result


def find_self_test_pair() -> tuple[Path, Path]:
    contracts = sorted(CONTRACT_DIR.glob("*.json"))
    patches = sorted(PATCH_DIR.glob("*.json"))
    for contract_path in contracts:
        contract = load(contract_path)
        intake_id = contract.get("intake_id")
        insight_id = contract.get("insight_id")
        for patch_path in patches:
            patch = load(patch_path)
            insight = patch.get("insight") or {}
            if (
                patch.get("intake_id") == intake_id
                and insight.get("id") == insight_id
                and insight.get("status") == "review"
            ):
                return patch_path, contract_path
    raise PreflightError("self-test requires at least one materialized review case pair")


def make_invalid_contract(source: Path, destination: Path) -> None:
    data = load(source)
    decision = data.get("source_decision") or {}
    parts = decision.get("selected_parts")
    if isinstance(parts, list) and parts:
        decision["decision"] = "explainer_is_enough"
        # Keep selected_parts deliberately: semantic validator must reject this combination.
    else:
        decision["decision"] = "skim_selected_parts"
        decision["selected_parts"] = []
        # skim_selected_parts without a locator must be rejected.
    data["source_decision"] = decision
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def self_test() -> int:
    before = fingerprint_mutable_state()
    patch, contract = find_self_test_pair()

    success = run_preflight(patch.resolve(), contract.resolve())
    if not success.get("ok"):
        print(
            "preflight self-test failed: valid review case did not pass at "
            f"{success.get('failed_step')}: {(success.get('result') or {}).get('output', '')[-1000:]}"
        )
        return 1
    if fingerprint_mutable_state() != before:
        print("preflight self-test failed: success path mutated live repository state")
        return 1

    with tempfile.TemporaryDirectory(prefix="sti-bad-contract-") as tmp:
        bad_contract = Path(tmp) / contract.name
        make_invalid_contract(contract, bad_contract)
        failure = run_preflight(patch.resolve(), bad_contract.resolve())
    if failure.get("ok"):
        print("preflight self-test failed: intentionally invalid companion contract passed")
        return 1
    if fingerprint_mutable_state() != before:
        print("preflight self-test failed: failure path mutated live repository state")
        return 1

    print(
        "case preflight self-test passed: valid case succeeds, semantic failure is caught, "
        "and live registries/generated surfaces remain unchanged."
    )
    return 0


def print_result(result: dict) -> None:
    if result.get("ok"):
        print(
            f"PASS: {result['patch']} + {result['contract']} can materialize as review "
            f"({result['steps_completed']} preflight steps)."
        )
        print("Live repository state was not modified; the temporary workspace was removed.")
        return
    failed = result.get("result") or {}
    print(f"FAIL: {result.get('failed_step')} (exit {failed.get('returncode')}).")
    if failed.get("output"):
        print(failed["output"])
    print("Live repository state was not modified; the temporary workspace was removed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patch", nargs="?", help="Candidate case-patch JSON path")
    parser.add_argument("--contract", help="Companion case-contract JSON path; inferred when omitted")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.patch:
        parser.error("patch is required unless --self-test is used")

    try:
        patch = resolve_input(args.patch)
        contract = resolve_input(args.contract) if args.contract else infer_contract(patch)
        result = run_preflight(patch, contract)
    except (PreflightError, OSError, json.JSONDecodeError) as exc:
        result = {
            "ok": False,
            "patch": args.patch,
            "contract": args.contract,
            "failed_step": "input",
            "steps_completed": 0,
            "result": {"returncode": 2, "output": str(exc)},
            "workspace_persisted": False,
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_result(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
