from __future__ import annotations
from typing import Any

SCHEMA = "physical_commit_decision_v1.9"

class CommitGateError(RuntimeError): pass
class StalePolicyActionError(CommitGateError): pass


def gate_action(*, observation: dict[str, Any], proposed_action: dict[str, Any],
                runtime_state: dict[str, Any], expected_step: int, expected_revision: int,
                max_open_ratio_delta: float = 0.25) -> dict[str, Any]:
    if observation.get("schema") != "windowpilot_observation_v1.8":
        raise CommitGateError("expected windowpilot_observation_v1.8")
    if int(observation.get("step", -1)) != int(expected_step) or int(observation.get("revision", -1)) != int(expected_revision):
        raise StalePolicyActionError("observation step/revision mismatch")
    if int(proposed_action.get("source_step", -1)) != int(expected_step) or int(proposed_action.get("source_revision", -1)) != int(expected_revision):
        raise StalePolicyActionError("proposed action step/revision mismatch")
    changes = proposed_action.get("changes", {})
    if not isinstance(changes, dict):
        raise CommitGateError("proposed_action.changes must be object")

    safe = bool(observation.get("quality", {}).get("safe_for_control", False))
    decisions: dict[str, Any] = {}
    reasons: list[dict[str, Any]] = []

    for entity_id, change in changes.items():
        if entity_id not in runtime_state:
            decisions[entity_id] = {"decision":"reject","reason":"unknown_entity"}
            reasons.append({"entity_id":entity_id,"reason":"unknown_entity"})
            continue
        current = dict(runtime_state[entity_id].get("executed_state", {}))
        if not safe:
            decisions[entity_id] = {"decision":"hold","executed_state":current,"reason":"unsafe_observation"}
            continue
        if not isinstance(change, dict):
            decisions[entity_id] = {"decision":"reject","reason":"invalid_change"}
            continue
        target = dict(current)
        clamped = False
        for k,v in change.items():
            if k == "open_ratio":
                x = float(v)
                if x < 0.0 or x > 1.0: raise CommitGateError(f"{entity_id}.open_ratio outside [0,1]")
                cur = float(current.get("open_ratio", x))
                lo, hi = max(0.0, cur-max_open_ratio_delta), min(1.0, cur+max_open_ratio_delta)
                if x < lo: x, clamped = lo, True
                if x > hi: x, clamped = hi, True
                target[k] = round(x, 10)
            else:
                target[k] = v
        decisions[entity_id] = {"decision":"commit_clamped" if clamped else "commit", "executed_state":target,
                                "requested_change":change}
    rejected = sum(1 for d in decisions.values() if d["decision"] == "reject")
    held = sum(1 for d in decisions.values() if d["decision"] == "hold")
    committed = sum(1 for d in decisions.values() if d["decision"].startswith("commit"))
    return {"schema":SCHEMA,"source_step":expected_step,"source_revision":expected_revision,
            "observation_safe":safe,"decisions":decisions,
            "summary":{"committed":committed,"held":held,"rejected":rejected,
                       "ready_to_dispatch":safe and rejected==0},
            "policy":{"max_open_ratio_delta":max_open_ratio_delta},"reasons":reasons}
