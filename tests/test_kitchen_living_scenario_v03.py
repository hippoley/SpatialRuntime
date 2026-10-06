from spatialruntime.scenarios import run_kitchen_living_demo
from spatialruntime.runtime.session import trace_hash


def test_kitchen_living_two_step_closed_loop():
    result = run_kitchen_living_demo()
    cooking, rain = result["traces"]

    assert cooking["status"] == "completed"
    assert cooking["stages"]["safety"]["safety_forced_entities"] == [
        "hood_kitchen",
        "window_kitchen",
    ]
    assert cooking["next_runtime_state"]["hood_kitchen"]["executed_state"]["fan_level"] == 1
    assert cooking["next_runtime_state"]["window_kitchen"]["executed_state"]["open_ratio"] == 0.2

    assert rain["status"] == "completed"
    assert rain["stages"]["safety"]["safety_forced_entities"] == ["window_kitchen"]
    assert rain["next_runtime_state"]["window_kitchen"]["executed_state"]["open_ratio"] == 0.0

    assert result["final_step"] == 2
    assert result["final_revision"] == 2
    assert result["final_runtime_state"]["window_kitchen"]["state_source"] == "device_feedback"
    assert result["final_runtime_state"]["hood_kitchen"]["executed_state"]["fan_level"] == 1

    assert cooking["trace_hash"] == trace_hash(cooking)
    assert rain["trace_hash"] == trace_hash(rain)
