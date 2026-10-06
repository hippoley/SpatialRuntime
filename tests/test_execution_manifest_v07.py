import copy

import pytest

from spatialruntime.runtime.manifest import (
    MANIFEST_SCHEMA,
    build_execution_manifest,
    manifest_hash,
    validate_execution_manifest,
)
from spatialruntime.runtime.replay import (
    ReplayValidationError,
    bundle_hash,
    validate_bundle,
)
from spatialruntime.runtime.session import trace_hash
from spatialruntime.runtime.scenario_spec import run_scenario_spec


def scenario():
    return {
        "schema": "runtime_scenario_spec_v0.6",
        "name": "manifest-test",
        "case_id": "manifest-case",
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
        "steps": [
            {
                "safety_context": {"sensors": {"rain": {"value": "dry"}}},
                "policy_action": {"changes": {"window": {"open_ratio": 0.6}}},
            },
            {
                "safety_context": {"sensors": {"rain": {"value": "wet"}}},
            },
        ],
    }


def test_scenario_bundle_contains_valid_execution_manifest():
    bundle = run_scenario_spec(scenario())
    report = validate_bundle(bundle)
    manifest = bundle["execution_manifest"]

    assert manifest["schema"] == MANIFEST_SCHEMA
    assert manifest["case_id"] == "manifest-case"
    assert manifest["solver"]["mode"] == "fixture"
    assert manifest["solver"]["adapter_id"] == "deterministic-fixture"
    assert manifest["manifest_hash"] == manifest_hash(manifest)
    assert report.manifest_hash == manifest["manifest_hash"]


def test_manifest_rejects_solver_drift_even_if_trace_and_bundle_are_rehashed():
    bundle = run_scenario_spec(scenario())
    tampered = copy.deepcopy(bundle)

    provenance = tampered["traces"][1]["stages"]["solver"]["solver_provenance"]
    provenance["adapter_fingerprint"] = "f" * 64
    tampered["traces"][1]["trace_hash"] = trace_hash(tampered["traces"][1])
    tampered["bundle_hash"] = bundle_hash(tampered)

    with pytest.raises(ReplayValidationError, match="solver adapter fingerprint drift"):
        validate_bundle(tampered)


def test_manifest_rejects_safety_graph_drift_even_if_trace_and_bundle_are_rehashed():
    bundle = run_scenario_spec(scenario())
    tampered = copy.deepcopy(bundle)

    tampered["traces"][0]["stages"]["safety"]["graph_fingerprint"] = "a" * 64
    tampered["traces"][0]["trace_hash"] = trace_hash(tampered["traces"][0])
    tampered["bundle_hash"] = bundle_hash(tampered)

    with pytest.raises(ReplayValidationError, match="safety graph fingerprint drift"):
        validate_bundle(tampered)


def test_manifest_rejects_initial_state_substitution_with_rehashed_trace():
    bundle = run_scenario_spec(scenario())
    tampered = copy.deepcopy(bundle)

    first = tampered["traces"][0]
    first["runtime_state_before"]["window"]["executed_state"]["open_ratio"] = 0.1
    from spatialruntime.runtime.session import state_hash
    first["runtime_state_before_hash"] = state_hash(first["runtime_state_before"])
    first["trace_hash"] = trace_hash(first)
    tampered["bundle_hash"] = bundle_hash(tampered)

    with pytest.raises(ReplayValidationError, match="initial state fingerprint mismatch"):
        validate_bundle(tampered)


def test_manifest_hash_detects_direct_manifest_edit():
    bundle = run_scenario_spec(scenario())
    tampered = copy.deepcopy(bundle)
    tampered["execution_manifest"]["solver"]["mode"] = "other"
    tampered["bundle_hash"] = bundle_hash(tampered)

    with pytest.raises(ReplayValidationError, match="execution manifest hash mismatch"):
        validate_bundle(tampered)
