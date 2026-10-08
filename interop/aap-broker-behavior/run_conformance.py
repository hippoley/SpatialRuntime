#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def _json_blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _run_adapter(command: str, fixture: dict[str, Any]) -> dict[str, Any]:
    proc = subprocess.run(
        shlex.split(command),
        input=json.dumps({"case_id": fixture["id"], "scenario": fixture["scenario"]}),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"adapter failed for {fixture['id']}: rc={proc.returncode} stderr={proc.stderr.strip()}"
        )
    result = json.loads(proc.stdout)
    if not isinstance(result, dict):
        raise RuntimeError(f"adapter result for {fixture['id']} is not an object")
    return result


def verify_case(fixture: dict[str, Any], obs: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    scenario = fixture["scenario"]
    expected = fixture["expected"]

    if obs.get("case_id") != fixture["id"]:
        errors.append({"code": "CASE_ID_MISMATCH"})

    agent_visible = obs.get("agent_visible")
    audit = obs.get("audit")
    broker = obs.get("broker_observation")
    if not isinstance(agent_visible, dict):
        return [{"code": "MISSING_AGENT_VISIBLE"}]
    if not isinstance(audit, dict):
        return [{"code": "MISSING_AUDIT_EVIDENCE"}]
    if not isinstance(broker, dict):
        return [{"code": "MISSING_BROKER_OBSERVATION"}]

    visible_blob = _json_blob(agent_visible)
    for key in ("canary_credential", "canary_backend", "canary_provider"):
        value = scenario.get(key)
        if isinstance(value, str) and value and value in visible_blob:
            errors.append({"code": "AGENT_CONTEXT_LEAK", "material": key})

    if audit.get("present") is not True:
        errors.append({"code": "AUDIT_MISSING"})
    if audit.get("contains_credential_material") is not False:
        errors.append({"code": "AUDIT_CREDENTIAL_LEAK"})

    integrity = audit.get("integrity_evidence")
    if not isinstance(integrity, dict):
        errors.append({"code": "AUDIT_INTEGRITY_EVIDENCE_MISSING"})
    else:
        if integrity.get("kind") != "signature":
            errors.append({
                "code": "AUDIT_NOT_SIGNED",
                "kind": integrity.get("kind"),
            })
        if integrity.get("verified") is not True:
            errors.append({"code": "AUDIT_SIGNATURE_NOT_VERIFIED"})
        key_id = integrity.get("key_id")
        if not isinstance(key_id, str) or not key_id:
            errors.append({"code": "AUDIT_SIGNING_KEY_ID_MISSING"})
        digest = integrity.get("record_digest")
        if (
            not isinstance(digest, str)
            or not digest.startswith("sha256:")
            or len(digest) != 71
            or any(ch not in "0123456789abcdef" for ch in digest[7:])
        ):
            errors.append({"code": "AUDIT_RECORD_DIGEST_INVALID"})

    decision = broker.get("decision")
    executed = broker.get("operation_executed")
    if expected == "DENY":
        if decision != "deny":
            errors.append({"code": "EXPECTED_DENY", "actual": decision})
        if executed is not False:
            errors.append({"code": "DENIED_BUT_EXECUTED"})
        if agent_visible.get("status") != "denied":
            errors.append({"code": "DENIAL_NOT_AGENT_VISIBLE"})
    elif expected == "ALLOW":
        if decision != "allow":
            errors.append({"code": "EXPECTED_ALLOW", "actual": decision})
        if executed is not True:
            errors.append({"code": "ALLOWED_BUT_NOT_EXECUTED"})
        if agent_visible.get("status") != "ok":
            errors.append({"code": "SUCCESS_NOT_AGENT_VISIBLE"})
        result = scenario.get("operation_result")
        if not isinstance(result, str) or result not in visible_blob:
            errors.append({"code": "RESULT_NOT_RETURNED"})

    return errors


def run(adapter_command: str) -> dict[str, Any]:
    fixtures = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURES.glob("*.json"))
    ]
    rows: list[dict[str, Any]] = []
    denial_surfaces: list[str] = []

    for fixture in fixtures:
        obs = _run_adapter(adapter_command, fixture)
        errors = verify_case(fixture, obs)
        if fixture["expected"] == "DENY" and isinstance(obs.get("agent_visible"), dict):
            denial_surfaces.append(_json_blob(obs["agent_visible"]))
        rows.append(
            {
                "case_id": fixture["id"],
                "status": "PASS" if not errors else "FAIL",
                "errors": errors,
            }
        )

    if denial_surfaces and len(set(denial_surfaces)) != 1:
        rows.append(
            {
                "case_id": "denial-opacity-cross-case",
                "status": "FAIL",
                "errors": [{"code": "DENIAL_SURFACE_DISTINGUISHABLE"}],
            }
        )
    else:
        rows.append(
            {
                "case_id": "denial-opacity-cross-case",
                "status": "PASS",
                "errors": [],
            }
        )

    failed = sum(row["status"] == "FAIL" for row in rows)
    return {
        "profile": "aap-broker-behavior.v0.1",
        "total": len(rows),
        "passed": len(rows) - failed,
        "failed": failed,
        "result": "PASS" if failed == 0 else "FAIL",
        "rows": rows,
        "official_aap_conformance": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter-command", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    summary = run(args.adapter_command)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"conformance_result={summary['result']}\n")
            handle.write(f"passed_count={summary['passed']}\n")
            handle.write(f"failed_count={summary['failed']}\n")
            handle.write(f"total_count={summary['total']}\n")
    raise SystemExit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
