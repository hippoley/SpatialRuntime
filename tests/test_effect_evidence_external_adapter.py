import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "interop" / "agent-effect-authority" / "run_conformance.py"
REFERENCE = ROOT / "interop" / "agent-effect-authority" / "examples" / "reference_adapter.py"

SPEC = importlib.util.spec_from_file_location("run_effect_evidence_conformance", RUNNER)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

def test_external_adapter_can_run_full_bundle():
    summary = module.run(adapter_command=f"{sys.executable} {REFERENCE}")
    assert summary["adapter_mode"] is True
    assert summary["failed"] == 0
    assert summary["passed"] == summary["total"]
    assert summary["total"] >= 11

def test_new_proof_sufficiency_cases_are_present():
    summary = module.run(adapter_command=f"{sys.executable} {REFERENCE}")
    cases = {row["case_id"]: row for row in summary["results"]}
    assert cases["structured-response-without-postcondition-proof"]["pass"] is True
    assert cases["missing-field-without-completeness-guarantee"]["pass"] is True

def test_bundle_github_outputs(tmp_path: Path):
    summary = module.run(adapter_command=f"{sys.executable} {REFERENCE}")
    output = tmp_path / "github-output"
    module._write_github_outputs(summary, output, "artifacts/report.json")
    lines = output.read_text(encoding="utf-8").splitlines()
    assert "conformance_result=PASS" in lines
    assert "failed_count=0" in lines
    assert f"passed_count={summary['passed']}" in lines
    assert f"total_count={summary['total']}" in lines
    assert "report_path=artifacts/report.json" in lines

def test_cli_can_persist_machine_readable_report(tmp_path: Path):
    report = tmp_path / "evidence" / "effect-evidence.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--adapter-command",
            f"{sys.executable} {REFERENCE}",
            "--report",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["conformance_bundle"] == "effect-evidence-v0.1"
    assert payload["adapter_protocol"] == "effect-evidence-adapter.v0.1"
    assert payload["adapter_mode"] is True
    assert payload["failed"] == 0
