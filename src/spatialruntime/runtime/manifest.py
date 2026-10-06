from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

MANIFEST_SCHEMA = "runtime_execution_manifest_v0.7"


class ExecutionManifestError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: Any) -> str:
    return sha256(_canonical(value).encode()).hexdigest()


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    body = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    return fingerprint(body)


def build_execution_manifest(
    *,
    case_id: str,
    scenario_spec: Mapping[str, Any],
    initial_runtime_state: Mapping[str, Any],
    entity_catalog: Mapping[str, Any],
    safety_graph_fingerprint: str,
    solver_mode: str,
    solver_adapter_id: str | None,
    solver_adapter_fingerprint: str | None,
    hardware_mode: str | None,
    hardware_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not case_id:
        raise ExecutionManifestError("case_id required")
    out = {
        "schema": MANIFEST_SCHEMA,
        "case_id": case_id,
        "scenario_spec_fingerprint": fingerprint(scenario_spec),
        "initial_runtime_state_fingerprint": fingerprint(initial_runtime_state),
        "entity_catalog_fingerprint": fingerprint(entity_catalog),
        "safety_graph_fingerprint": safety_graph_fingerprint,
        "solver": {
            "mode": solver_mode,
            "adapter_id": solver_adapter_id,
            "adapter_fingerprint": solver_adapter_fingerprint,
        },
        "hardware": {
            "mode": hardware_mode,
            "config_fingerprint": fingerprint(hardware_config) if hardware_config is not None else None,
        },
    }
    out["manifest_hash"] = manifest_hash(out)
    return out


def validate_execution_manifest(manifest: Mapping[str, Any]) -> None:
    if not isinstance(manifest, Mapping):
        raise ExecutionManifestError("execution manifest must be object")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ExecutionManifestError(f"unsupported execution manifest schema: {manifest.get('schema')}")
    if not isinstance(manifest.get("case_id"), str) or not manifest.get("case_id"):
        raise ExecutionManifestError("execution manifest case_id required")
    for key in (
        "scenario_spec_fingerprint",
        "initial_runtime_state_fingerprint",
        "entity_catalog_fingerprint",
        "safety_graph_fingerprint",
        "manifest_hash",
    ):
        value = manifest.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ExecutionManifestError(f"{key} must be SHA-256 hex")
        try:
            int(value, 16)
        except ValueError as exc:
            raise ExecutionManifestError(f"{key} must be SHA-256 hex") from exc
    if manifest.get("manifest_hash") != manifest_hash(manifest):
        raise ExecutionManifestError("execution manifest hash mismatch")
    solver = manifest.get("solver")
    hardware = manifest.get("hardware")
    if not isinstance(solver, Mapping) or not isinstance(hardware, Mapping):
        raise ExecutionManifestError("solver/hardware manifest sections required")
