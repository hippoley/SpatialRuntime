import json
import sys

import pytest

from spatialruntime.runtime.replay import validate_bundle
from spatialruntime.runtime.scenario_spec import ScenarioSpecError, run_scenario_spec
from spatialruntime.solver.contract import (
    SolverContractError,
    build_solver_request,
    normalize_solver_feedback,
)
from spatialruntime.solver.fixture import DeterministicSolverAdapter
from spatialruntime.solver.process import JsonProcessSolverAdapter, SolverProcessError


def request():
    return build_solver_request(
        case_id="solver-case",
        source_step=2,
        source_revision=3,
        world_state={"window": {"executed_state": {"open_ratio": 0.4}}},
        model={"zones": ["kitchen"]},
        boundary_conditions={"outdoor_temperature_c": 20},
    )


def test_fixture_solver_binds_provenance_to_request():
    adapter = DeterministicSolverAdapter(
        zones={"kitchen": {"pressure_pa": 1.2, "ach_1_h": 0.7}},
        flow_paths={"window": {"flow_m3_s": 0.03}},
    )
    feedback = adapter.solve(request())
    assert feedback["schema"] == "solver_feedback_v0.6"
    assert feedback["source_step"] == 2
    assert feedback["source_revision"] == 3
    assert feedback["zones"]["kitchen"]["pressure_pa"] == 1.2
    assert feedback["solver_provenance"]["adapter_id"] == "deterministic-fixture"
    assert len(feedback["solver_provenance"]["request_hash"]) == 64
    assert len(feedback["solver_provenance"]["result_hash"]) == 64


def test_normalizer_rejects_stale_solver_response():
    with pytest.raises(SolverContractError, match="source_step mismatch"):
        normalize_solver_feedback(
            {"source_step": 1, "zones": {}, "flow_paths": {}},
            request=request(),
            adapter_id="x",
            adapter_fingerprint="f",
        )


def test_process_solver_uses_explicit_json_stdin_stdout_contract():
    script = (
        "import json,sys;"
        "r=json.load(sys.stdin);"
        "json.dump({'case_id':r['case_id'],'source_step':r['source_step'],"
        "'source_revision':r['source_revision'],"
        "'zones':{'kitchen':{'pressure_pa':2.5}},'flow_paths':{}},sys.stdout)"
    )
    adapter = JsonProcessSolverAdapter([sys.executable, "-c", script], timeout_s=5)
    feedback = adapter.solve(request())
    assert feedback["zones"]["kitchen"]["pressure_pa"] == 2.5
    assert feedback["solver_provenance"]["adapter_id"] == "json-process"


def test_process_solver_rejects_non_json_stdout():
    adapter = JsonProcessSolverAdapter(
        [sys.executable, "-c", "print('not-json')"],
        timeout_s=5,
    )
    with pytest.raises(SolverProcessError, match="not valid JSON"):
        adapter.solve(request())


def scenario_with_solver():
    return {
        "schema": "runtime_scenario_spec_v0.6",
        "name": "solver-backed",
        "case_id": "solver-backed-case",
        "initial_runtime_state": {
            "window": {"executed_state": {"open_ratio": 0.5}},
        },
        "entity_catalog": {
            "window": {"kind": "window", "exterior": True, "room": "kitchen"},
        },
        "safety_graph": {
            "schema": "whole_home_safety_graph_v3.3",
            "rules": [],
        },
        "solver": {
            "mode": "fixture",
            "zones": {
                "kitchen": {
                    "pressure_pa": 0.5,
                    "temperature_c": 24,
                    "ach_1_h": 0.8,
                }
            },
            "flow_paths": {
                "window": {"flow_m3_s": 0.02}
            },
        },
        "steps": [
            {
                "policy_action": {"changes": {"window": {"open_ratio": 0.6}}},
                "safety_context": {},
            },
            {
                "policy_action": {"changes": {"window": {"open_ratio": 0.7}}},
                "safety_context": {},
            },
        ],
    }


def test_scenario_spec_can_use_solver_adapter_instead_of_embedded_feedback():
    bundle = run_scenario_spec(scenario_with_solver())
    assert validate_bundle(bundle).trace_count == 2
    first = bundle["traces"][0]
    second = bundle["traces"][1]
    assert first["stages"]["solver"]["schema"] == "solver_feedback_v0.6"
    assert first["stages"]["solver"]["source_step"] == 0
    assert second["stages"]["solver"]["source_step"] == 1
    assert first["stages"]["solver"]["solver_provenance"]["request_hash"] != second["stages"]["solver"]["solver_provenance"]["request_hash"]
    assert bundle["metadata"]["solver_mode"] == "fixture"


def test_scenario_spec_refuses_arbitrary_process_solver_config():
    spec = scenario_with_solver()
    spec["solver"] = {"mode": "process", "argv": ["some-solver"]}
    with pytest.raises(ScenarioSpecError, match="explicitly by application code"):
        run_scenario_spec(spec)


def test_solver_and_embedded_feedback_are_mutually_exclusive():
    spec = scenario_with_solver()
    spec["steps"][0]["solver_feedback"] = {"zones": {}, "flow_paths": {}}
    with pytest.raises(ScenarioSpecError, match="cannot provide solver_feedback"):
        run_scenario_spec(spec)


def test_fixture_fingerprint_changes_when_physical_values_change():
    a = DeterministicSolverAdapter(
        zones={"kitchen": {"pressure_pa": 0.5}},
        flow_paths={"window": {"flow_m3_s": 0.02}},
    )
    b = DeterministicSolverAdapter(
        zones={"kitchen": {"pressure_pa": 5.0}},
        flow_paths={"window": {"flow_m3_s": 0.02}},
    )
    assert a.fingerprint != b.fingerprint
