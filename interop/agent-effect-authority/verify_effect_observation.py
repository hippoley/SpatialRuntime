import json
from pathlib import Path
import sys


NON_AUTHORITATIVE_KINDS = {
    "model_estimate",
    "transport_ack",
    "cached_state",
    "unprovenanced",
}


def _source_allowed(observation, authority_policy):
    if not isinstance(authority_policy, dict):
        return False
    domain = str(observation.get("effect_domain", "")).strip()
    source_id = str(observation.get("source_id", "")).strip()
    kind = str(observation.get("observation_kind", "")).strip().lower()
    allowed = authority_policy.get("allowed_sources", [])
    for row in allowed:
        if (
            str(row.get("effect_domain", "")).strip() == domain
            and str(row.get("source_id", "")).strip() == source_id
            and kind in {str(x).strip().lower() for x in row.get("observation_kinds", [])}
        ):
            return True
    return False


def evaluate_observation(observation, authority_policy):
    required = {
        "logical_effect_id",
        "effect_domain",
        "observed_after_attempt",
        "fresh",
        "source_id",
        "observation_kind",
        "verdict",
    }
    missing = sorted(required - set(observation))
    if missing:
        return {"status": "UNRESOLVED", "reason": "MISSING_FIELDS", "missing": missing}

    if not str(observation["logical_effect_id"]).strip():
        return {"status": "UNRESOLVED", "reason": "EFFECT_ID_MISSING"}

    if observation["observed_after_attempt"] is not True:
        return {"status": "UNRESOLVED", "reason": "NOT_POST_ATTEMPT"}

    if observation["fresh"] is not True:
        return {"status": "UNRESOLVED", "reason": "NOT_FRESH"}

    kind = str(observation["observation_kind"]).strip().lower()
    if kind in NON_AUTHORITATIVE_KINDS:
        return {"status": "UNRESOLVED", "reason": "NON_AUTHORITATIVE_KIND"}

    if not _source_allowed(observation, authority_policy):
        return {"status": "UNRESOLVED", "reason": "SOURCE_NOT_AUTHORIZED"}

    verdict = str(observation["verdict"]).strip().upper()
    if verdict not in {"CONFIRMED", "CONTRADICTED", "UNRESOLVED"}:
        raise ValueError("unsupported verdict")

    return {"status": verdict, "reason": "AUTHORITATIVE_OBSERVATION"}


def main(observation_path, policy_path):
    observation = json.loads(Path(observation_path).read_text(encoding="utf-8"))
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    print(json.dumps(evaluate_observation(observation, policy), sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
