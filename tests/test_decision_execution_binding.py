import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "interop" / "decision-execution-binding"
SPEC = importlib.util.spec_from_file_location("deb_verify", DIR / "verify.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def load(name: str):
    return json.loads((DIR / "fixtures" / name).read_text(encoding="utf-8"))


def test_per_call_binding_passes():
    report = MOD.verify(load("per-call-pass.json"))
    assert report["result"] == "PASS"
    assert report["decisions"][0]["bound_executions"] == 1


def test_standing_decision_can_cover_multiple_calls():
    report = MOD.verify(load("standing-pass.json"))
    assert report["result"] == "PASS"
    assert report["decisions"][0]["bound_executions"] == 2


def test_per_call_decision_cannot_be_reused():
    report = MOD.verify(load("per-call-reused.json"))
    assert report["result"] == "FAIL"
    assert any(e["code"] == "PER_CALL_DECISION_REUSED" for e in report["errors"])


def test_not_checked_scope_is_unresolved():
    report = MOD.verify(load("standing-not-checked.json"))
    assert report["result"] == "UNRESOLVED"
    assert any(u["code"] == "SCOPE_BINDING_NOT_CHECKED" for u in report["unresolved"])


def test_denied_decision_cannot_have_execution():
    report = MOD.verify(load("deny-with-execution.json"))
    assert report["result"] == "FAIL"
    assert any(e["code"] == "DENIED_DECISION_HAS_EXECUTION" for e in report["errors"])


def test_github_outputs(tmp_path: Path):
    report = MOD.verify(load("standing-not-checked.json"))
    out = tmp_path / "out"
    MOD.write_github_outputs(report, out)
    assert out.read_text(encoding="utf-8").splitlines() == [
        "conformance_result=UNRESOLVED",
        "unresolved_count=1",
        "error_count=0",
    ]
