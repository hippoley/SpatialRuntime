import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "interop" / "otel-tool-decision-lifecycle"
SPEC = importlib.util.spec_from_file_location("tdl_verify", DIR / "verify.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def load(name: str):
    return json.loads((DIR / "fixtures" / name).read_text(encoding="utf-8"))


def test_positive_path_correlates_one_execution():
    report = MOD.verify(load("positive-path.otlp.json"))
    assert report["result"] == "PASS"
    assert report["lifecycles"][0]["status"] == "POSITIVE_PATH_OBSERVED"
    assert report["lifecycles"][0]["observed_executions"] == 1
    assert report["external_effect_confirmation"] is False


def test_missing_call_id_is_unresolved_not_failure():
    report = MOD.verify(load("devplane-style-no-call-id.otlp.json"))
    assert report["result"] == "UNRESOLVED"
    assert report["unresolved"][0]["code"] == "UNRESOLVED_CORRELATION"
    assert report["errors"] == []


def test_deny_plus_execution_is_contradiction():
    report = MOD.verify(load("deny-with-execution.otlp.json"))
    assert report["result"] == "FAIL"
    assert report["errors"][0]["code"] == "DENY_WITH_OBSERVED_EXECUTION"


def test_github_output_file(tmp_path: Path):
    report = MOD.verify(load("devplane-style-no-call-id.otlp.json"))
    output = tmp_path / "github-output"
    MOD.write_github_outputs(report, output)
    assert output.read_text(encoding="utf-8").splitlines() == [
        "lifecycle_result=UNRESOLVED",
        "unresolved_count=1",
        "error_count=0",
    ]
