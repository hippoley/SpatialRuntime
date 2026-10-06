from __future__ import annotations
from typing import Any
from spatialruntime.hardware.contract import CommandLedger, build_dispatch_batch


def dispatch_once(*, case_id: str, commit_decision: dict[str, Any], device_bindings: dict[str,dict[str,Any]],
                  gateway: Any, ledger: CommandLedger, now_ms: int) -> dict[str, Any]:
    batch = build_dispatch_batch(case_id=case_id, commit_decision=commit_decision,
                                 device_bindings=device_bindings, now_ms=now_ms)
    ledger.register_batch(batch)
    events=[]
    for cmd in batch["commands"]:
        snap=ledger.mark_dispatched(cmd["command_id"],now_ms=now_ms)
        if snap["status"] in {"failed", "confirmed", "cancelled"}:
            continue
        for event in gateway.send(cmd,now_ms=now_ms):
            ledger.ingest_event(event, expected_step=batch["source_step"], expected_revision=batch["source_revision"])
            events.append(event)
    feedback=ledger.build_device_feedback(case_id=case_id,source_step=batch["source_step"],source_revision=batch["source_revision"])
    return {"batch":batch,"events":events,"device_feedback":feedback}
