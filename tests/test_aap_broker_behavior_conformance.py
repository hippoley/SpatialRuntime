import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "interop" / "aap-broker-behavior"
SPEC = importlib.util.spec_from_file_location("aap_behavior", DIR / "run_conformance.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)

REFERENCE = DIR / "examples" / "reference_adapter.py"
HOSTILE = DIR / "examples" / "leaky_adapter.py"


def test_reference_adapter_passes_behavior_subset():
    report = MOD.run(f"{sys.executable} {REFERENCE}")
    assert report["result"] == "PASS"
    assert report["failed"] == 0
    assert report["official_aap_conformance"] is False


def test_agent_visible_canary_leak_is_rejected():
    report = MOD.run(f"{sys.executable} {HOSTILE}")
    assert report["result"] == "FAIL"
    codes = {
        err["code"]
        for row in report["rows"]
        for err in row["errors"]
    }
    assert "AGENT_CONTEXT_LEAK" in codes


def test_denial_surface_is_compared_across_failure_classes(tmp_path: Path):
    adapter = tmp_path / "distinguishable.py"
    adapter.write_text(
        """
import json, sys
req=json.load(sys.stdin)
kind=req["scenario"]["kind"]
json.dump({
  "case_id": req["case_id"],
  "agent_visible": {
    "status": "denied" if kind != "success" else "ok",
    "error": kind if kind != "success" else None,
    "result": req["scenario"].get("operation_result")
  },
  "audit": {
    "present": True,
    "contains_credential_material": False,
    "integrity_evidence": {
      "kind": "signature",
      "verified": True,
      "key_id": "synthetic-harness-key",
      "record_digest": "sha256:" + "c" * 64
    }
  },
  "broker_observation": {
    "decision": "deny" if kind != "success" else "allow",
    "operation_executed": kind == "success"
  }
}, sys.stdout)
""".strip(),
        encoding="utf-8",
    )
    report = MOD.run(f"{sys.executable} {adapter}")
    assert report["result"] == "FAIL"
    assert any(
        row["case_id"] == "denial-opacity-cross-case"
        and any(err["code"] == "DENIAL_SURFACE_DISTINGUISHABLE" for err in row["errors"])
        for row in report["rows"]
    )


UNSIGNED = DIR / "examples" / "unsigned_audit_adapter.py"


def test_unsigned_audit_is_rejected():
    report = MOD.run(f"{sys.executable} {UNSIGNED}")
    assert report["result"] == "FAIL"
    codes = {
        err["code"]
        for row in report["rows"]
        for err in row["errors"]
    }
    assert "AUDIT_NOT_SIGNED" in codes
    assert "AUDIT_SIGNATURE_NOT_VERIFIED" in codes



def test_bare_signed_boolean_is_not_sufficient(tmp_path: Path):
    adapter = tmp_path / "self_asserted_signed.py"
    adapter.write_text(
        """
import json, sys
req=json.load(sys.stdin)
kind=req["scenario"]["kind"]
json.dump({
  "case_id": req["case_id"],
  "agent_visible": {
    "status": "ok" if kind == "success" else "denied",
    "error": None if kind == "success" else "grant_denied",
    "result": req["scenario"].get("operation_result")
  },
  "audit": {
    "present": True,
    "signed": True,
    "contains_credential_material": False
  },
  "broker_observation": {
    "decision": "allow" if kind == "success" else "deny",
    "operation_executed": kind == "success"
  }
}, sys.stdout)
""".strip(),
        encoding="utf-8",
    )
    report = MOD.run(f"{sys.executable} {adapter}")
    assert report["result"] == "FAIL"
    codes = {
        err["code"]
        for row in report["rows"]
        for err in row["errors"]
    }
    assert "AUDIT_INTEGRITY_EVIDENCE_MISSING" in codes
