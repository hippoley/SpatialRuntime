#!/usr/bin/env python3
"""Fail-closed repository P0 evidence verification.

File presence is provenance preparation, never proof that a user story passed.
The verifier runs the acceptance checks on the current checkout. GitHub Actions
run identity is provided separately by the hosting CI system.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("P0-CLOSURE.v0.1.json")
EXTERNAL_REGISTRY = ROOT / "interop" / "external-results" / "registry.v0.1.json"

CHECKS = {
    "P0-A": [[sys.executable, "interop/conformance/verify_catalog.py"]],
    "P0-B": [[sys.executable, "interop/external-results/verify_registry.py"]],
    "P0-C": [[sys.executable, "interop/verify_maturity.py"]],
    "P0-D": [[sys.executable, "-m", "pytest", "-q", "tests/test_runtime_application_assembly.py"]],
    "P0-E": [[sys.executable, "-m", "pytest", "-q", "tests/test_runtime_session_resume.py"]],
}


def _is_unrelated(repo: object) -> bool:
    return (
        isinstance(repo, str)
        and repo.count("/") == 1
        and all(repo.split("/"))
        and repo.split("/")[0].casefold() != "hippoley"
    )


def _external_gate(registry: dict) -> tuple[bool, list[dict]]:
    qualifying = []
    for entry in registry.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("evidence_maturity") != "externally-consumed" or entry.get("external_consumption") is not True:
            continue
        consumer = entry.get("consumer")
        if not isinstance(consumer, dict):
            continue
        if consumer.get("project_owned_evidence") is not True or not _is_unrelated(consumer.get("repository")):
            continue
        qualifying.append({"id": entry.get("id"), "repository": consumer.get("repository")})
    return bool(qualifying), qualifying


def _check(command: list[str]) -> dict:
    try:
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True,
            timeout=120, check=False,
        )
        return {
            "command": command[1:], "passed": result.returncode == 0,
            "returncode": result.returncode,
            "output_tail": (result.stdout + "\n" + result.stderr)[-1000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command[1:], "passed": False, "error": type(exc).__name__}


def verify() -> dict:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    registry = json.loads(EXTERNAL_REGISTRY.read_text(encoding="utf-8"))
    errors = []
    rows = []

    for item in doc.get("p0", []):
        p0_id = item.get("id")
        if item.get("owner") != "repository":
            errors.append(f"{p0_id}: repository P0 manifest contains external-owned gate")
            continue
        missing = [rel for rel in item.get("evidence_paths", []) if not (ROOT / rel).is_file()]
        if p0_id not in CHECKS:
            errors.append(f"{p0_id}: missing executable acceptance contract")
        results = [_check(command) for command in CHECKS.get(p0_id, [])] if not missing else []
        status = (
            "OPEN_MISSING_EVIDENCE" if missing else
            "UNVERIFIED_NO_ACCEPTANCE_CHECK" if not results else
            "VERIFIED_LOCAL" if all(result["passed"] for result in results) else
            "FAILED_ACCEPTANCE"
        )
        rows.append({"id": p0_id, "status": status, "missing_evidence": missing, "checks": results})
        if status != "VERIFIED_LOCAL":
            errors.append(f"{p0_id}: {status}")

    external_closed, qualifying = _external_gate(registry)
    external = doc.get("external_exit_gate", {})
    return {
        "schema": doc.get("schema"),
        "repository_p0_locally_verified": bool(rows) and all(row["status"] == "VERIFIED_LOCAL" for row in rows),
        "ci_run_attestation": "NOT_VERIFIED_BY_LOCAL_CHECKER",
        "external_adoption_gate": {
            "id": external.get("id"),
            "status": "CLOSED" if external_closed else "OPEN_EXTERNAL_GATE",
            "qualifying_evidence": qualifying,
        },
        "rows": rows,
        "errors": errors,
    }


def main() -> None:
    report = verify()
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"] or not report["repository_p0_locally_verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
