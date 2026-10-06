from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from spatialruntime.runtime.state_reconciler import reconcile
from spatialruntime.runtime.observation import build_observation, ObservationBuildError
from spatialruntime.runtime.commit_gate import gate_action
from spatialruntime.safety.pipeline import run_safety_pipeline
from spatialruntime.safety.dependency_graph import CompiledSafetyGraph
from spatialruntime.hardware.runtime import dispatch_once

TRACE_SCHEMA = "runtime_episode_trace_v0.2"


class RuntimeSessionError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def trace_hash(trace: Mapping[str, Any]) -> str:
    body = {k: v for k, v in trace.items() if k != "trace_hash"}
    return sha256(_canonical(body).encode()).hexdigest()


def _next_runtime_state(runtime_state: Mapping[str, Any], commit_decision: Mapping[str, Any],
                        hardware_feedback: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build next recorded runtime state without equating ACK with convergence."""
    out = deepcopy(dict(runtime_state))
    feedback_devices = (hardware_feedback or {}).get("devices", {})
    for entity_id, decision in (commit_decision.get("decisions") or {}).items():
        if not str(decision.get("decision", "")).startswith("commit"):
            continue
        out.setdefault(entity_id, {})
        target = dict(decision.get("executed_state") or {})
        observed = feedback_devices.get(entity_id)
        if isinstance(observed, Mapping) and isinstance(observed.get("state"), Mapping):
            out[entity_id]["executed_state"] = dict(observed["state"])
            out[entity_id]["state_source"] = "device_feedback"
        else:
            out[entity_id]["executed_state"] = target
            out[entity_id]["state_source"] = "committed_target_unconfirmed"
    return out


@dataclass
class RuntimeSession:
    case_id: str
    step: int
    revision: int
    runtime_state: dict[str, Any]
    entity_catalog: Mapping[str, Mapping[str, Any]]
    compiled_safety_graph: CompiledSafetyGraph
    history: list[dict[str, Any]] = field(default_factory=list)

    def execute(
        self,
        *,
        solver_feedback: dict[str, Any],
        policy_action: Mapping[str, Any] | None,
        safety_context: Mapping[str, Any],
        device_feedback: dict[str, Any] | None = None,
        sensor_observation: dict[str, Any] | None = None,
        recovery_actions: Sequence[Mapping[str, Any]] | None = None,
        reconcile_policy: dict[str, Any] | None = None,
        supervisor_policy: Mapping[str, Any] | None = None,
        max_open_ratio_delta: float = 0.25,
        gateway: Any | None = None,
        command_ledger: Any | None = None,
        device_bindings: dict[str, dict[str, Any]] | None = None,
        now_ms: int | None = None,
    ) -> dict[str, Any]:
        stage_trace: dict[str, Any] = {}
        reconciled = reconcile(
            case_id=self.case_id,
            step=self.step,
            revision=self.revision,
            solver_feedback=solver_feedback,
            runtime_state=self.runtime_state,
            device_feedback=device_feedback,
            sensor_observation=sensor_observation,
            policy=reconcile_policy,
        )
        stage_trace["reconcile"] = reconciled

        try:
            observation = build_observation(reconciled)
        except ObservationBuildError as exc:
            trace = {
                "schema": TRACE_SCHEMA,
                "case_id": self.case_id,
                "step": self.step,
                "revision": self.revision,
                "status": "observation_blocked",
                "blocked_at": "observation",
                "error": str(exc),
                "stages": stage_trace,
                "next_runtime_state": deepcopy(self.runtime_state),
            }
            trace["trace_hash"] = trace_hash(trace)
            self.history.append(trace)
            return trace

        stage_trace["observation"] = observation

        safe = run_safety_pipeline(
            source_step=self.step,
            source_revision=self.revision,
            policy_action=policy_action,
            recovery_actions=recovery_actions or [],
            runtime_state=self.runtime_state,
            safety_context=safety_context,
            entity_catalog=self.entity_catalog,
            compiled_graph=self.compiled_safety_graph,
            supervisor_policy=supervisor_policy,
        )
        stage_trace["safety"] = safe

        committed = gate_action(
            observation=observation,
            proposed_action={
                "source_step": self.step,
                "source_revision": self.revision,
                "changes": safe["motion_changes"],
            },
            runtime_state=self.runtime_state,
            expected_step=self.step,
            expected_revision=self.revision,
            max_open_ratio_delta=max_open_ratio_delta,
            safety_override_entities=set(safe.get("safety_forced_entities") or ()),
        )
        stage_trace["commit"] = committed

        dispatch = None
        hardware_feedback = None
        if gateway is not None or command_ledger is not None or device_bindings is not None:
            if gateway is None or command_ledger is None or device_bindings is None or now_ms is None:
                raise RuntimeSessionError(
                    "gateway, command_ledger, device_bindings and now_ms must be supplied together"
                )
            if committed.get("summary", {}).get("ready_to_dispatch", False):
                dispatch = dispatch_once(
                    case_id=self.case_id,
                    commit_decision=committed,
                    device_bindings=device_bindings,
                    gateway=gateway,
                    ledger=command_ledger,
                    now_ms=int(now_ms),
                )
                stage_trace["hardware"] = dispatch
                hardware_feedback = dispatch.get("device_feedback")

        next_state = _next_runtime_state(self.runtime_state, committed, hardware_feedback)
        status = "completed"
        if not committed.get("summary", {}).get("ready_to_dispatch", False):
            status = "commit_blocked"
        elif dispatch is not None and not (hardware_feedback or {}).get("complete", False):
            status = "hardware_incomplete"

        trace = {
            "schema": TRACE_SCHEMA,
            "case_id": self.case_id,
            "step": self.step,
            "revision": self.revision,
            "status": status,
            "blocked_at": None if status == "completed" else (
                "hardware" if status == "hardware_incomplete" else "commit"
            ),
            "stages": stage_trace,
            "next_runtime_state": next_state,
        }
        trace["trace_hash"] = trace_hash(trace)
        self.history.append(trace)
        return trace

    def advance(self, trace: Mapping[str, Any]) -> None:
        """Advance only from a trace produced by this exact session revision."""
        if trace.get("schema") != TRACE_SCHEMA:
            raise RuntimeSessionError("invalid runtime trace schema")
        if trace.get("case_id") != self.case_id:
            raise RuntimeSessionError("trace case_id mismatch")
        if int(trace.get("step", -1)) != self.step or int(trace.get("revision", -1)) != self.revision:
            raise RuntimeSessionError("stale runtime trace")
        if trace.get("trace_hash") != trace_hash(trace):
            raise RuntimeSessionError("runtime trace integrity mismatch")
        if trace.get("status") not in {"completed", "hardware_incomplete"}:
            raise RuntimeSessionError(f"cannot advance blocked trace: {trace.get('status')}")
        self.runtime_state = deepcopy(trace["next_runtime_state"])
        self.step += 1
        self.revision += 1
