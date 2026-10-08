from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AEA = ROOT / "interop" / "agent-effect-authority"
VERIFIER = AEA / "verify_claim.py"
EXAMPLE = AEA / "claim.example.json"


def run_claim(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFIER), str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_agent_effect_authority_example_claim_passes() -> None:
    result = run_claim(EXAMPLE)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["spec"] == "agent-effect-authority.v0.1"
    assert report["requirements"] == 9
    assert report["claim_envelope"] == "PASS"
    assert report["evidence_truth_verified"] is False


def test_agent_effect_authority_rejects_missing_requirement(tmp_path: Path) -> None:
    claim = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    claim["requirements"] = claim["requirements"][:-1]
    candidate = tmp_path / "claim.json"
    candidate.write_text(json.dumps(claim), encoding="utf-8")

    result = run_claim(candidate)
    assert result.returncode != 0
    assert "missing requirements" in result.stderr
