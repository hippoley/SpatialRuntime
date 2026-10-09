from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "interop" / "conformance" / "CHANGELOG.md"
POLICY = ROOT / "interop" / "conformance" / "RELEASE-POLICY.md"
VERIFIER = ROOT / "interop" / "conformance" / "verify_release_contract.py"

TAG = "conformance-v0.1.0"
COMMIT = "6d8e0d4a5c9c665e10dad853ab6aadc280db6b55"
RUN_ID = "37878503867"
DIGEST = "a567aa55052c055a174891037d65c5d72a09dea2ece2fc9e963b0675397994dc"


def test_published_release_state_is_self_consistent():
    changelog = CHANGELOG.read_text(encoding="utf-8")
    policy = POLICY.read_text(encoding="utf-8")

    for marker in (TAG, COMMIT, RUN_ID, DIGEST):
        assert marker in changelog
    assert TAG in policy
    assert COMMIT in policy


def test_release_contract_verifier_accepts_published_release_state():
    result = subprocess.run(
        [sys.executable, str(VERIFIER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_obsolete_no_tag_blocker_is_not_required_after_release():
    changelog = CHANGELOG.read_text(encoding="utf-8")
    assert "No immutable conformance tag exists yet." not in changelog
