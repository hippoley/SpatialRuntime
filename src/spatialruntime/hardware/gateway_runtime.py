from __future__ import annotations
from typing import Any
from spatialruntime.hardware.contract import build_dispatch_batch


def dispatch_via_gateway(*, case_id: str, commit_decision: dict[str,Any], device_bindings: dict[str,dict[str,Any]],
                         gateway: Any, ledger: Any, now_ms: int) -> dict[str,Any]:
    batch=build_dispatch_batch(case_id=case_id,commit_decision=commit_decision,device_bindings=device_bindings,now_ms=now_ms)
    ledger.register_batch(batch)
    all_events=[]; failures=[]
    for command in batch["commands"]:
        snap=ledger.mark_dispatched(command["command_id"],now_ms=now_ms)
        if snap["status"] in {"confirmed","failed","cancelled"}: continue
        try:
            events=gateway.send(command,now_ms=now_ms)
        except Exception as exc:
            failures.append({"command_id":command["command_id"],"error":type(exc).__name__,"message":str(exc)})
            continue
        for event in events:
            ledger.ingest_event(event,expected_step=batch["source_step"],expected_revision=batch["source_revision"])
            all_events.append(event)
    feedback=ledger.build_device_feedback(case_id=case_id,source_step=batch["source_step"],source_revision=batch["source_revision"])
    return {"schema":"gateway_dispatch_result_v2.2","batch":batch,"events":all_events,"transport_failures":failures,"device_feedback":feedback}
