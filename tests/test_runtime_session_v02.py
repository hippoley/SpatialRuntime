import pytest

from spatialruntime.hardware.contract import CommandLedger, MockGateway
from spatialruntime.runtime.session import RuntimeSession, RuntimeSessionError, trace_hash
from spatialruntime.safety.dependency_graph import compile_safety_graph, SCHEMA as GRAPH_SCHEMA


CATALOG = {"w": {"kind": "window", "exterior": True, "room": "kitchen"}}
RUNTIME = {"w": {"executed_state": {"open_ratio": 0.5}}}


def compiled_graph(*, rain=False):
    rules = []
    if rain:
        rules.append({
            "id": "rain",
            "priority": 90,
            "when": {"path": "sensors.rain.value", "op": "eq", "value": "wet"},
            "effects": [{
                "kind": "constrain",
                "selector": {"where": {"kind": "window", "exterior": True}},
                "property": "open_ratio",
                "op": "max",
                "value": 0,
            }],
        })
    return compile_safety_graph({"schema": GRAPH_SCHEMA, "rules": rules}, CATALOG)


def session(*, rain_graph=False):
    return RuntimeSession(
        case_id="case",
        step=0,
        revision=0,
        runtime_state={"w": {"executed_state": {"open_ratio": 0.5}}},
        entity_catalog=CATALOG,
        compiled_safety_graph=compiled_graph(rain=rain_graph),
    )


def solver():
    return {"source_step": 0, "source_revision": 0, "zones": {}, "flow_paths": {}}


def context(rain="dry"):
    return {
        "source_step": 0,
        "source_revision": 0,
        "sensors": {"rain": {"value": rain}},
    }


def action(value):
    return {
        "source_step": 0,
        "source_revision": 0,
        "changes": {"w": {"open_ratio": value}},
    }


def test_normal_policy_still_uses_commit_rate_limit():
    s = session()
    trace = s.execute(
        solver_feedback=solver(),
        policy_action=action(0.9),
        safety_context=context(),
    )
    assert trace["status"] == "completed"
    d = trace["stages"]["commit"]["decisions"]["w"]
    assert d["decision"] == "commit_clamped"
    assert d["executed_state"]["open_ratio"] == 0.75
    assert d["safety_override"] is False


def test_rain_safety_override_is_not_weakened_by_lower_priority_rate_limit():
    s = session(rain_graph=True)
    trace = s.execute(
        solver_feedback=solver(),
        policy_action=action(0.9),
        safety_context=context("wet"),
    )
    safety = trace["stages"]["safety"]
    assert safety["motion_changes"]["w"]["open_ratio"] == 0
    assert safety["safety_forced_entities"] == ["w"]

    d = trace["stages"]["commit"]["decisions"]["w"]
    assert d["decision"] == "commit_safety_override"
    assert d["executed_state"]["open_ratio"] == 0
    assert trace["next_runtime_state"]["w"]["executed_state"]["open_ratio"] == 0


def test_hard_device_disagreement_blocks_before_safety_or_commit():
    s = session()
    feedback = {
        "source_step": 0,
        "source_revision": 0,
        "devices": {
            "w": {"quality": 1.0, "state": {"open_ratio": 0.2}},
        },
    }
    trace = s.execute(
        solver_feedback=solver(),
        device_feedback=feedback,
        policy_action=action(0.7),
        safety_context=context(),
    )
    assert trace["status"] == "observation_blocked"
    assert trace["blocked_at"] == "observation"
    assert trace["stages"]["reconcile"]["summary"]["hard_disagreements"] == 1
    assert "safety" not in trace["stages"]
    assert "commit" not in trace["stages"]


def test_hardware_feedback_becomes_next_state_and_trace_can_advance():
    s = session()
    ledger = CommandLedger()
    gateway = MockGateway()
    trace = s.execute(
        solver_feedback=solver(),
        policy_action=action(0.7),
        safety_context=context(),
        gateway=gateway,
        command_ledger=ledger,
        device_bindings={"w": {"device_id": "window-1"}},
        now_ms=1000,
    )
    assert trace["status"] == "completed"
    assert trace["stages"]["hardware"]["device_feedback"]["complete"] is True
    assert trace["next_runtime_state"]["w"]["executed_state"]["open_ratio"] == 0.7
    assert trace["next_runtime_state"]["w"]["state_source"] == "device_feedback"
    assert trace["trace_hash"] == trace_hash(trace)

    s.advance(trace)
    assert (s.step, s.revision) == (1, 1)
    assert s.runtime_state["w"]["executed_state"]["open_ratio"] == 0.7

    tampered = dict(trace)
    tampered["status"] = "hardware_incomplete"
    with pytest.raises(RuntimeSessionError):
        # Stale trace is rejected even before integrity would be considered.
        s.advance(tampered)
