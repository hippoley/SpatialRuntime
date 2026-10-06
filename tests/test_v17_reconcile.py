from spatialruntime.runtime.state_reconciler import reconcile, StaleObservationError

solver = {"source_step":4,"source_revision":9,
          "zones":{"zone::room_kitchen":{"pressure_pa":2.0,"temperature_c":24.0,"ach_1_h":1.4,"airflow_in_m3_s":0.08,"airflow_out_m3_s":0.09}},
          "flow_paths":{"flow::window_kitchen_01":{"flow_m3_s":0.055,"pressure_difference_pa":2.0}}}
runtime = {"window_kitchen_01":{"executed_state":{"open_ratio":0.5}},"hood_kitchen_01":{"executed_state":{"fan_level":2}}}
device = {"source_step":4,"source_revision":9,"devices":{"window_kitchen_01":{"quality":0.98,"state":{"open_ratio":0.5}},"hood_kitchen_01":{"quality":0.99,"state":{"fan_level":2}}}}
sensor = {"source_step":4,"source_revision":9,"zones":{"zone::room_kitchen":{"quality":0.96,"measurements":{"pressure_pa":2.4,"temperature_c":24.3}}},"flow_paths":{"flow::window_kitchen_01":{"quality":0.9,"measurements":{"flow_m3_s":0.061}}}}
r = reconcile(case_id="kitchen",step=4,revision=9,solver_feedback=solver,runtime_state=runtime,device_feedback=device,sensor_observation=sensor)
assert r["summary"]["safe_for_control"] is True
assert r["zones"]["zone::room_kitchen"]["state"]["pressure_pa"] == 2.4
assert r["zones"]["zone::room_kitchen"]["field_sources"]["pressure_pa"] == "sensor"
assert r["devices"]["window_kitchen_01"]["source"] == "device_feedback"

# High-quality disagreement must block control.
bad_sensor = {"source_step":4,"source_revision":9,"zones":{"zone::room_kitchen":{"quality":0.99,"measurements":{"pressure_pa":8.0}}}}
r2 = reconcile(case_id="kitchen",step=4,revision=9,solver_feedback=solver,runtime_state=runtime,device_feedback=device,sensor_observation=bad_sensor)
assert r2["summary"]["safe_for_control"] is False
assert any(d["kind"]=="model_sensor_residual" and d["severity"]=="hard" for d in r2["disagreements"])

# Device says actuator did not reach command: device observation wins and blocks control.
bad_device = {"source_step":4,"source_revision":9,"devices":{"window_kitchen_01":{"quality":0.99,"state":{"open_ratio":0.2}}}}
r3 = reconcile(case_id="kitchen",step=4,revision=9,solver_feedback=solver,runtime_state=runtime,device_feedback=bad_device)
assert r3["devices"]["window_kitchen_01"]["state"]["open_ratio"] == 0.2
assert r3["summary"]["safe_for_control"] is False

try:
    reconcile(case_id="kitchen",step=4,revision=9,solver_feedback=solver,runtime_state=runtime,
              sensor_observation={"source_step":3,"source_revision":9,"zones":{}})
    raise AssertionError("stale sensor should fail")
except StaleObservationError:
    pass
print("PASS v1.7 closed-loop reconciliation")
