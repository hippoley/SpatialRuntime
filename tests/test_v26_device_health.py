from spatialruntime.hardware.thingmodel import normalize_profile
from spatialruntime.hardware.health import *

P=normalize_profile({"profile_id":"p","thing_model":"m","properties":{"open_ratio":{"native":"p"}},
                     "online_property":"online","fault_property":"fault","blocking_fault_codes":[9]})

def t(online=True,fault=0,q=.99):
    return {"device_id":"d","sequence":1,"observed_at_ms":1,"quality":q,"health":{"online":online,"fault_code":fault}}

def test_healthy():
    assert not evaluate_device_health(telemetry=t(),profile=P)["blocking"]

def test_offline_blocks():
    try: assert_device_healthy(telemetry=t(online=False),profile=P); assert False
    except DeviceHealthBlocked: pass

def test_blocking_fault_blocks():
    s=evaluate_device_health(telemetry=t(fault=9),profile=P)
    assert s["blocking"] and s["blockers"][0]["kind"]=="blocking_fault"

def test_unknown_fault_warns_not_guesses():
    s=evaluate_device_health(telemetry=t(fault=77),profile=P)
    assert not s["blocking"] and s["warnings"]
