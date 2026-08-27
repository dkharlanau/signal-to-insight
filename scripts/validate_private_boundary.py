#!/usr/bin/env python3
"""Fail if private personal/source context can leak into versioned/public projection paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "run-manifests"
GITIGNORE = ROOT / ".gitignore"
PUBLIC_BUILDERS = [
    ROOT / "scripts" / "build.py",
    ROOT / "scripts" / "build_previews.py",
    ROOT / "scripts" / "build_graph.py",
    ROOT / "scripts" / "build_public_graph.py",
    ROOT / "scripts" / "build_library.py",
    ROOT / "scripts" / "build_syntheses.py",
    ROOT / "scripts" / "build_sitemap.py",
    ROOT / "scripts" / "build_history.py",
    ROOT / "scripts" / "build_reanalysis.py",
]
FORBIDDEN_BUILDER_MARKERS = [
    ".local/",
    "personal-baseline.json",
    "action-outcomes.json",
    "run-context/",
    "private_overlay",
    ".local/private",
]
ALLOWED_MANIFEST_KEYS = {
    "available",
    "baseline_version",
    "baseline_revision",
    "baseline_fingerprint",
    "outcomes_fingerprint",
    "private_sidecar",
    "selected_entries",
    "selected_outcomes",
    "privacy",
}
FORBIDDEN_PERSONAL_KEYS = {
    "entries", "active_context", "goals", "projects", "questions", "action_outcomes",
    "hypothesis", "intended_outcome", "result_summary", "user_assertion", "experience"
}


class PrivateBoundaryError(ValueError):
    pass


def validate_manifest_personal(manifest: dict, where: str) -> None:
    personal = manifest.get("personal_context")
    if personal is None:
        return
    if not isinstance(personal, dict):
        raise PrivateBoundaryError(f"{where}.personal_context must be metadata object")
    unknown = set(personal) - ALLOWED_MANIFEST_KEYS
    if unknown:
        raise PrivateBoundaryError(f"{where}.personal_context leaks unsupported fields: {sorted(unknown)}")
    forbidden = set(personal) & FORBIDDEN_PERSONAL_KEYS
    if forbidden:
        raise PrivateBoundaryError(f"{where}.personal_context leaks private content: {sorted(forbidden)}")
    sidecar = personal.get("private_sidecar")
    if sidecar is not None and not (isinstance(sidecar, str) and sidecar.startswith(".local/run-context/")):
        raise PrivateBoundaryError(f"{where}.private_sidecar must stay under .local/run-context/")
    if personal.get("privacy") != "private_local_not_public_evidence":
        raise PrivateBoundaryError(f"{where}.personal_context must declare private boundary")


def validate_repo() -> None:
    ignore = GITIGNORE.read_text(encoding="utf-8") if GITIGNORE.exists() else ""
    if ".local/" not in {line.strip() for line in ignore.splitlines()}:
        raise PrivateBoundaryError(".gitignore must exclude .local/")

    for path in PUBLIC_BUILDERS:
        if not path.exists():
            raise PrivateBoundaryError(f"missing public builder: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        matches = [marker for marker in FORBIDDEN_BUILDER_MARKERS if marker in text]
        if matches:
            raise PrivateBoundaryError(
                f"public builder {path.relative_to(ROOT)} references private storage markers: {matches}"
            )

    if MANIFESTS.exists():
        for path in sorted(MANIFESTS.glob("*.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            validate_manifest_personal(manifest, str(path.relative_to(ROOT)))


def self_test() -> int:
    safe = {
        "personal_context": {
            "available": True,
            "baseline_version": "1.0.0",
            "baseline_revision": 4,
            "baseline_fingerprint": "abc",
            "outcomes_fingerprint": "def",
            "private_sidecar": ".local/run-context/intake.json",
            "selected_entries": 2,
            "selected_outcomes": 1,
            "privacy": "private_local_not_public_evidence",
        }
    }
    validate_manifest_personal(safe, "fixture")
    leaking = {"personal_context": dict(safe["personal_context"], entries=[{"concept": "secret"}])}
    try:
        validate_manifest_personal(leaking, "fixture-leak")
    except PrivateBoundaryError:
        pass
    else:
        print("private boundary self-test failed: leaked entries accepted")
        return 1
    print("private boundary self-test passed; manifests can keep fingerprints/counts but not personal content.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            return self_test()
        validate_repo()
    except (PrivateBoundaryError, json.JSONDecodeError) as exc:
        print(f"private boundary validation failed: {exc}")
        return 1
    print("Private boundary validation passed; public builders are independent of .local personal/source context.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
