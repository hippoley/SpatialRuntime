from __future__ import annotations

from typing import Any

from spatialruntime.hardware.contract import CommandLedger, MockGateway
from spatialruntime.runtime.session import RuntimeSession
from spatialruntime.safety.dependency_graph import compile_safety_graph, SCHEMA as GRAPH_SCHEMA


CATALOG = {
    "window_kitchen": {"kind": "window", "exterior": True, "room": "kitchen"},
    "hood_kitchen": {"kind": "hood", "room": "kitchen"},
}

SAFETY_GRAPH = {
    "schema": GRAPH_SCHEMA,
    "rules": [
        {
            "id": "cooking_requires_makeup_air",
            "priority": 70,
            "when": {"path": "sensors.cooking.value", "op": "eq", "value": True},
            "effects": [
                {
                    "kind": "emit_change",
                    "selector": {"ids": ["hood_kitchen"]},
                    "changes": {"fan_level": 1},
                },
                {
                    "kind": "emit_change",
                    "selector": {"ids": ["window_kitchen"]},
                    "changes": {"open_ratio": 0.2},
                },
            ],
        },
        {
            "id": "rain_closes_exterior_window",
            "priority": 100,
            "when": {"path": "sensors.rain.value", "op": "eq", "value": "wet"},
            "effects": [
                {
                    "kind": "emit_change",
                    "selector": {"where": {"kind": "window", "exterior": True}},
                    "changes": {"open_ratio": 0.0},
                }
            ],
        },
    ],
}


def _solver(step: int, revision: int) -> dict[str, Any]:
    return {
        "source_step": step,
        "source_revision": revision,
        "zones": {
            "kitchen": {
                "pressure_pa": 0.0,
                "temperature_c": 24.0,
                "ach_1_h": 0.5,
                "airflow_in_m3_s": 0.02,
                "airflow_out_m3_s": 0.02,
            },
            "living": {
                "pressure_pa": 0.0,
                "temperature_c": 24.0,
                "ach_1_h": 0.3,
                "airflow_in_m3_s": 0.01,
                "airflow_out_m3_s": 0.01,
            },
        },
        "flow_paths": {},
    }


def _context(step: int, revision: int, *, cooking: bool, rain: str) -> dict[str, Any]:
    return {
        "source_step": step,
        "source_revision": revision,
        "sensors": {
            "cooking": {"value": cooking, "quality": 1.0},
            "rain": {"value": rain, "quality": 1.0},
        },
    }


def _empty_policy(step: int, revision: int) -> dict[str, Any]:
    return {"source_step": step, "source_revision": revision, "changes": {}}


def run_kitchen_living_demo() -> dict[str, Any]:
    """Run a deterministic two-step closed-loop example.

    Step 0: cooking safety graph starts hood and establishes make-up-air opening.
    Step 1: rain safety rule force-closes the exterior window.
    Hardware is the deterministic contract fixture; no real device is implied.
    """
    session = RuntimeSession(
        case_id="kitchen-living-demo",
        step=0,
        revision=0,
        runtime_state={
            "window_kitchen": {"executed_state": {"open_ratio": 0.5}},
            "hood_kitchen": {"executed_state": {"fan_level": 0}},
        },
        entity_catalog=CATALOG,
        compiled_safety_graph=compile_safety_graph(SAFETY_GRAPH, CATALOG),
    )
    ledger = CommandLedger()
    gateway = MockGateway()
    bindings = {
        "window_kitchen": {"device_id": "window-device-01"},
        "hood_kitchen": {"device_id": "hood-device-01"},
    }

    cooking_trace = session.execute(
        solver_feedback=_solver(session.step, session.revision),
        policy_action=_empty_policy(session.step, session.revision),
        safety_context=_context(session.step, session.revision, cooking=True, rain="dry"),
        gateway=gateway,
        command_ledger=ledger,
        device_bindings=bindings,
        now_ms=1_000,
    )
    session.advance(cooking_trace)

    rain_trace = session.execute(
        solver_feedback=_solver(session.step, session.revision),
        policy_action=_empty_policy(session.step, session.revision),
        safety_context=_context(session.step, session.revision, cooking=False, rain="wet"),
        gateway=gateway,
        command_ledger=ledger,
        device_bindings=bindings,
        now_ms=2_000,
    )
    session.advance(rain_trace)

    return {
        "case_id": session.case_id,
        "schema": "kitchen_living_demo_v0.3",
        "traces": [cooking_trace, rain_trace],
        "final_step": session.step,
        "final_revision": session.revision,
        "final_runtime_state": session.runtime_state,
    }
