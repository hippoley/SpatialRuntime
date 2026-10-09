import pytest

from spatialruntime.runtime.replay import (
    ReplayValidationError,
    resume_session_from_bundle,
    validate_bundle,
)
from spatialruntime.runtime.scenario_spec import run_scenario_spec
from spatialruntime.safety.dependency_graph import compile_safety_graph


def base_spec(*, hardware=False, offline=False):
    spec = {
        "schema": "runtime_scenario_spec_v0.6",
        "name": "resume-test",
        "case_id": "resume-case",
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
                "solver_feedback": {"zones": {}, "flow_paths": {}},
                "safety_context": {},
                "policy_action": {"changes": {"window": {"open_ratio": 0.7}}},
                "now_ms": 1000,
            }
        ],
    }
    if hardware:
        spec["hardware"] = {
            "mode": "fixture",
            "device_bindings": {
                "window": {"device_id": "window-01"},
            },
        }
        if offline:
            spec["hardware"]["offline_devices"] = ["window-01"]
    return spec


def compiled_for(spec):
    return compile_safety_graph(spec["safety_graph"], spec["entity_catalog"])


def test_valid_bundle_resumes_live_session_and_can_continue():
    spec = base_spec(hardware=True, offline=False)
    bundle = run_scenario_spec(spec)
    assert validate_bundle(bundle).valid is True

    session = resume_session_from_bundle(
        bundle,
        entity_catalog=spec["entity_catalog"],
        compiled_safety_graph=compiled_for(spec),
    )

    assert session.step == 1
    assert session.revision == 1
    assert len(session.history) == 1
    assert session.runtime_state["window"]["executed_state"]["open_ratio"] == 0.7

    trace = session.execute(
        solver_feedback={
            "source_step": 1,
            "source_revision": 1,
            "zones": {},
            "flow_paths": {},
        },
        policy_action={
            "source_step": 1,
            "source_revision": 1,
            "changes": {"window": {"open_ratio": 0.6}},
        },
        safety_context={
            "source_step": 1,
            "source_revision": 1,
        },
    )
    assert trace["status"] == "completed"
    session.advance(trace)
    assert (session.step, session.revision) == (2, 2)


def test_resume_rejects_catalog_or_graph_drift():
    spec = base_spec()
    bundle = run_scenario_spec(spec)

    bad_catalog = {
        **spec["entity_catalog"],
        "other": {"kind": "window", "exterior": False, "room": "hall"},
    }
    with pytest.raises(ReplayValidationError, match="entity_catalog fingerprint mismatch"):
        resume_session_from_bundle(
            bundle,
            entity_catalog=bad_catalog,
            compiled_safety_graph=compiled_for(spec),
        )

    other_graph = compile_safety_graph(
        {
            "schema": "whole_home_safety_graph_v3.3",
            "rules": [{
                "id": "different",
                "priority": 1,
                "when": {"path": "x", "op": "truthy"},
                "effects": [],
            }],
        },
        spec["entity_catalog"],
    )
    with pytest.raises(ReplayValidationError, match="safety graph fingerprint mismatch"):
        resume_session_from_bundle(
            bundle,
            entity_catalog=spec["entity_catalog"],
            compiled_safety_graph=other_graph,
        )


def test_hardware_incomplete_resume_stays_fail_closed_until_fresh_feedback():
    spec = base_spec(hardware=True, offline=True)
    bundle = run_scenario_spec(spec)
    assert bundle["traces"][-1]["status"] == "hardware_incomplete"
    assert (
        bundle["traces"][-1]["next_runtime_state"]["window"]["state_source"]
        == "committed_target_unconfirmed"
    )

    session = resume_session_from_bundle(
        bundle,
        entity_catalog=spec["entity_catalog"],
        compiled_safety_graph=compiled_for(spec),
    )

    trace = session.execute(
        solver_feedback={
            "source_step": 1,
            "source_revision": 1,
            "zones": {},
            "flow_paths": {},
        },
        policy_action={
            "source_step": 1,
            "source_revision": 1,
            "changes": {"window": {"open_ratio": 0.8}},
        },
        safety_context={
            "source_step": 1,
            "source_revision": 1,
        },
    )
    assert trace["status"] == "observation_blocked"
    assert any(
        item["kind"] == "unconfirmed_committed_target"
        for item in trace["stages"]["reconcile"]["disagreements"]
    )


def test_resume_requires_execution_manifest():
    spec = base_spec()
    bundle = run_scenario_spec(spec)
    bundle = dict(bundle)
    bundle.pop("execution_manifest")
    from spatialruntime.runtime.replay import bundle_hash
    bundle["bundle_hash"] = bundle_hash(bundle)

    with pytest.raises(ReplayValidationError, match="requires execution_manifest"):
        resume_session_from_bundle(
            bundle,
            entity_catalog=spec["entity_catalog"],
            compiled_safety_graph=compiled_for(spec),
        )
