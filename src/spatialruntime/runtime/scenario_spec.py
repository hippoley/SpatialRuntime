from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from spatialruntime.hardware.contract import CommandLedger, MockGateway
from spatialruntime.runtime.manifest import build_execution_manifest
from spatialruntime.runtime.replay import ReplayValidationError, make_bundle, validate_bundle
from spatialruntime.runtime.session import RuntimeSession
from spatialruntime.safety.dependency_graph import compile_safety_graph
from spatialruntime.solver.contract import build_solver_request, SolverContractError
from spatialruntime.solver.fixture import DeterministicSolverAdapter

SCHEMA = "runtime_scenario_spec_v0.6"
LEGACY_SCHEMA = "runtime_scenario_spec_v0.5"


class ScenarioSpecError(ReplayValidationError):
    pass


def load_scenario_spec(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScenarioSpecError(f"scenario not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise ScenarioSpecError(f"invalid scenario JSON: {p}") from exc
    if not isinstance(data, dict):
        raise ScenarioSpecError("scenario root must be object")
    return data


def _with_envelope(payload: Mapping[str, Any] | None, *, step: int, revision: int) -> dict[str, Any] | None:
    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise ScenarioSpecError("step payload must be object")
    out = deepcopy(dict(payload))
    supplied_step = out.get("source_step")
    supplied_revision = out.get("source_revision")
    if supplied_step is not None and int(supplied_step) != step:
        raise ScenarioSpecError(f"scenario supplied stale source_step: {supplied_step} != {step}")
    if supplied_revision is not None and int(supplied_revision) != revision:
        raise ScenarioSpecError(
            f"scenario supplied stale source_revision: {supplied_revision} != {revision}"
        )
    out["source_step"] = step
    out["source_revision"] = revision
    return out


def _normalize_recovery(actions: Any, *, step: int, revision: int) -> list[dict[str, Any]]:
    if actions is None:
        return []
    if not isinstance(actions, list):
        raise ScenarioSpecError("recovery_actions must be array")
    out = []
    for raw in actions:
        if not isinstance(raw, Mapping):
            raise ScenarioSpecError("recovery action must be object")
        item = _with_envelope(raw, step=step, revision=revision)
        assert item is not None
        item.setdefault("schema", "fault_recovery_action_v2.8")
        out.append(item)
    return out


def _build_fixture_solver(config: Mapping[str, Any] | None) -> DeterministicSolverAdapter | None:
    if config is None:
        return None
    if not isinstance(config, Mapping):
        raise ScenarioSpecError("solver must be object")
    mode = config.get("mode")
    if mode != "fixture":
        raise ScenarioSpecError(
            "scenario files only support solver.mode='fixture'; external solver processes "
            "must be instantiated explicitly by application code"
        )
    zones = config.get("zones", {})
    flow_paths = config.get("flow_paths", {})
    if not isinstance(zones, Mapping) or not isinstance(flow_paths, Mapping):
        raise ScenarioSpecError("fixture solver zones/flow_paths must be objects")
    return DeterministicSolverAdapter(zones=zones, flow_paths=flow_paths)


def validate_scenario_spec(spec: Mapping[str, Any]) -> None:
    if spec.get("schema") not in {SCHEMA, LEGACY_SCHEMA}:
        raise ScenarioSpecError(f"unsupported scenario schema: {spec.get('schema')}")
    case_id = spec.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ScenarioSpecError("case_id required")
    for key in ("initial_runtime_state", "entity_catalog", "safety_graph"):
        if not isinstance(spec.get(key), Mapping):
            raise ScenarioSpecError(f"{key} must be object")
    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ScenarioSpecError("steps must be a non-empty array")

    hardware = spec.get("hardware")
    if hardware is not None:
        if not isinstance(hardware, Mapping):
            raise ScenarioSpecError("hardware must be object")
        if hardware.get("mode") != "fixture":
            raise ScenarioSpecError(
                "scenario files only support hardware.mode='fixture'; real hardware requires an explicit runtime adapter"
            )
        bindings = hardware.get("device_bindings")
        if not isinstance(bindings, Mapping) or not bindings:
            raise ScenarioSpecError("fixture hardware requires device_bindings")

    solver_cfg = spec.get("solver")
    if solver_cfg is not None:
        _build_fixture_solver(solver_cfg)

    for index, raw_step in enumerate(steps):
        if not isinstance(raw_step, Mapping):
            raise ScenarioSpecError(f"steps[{index}] must be object")
        if solver_cfg is None and raw_step.get("solver_feedback") is None:
            raise ScenarioSpecError(
                f"steps[{index}].solver_feedback required when no solver adapter is configured"
            )
        if solver_cfg is not None and raw_step.get("solver_feedback") is not None:
            raise ScenarioSpecError(
                f"steps[{index}] cannot provide solver_feedback when a solver adapter is configured"
            )


def _solve_step(
    *,
    adapter: DeterministicSolverAdapter | None,
    raw_step: Mapping[str, Any],
    case_id: str,
    step: int,
    revision: int,
    runtime_state: Mapping[str, Any],
) -> dict[str, Any]:
    if adapter is None:
        solver = _with_envelope(raw_step.get("solver_feedback"), step=step, revision=revision)
        if solver is None:
            raise ScenarioSpecError("solver_feedback required")
        return solver

    model = raw_step.get("solver_model", {})
    boundary = raw_step.get("boundary_conditions", {})
    if not isinstance(model, Mapping) or not isinstance(boundary, Mapping):
        raise ScenarioSpecError("solver_model/boundary_conditions must be objects")
    request = build_solver_request(
        case_id=case_id,
        source_step=step,
        source_revision=revision,
        world_state=runtime_state,
        model=model,
        boundary_conditions=boundary,
    )
    try:
        return adapter.solve(request)
    except SolverContractError as exc:
        raise ScenarioSpecError(f"solver adapter failed: {exc}") from exc


def run_scenario_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    validate_scenario_spec(spec)
    case_id = str(spec["case_id"])
    initial = deepcopy(dict(spec["initial_runtime_state"]))
    catalog = deepcopy(dict(spec["entity_catalog"]))
    compiled = compile_safety_graph(spec["safety_graph"], catalog)
    solver_adapter = _build_fixture_solver(spec.get("solver"))

    session = RuntimeSession(
        case_id=case_id,
        step=int(spec.get("initial_step", 0)),
        revision=int(spec.get("initial_revision", 0)),
        runtime_state=initial,
        entity_catalog=catalog,
        compiled_safety_graph=compiled,
    )

    hardware = spec.get("hardware")
    ledger = None
    gateway = None
    bindings = None
    if isinstance(hardware, Mapping):
        ledger = CommandLedger()
        gateway = MockGateway(offline_devices=set(hardware.get("offline_devices") or []))
        bindings = deepcopy(dict(hardware["device_bindings"]))

    traces: list[dict[str, Any]] = []
    stop_reason = None
    for index, raw_step in enumerate(spec["steps"]):
        solver = _solve_step(
            adapter=solver_adapter,
            raw_step=raw_step,
            case_id=case_id,
            step=session.step,
            revision=session.revision,
            runtime_state=session.runtime_state,
        )
        context = _with_envelope(raw_step.get("safety_context", {}), step=session.step, revision=session.revision)
        policy = _with_envelope(raw_step.get("policy_action", {"changes": {}}), step=session.step, revision=session.revision)
        device_feedback = _with_envelope(raw_step.get("device_feedback"), step=session.step, revision=session.revision)
        sensor_observation = _with_envelope(raw_step.get("sensor_observation"), step=session.step, revision=session.revision)
        recovery = _normalize_recovery(raw_step.get("recovery_actions"), step=session.step, revision=session.revision)

        kwargs: dict[str, Any] = {}
        if gateway is not None:
            kwargs.update({
                "gateway": gateway,
                "command_ledger": ledger,
                "device_bindings": bindings,
                "now_ms": int(raw_step.get("now_ms", (index + 1) * 1000)),
            })

        trace = session.execute(
            solver_feedback=solver,
            policy_action=policy,
            safety_context=context or {"source_step": session.step, "source_revision": session.revision},
            device_feedback=device_feedback,
            sensor_observation=sensor_observation,
            recovery_actions=recovery,
            reconcile_policy=raw_step.get("reconcile_policy"),
            supervisor_policy=raw_step.get("supervisor_policy"),
            max_open_ratio_delta=float(raw_step.get("max_open_ratio_delta", 0.25)),
            **kwargs,
        )
        traces.append(trace)

        if trace["status"] not in {"completed", "hardware_incomplete"}:
            stop_reason = {
                "index": index,
                "status": trace["status"],
                "blocked_at": trace.get("blocked_at"),
            }
            break
        session.advance(trace)

    execution_manifest = build_execution_manifest(
        case_id=case_id,
        scenario_spec=spec,
        initial_runtime_state=initial,
        entity_catalog=catalog,
        safety_graph_fingerprint=compiled.fingerprint,
        solver_mode=(
            spec.get("solver", {}).get("mode")
            if isinstance(spec.get("solver"), Mapping)
            else "embedded_feedback"
        ),
        solver_adapter_id=solver_adapter.adapter_id if solver_adapter is not None else None,
        solver_adapter_fingerprint=solver_adapter.fingerprint if solver_adapter is not None else None,
        hardware_mode=hardware.get("mode") if isinstance(hardware, Mapping) else None,
        hardware_config=hardware if isinstance(hardware, Mapping) else None,
    )

    bundle = make_bundle(
        case_id=case_id,
        traces=traces,
        execution_manifest=execution_manifest,
        metadata={
            "scenario_schema": spec.get("schema"),
            "runtime_scenario_schema": SCHEMA,
            "scenario_name": spec.get("name"),
            "executed_steps": len(traces),
            "requested_steps": len(spec["steps"]),
            "stop_reason": stop_reason,
            "final_step": session.step,
            "final_revision": session.revision,
            "final_runtime_state": session.runtime_state,
            "hardware_mode": hardware.get("mode") if isinstance(hardware, Mapping) else None,
            "solver_mode": spec.get("solver", {}).get("mode") if isinstance(spec.get("solver"), Mapping) else "embedded_feedback",
            "solver_adapter_fingerprint": solver_adapter.fingerprint if solver_adapter is not None else None,
        },
    )
    validate_bundle(bundle)
    return bundle
