from spatialruntime.safety.recovery import *

CAP={"writable_properties":["open_ratio"],"actions":["stop"]}
CMD={"command_id":"cmd1","entity_id":"window_1","device_id":"d1","target_state":{"open_ratio":0.8}}

def tel(pos=.4,fault=101):
    return {"device_id":"d1","state":{"open_ratio":pos},"health":{"online":True,"fault_code":fault}}

def conv(ok=False): return {"converged":ok}

def machine(max_attempts=1):
    return RecoveryStateMachine(entity_id="window_1",device_id="d1",policy={
        "obstruction_fault_codes":[101],"max_recovery_attempts":max_attempts,"release_delta":.1})

def test_obstruction_generates_stop_then_bounded_reverse():
    m=machine(); r=m.observe(source_step=3,source_revision=7,command=CMD,telemetry=tel(.4,101),convergence=conv(False),capability=CAP)
    assert r["state"]=="release_pending" and len(r["actions"])==2
    assert r["actions"][0]["kind"]=="stop"
    assert abs(r["actions"][1]["target_state"]["open_ratio"]-.3)<1e-9
    assert all(a["requires_commit_gate"] for a in r["actions"])

def test_release_clear_allows_single_retry_and_success():
    m=machine(); m.observe(source_step=3,source_revision=7,command=CMD,telemetry=tel(.4,101),convergence=conv(False),capability=CAP)
    r=m.confirm_release(source_step=3,source_revision=7,telemetry=tel(.3,0),capability=CAP)
    assert r["state"]=="retry_pending" and r["actions"][0]["target_state"]["open_ratio"]==.8
    r2=m.confirm_retry(source_step=3,source_revision=7,telemetry=tel(.8,0),convergence=conv(True))
    assert r2["state"]=="nominal" and m.recovery_attempts==0

def test_persistent_fault_latches_manual_service():
    m=machine(); m.observe(source_step=3,source_revision=7,command=CMD,telemetry=tel(.4,101),convergence=conv(False),capability=CAP)
    r=m.confirm_release(source_step=3,source_revision=7,telemetry=tel(.3,101),capability=CAP)
    assert r["state"]=="manual_service_required" and "fault_persists_after_release" in r["blockers"]

def test_unknown_fault_never_auto_moves():
    m=machine(); r=m.observe(source_step=3,source_revision=7,command=CMD,telemetry=tel(.4,777),convergence=conv(False),capability=CAP)
    assert r["state"]=="manual_service_required" and not r["actions"]

def test_nonconvergence_without_fault_holds_for_diagnosis():
    m=machine(); r=m.observe(source_step=3,source_revision=7,command=CMD,telemetry=tel(.4,0),convergence=conv(False),capability=CAP)
    assert r["state"]=="hold_for_diagnosis" and not r["actions"]

def test_missing_stop_capability_blocks_automatic_recovery():
    m=machine(); r=m.observe(source_step=3,source_revision=7,command=CMD,telemetry=tel(.4,101),convergence=conv(False),capability={"writable_properties":["open_ratio"]})
    assert r["state"]=="manual_service_required" and "stop_capability_missing" in r["blockers"]
