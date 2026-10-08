import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SINGLE = ROOT / "interop" / "agent-effect-authority" / "verify_effect_observation.py"
SPEC = importlib.util.spec_from_file_location("verify_effect_observation", SINGLE)
single = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(single)


def evaluate_evidence_set(observations, authority_policy):
    if not observations:
        return {"status": "INDETERMINATE", "reason": "NO_EVIDENCE"}

    resolved = []
    unresolved = []

    effect_ids = {
        str(item.get("logical_effect_id", "")).strip()
        for item in observations
        if str(item.get("logical_effect_id", "")).strip()
    }
    domains = {
        str(item.get("effect_domain", "")).strip()
        for item in observations
        if str(item.get("effect_domain", "")).strip()
    }

    if len(effect_ids) != 1:
        return {"status": "INDETERMINATE", "reason": "EFFECT_ID_SET_MISMATCH"}
    if len(domains) != 1:
        return {"status": "INDETERMINATE", "reason": "EFFECT_DOMAIN_SET_MISMATCH"}

    for observation in observations:
        result = single.evaluate_observation(observation, authority_policy)
        if result["status"] in {"CONFIRMED", "CONTRADICTED"}:
            resolved.append(result["status"])
        else:
            unresolved.append(result)

    terminal = set(resolved)

    if {"CONFIRMED", "CONTRADICTED"} <= terminal:
        return {
            "status": "CONFLICT",
            "reason": "AUTHENTIC_EVIDENCE_CONFLICT",
            "ordinary_continuation": False,
        }

    if terminal == {"CONFIRMED"}:
        return {"status": "CONFIRMED", "reason": "CONSISTENT_AUTHORITATIVE_EVIDENCE"}

    if terminal == {"CONTRADICTED"}:
        return {"status": "CONTRADICTED", "reason": "CONSISTENT_AUTHORITATIVE_EVIDENCE"}

    return {
        "status": "INDETERMINATE",
        "reason": "NO_CONSISTENT_TERMINAL_VERDICT",
        "unresolved_count": len(unresolved),
    }
