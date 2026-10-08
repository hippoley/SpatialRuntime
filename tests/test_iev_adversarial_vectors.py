import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "interop" / "agent-effect-authority" / "iev-adversarial-vectors.v0.1.json"
VERIFIER = ROOT / "interop" / "agent-effect-authority" / "verify_effect_observation.py"

SPEC = importlib.util.spec_from_file_location("verify_effect_observation", VERIFIER)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_iev_adversarial_vectors_replay():
    payload = json.loads(VECTORS.read_text(encoding="utf-8"))
    policy = payload["authority_policy"]

    for case in payload["cases"]:
        result = module.evaluate_observation(case["observation"], policy)
        assert result == case["expected"], case["id"]


def test_vectors_are_explicitly_non_normative():
    payload = json.loads(VECTORS.read_text(encoding="utf-8"))
    text = " ".join(payload["nonclaims"]).lower()
    assert "official ietf conformance" in text
    assert "novelty" in text
    assert "independent executable review artifact" in text
