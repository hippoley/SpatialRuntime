from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any, Mapping

REQUEST_SCHEMA = "solver_request_v0.6"
FEEDBACK_SCHEMA = "solver_feedback_v0.6"


class SolverContractError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(value: Any) -> str:
    return sha256(_canonical(value).encode()).hexdigest()


def _finite(value: Any, label: str) -> float:
    try:
        x = float(value)
    except Exception as exc:
        raise SolverContractError(f"{label} must be numeric") from exc
    if not math.isfinite(x):
        raise SolverContractError(f"{label} must be finite")
    return x


@dataclass(frozen=True)
class SolverRequest:
    case_id: str
    source_step: int
    source_revision: int
    world_state: dict[str, Any]
    model: dict[str, Any]
    boundary_conditions: dict[str, Any]
    request_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REQUEST_SCHEMA,
            "case_id": self.case_id,
            "source_step": self.source_step,
            "source_revision": self.source_revision,
            "world_state": self.world_state,
            "model": self.model,
            "boundary_conditions": self.boundary_conditions,
            "request_hash": self.request_hash,
        }


def build_solver_request(
    *,
    case_id: str,
    source_step: int,
    source_revision: int,
    world_state: Mapping[str, Any],
    model: Mapping[str, Any] | None = None,
    boundary_conditions: Mapping[str, Any] | None = None,
) -> SolverRequest:
    if not case_id:
        raise SolverContractError("case_id required")
    body = {
        "schema": REQUEST_SCHEMA,
        "case_id": case_id,
        "source_step": int(source_step),
        "source_revision": int(source_revision),
        "world_state": dict(world_state),
        "model": dict(model or {}),
        "boundary_conditions": dict(boundary_conditions or {}),
    }
    return SolverRequest(
        case_id=case_id,
        source_step=int(source_step),
        source_revision=int(source_revision),
        world_state=dict(world_state),
        model=dict(model or {}),
        boundary_conditions=dict(boundary_conditions or {}),
        request_hash=payload_hash(body),
    )


class SolverAdapter(ABC):
    adapter_id: str

    @property
    @abstractmethod
    def fingerprint(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def solve(self, request: SolverRequest) -> dict[str, Any]:
        raise NotImplementedError


def normalize_solver_feedback(
    raw: Mapping[str, Any],
    *,
    request: SolverRequest,
    adapter_id: str,
    adapter_fingerprint: str,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise SolverContractError("solver response must be object")

    supplied_step = raw.get("source_step")
    supplied_revision = raw.get("source_revision")
    supplied_case = raw.get("case_id")
    if supplied_step is not None and int(supplied_step) != request.source_step:
        raise SolverContractError("solver response source_step mismatch")
    if supplied_revision is not None and int(supplied_revision) != request.source_revision:
        raise SolverContractError("solver response source_revision mismatch")
    if supplied_case is not None and supplied_case != request.case_id:
        raise SolverContractError("solver response case_id mismatch")

    zones = raw.get("zones", {})
    flow_paths = raw.get("flow_paths", {})
    if not isinstance(zones, Mapping) or not isinstance(flow_paths, Mapping):
        raise SolverContractError("zones and flow_paths must be objects")

    normalized_zones: dict[str, Any] = {}
    for zone_id, values in zones.items():
        if not isinstance(zone_id, str) or not zone_id or not isinstance(values, Mapping):
            raise SolverContractError("invalid zone result")
        out = {}
        for key, value in values.items():
            if key in {
                "pressure_pa",
                "temperature_c",
                "ach_1_h",
                "airflow_in_m3_s",
                "airflow_out_m3_s",
            }:
                out[key] = _finite(value, f"zones.{zone_id}.{key}")
            else:
                out[key] = value
        normalized_zones[zone_id] = out

    normalized_paths: dict[str, Any] = {}
    for path_id, values in flow_paths.items():
        if not isinstance(path_id, str) or not path_id or not isinstance(values, Mapping):
            raise SolverContractError("invalid flow path result")
        out = {}
        for key, value in values.items():
            if key in {"flow_m3_s", "mass_flow_kg_s", "delta_pressure_pa"}:
                out[key] = _finite(value, f"flow_paths.{path_id}.{key}")
            else:
                out[key] = value
        normalized_paths[path_id] = out

    raw_result_body = {
        "zones": normalized_zones,
        "flow_paths": normalized_paths,
        "metadata": dict(raw.get("metadata") or {}),
    }
    return {
        "schema": FEEDBACK_SCHEMA,
        "case_id": request.case_id,
        "source_step": request.source_step,
        "source_revision": request.source_revision,
        "zones": normalized_zones,
        "flow_paths": normalized_paths,
        "metadata": dict(raw.get("metadata") or {}),
        "solver_provenance": {
            "adapter_id": adapter_id,
            "adapter_fingerprint": adapter_fingerprint,
            "request_hash": request.request_hash,
            "result_hash": payload_hash(raw_result_body),
        },
    }
