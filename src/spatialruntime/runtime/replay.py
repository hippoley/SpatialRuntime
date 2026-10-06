from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from spatialruntime.runtime.session import TRACE_SCHEMA, trace_hash, state_hash

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "runtime_replay_report_v0.4",
            "valid": self.valid,
            "case_id": self.case_id,
            "trace_count": self.trace_count,
            "first_step": self.first_step,
            "last_step": self.last_step,
            "final_state_hash": self.final_state_hash,
            "bundle_hash": self.bundle_hash,
        }


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def bundle_hash(bundle: Mapping[str, Any]) -> str:
    body = {k: v for k, v in bundle.items() if k != "bundle_hash"}
    return sha256(_canonical(body).encode()).hexdigest()


def make_bundle(*, case_id: str, traces: Sequence[Mapping[str, Any]],
                metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "schema": BUNDLE_SCHEMA,
        "case_id": case_id,
        "traces": [dict(t) for t in traces],
        "metadata": dict(metadata or {}),
    }
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

    return ReplayReport(
        valid=True,
        case_id=case_id,
        trace_count=len(traces),
        first_step=int(traces[0]["step"]),
        last_step=int(traces[-1]["step"]),
        final_state_hash=str(traces[-1]["next_runtime_state_hash"]),
        bundle_hash=str(bundle["bundle_hash"]),
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
