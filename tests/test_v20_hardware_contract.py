from spatialruntime.hardware.contract import *
from spatialruntime.hardware.runtime import dispatch_once

SAFE={"schema":"physical_commit_decision_v1.9","source_step":5,"source_revision":10,
      "summary":{"ready_to_dispatch":True},"decisions":{
       "window_kitchen_01":{"decision":"commit","executed_state":{"open_ratio":0.75},"requested_change":{"open_ratio":0.9}},
       "hood_kitchen_01":{"decision":"commit","executed_state":{"fan_level":3},"requested_change":{"fan_level":3}}}}
BIND={"window_kitchen_01":{"device_id":"CWDS-CA01","gateway_id":"gw-home","thing_model":"window_actuator"},
      "hood_kitchen_01":{"device_id":"hood-01","gateway_id":"gw-home","thing_model":"range_hood"}}

# deterministic id + end-to-end ACK/feedback
ledger=CommandLedger(); gw=MockGateway()
r=dispatch_once(case_id="kitchen",commit_decision=SAFE,device_bindings=BIND,gateway=gw,ledger=ledger,now_ms=1000)
assert r["device_feedback"]["complete"] is True
assert r["device_feedback"]["devices"]["window_kitchen_01"]["state"]["open_ratio"]==0.75
cmd=r["batch"]["commands"][0]
assert cmd["command_id"]==deterministic_command_id(case_id="kitchen",source_step=5,source_revision=10,entity_id=cmd["entity_id"],target_state=cmd["target_state"])

# exact replay is idempotent: same command ids, no conflict
r2=dispatch_once(case_id="kitchen",commit_decision=SAFE,device_bindings=BIND,gateway=gw,ledger=ledger,now_ms=1100)
assert [c["command_id"] for c in r2["batch"]["commands"]]==[c["command_id"] for c in r["batch"]["commands"]]
assert all(ledger.records[c["command_id"]].attempts==1 for c in r["batch"]["commands"])

# stale hardware event is rejected
bad={"schema":EVENT_SCHEMA,"command_id":cmd["command_id"],"source_step":4,"source_revision":10,
     "entity_id":cmd["entity_id"],"device_id":cmd["device_id"],"kind":"ack","accepted":True,"event_at_ms":1200}
try:
    ledger.ingest_event(bad,expected_step=5,expected_revision=10); raise AssertionError("expected stale event rejection")
except StaleHardwareEventError: pass

# retry path when no ACK arrives
batch=build_dispatch_batch(case_id="kitchen",commit_decision=SAFE,device_bindings=BIND,now_ms=2000,ack_timeout_ms=100,max_attempts=2)
l2=CommandLedger(); l2.register_batch(batch); cid=batch["commands"][0]["command_id"]; l2.mark_dispatched(cid,now_ms=2000)
assert l2.due_retries(now_ms=2100)==[cid]
l2.mark_dispatched(cid,now_ms=2100)
assert l2.due_retries(now_ms=2200)==[] and l2.snapshot(cid)["status"]=="failed"

# offline device fail-closed
l3=CommandLedger(); off=MockGateway(offline_devices={"CWDS-CA01"})
r3=dispatch_once(case_id="kitchen",commit_decision=SAFE,device_bindings=BIND,gateway=off,ledger=l3,now_ms=3000)
assert r3["device_feedback"]["complete"] is False
w=[x for x in r3["device_feedback"]["incomplete"] if x["entity_id"]=="window_kitchen_01"][0]
assert w["status"]=="failed" and w["error"]=="device_offline"
print("PASS v2.0 hardware-in-the-loop contract")
