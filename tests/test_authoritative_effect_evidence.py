import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "interop" / "agent-effect-authority" / "verify_effect_observation.py"
SPEC = importlib.util.spec_from_file_location("verify_effect_observation", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


POLICY = {
    "allowed_sources": [
        {
            "effect_domain": "physical-window",
            "source_id": "device-encoder",
            "observation_kinds": ["measured_state"],
        },
        {
            "effect_domain": "durable-record",
            "source_id": "primary-store-readback",
            "observation_kinds": ["durable_state"],
        },
    ]
}


def obs(**overrides):
    base = {
        "logical_effect_id": "effect-1",
        "effect_domain": "physical-window",
        "observed_after_attempt": True,
        "fresh": True,
        "source_id": "device-encoder",
        "observation_kind": "measured_state",
        "verdict": "CONFIRMED",
    }
    base.update(overrides)
    return base


def test_authorized_fresh_post_attempt_evidence_can_resolve():
    assert module.evaluate_observation(obs(), POLICY)["status"] == "CONFIRMED"


def test_stale_observation_stays_unresolved():
    assert module.evaluate_observation(obs(fresh=False), POLICY) == {
        "status": "UNRESOLVED",
        "reason": "NOT_FRESH",
    }


def test_model_estimate_cannot_resolve_effect():
    assert module.evaluate_observation(
        obs(observation_kind="model_estimate"), POLICY
    ) == {"status": "UNRESOLVED", "reason": "NON_AUTHORITATIVE_KIND"}


def test_transport_ack_cannot_resolve_effect():
    assert module.evaluate_observation(
        obs(observation_kind="transport_ack"), POLICY
    ) == {"status": "UNRESOLVED", "reason": "NON_AUTHORITATIVE_KIND"}


def test_self_declared_unknown_source_cannot_resolve():
    assert module.evaluate_observation(
        obs(source_id="model-says-authoritative"), POLICY
    ) == {"status": "UNRESOLVED", "reason": "SOURCE_NOT_AUTHORIZED"}


def test_source_authority_is_domain_specific():
    assert module.evaluate_observation(
        obs(effect_domain="payment"), POLICY
    ) == {"status": "UNRESOLVED", "reason": "SOURCE_NOT_AUTHORIZED"}


def test_pre_attempt_observation_stays_unresolved():
    assert module.evaluate_observation(
        obs(observed_after_attempt=False), POLICY
    ) == {"status": "UNRESOLVED", "reason": "NOT_POST_ATTEMPT"}


def test_authoritative_contradiction_is_preserved():
    assert module.evaluate_observation(
        obs(verdict="CONTRADICTED"), POLICY
    )["status"] == "CONTRADICTED"


def test_durable_store_readback_can_resolve_in_its_own_domain():
    observation = obs(
        effect_domain="durable-record",
        source_id="primary-store-readback",
        observation_kind="durable_state",
    )
    assert module.evaluate_observation(observation, POLICY)["status"] == "CONFIRMED"
