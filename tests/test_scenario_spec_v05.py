import json

import pytest

from spatialruntime.cli import main
from spatialruntime.runtime.replay import validate_bundle
from spatialruntime.runtime.scenario_spec import (
    ScenarioSpecError,
    run_scenario_spec,
)


def base_spec():
    return {
        "schema": "runtime_scenario_spec_v0.5",
        "name": "spec-test",
        "case_id": "spec-case",
        "initial_runtime_state": {
            "window": {"executed_state": {"open_ratio": 0.5}},
        },
        "entity_catalog": {
            "window": {"kind": "window", "exterior": True, "room": "kitchen"},
        },
        "safety_graph": {
            "schema": "whole_home_safety_graph_v3.3",
            "rules": [{
                "id": "rain",
                "priority": 100,
                "when": {"path": "sensors.rain.value", "op": "eq", "value": "wet"},
                "effects": [{
                    "kind": "emit_change",
                    "selector": {"ids": ["window"]},
                    "changes": {"open_ratio": 0.0},
                }],
            }],
        },
        "hardware": {
            "mode": "fixture",
            "device_bindings": {
                "window": {"device_id": "window-01"},
            },
        },
        "steps": [
            {
                "solver_feedback": {"zones": {}, "flow_paths": {}},
                "safety_context": {"sensors": {"rain": {"value": "dry"}}},
                "policy_action": {"changes": {"window": {"open_ratio": 0.7}}},
                "now_ms": 1000,
            },
            {
                "solver_feedback": {"zones": {}, "flow_paths": {}},
                "safety_context": {"sensors": {"rain": {"value": "wet"}}},
                "now_ms": 2000,
            },
        ],
    }


def test_scenario_spec_runs_and_produces_replayable_bundle():
    bundle = run_scenario_spec(base_spec())
    report = validate_bundle(bundle)
    assert report.valid is True
    assert report.trace_count == 2
    assert bundle["metadata"]["executed_steps"] == 2
    assert bundle["metadata"]["stop_reason"] is None
    assert bundle["traces"][0]["next_runtime_state"]["window"]["executed_state"]["open_ratio"] == 0.7
    assert bundle["traces"][1]["next_runtime_state"]["window"]["executed_state"]["open_ratio"] == 0.0


def test_scenario_spec_rejects_stale_explicit_envelope():
    spec = base_spec()
    spec["steps"][1]["solver_feedback"]["source_step"] = 0
    with pytest.raises(ScenarioSpecError, match="stale source_step"):
        run_scenario_spec(spec)


def test_scenario_spec_refuses_implicit_real_hardware_mode():
    spec = base_spec()
    spec["hardware"]["mode"] = "http"
    with pytest.raises(ScenarioSpecError, match="real hardware requires"):
        run_scenario_spec(spec)


def test_cli_run_spec_writes_valid_bundle(tmp_path, capsys):
    spec_path = tmp_path / "scenario.json"
    out_path = tmp_path / "episode.json"
    spec_path.write_text(json.dumps(base_spec()), encoding="utf-8")

    assert main(["run", str(spec_path), "-o", str(out_path)]) == 0
    capsys.readouterr()
    bundle = json.loads(out_path.read_text(encoding="utf-8"))
    assert validate_bundle(bundle).trace_count == 2


def test_blocked_scenario_stops_without_advancing_further_steps():
    spec = base_spec()
    spec["steps"][0]["device_feedback"] = {
        "devices": {"window": {"quality": 1.0, "state": {"open_ratio": 0.1}}},
    }
    bundle = run_scenario_spec(spec)
    assert len(bundle["traces"]) == 1
    assert bundle["traces"][0]["status"] == "observation_blocked"
    assert bundle["metadata"]["stop_reason"]["blocked_at"] == "observation"
    assert bundle["metadata"]["final_step"] == 0
