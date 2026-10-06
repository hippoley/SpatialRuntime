from spatialruntime.runtime.state_reconciler import reconcile
from spatialruntime.runtime.observation import build_observation, ObservationBuildError

solver={"source_step":2,"source_revision":3,"zones":{"zone::room_kitchen":{"pressure_pa":1.0,"temperature_c":23.0,"ach_1_h":1.2}},"flow_paths":{}}
runtime={"window_kitchen_01":{"executed_state":{"open_ratio":0.4}}}
sensor={"source_step":2,"source_revision":3,"zones":{"zone::room_kitchen":{"quality":0.95,"measurements":{"pressure_pa":1.2}}}}
r=reconcile(case_id="k",step=2,revision=3,solver_feedback=solver,runtime_state=runtime,sensor_observation=sensor)
o=build_observation(r)
assert o["schema"]=="windowpilot_observation_v1.8"
assert o["zones"]["zone::room_kitchen"]["pressure_pa"]==1.2
assert o["quality"]["safe_for_control"] is True

bad_sensor={"source_step":2,"source_revision":3,"zones":{"zone::room_kitchen":{"quality":0.99,"measurements":{"pressure_pa":9.0}}}}
br=reconcile(case_id="k",step=2,revision=3,solver_feedback=solver,runtime_state=runtime,sensor_observation=bad_sensor)
try:
    build_observation(br)
    raise AssertionError("unsafe observation should be blocked")
except ObservationBuildError:
    pass
assert build_observation(br, allow_degraded=True)["quality"]["degraded"] is True
print("PASS v1.8 WindowPilot observation gate")
