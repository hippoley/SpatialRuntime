import pytest

from spatialruntime.hardware.contract import CommandLedger
from spatialruntime.hardware.gateway import (
    DeterministicGatewayFixture,
    ThingModelGatewayAdapter,
)
from spatialruntime.hardware.ledger import DurableCommandLedger
from spatialruntime.runtime.application import (
    RuntimeApplicationError,
    run_application_spec,
)
from spatialruntime.runtime.replay import validate_bundle
from spatialruntime.solver.fixture import DeterministicSolverAdapter


def app_spec():
    return {
        "schema": "runtime_scenario_spec_v0.6",
        "name": "explicit-app-test",
        "case_id": "explicit-app-case",
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
        "steps": [
            {
                "solver_model": {},
                "boundary_conditions": {},
                "safety_context": {"sensors": {"rain": {"value": "dry"}}},
                "policy_action": {"changes": {"window": {"open_ratio": 0.7}}},
                "now_ms": 1000,
            }
        ],
    }


def injected_gateway():
    fixture = DeterministicGatewayFixture(
        capabilities={
            "window-01": {
                "thing_model": "window_actuator_v1",
                "writable_properties": ["open_ratio"],
                "readable_properties": ["open_ratio"],
                "supports_command_id": True,
                "supports_ack": True,
                "supports_state_feedback": True,
            }
        }
    )
    gateway = ThingModelGatewayAdapter(
        gateway_id="gw-test",
        discover_transport=fixture.discover_transport,
        command_transport=fixture.command_transport,
    )
    return fixture, gateway


def test_explicit_application_injects_solver_and_gateway_into_same_closed_loop():
    fixture, gateway = injected_gateway()
    solver = DeterministicSolverAdapter(zones={}, flow_paths={})
    ledger = CommandLedger()

    bundle = run_application_spec(
        app_spec(),
        solver_adapter=solver,
        gateway=gateway,
        command_ledger=ledger,
        device_bindings={
            "window": {
                "device_id": "window-01",
                "gateway_id": "gw-test",
                "thing_model": "window_actuator_v1",
            }
        },
        hardware_descriptor={
            "adapter_id": "thing-model-gateway-test",
            "gateway_id": "gw-test",
        },
    )

    report = validate_bundle(bundle)
    assert report.valid is True
    assert bundle["metadata"]["application_assembly"] == "explicit_dependencies_v0.1"
    assert bundle["metadata"]["solver_mode"] == "injected_adapter"
    assert bundle["metadata"]["hardware_mode"] == "injected_adapter"
    assert bundle["execution_manifest"]["solver"]["adapter_id"] == solver.adapter_id
    assert bundle["traces"][0]["status"] == "completed"
    assert bundle["traces"][0]["next_runtime_state"]["window"]["state_source"] == "device_feedback"
    assert bundle["traces"][0]["next_runtime_state"]["window"]["executed_state"]["open_ratio"] == 0.7
    assert len(fixture.command_calls) == 1


def test_explicit_application_accepts_restart_safe_durable_ledger(tmp_path):
    _, gateway = injected_gateway()
    solver = DeterministicSolverAdapter(zones={}, flow_paths={})
    journal = tmp_path / "hardware.jsonl"
    ledger = DurableCommandLedger(journal)

    bundle = run_application_spec(
        app_spec(),
        solver_adapter=solver,
        gateway=gateway,
        command_ledger=ledger,
        device_bindings={
            "window": {
                "device_id": "window-01",
                "gateway_id": "gw-test",
                "thing_model": "window_actuator_v1",
            }
        },
        hardware_descriptor={
            "adapter_id": "thing-model-gateway-test",
            "gateway_id": "gw-test",
        },
    )
    assert validate_bundle(bundle).valid is True

    recovered = DurableCommandLedger(journal)
    verification = recovered.verify_journal()
    assert verification["valid"] is True
    assert verification["entries"] > 0
    assert len(recovered.records) == 1
    only = next(iter(recovered.records.values()))
    assert only.status == "confirmed"


def test_explicit_application_keeps_executable_config_out_of_scenario_json():
    solver = DeterministicSolverAdapter(zones={}, flow_paths={})

    spec = app_spec()
    spec["solver"] = {"mode": "fixture", "zones": {}, "flow_paths": {}}
    with pytest.raises(RuntimeApplicationError, match="forbids scenario.solver"):
        run_application_spec(spec, solver_adapter=solver)

    spec = app_spec()
    spec["hardware"] = {
        "mode": "fixture",
        "device_bindings": {"window": {"device_id": "window-01"}},
    }
    with pytest.raises(RuntimeApplicationError, match="forbids scenario.hardware"):
        run_application_spec(spec, solver_adapter=solver)


def test_explicit_application_rejects_partial_hardware_dependency_injection():
    solver = DeterministicSolverAdapter(zones={}, flow_paths={})
    _, gateway = injected_gateway()

    with pytest.raises(RuntimeApplicationError, match="must be supplied together"):
        run_application_spec(
            app_spec(),
            solver_adapter=solver,
            gateway=gateway,
        )
