import json
import copy

import pytest

from spatialruntime.cli import main
from spatialruntime.runtime.preflight import (
    PreflightError,
    build_preflight_plan,
    plan_hash,
    verify_preflight_plan,
)
from spatialruntime.runtime.replay import validate_bundle


def scenario():
    return {
        "schema": "runtime_scenario_spec_v0.6",
        "name": "preflight-test",
        "case_id": "preflight-case",
        "initial_runtime_state": {
            "window": {"executed_state": {"open_ratio": 0.5}},
        },
        "entity_catalog": {
            "window": {"kind": "window", "exterior": True, "room": "kitchen"},
        },
        "solver": {
            "mode": "fixture",
            "zones": {"kitchen": {"pressure_pa": 0.5}},
            "flow_paths": {"window": {"flow_m3_s": 0.02}},
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
                "safety_context": {"sensors": {"rain": {"value": "dry"}}},
                "policy_action": {"changes": {"window": {"open_ratio": 0.6}}},
                "now_ms": 1000,
            },
            {
                "safety_context": {"sensors": {"rain": {"value": "wet"}}},
                "now_ms": 2000,
            },
        ],
    }


def test_preflight_plan_verifies_unchanged_scenario():
    spec = scenario()
    plan = build_preflight_plan(spec)
    report = verify_preflight_plan(plan, spec)
    assert report["valid"] is True
    assert report["drift"] == []
    assert report["plan_hash"] == plan["plan_hash"]
    assert report["manifest_hash"] == plan["execution_manifest"]["manifest_hash"]


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda s: s["initial_runtime_state"]["window"]["executed_state"].update({"open_ratio": 0.1}),
            "initial_runtime_state",
        ),
        (
            lambda s: s["safety_graph"]["rules"][0].update({"priority": 99}),
            "safety_graph",
        ),
        (
            lambda s: s["solver"]["zones"]["kitchen"].update({"pressure_pa": 5.0}),
            "solver.adapter_fingerprint",
        ),
        (
            lambda s: s["hardware"]["device_bindings"]["window"].update({"device_id": "window-02"}),
            "hardware.config",
        ),
    ],
)
def test_preflight_rejects_configuration_drift(mutator, expected):
    approved = scenario()
    plan = build_preflight_plan(approved)
    changed = copy.deepcopy(approved)
    mutator(changed)
    with pytest.raises(PreflightError) as exc:
        verify_preflight_plan(plan, changed)
    assert expected in str(exc.value)


def test_preflight_plan_hash_detects_plan_tampering():
    spec = scenario()
    plan = build_preflight_plan(spec)
    plan["requested_steps"] = 999
    with pytest.raises(PreflightError, match="plan hash mismatch"):
        verify_preflight_plan(plan, spec)


def test_cli_plan_then_run_with_plan(tmp_path, capsys):
    spec_path = tmp_path / "scenario.json"
    plan_path = tmp_path / "execution.plan.json"
    episode_path = tmp_path / "episode.json"
    spec_path.write_text(json.dumps(scenario()), encoding="utf-8")

    assert main(["plan", str(spec_path), "-o", str(plan_path)]) == 0
    plan_stdout = json.loads(capsys.readouterr().out)
    assert plan_stdout["valid"] is True
    assert plan_path.exists()

    assert main([
        "run",
        str(spec_path),
        "--plan",
        str(plan_path),
        "-o",
        str(episode_path),
    ]) == 0
    run_stdout = json.loads(capsys.readouterr().out)
    assert run_stdout["valid"] is True

    bundle = json.loads(episode_path.read_text(encoding="utf-8"))
    report = validate_bundle(bundle)
    assert report.valid is True
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert bundle["metadata"]["preflight_plan_hash"] == plan["plan_hash"]
    assert bundle["metadata"]["preflight_manifest_hash"] == plan["execution_manifest"]["manifest_hash"]


def test_cli_run_refuses_drift_before_execution(tmp_path, capsys):
    original = scenario()
    spec_path = tmp_path / "scenario.json"
    plan_path = tmp_path / "execution.plan.json"
    episode_path = tmp_path / "episode.json"

    spec_path.write_text(json.dumps(original), encoding="utf-8")
    assert main(["plan", str(spec_path), "-o", str(plan_path)]) == 0
    capsys.readouterr()

    changed = copy.deepcopy(original)
    changed["solver"]["zones"]["kitchen"]["pressure_pa"] = 7.0
    spec_path.write_text(json.dumps(changed), encoding="utf-8")

    assert main([
        "run",
        str(spec_path),
        "--plan",
        str(plan_path),
        "-o",
        str(episode_path),
    ]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["valid"] is False
    assert "preflight drift detected" in error["error"]
    assert not episode_path.exists()
