from __future__ import annotations
from typing import Any, Mapping, Sequence

SCHEMA="action_arbitration_v3.2"
class ActionArbitrationError(RuntimeError): pass


def arbitrate_actions(*, source_step:int, source_revision:int,
                      policy_action:Mapping[str,Any]|None,
                      recovery_actions:Sequence[Mapping[str,Any]]|None=None)->dict[str,Any]:
    """Merge policy and recovery intents before SafetySupervisor.

    Per entity precedence: recovery STOP > recovery set_state > normal policy.
    STOP is represented as a non-motion control action and must be dispatched via
    the hardware action path, while set_state is converted into the common change bus.
    """
    policy_action=dict(policy_action or {"source_step":source_step,"source_revision":source_revision,"changes":{}})
    if int(policy_action.get("source_step",-1))!=int(source_step) or int(policy_action.get("source_revision",-1))!=int(source_revision):
        raise ActionArbitrationError("policy action step/revision mismatch")
    changes=policy_action.get("changes") or {}
    if not isinstance(changes,Mapping): raise ActionArbitrationError("policy changes must be object")
    merged={k:dict(v) for k,v in changes.items() if isinstance(v,Mapping)}
    origins={k:"policy" for k in merged}
    control_actions=[]
    seen_recovery_entities=set()
    for a in recovery_actions or []:
        if a.get("schema")!="fault_recovery_action_v2.8": raise ActionArbitrationError("unsupported recovery action schema")
        if int(a.get("source_step",-1))!=int(source_step) or int(a.get("source_revision",-1))!=int(source_revision):
            raise ActionArbitrationError("recovery action step/revision mismatch")
        eid=a.get("entity_id")
        if not eid: raise ActionArbitrationError("recovery action missing entity_id")
        kind=a.get("kind")
        if kind=="stop":
            # STOP preempts both policy and recovery motion for the entity.
            merged.pop(eid,None); origins[eid]="recovery_stop"
            control_actions.append({"kind":"stop","entity_id":eid,"device_id":a.get("device_id"),"reason":a.get("reason"),"requires_commit_gate":True})
            seen_recovery_entities.add(eid)
        elif kind=="set_state":
            # If a STOP for the same entity already exists in this batch, do not also
            # emit motion. The next recovery phase may submit release after STOP ACK.
            if eid in seen_recovery_entities and any(x["kind"]=="stop" and x["entity_id"]==eid for x in control_actions):
                continue
            target=a.get("target_state") or {}
            if not isinstance(target,Mapping): raise ActionArbitrationError("recovery target_state must be object")
            merged[eid]=dict(target); origins[eid]="recovery_motion"; seen_recovery_entities.add(eid)
        else:
            raise ActionArbitrationError(f"unsupported recovery action kind: {kind}")
    return {"schema":SCHEMA,"source_step":int(source_step),"source_revision":int(source_revision),
            "changes":merged,"origins":origins,"control_actions":control_actions,
            "kind":"arbitrated","summary":{"motion_changes":len(merged),"control_actions":len(control_actions)}}
