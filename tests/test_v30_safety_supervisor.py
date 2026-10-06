import pytest
from spatialruntime.safety.supervisor import supervise_actions, StaleSafetyContextError

RUNTIME={
 "window_kitchen":{"executed_state":{"open_ratio":0.4}},
 "window_bed":{"executed_state":{"open_ratio":0.2}},
}

def act(changes, step=7, rev=3, kind="policy"):
 return {"source_step":step,"source_revision":rev,"changes":changes,"kind":kind}
def ctx(**kw):
 d={"source_step":7,"source_revision":3,"sensors":{}}
 d.update(kw); return d

def test_rain_blocks_open_but_allows_close():
 c=ctx(sensors={"rain":{"value":"wet","quality":1}})
 r=supervise_actions(source_step=7,source_revision=3,proposed_action=act({"window_kitchen":{"open_ratio":.7}}),runtime_state=RUNTIME,safety_context=c)
 assert r["decisions"]["window_kitchen"]["reason"]=="rain_interlock"
 r2=supervise_actions(source_step=7,source_revision=3,proposed_action=act({"window_kitchen":{"open_ratio":.1}}),runtime_state=RUNTIME,safety_context=c)
 assert r2["changes"]["window_kitchen"]["open_ratio"]==.1

def test_high_wind_blocks_opening():
 c=ctx(sensors={"wind_m_s":{"value":15,"quality":.99}})
 r=supervise_actions(source_step=7,source_revision=3,proposed_action=act({"window_kitchen":{"open_ratio":.8}}),runtime_state=RUNTIME,safety_context=c)
 assert r["decisions"]["window_kitchen"]["reason"]=="high_wind_interlock"

def test_pressure_blocks_any_motion():
 c=ctx(sensors={"abs_pressure_diff_pa":{"value":100,"quality":1}})
 r=supervise_actions(source_step=7,source_revision=3,proposed_action=act({"window_kitchen":{"open_ratio":.1}}),runtime_state=RUNTIME,safety_context=c)
 assert r["decisions"]["window_kitchen"]["reason"]=="pressure_interlock"

def test_child_lock_only_blocks_opening():
 c=ctx(child_lock=True)
 r=supervise_actions(source_step=7,source_revision=3,proposed_action=act({"window_kitchen":{"open_ratio":.8},"window_bed":{"open_ratio":.0}}),runtime_state=RUNTIME,safety_context=c)
 assert "window_kitchen" not in r["changes"]
 assert r["changes"]["window_bed"]["open_ratio"]==0

def test_emergency_close_overrides_policy_and_targets_all_windows():
 c=ctx(emergency_close=True)
 r=supervise_actions(source_step=7,source_revision=3,proposed_action=act({"window_kitchen":{"open_ratio":.9}}),runtime_state=RUNTIME,safety_context=c)
 assert r["changes"]["window_kitchen"]["open_ratio"]==0
 assert r["changes"]["window_bed"]["open_ratio"]==0
 assert r["decisions"]["window_kitchen"]["decision"]=="override_close"

def test_maintenance_lock_beats_normal_policy():
 r=supervise_actions(source_step=7,source_revision=3,proposed_action=act({"window_kitchen":{"open_ratio":.8}}),runtime_state=RUNTIME,safety_context=ctx(maintenance_lock=True))
 assert r["decisions"]["window_kitchen"]["reason"]=="maintenance_lock"

def test_hard_fault_blocks_motion():
 r=supervise_actions(source_step=7,source_revision=3,proposed_action=act({"window_kitchen":{"open_ratio":.8}}),runtime_state=RUNTIME,safety_context=ctx(hard_fault_entities=["window_kitchen"]))
 assert r["decisions"]["window_kitchen"]["reason"]=="hard_fault"

def test_emergency_close_has_priority_over_rain_child_lock_maintenance():
 c=ctx(emergency_close=True,maintenance_lock=True,child_lock=True,sensors={"rain":{"value":"wet","quality":1},"wind_m_s":{"value":30,"quality":1}})
 r=supervise_actions(source_step=7,source_revision=3,proposed_action=act({"window_kitchen":{"open_ratio":.9}}),runtime_state=RUNTIME,safety_context=c)
 assert r["changes"]["window_kitchen"]["open_ratio"]==0
 assert r["events"][0]["rule"]=="emergency_close"

def test_stale_context_rejected():
 with pytest.raises(StaleSafetyContextError):
  supervise_actions(source_step=7,source_revision=3,proposed_action=act({}),runtime_state=RUNTIME,safety_context={"source_step":6,"source_revision":3})
