from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from spatialruntime.runtime.manifest import build_execution_manifest, validate_execution_manifest
from spatialruntime.runtime.scenario_spec import (
    _build_fixture_solver,
    validate_scenario_spec,
)
from spatialruntime.safety.dependency_graph import compile_safety_graph

PLAN_SCHEMA = "runtime_preflight_plan_v0.8"
REPORT_SCHEMA = "runtime_preflight_report_v0.8"


class PreflightError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def plan_hash(plan: Mapping[str, Any]) -> str:
    body = {k: v for k, v in plan.items() if k != "plan_hash"}
    return sha256(_canonical(body).encode()).hexdigest()


def _manifest_from_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    validate_scenario_spec(spec)
    case_id = str(spec["case_id"])
    initial = dict(spec["initial_runtime_state"])
    catalog = dict(spec["entity_catalog"])
    compiled = compile_safety_graph(spec["safety_graph"], catalog)
    solver_adapter = _build_fixture_solver(spec.get("solver"))
    hardware = spec.get("hardware")

    return build_execution_manifest(
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


def build_preflight_plan(spec: Mapping[str, Any]) -> dict[str, Any]:
    manifest = _manifest_from_spec(spec)
    out = {
        "schema": PLAN_SCHEMA,
        "case_id": manifest["case_id"],
        "scenario_schema": spec.get("schema"),
        "requested_steps": len(spec.get("steps") or []),
        "execution_manifest": manifest,
    }
    out["plan_hash"] = plan_hash(out)
    return out


def validate_preflight_plan(plan: Mapping[str, Any]) -> None:
    if not isinstance(plan, Mapping):
        raise PreflightError("preflight plan must be object")
    if plan.get("schema") != PLAN_SCHEMA:
        raise PreflightError(f"unsupported preflight plan schema: {plan.get('schema')}")
    value = plan.get("plan_hash")
    if not isinstance(value, str) or len(value) != 64:
        raise PreflightError("plan_hash must be SHA-256 hex")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PreflightError("plan_hash must be SHA-256 hex") from exc
    if value != plan_hash(plan):
        raise PreflightError("preflight plan hash mismatch")
    manifest = plan.get("execution_manifest")
    if not isinstance(manifest, Mapping):
        raise PreflightError("execution_manifest required")
    try:
        validate_execution_manifest(manifest)
    except Exception as exc:
        raise PreflightError(str(exc)) from exc
    if plan.get("case_id") != manifest.get("case_id"):
        raise PreflightError("preflight plan case_id mismatch")


def _drift_dimensions(approved: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    drift = []
    scalar_keys = [
        ("scenario_spec_fingerprint", "scenario_spec"),
        ("initial_runtime_state_fingerprint", "initial_runtime_state"),
        ("entity_catalog_fingerprint", "entity_catalog"),
        ("safety_graph_fingerprint", "safety_graph"),
    ]
    for key, label in scalar_keys:
        if approved.get(key) != current.get(key):
            drift.append(label)

    a_solver = approved.get("solver") or {}
    c_solver = current.get("solver") or {}
    if a_solver.get("mode") != c_solver.get("mode"):
        drift.append("solver.mode")
    if a_solver.get("adapter_id") != c_solver.get("adapter_id"):
        drift.append("solver.adapter_id")
    if a_solver.get("adapter_fingerprint") != c_solver.get("adapter_fingerprint"):
        drift.append("solver.adapter_fingerprint")

    a_hw = approved.get("hardware") or {}
    c_hw = current.get("hardware") or {}
    if a_hw.get("mode") != c_hw.get("mode"):
        drift.append("hardware.mode")
    if a_hw.get("config_fingerprint") != c_hw.get("config_fingerprint"):
        drift.append("hardware.config")
    return drift


def verify_preflight_plan(plan: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    validate_preflight_plan(plan)
    current = _manifest_from_spec(spec)
    approved = plan["execution_manifest"]
    drift = _drift_dimensions(approved, current)
    if approved.get("manifest_hash") != current.get("manifest_hash"):
        if not drift:
            drift.append("execution_manifest")
        raise PreflightError("preflight drift detected: " + ", ".join(drift))

    return {
        "schema": REPORT_SCHEMA,
        "valid": True,
        "case_id": current["case_id"],
        "plan_hash": plan["plan_hash"],
        "manifest_hash": current["manifest_hash"],
        "drift": [],
    }


def load_preflight_plan(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PreflightError(f"preflight plan not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise PreflightError(f"invalid preflight plan JSON: {p}") from exc
    if not isinstance(data, dict):
        raise PreflightError("preflight plan root must be object")
    return data


def save_preflight_plan(plan: Mapping[str, Any], path: str | Path) -> Path:
    validate_preflight_plan(plan)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return p
