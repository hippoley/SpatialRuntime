from spatialruntime.hardware.thingmodel import *
from spatialruntime.hardware.gateway import ThingModelGatewayAdapter

PROFILE={
    "profile_id":"cwds_ca01_v1",
    "thing_model":"CWDS-CA01",
    "properties":{
        "open_ratio":{"native":"position_pct","codec":"linear","scale":100.0,"offset":0.0,"min":0.0,"max":1.0},
        "fault_code":{"native":"fault_code","codec":"identity"},
    },
    "online_property":"online",
    "fault_property":"fault_code",
    "blocking_fault_codes":[101,102],
}

class Backend:
    def __init__(self): self.writes=[]
    def describe(self,dev):
        return BackendResult(200,{"device_id":dev,"thing_model":"CWDS-CA01","writable_properties":["position_pct"],
                                  "readable_properties":["position_pct","fault_code"],"supports_command_id":True,
                                  "supports_ack":True,"supports_state_feedback":True})
    def write(self,dev,payload,cid):
        self.writes.append((dev,payload,cid))
        return BackendResult(200,{"command_id":cid,"status":"accepted","state":payload})

def command():
    return {"command_id":"c1","gateway_id":"g1","device_id":"d1","source_step":3,"source_revision":7,
            "entity_id":"window_1","target_state":{"open_ratio":0.5}}

def test_binding_and_gateway_roundtrip():
    b=Backend(); binding=ThingModelBackendBinding(gateway_id="g1",profile=PROFILE,describe_device=b.describe,write_properties=b.write)
    gw=ThingModelGatewayAdapter(gateway_id="g1",discover_transport=binding.discover_transport,command_transport=binding.command_transport)
    cap=gw.discover("d1")
    assert cap["writable_properties"]==["open_ratio"]
    events=gw.send(command(),now_ms=1000)
    assert b.writes[0][1]=={"position_pct":50.0}
    assert events[-1]["state"]["open_ratio"]==0.5

def test_missing_binding_rejected():
    p=normalize_profile(PROFILE)
    try: encode_state({"fan_level":2},p); assert False
    except ThingModelCodecError: pass

def test_telemetry_normalization():
    b=Backend(); binding=ThingModelBackendBinding(gateway_id="g1",profile=PROFILE,describe_device=b.describe,write_properties=b.write)
    e=binding.normalize_telemetry({"device_id":"d1","sequence":9,"observed_at_ms":1234,
                                   "state":{"position_pct":75.0,"online":True,"fault_code":0},"quality":0.99},
                                  source_step=3,source_revision=7)
    assert e["state"]["open_ratio"]==0.75
    assert e["health"]=={"online":True,"fault_code":0}
