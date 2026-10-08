import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "interop"
    / "agent-effect-authority"
    / "verify_effect_observation_v02.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_effect_observation_v02", MODULE_PATH
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def claim(**overrides):
    base = {
        "logical_effect_id": "effect-1",
        "attempt_id": "attempt-7",
        "evidence_id": "obs-17",
        "evidence_digest": "sha256:abc123",
        "effect_domain": "physical-window",
        "source_id": "device-encoder",
        "observation_kind": "measured_state",
        "verdict": "CONFIRMED",
    }
    base.update(overrides)
    return base


def registry_entry(**overrides):
    base = {
        **claim(),
        "verifier_id": "gateway-attestor",
        "trust": "verified",
        "invalidation": "valid",
        "observed_after_attempt": True,
        "fresh": True,
    }
    base.update(overrides)
    return base


def policy(*entries):
    return {"verified_evidence": list(entries or (registry_entry(),))}


def test_verified_evidence_resolves_effect():
    result = module.evaluate_observation(claim(), policy())
    assert result == {
        "status": "CONFIRMED",
        "reason": "TRUSTED_EVIDENCE",
        "evidence_id": "obs-17",
        "verifier_id": "gateway-attestor",
        "trust": "verified",
    }


def test_spoofed_allowed_source_without_registry_match_stays_unresolved():
    result = module.evaluate_observation(
        claim(evidence_digest="sha256:forged"),
        policy(),
    )
    assert result == {
        "status": "UNRESOLVED",
        "reason": "EVIDENCE_NOT_VERIFIED",
    }


def test_evidence_cannot_be_reused_for_another_effect():
    result = module.evaluate_observation(
        claim(logical_effect_id="effect-2"),
        policy(),
    )
    assert result["reason"] == "EVIDENCE_NOT_VERIFIED"


def test_evidence_cannot_be_reused_for_another_attempt():
    result = module.evaluate_observation(
        claim(attempt_id="attempt-8"),
        policy(),
    )
    assert result["reason"] == "EVIDENCE_NOT_VERIFIED"


def test_untrusted_registry_entry_stays_unresolved():
    result = module.evaluate_observation(
        claim(),
        policy(registry_entry(trust="observed")),
    )
    assert result == {
        "status": "UNRESOLVED",
        "reason": "INSUFFICIENT_TRUST",
    }


def test_invalidated_registry_entry_stays_unresolved():
    result = module.evaluate_observation(
        claim(),
        policy(registry_entry(invalidation="revoked")),
    )
    assert result == {
        "status": "UNRESOLVED",
        "reason": "EVIDENCE_INVALIDATED",
    }


def test_stale_registry_entry_stays_unresolved():
    result = module.evaluate_observation(
        claim(),
        policy(registry_entry(fresh=False)),
    )
    assert result == {
        "status": "UNRESOLVED",
        "reason": "NOT_FRESH",
    }


def test_pre_attempt_registry_entry_stays_unresolved():
    result = module.evaluate_observation(
        claim(),
        policy(registry_entry(observed_after_attempt=False)),
    )
    assert result == {
        "status": "UNRESOLVED",
        "reason": "NOT_POST_ATTEMPT",
    }


def test_transport_ack_is_non_authoritative_even_if_registry_lists_it():
    c = claim(observation_kind="transport_ack")
    e = registry_entry(observation_kind="transport_ack")
    result = module.evaluate_observation(c, policy(e))
    assert result == {
        "status": "UNRESOLVED",
        "reason": "NON_AUTHORITATIVE_KIND",
    }


def test_verified_contradiction_is_preserved():
    c = claim(verdict="CONTRADICTED")
    e = registry_entry(verdict="CONTRADICTED")
    result = module.evaluate_observation(c, policy(e))
    assert result["status"] == "CONTRADICTED"


def test_missing_verifier_stays_unresolved():
    result = module.evaluate_observation(
        claim(),
        policy(registry_entry(verifier_id="")),
    )
    assert result == {
        "status": "UNRESOLVED",
        "reason": "VERIFIER_MISSING",
    }
