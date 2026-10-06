from spatialruntime.runtime.commit_gate import gate_action, StalePolicyActionError

runtime={"window_kitchen_01":{"executed_state":{"open_ratio":0.5}},"hood_kitchen_01":{"executed_state":{"fan_level":2}}}
safe_obs={"schema":"windowpilot_observation_v1.8","step":5,"revision":10,"quality":{"safe_for_control":True}}
action={"source_step":5,"source_revision":10,"changes":{"window_kitchen_01":{"open_ratio":0.9},"hood_kitchen_01":{"fan_level":3}}}
d=gate_action(observation=safe_obs,proposed_action=action,runtime_state=runtime,expected_step=5,expected_revision=10)
assert d["decisions"]["window_kitchen_01"]["decision"]=="commit_clamped"
assert d["decisions"]["window_kitchen_01"]["executed_state"]["open_ratio"]==0.75
assert d["decisions"]["hood_kitchen_01"]["decision"]=="commit"
assert d["summary"]["ready_to_dispatch"] is True

unsafe={"schema":"windowpilot_observation_v1.8","step":5,"revision":10,"quality":{"safe_for_control":False}}
h=gate_action(observation=unsafe,proposed_action=action,runtime_state=runtime,expected_step=5,expected_revision=10)
assert h["summary"]["committed"]==0 and h["summary"]["held"]==2
assert h["decisions"]["window_kitchen_01"]["executed_state"]["open_ratio"]==0.5
assert h["summary"]["ready_to_dispatch"] is False

try:
    gate_action(observation=safe_obs,proposed_action={"source_step":4,"source_revision":10,"changes":{}},runtime_state=runtime,expected_step=5,expected_revision=10)
    raise AssertionError("stale action should fail")
except StalePolicyActionError: pass
print("PASS v1.9 physical commit gate")
