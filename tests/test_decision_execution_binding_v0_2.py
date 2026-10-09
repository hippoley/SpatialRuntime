import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "interop" / "decision-execution-binding"
FIX = DIR / "fixtures"

SPEC = importlib.util.spec_from_file_location("decision_execution_v02", DIR / "verify_v0_2.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_aap_approval_exact_attempt_passes():
    report = MOD.verify(load("aap-approval-pass.json"))
    assert report["result"] == "PASS"


def test_aap_approval_at_expiry_fails():
    report = MOD.verify(load("aap-approval-expired.json"))
    assert report["result"] == "FAIL"
    assert any(e["code"] == "DECISION_EXPIRED_BEFORE_EXECUTION" for e in report["errors"])


def test_aap_per_call_approval_cannot_bind_two_executions():
    report = MOD.verify(load("aap-approval-reused.json"))
    assert report["result"] == "FAIL"
    assert any(e["code"] == "PER_CALL_DECISION_REUSED" for e in report["errors"])


def test_aap_missing_execution_start_is_unresolved():
    report = MOD.verify(load("aap-approval-missing-start.json"))
    assert report["result"] == "UNRESOLVED"
    codes = {u["code"] for u in report["unresolved"]}
    assert "EXECUTION_START_TIME_NOT_EVIDENCED" in codes
    assert "DECISION_EXPIRY_NOT_CHECKABLE" in codes


def test_aap_mutated_execution_scope_fails():
    report = MOD.verify(load("aap-approval-scope-mismatch.json"))
    assert report["result"] == "FAIL"
    assert any(e["code"] == "SCOPE_BINDING_MISMATCH" for e in report["errors"])
