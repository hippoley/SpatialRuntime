import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "interop" / "agent-effect-authority" / "run_conformance.py"

SPEC = importlib.util.spec_from_file_location("run_effect_evidence_conformance", RUNNER)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_effect_evidence_bundle_is_green():
    summary = module.run()
    assert summary["conformance_bundle"] == "effect-evidence-v0.1"
    assert summary["failed"] == 0
    assert summary["passed"] == summary["total"]
    assert summary["total"] >= 9
