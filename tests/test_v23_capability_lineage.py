from spatialruntime.hardware.gateway import *
from spatialruntime.hardware.capabilities import CapabilityRegistry, CapabilityDriftError
from spatialruntime.hardware.gateway_guard import ReviewedGateway
from spatialruntime.hardware.contract import build_dispatch_batch


def cap(writable=("open_ratio",), tm="window_v1"):
    return {"thing_model":tm,"writable_properties":list(writable),"readable_properties":["open_ratio"],
            "supports_command_id":True,"supports_ack":True,"supports_state_feedback":True}

def make_gateway(c):
    f=DeterministicGatewayFixture(capabilities={"d1":c})
    return f,ThingModelGatewayAdapter(gateway_id="g1",discover_transport=f.discover_transport,command_transport=f.command_transport)

def command():
    dec={"schema":"physical_commit_decision_v1.9","source_step":1,"source_revision":1,"summary":{"ready_to_dispatch":True},
         "decisions":{"w":{"decision":"commit","executed_state":{"open_ratio":0.5},"requested_change":{"open_ratio":0.5}}}}
    return build_dispatch_batch(case_id="c",commit_decision=dec,device_bindings={"w":{"device_id":"d1","gateway_id":"g1"}},now_ms=0)["commands"][0]

def test_reviewed_capability_allows_command():
    _,g=make_gateway(cap()); reg=CapabilityRegistry(); reg.approve(g.discover("d1"))
    guarded=ReviewedGateway(g,reg); ev=guarded.send(command(),now_ms=0)
    assert ev[-1]["kind"]=="state_feedback"

def test_firmware_or_thing_model_drift_blocks():
    fixture,g=make_gateway(cap()); reg=CapabilityRegistry(); reg.approve(g.discover("d1"))
    fixture.capabilities["d1"]=cap(writable=("position",),tm="window_v2")
    try: ReviewedGateway(g,reg).send(command(),now_ms=0); assert False
    except CapabilityDriftError: pass

def test_explicit_reapproval_advances_revision():
    fixture,g=make_gateway(cap()); reg=CapabilityRegistry(); a=reg.approve(g.discover("d1")); assert a["revision"]==0
    fixture.capabilities["d1"]=cap(writable=("open_ratio","stop"))
    b=reg.approve(g.discover("d1")); assert b["revision"]==1 and b["fingerprint"]!=a["fingerprint"]
