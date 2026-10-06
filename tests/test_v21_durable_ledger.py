import json, tempfile
from pathlib import Path
from spatialruntime.hardware.contract import build_dispatch_batch, MockGateway, EVENT_SCHEMA
from spatialruntime.hardware.ledger import DurableCommandLedger, JournalIntegrityError

SAFE={"schema":"physical_commit_decision_v1.9","source_step":7,"source_revision":12,
      "summary":{"ready_to_dispatch":True},"decisions":{"window_kitchen_01":{"decision":"commit","executed_state":{"open_ratio":0.6},"requested_change":{"open_ratio":0.6}}}}
BIND={"window_kitchen_01":{"device_id":"CWDS-CA01","gateway_id":"gw-home"}}

with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"commands.jsonl"
    batch=build_dispatch_batch(case_id="k",commit_decision=SAFE,device_bindings=BIND,now_ms=1000)
    cmd=batch["commands"][0]
    l=DurableCommandLedger(p); l.register_batch(batch); l.mark_dispatched(cmd["command_id"],now_ms=1000)
    ack={"schema":EVENT_SCHEMA,"command_id":cmd["command_id"],"source_step":7,"source_revision":12,"entity_id":"window_kitchen_01","device_id":"CWDS-CA01","kind":"ack","accepted":True,"event_at_ms":1010}
    l.ingest_event(ack,expected_step=7,expected_revision=12)
    assert l.snapshot(cmd["command_id"])["status"]=="acked"
    assert l.verify_journal()["entries"]==3

    # process restart restores ACK and does not forget attempt count
    l2=DurableCommandLedger(p)
    assert l2.snapshot(cmd["command_id"])["status"]=="acked"
    assert l2.snapshot(cmd["command_id"])["attempts"]==1
    feedback={"schema":EVENT_SCHEMA,"command_id":cmd["command_id"],"source_step":7,"source_revision":12,"entity_id":"window_kitchen_01","device_id":"CWDS-CA01","kind":"state_feedback","state":{"open_ratio":0.6},"event_at_ms":1050}
    l2.ingest_event(feedback,expected_step=7,expected_revision=12)
    l3=DurableCommandLedger(p)
    assert l3.snapshot(cmd["command_id"])["status"]=="confirmed"
    assert l3.build_device_feedback(case_id="k",source_step=7,source_revision=12)["complete"] is True

    # exact batch replay across restart remains idempotent (no extra register entry)
    n=l3.verify_journal()["entries"]; l3.register_batch(build_dispatch_batch(case_id="k",commit_decision=SAFE,device_bindings=BIND,now_ms=5000))
    assert l3.verify_journal()["entries"]==n

    # any journal tamper is rejected on next recovery
    lines=p.read_text().splitlines(); e=json.loads(lines[0]); e["payload"]["commands"][0]["target_state"]["open_ratio"]=0.1; lines[0]=json.dumps(e,separators=(",",":")); p.write_text("\n".join(lines)+"\n")
    try:
        DurableCommandLedger(p); raise AssertionError("tamper must be rejected")
    except JournalIntegrityError: pass

print("PASS v2.1 durable command ledger + crash recovery + tamper detection")
