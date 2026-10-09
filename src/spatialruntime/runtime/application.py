from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from spatialruntime.hardware.contract import CommandLedger
from spatialruntime.runtime.manifest import build_execution_manifest
from spatialruntime.runtime.replay import make_bundle, validate_bundle
from spatialruntime.runtime.scenario_spec import (
    LEGACY_SCHEMA,
    SCHEMA,
    ScenarioSpecError,
    _normalize_recovery,
    _with_envelope,
)
from spatialruntime.runtime.session import RuntimeSession
from spatialruntime.safety.dependency_graph import compile_safety_graph
from spatialruntime.solver.contract import SolverAdapter, SolverContractError, build_solver_request


class RuntimeApplicationError(ScenarioSpecError):
    pass


@dataclass(frozen=True)
class RuntimeApplication:
    """Explicitly assembled runtime dependencies.

    Scenario JSON remains inert data. External solver processes, transports,
    credentials and endpoints are bound by application code, never discovered
    from scenario data.
    """

    solver_adapter: SolverAdapter | None = None
    gateway: Any | None = None
    command_ledger: CommandLedger | None = None
    device_bindings: Mapping[str, Mapping[str, Any]] | None = None
    hardware_descriptor: Mapping[str, Any] | None = None

    def _validate_dependencies(self) -> None:
        hardware_values = (
            self.gateway,
            self.command_ledger,
            self.device_bindings,
            self.hardware_descriptor,
        )
        supplied = [value is not None for value in hardware_values]
        if any(supplied) and not all(supplied):
            raise RuntimeApplicationError(
                "gateway, command_ledger, device_bindings and hardware_descriptor "
                "must be supplied together"
            )
        if self.device_bindings is not None and not self.device_bindings:
            raise RuntimeApplicationError("device_bindings must not be empty")
        if self.hardware_descriptor is not None:
            adapter_id = self.hardware_descriptor.get("adapter_id")
            if not isinstance(adapter_id, str) or not adapter_id:
                raise RuntimeApplicationError(
                    "hardware_descriptor.adapter_id is required"
                )

    def validate_spec(self, spec: Mapping[str, Any]) -> None:
        self._validate_dependencies()
        if spec.get("schema") not in {SCHEMA, LEGACY_SCHEMA}:
            raise RuntimeApplicationError(
                f"unsupported scenario schema: {spec.get('schema')}"
            )
        case_id = spec.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise RuntimeApplicationError("case_id required")
        for key in ("initial_runtime_state", "entity_catalog", "safety_graph"):
            if not isinstance(spec.get(key), Mapping):
                raise RuntimeApplicationError(f"{key} must be object")
        steps = spec.get("steps")
        if not isinstance(steps, list) or not steps:
            raise RuntimeApplicationError("steps must be a non-empty array")

        if spec.get("solver") is not None:
            raise RuntimeApplicationError(
                "explicit application assembly forbids scenario.solver; "
                "inject solver_adapter from application code"
            )
        if spec.get("hardware") is not None:
            raise RuntimeApplicationError(
                "explicit application assembly forbids scenario.hardware; "
                "inject gateway/device bindings from application code"
            )

        for index, raw_step in enumerate(steps):
            if not isinstance(raw_step, Mapping):
                raise RuntimeApplicationError(f"steps[{index}] must be object")
            has_feedback = raw_step.get("solver_feedback") is not None
            if self.solver_adapter is None and not has_feedback:
                raise RuntimeApplicationError(
                    f"steps[{index}].solver_feedback required when no solver_adapter is injected"
                )
            if self.solver_adapter is not None and has_feedback:
                raise RuntimeApplicationError(
                    f"steps[{index}] cannot provide solver_feedback when solver_adapter is injected"
                )

    def _solve(
        self,
        *,
        raw_step: Mapping[str, Any],
        case_id: str,
        step: int,
        revision: int,
        runtime_state: Mapping[str, Any],
    ) -> dict[str, Any]:
        if self.solver_adapter is None:
            payload = _with_envelope(
                raw_step.get("solver_feedback"),
                step=step,
                revision=revision,
            )
            if payload is None:
                raise RuntimeApplicationError("solver_feedback required")
            return payload

        model = raw_step.get("solver_model", {})
        boundary = raw_step.get("boundary_conditions", {})
        if not isinstance(model, Mapping) or not isinstance(boundary, Mapping):
            raise RuntimeApplicationError(
                "solver_model/boundary_conditions must be objects"
            )
        request = build_solver_request(
            case_id=case_id,
            source_step=step,
            source_revision=revision,
            world_state=runtime_state,
            model=model,
            boundary_conditions=boundary,
        )
        try:
            return self.solver_adapter.solve(request)
        except SolverContractError as exc:
            raise RuntimeApplicationError(f"solver adapter failed: {exc}") from exc

    def run(self, spec: Mapping[str, Any]) -> dict[str, Any]:
        self.validate_spec(spec)

        case_id = str(spec["case_id"])
        initial = deepcopy(dict(spec["initial_runtime_state"]))
        catalog = deepcopy(dict(spec["entity_catalog"]))
        compiled = compile_safety_graph(spec["safety_graph"], catalog)

        session = RuntimeSession(
            case_id=case_id,
            step=int(spec.get("initial_step", 0)),
            revision=int(spec.get("initial_revision", 0)),
            runtime_state=initial,
            entity_catalog=catalog,
            compiled_safety_graph=compiled,
        )

        traces: list[dict[str, Any]] = []
        stop_reason = None

        for index, raw_step in enumerate(spec["steps"]):
            solver = self._solve(
                raw_step=raw_step,
                case_id=case_id,
                step=session.step,
                revision=session.revision,
                runtime_state=session.runtime_state,
            )
            context = _with_envelope(
                raw_step.get("safety_context", {}),
                step=session.step,
                revision=session.revision,
            )
            policy = _with_envelope(
                raw_step.get("policy_action", {"changes": {}}),
                step=session.step,
                revision=session.revision,
            )
            device_feedback = _with_envelope(
                raw_step.get("device_feedback"),
                step=session.step,
                revision=session.revision,
            )
            sensor_observation = _with_envelope(
                raw_step.get("sensor_observation"),
                step=session.step,
                revision=session.revision,
            )
            recovery = _normalize_recovery(
                raw_step.get("recovery_actions"),
                step=session.step,
                revision=session.revision,
            )

            kwargs: dict[str, Any] = {}
            if self.gateway is not None:
                kwargs.update(
                    {
                        "gateway": self.gateway,
                        "command_ledger": self.command_ledger,
                        "device_bindings": deepcopy(dict(self.device_bindings or {})),
                        "now_ms": int(raw_step.get("now_ms", (index + 1) * 1000)),
                    }
                )

            trace = session.execute(
                solver_feedback=solver,
                policy_action=policy,
                safety_context=context
                or {
                    "source_step": session.step,
                    "source_revision": session.revision,
                },
                device_feedback=device_feedback,
                sensor_observation=sensor_observation,
                recovery_actions=recovery,
                reconcile_policy=raw_step.get("reconcile_policy"),
                supervisor_policy=raw_step.get("supervisor_policy"),
                max_open_ratio_delta=float(
                    raw_step.get("max_open_ratio_delta", 0.25)
                ),
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

        solver_mode = "embedded_feedback"
        solver_id = None
        solver_fp = None
        if self.solver_adapter is not None:
            solver_mode = "injected_adapter"
            solver_id = self.solver_adapter.adapter_id
            solver_fp = self.solver_adapter.fingerprint

        hardware_mode = None
        hardware_config = None
        if self.gateway is not None:
            hardware_mode = "injected_adapter"
            hardware_config = {
                "descriptor": deepcopy(dict(self.hardware_descriptor or {})),
                "device_bindings": deepcopy(dict(self.device_bindings or {})),
            }

        execution_manifest = build_execution_manifest(
            case_id=case_id,
            scenario_spec=spec,
            initial_runtime_state=initial,
            entity_catalog=catalog,
            safety_graph_fingerprint=compiled.fingerprint,
            solver_mode=solver_mode,
            solver_adapter_id=solver_id,
            solver_adapter_fingerprint=solver_fp,
            hardware_mode=hardware_mode,
            hardware_config=hardware_config,
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
                "hardware_mode": hardware_mode,
                "solver_mode": solver_mode,
                "solver_adapter_id": solver_id,
                "solver_adapter_fingerprint": solver_fp,
                "application_assembly": "explicit_dependencies_v0.1",
            },
        )
        validate_bundle(bundle)
        return bundle


def run_application_spec(
    spec: Mapping[str, Any],
    *,
    solver_adapter: SolverAdapter | None = None,
    gateway: Any | None = None,
    command_ledger: CommandLedger | None = None,
    device_bindings: Mapping[str, Mapping[str, Any]] | None = None,
    hardware_descriptor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return RuntimeApplication(
        solver_adapter=solver_adapter,
        gateway=gateway,
        command_ledger=command_ledger,
        device_bindings=device_bindings,
        hardware_descriptor=hardware_descriptor,
    ).run(spec)
