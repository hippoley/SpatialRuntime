from spatialruntime.hardware.gateway import *
from spatialruntime.hardware.contract import build_dispatch_batch, CommandLedger, DeviceOfflineError


def decision():
    return {"schema":"physical_commit_decision_v1.9","source_step":4,"source_revision":9,
            "summary":{"ready_to_dispatch":True},
            "decisions":{"window_01":{"decision":"commit","executed_state":{"open_ratio":0.75},"requested_change":{"open_ratio":0.9}}}}


def binding():
    return {"window_01":{"device_id":"cwds-ca01","gateway_id":"gw-home","thing_model":"window_actuator_v1"}}


def fixture(**kw):
    caps={"cwds-ca01":{"thing_model":"window_actuator_v1","writable_properties":["open_ratio"],
                       "readable_properties":["open_ratio","fault_code"],"supports_command_id":True,
                       "supports_ack":True,"supports_state_feedback":True}}
    f=DeterministicGatewayFixture(capabilities=caps,**kw)
    return f, ThingModelGatewayAdapter(gateway_id="gw-home",discover_transport=f.discover_transport,command_transport=f.command_transport)


def test_capability_and_command_roundtrip():
    f,g=fixture(); cap=g.discover("cwds-ca01")
    assert cap["fingerprint"] and cap["writable_properties"]==["open_ratio"]
    batch=build_dispatch_batch(case_id="case",commit_decision=decision(),device_bindings=binding(),now_ms=100)
    ev=g.send(batch["commands"][0],now_ms=100)
    assert [x["kind"] for x in ev]==["ack","state_feedback"]
    assert ev[1]["state"]["open_ratio"]==0.75
    assert len(f.command_calls)==1


def test_non_writable_property_rejected_before_transport():
    f,g=fixture(); g.discover("cwds-ca01")
    b=build_dispatch_batch(case_id="case",commit_decision=decision(),device_bindings=binding(),now_ms=100)
    b["commands"][0]["target_state"]={"fan_level":2}
    try: g.send(b["commands"][0],now_ms=100); assert False
    except DeviceCapabilityError: pass
    assert not f.command_calls


def test_missing_idempotency_contract_rejected():
    caps={"cwds-ca01":{"writable_properties":["open_ratio"],"readable_properties":["open_ratio"],
                       "supports_command_id":False,"supports_ack":True,"supports_state_feedback":True}}
    f=DeterministicGatewayFixture(capabilities=caps)
    g=ThingModelGatewayAdapter(gateway_id="gw-home",discover_transport=f.discover_transport,command_transport=f.command_transport)
    b=build_dispatch_batch(case_id="case",commit_decision=decision(),device_bindings=binding(),now_ms=100)
    try: g.send(b["commands"][0],now_ms=100); assert False
    except DeviceCapabilityError: pass


def test_offline_and_reject():
    _,g=fixture(offline={"cwds-ca01"})
    b=build_dispatch_batch(case_id="case",commit_decision=decision(),device_bindings=binding(),now_ms=100)
    try: g.send(b["commands"][0],now_ms=100); assert False
    except DeviceOfflineError: pass
    _,g=fixture(reject={"cwds-ca01"})
    ev=g.send(b["commands"][0],now_ms=100)
    assert ev[0]["kind"]=="ack" and ev[0]["accepted"] is False


def test_feedback_can_differ_from_target():
    _,g=fixture(state_overrides={"cwds-ca01":{"open_ratio":0.62,"fault_code":0}})
    b=build_dispatch_batch(case_id="case",commit_decision=decision(),device_bindings=binding(),now_ms=100)
    ev=g.send(b["commands"][0],now_ms=100)
    assert ev[-1]["state"]["open_ratio"]==0.62
