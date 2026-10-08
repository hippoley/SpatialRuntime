import json
from pathlib import Path
import sys

PROFILE = Path(__file__).with_name("evidence-profile.v0.1.json")


def evaluate_observation(observation):
    required = {
        "logical_effect_id",
        "observed_after_attempt",
        "fresh",
        "authoritative_source",
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

    if not str(observation["authoritative_source"]).strip():
        return {"status": "UNRESOLVED", "reason": "SOURCE_NOT_AUTHORITATIVE"}

    kind = str(observation["observation_kind"]).strip().lower()
    if kind in {"model_estimate", "transport_ack", "cached_state", "unprovenanced"}:
        return {"status": "UNRESOLVED", "reason": "NON_AUTHORITATIVE_KIND"}

    verdict = str(observation["verdict"]).strip().upper()
    if verdict not in {"CONFIRMED", "CONTRADICTED", "UNRESOLVED"}:
        raise ValueError("unsupported verdict")

    return {"status": verdict, "reason": "AUTHORITATIVE_OBSERVATION"}


def main(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    print(json.dumps(evaluate_observation(payload), sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1])
