import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "interop" / "agent-effect-authority" / "verify_effect_observation.py"
SPEC = importlib.util.spec_from_file_location("verify_effect_observation", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def obs(**overrides):
    base = {
        "logical_effect_id": "effect-1",
        "observed_after_attempt": True,
        "fresh": True,
        "authoritative_source": "device-encoder",
        "observation_kind": "measured_state",
        "verdict": "CONFIRMED",
    }
    base.update(overrides)
    return base


def test_fresh_authoritative_post_attempt_evidence_can_resolve():
    assert module.evaluate_observation(obs())["status"] == "CONFIRMED"


def test_stale_observation_stays_unresolved():
    result = module.evaluate_observation(obs(fresh=False))
    assert result == {"status": "UNRESOLVED", "reason": "NOT_FRESH"}


def test_model_estimate_cannot_resolve_effect():
    result = module.evaluate_observation(obs(observation_kind="model_estimate"))
    assert result == {"status": "UNRESOLVED", "reason": "NON_AUTHORITATIVE_KIND"}


def test_transport_ack_cannot_resolve_effect():
    result = module.evaluate_observation(obs(observation_kind="transport_ack"))
    assert result == {"status": "UNRESOLVED", "reason": "NON_AUTHORITATIVE_KIND"}


def test_missing_source_stays_unresolved():
    result = module.evaluate_observation(obs(authoritative_source=""))
    assert result == {"status": "UNRESOLVED", "reason": "SOURCE_NOT_AUTHORITATIVE"}


def test_pre_attempt_observation_stays_unresolved():
    result = module.evaluate_observation(obs(observed_after_attempt=False))
    assert result == {"status": "UNRESOLVED", "reason": "NOT_POST_ATTEMPT"}


def test_authoritative_contradiction_is_preserved():
    assert module.evaluate_observation(obs(verdict="CONTRADICTED"))["status"] == "CONTRADICTED"
