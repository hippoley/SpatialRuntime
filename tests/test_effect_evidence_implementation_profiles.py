import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "interop" / "agent-effect-authority" / "implementation-profiles.v0.1.json"


def test_profiles_cover_multiple_independent_implementations():
    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    implementations = payload["implementations"]
    repos = {item["repository"] for item in implementations}

    assert "studivox/agentx" in repos
    assert "OpenAdaptAI/openadapt-flow" in repos
    assert len(repos) >= 2


def test_profiles_distinguish_executed_conformance_from_source_audit():
    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    for item in payload["implementations"]:
        assert item["audit_kind"] == "source-review"
        nonclaims = " ".join(item["nonclaims"]).lower()
        assert "not an executed compatibility score" in nonclaims


def test_openadapt_profile_preserves_fail_closed_semantics():
    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    item = next(
        row for row in payload["implementations"]
        if row["repository"] == "OpenAdaptAI/openadapt-flow"
    )
    states = item["native_states"]

    assert states["STALE"] == "unresolved"
    assert states["CONFLICTING"] == "conflict"
    assert states["INDETERMINATE"] == "unresolved"


def test_agentx_profile_records_proof_sufficiency_gaps_without_overclaiming():
    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    item = next(
        row for row in payload["implementations"]
        if row["repository"] == "studivox/agentx"
    )
    gaps = " ".join(item["observed_gaps_against_bundle"])

    assert "structured JSON" in gaps
    assert "completeness guarantee" in gaps
    assert "does not claim AgentX violates" in " ".join(item["nonclaims"])
