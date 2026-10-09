from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from spatialruntime.runtime.manifest import (
    ExecutionManifestError,
    fingerprint,
    validate_execution_manifest,
)
from spatialruntime.runtime.session import TRACE_SCHEMA, RuntimeSession, trace_hash, state_hash

BUNDLE_SCHEMA = "runtime_episode_bundle_v0.4"


class ReplayValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReplayReport:
    valid: bool
    case_id: str
    trace_count: int
    first_step: int
    last_step: int
    final_state_hash: str
    bundle_hash: str
    manifest_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "runtime_replay_report_v0.7",
            "valid": self.valid,
            "case_id": self.case_id,
            "trace_count": self.trace_count,
            "first_step": self.first_step,
            "last_step": self.last_step,
            "final_state_hash": self.final_state_hash,
            "bundle_hash": self.bundle_hash,
            "manifest_hash": self.manifest_hash,
        }


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def bundle_hash(bundle: Mapping[str, Any]) -> str:
    body = {k: v for k, v in bundle.items() if k != "bundle_hash"}
    return sha256(_canonical(body).encode()).hexdigest()


def make_bundle(*, case_id: str, traces: Sequence[Mapping[str, Any]],
                metadata: Mapping[str, Any] | None = None,
                execution_manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "schema": BUNDLE_SCHEMA,
        "case_id": case_id,
        "traces": [dict(t) for t in traces],
        "metadata": dict(metadata or {}),
    }
    if execution_manifest is not None:
        out["execution_manifest"] = dict(execution_manifest)
    out["bundle_hash"] = bundle_hash(out)
    return out


def validate_trace(trace: Mapping[str, Any]) -> None:
    if trace.get("schema") != TRACE_SCHEMA:
        raise ReplayValidationError(f"unsupported trace schema: {trace.get('schema')}")
    if trace.get("trace_hash") != trace_hash(trace):
        raise ReplayValidationError(
            f"trace hash mismatch at step={trace.get('step')} revision={trace.get('revision')}"
        )
    before = trace.get("runtime_state_before")
    after = trace.get("next_runtime_state")
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise ReplayValidationError("trace must include runtime_state_before and next_runtime_state")
    if trace.get("runtime_state_before_hash") != state_hash(before):
        raise ReplayValidationError(
            f"runtime_state_before hash mismatch at step={trace.get('step')}"
        )
    if trace.get("next_runtime_state_hash") != state_hash(after):
        raise ReplayValidationError(
            f"next_runtime_state hash mismatch at step={trace.get('step')}"
        )

    step = int(trace.get("step", -1))
    revision = int(trace.get("revision", -1))
    stages = trace.get("stages") or {}
    if not isinstance(stages, Mapping):
        raise ReplayValidationError(f"stages must be object at step={step}")
    for name, stage in stages.items():
        if not isinstance(stage, Mapping):
            raise ReplayValidationError(f"stage {name} must be object at step={step}")
        stage_step = stage.get("source_step", stage.get("step"))
        stage_revision = stage.get("source_revision", stage.get("revision"))
        if stage_step is not None and int(stage_step) != step:
            raise ReplayValidationError(
                f"stage {name} step mismatch at trace step={step}: {stage_step}"
            )
        if stage_revision is not None and int(stage_revision) != revision:
            raise ReplayValidationError(
                f"stage {name} revision mismatch at trace revision={revision}: {stage_revision}"
            )


def _validate_manifest_against_traces(
    manifest: Mapping[str, Any],
    *,
    case_id: str,
    traces: Sequence[Mapping[str, Any]],
) -> None:
    try:
        validate_execution_manifest(manifest)
    except ExecutionManifestError as exc:
        raise ReplayValidationError(str(exc)) from exc

    if manifest.get("case_id") != case_id:
        raise ReplayValidationError("execution manifest case_id mismatch")
    if not traces:
        raise ReplayValidationError("cannot validate manifest without traces")
    first = traces[0]
    if manifest.get("initial_runtime_state_fingerprint") != first.get("runtime_state_before_hash"):
        raise ReplayValidationError("execution manifest initial state fingerprint mismatch")

    expected_safety = manifest.get("safety_graph_fingerprint")
    solver_manifest = manifest.get("solver") or {}
    expected_solver_fp = solver_manifest.get("adapter_fingerprint")
    expected_solver_id = solver_manifest.get("adapter_id")

    for idx, trace in enumerate(traces):
        stages = trace.get("stages") or {}
        safety = stages.get("safety")
        if isinstance(safety, Mapping):
            if safety.get("graph_fingerprint") != expected_safety:
                raise ReplayValidationError(
                    f"safety graph fingerprint drift at trace[{idx}]"
                )

        solver = stages.get("solver")
        if expected_solver_fp is not None:
            if not isinstance(solver, Mapping):
                raise ReplayValidationError(f"solver evidence missing at trace[{idx}]")
            provenance = solver.get("solver_provenance")
            if not isinstance(provenance, Mapping):
                raise ReplayValidationError(f"solver provenance missing at trace[{idx}]")
            if provenance.get("adapter_fingerprint") != expected_solver_fp:
                raise ReplayValidationError(
                    f"solver adapter fingerprint drift at trace[{idx}]"
                )
            if expected_solver_id is not None and provenance.get("adapter_id") != expected_solver_id:
                raise ReplayValidationError(f"solver adapter id drift at trace[{idx}]")


def validate_bundle(bundle: Mapping[str, Any]) -> ReplayReport:
    if bundle.get("schema") != BUNDLE_SCHEMA:
        raise ReplayValidationError(f"unsupported bundle schema: {bundle.get('schema')}")
    if bundle.get("bundle_hash") != bundle_hash(bundle):
        raise ReplayValidationError("bundle hash mismatch")

    case_id = bundle.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ReplayValidationError("bundle case_id required")
    traces = bundle.get("traces")
    if not isinstance(traces, list) or not traces:
        raise ReplayValidationError("bundle traces must be a non-empty array")

    previous = None
    for idx, trace in enumerate(traces):
        if not isinstance(trace, Mapping):
            raise ReplayValidationError(f"trace[{idx}] must be object")
        validate_trace(trace)
        if trace.get("case_id") != case_id:
            raise ReplayValidationError(f"trace[{idx}] case_id mismatch")
        if previous is not None:
            if int(trace["step"]) != int(previous["step"]) + 1:
                raise ReplayValidationError(
                    f"non-contiguous step between {previous['step']} and {trace['step']}"
                )
            if int(trace["revision"]) != int(previous["revision"]) + 1:
                raise ReplayValidationError(
                    f"non-contiguous revision between {previous['revision']} and {trace['revision']}"
                )
            if previous.get("next_runtime_state_hash") != trace.get("runtime_state_before_hash"):
                raise ReplayValidationError(
                    f"state-chain hash mismatch between steps {previous['step']} and {trace['step']}"
                )
            if previous.get("next_runtime_state") != trace.get("runtime_state_before"):
                raise ReplayValidationError(
                    f"state-chain payload mismatch between steps {previous['step']} and {trace['step']}"
                )
        previous = trace

    manifest = bundle.get("execution_manifest")
    manifest_hash_value = None
    if manifest is not None:
        if not isinstance(manifest, Mapping):
            raise ReplayValidationError("execution_manifest must be object")
        _validate_manifest_against_traces(manifest, case_id=case_id, traces=traces)
        manifest_hash_value = str(manifest.get("manifest_hash"))

    return ReplayReport(
        valid=True,
        case_id=case_id,
        trace_count=len(traces),
        first_step=int(traces[0]["step"]),
        last_step=int(traces[-1]["step"]),
        final_state_hash=str(traces[-1]["next_runtime_state_hash"]),
        bundle_hash=str(bundle["bundle_hash"]),
        manifest_hash=manifest_hash_value,
    )


def load_bundle(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReplayValidationError(f"bundle not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise ReplayValidationError(f"invalid JSON bundle: {p}") from exc
    if not isinstance(data, dict):
        raise ReplayValidationError("bundle root must be object")
    return data


def save_bundle(bundle: Mapping[str, Any], path: str | Path) -> Path:
    validate_bundle(bundle)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return p


def resume_session_from_bundle(
    bundle: Mapping[str, Any],
    *,
    entity_catalog: Mapping[str, Mapping[str, Any]],
    compiled_safety_graph: Any,
) -> RuntimeSession:
    """Rebuild a live RuntimeSession from a validated episode bundle.

    Safe resume requires an execution manifest so the caller-supplied entity
    catalog and compiled safety graph can be bound back to the historical run.
    A hardware-incomplete trace is resumable because its next runtime state
    preserves committed_target_unconfirmed; the next control step will remain
    blocked until fresh device feedback reconciles that state.
    """

    report = validate_bundle(bundle)
    manifest = bundle.get("execution_manifest")
    if not isinstance(manifest, Mapping):
        raise ReplayValidationError(
            "safe session resume requires execution_manifest"
        )

    expected_catalog_fp = manifest.get("entity_catalog_fingerprint")
    actual_catalog_fp = fingerprint(entity_catalog)
    if expected_catalog_fp != actual_catalog_fp:
        raise ReplayValidationError(
            "resume entity_catalog fingerprint mismatch"
        )

    expected_graph_fp = manifest.get("safety_graph_fingerprint")
    actual_graph_fp = getattr(compiled_safety_graph, "fingerprint", None)
    if not isinstance(actual_graph_fp, str) or actual_graph_fp != expected_graph_fp:
        raise ReplayValidationError(
            "resume safety graph fingerprint mismatch"
        )

    traces = bundle.get("traces") or []
    if not traces:
        raise ReplayValidationError("cannot resume bundle without traces")
    last = traces[-1]
    status = last.get("status")
    if status not in {"completed", "hardware_incomplete"}:
        raise ReplayValidationError(
            f"cannot resume terminal trace with status={status}"
        )

    return RuntimeSession(
        case_id=report.case_id,
        step=int(last["step"]) + 1,
        revision=int(last["revision"]) + 1,
        runtime_state=deepcopy(dict(last["next_runtime_state"])),
        entity_catalog=deepcopy(dict(entity_catalog)),
        compiled_safety_graph=compiled_safety_graph,
        history=[deepcopy(dict(trace)) for trace in traces],
    )
