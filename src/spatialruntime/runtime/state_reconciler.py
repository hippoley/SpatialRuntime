from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

SCHEMA = "physical_state_reconcile_v1.7"

class ReconcileError(RuntimeError): pass
class StaleObservationError(ReconcileError): pass
class ObservationProtocolError(ReconcileError): pass


def _finite(v: Any, name: str) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError) as exc:
        raise ObservationProtocolError(f"{name} must be numeric") from exc
    if not math.isfinite(x):
        raise ObservationProtocolError(f"{name} must be finite")
    return x


def _validate_envelope(payload: dict[str, Any], *, step: int, revision: int, label: str) -> None:
    if not isinstance(payload, dict):
        raise ObservationProtocolError(f"{label} must be object")
    if int(payload.get("source_step", -1)) != int(step):
        raise StaleObservationError(f"{label} source_step mismatch: {payload.get('source_step')} != {step}")
    if int(payload.get("source_revision", -1)) != int(revision):
        raise StaleObservationError(f"{label} source_revision mismatch: {payload.get('source_revision')} != {revision}")


def reconcile(*, case_id: str, step: int, revision: int,
              solver_feedback: dict[str, Any],
              runtime_state: dict[str, Any],
              device_feedback: dict[str, Any] | None = None,
              sensor_observation: dict[str, Any] | None = None,
              policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fuse model/device/sensor evidence without silently overwriting disagreement.

    Source policy:
      * actuator state: device feedback > runtime executed state; mismatches are explicit.
      * measured environmental fields: fresh/valid sensor > solver prediction.
      * latent/unmeasured fields: solver prediction.
    """
    _validate_envelope(solver_feedback, step=step, revision=revision, label="solver_feedback")
    if device_feedback is not None:
        _validate_envelope(device_feedback, step=step, revision=revision, label="device_feedback")
    if sensor_observation is not None:
        _validate_envelope(sensor_observation, step=step, revision=revision, label="sensor_observation")

    policy = policy or {}
    pressure_tol = float(policy.get("pressure_tolerance_pa", 1.0))
    temp_tol = float(policy.get("temperature_tolerance_c", 1.0))
    airflow_tol = float(policy.get("airflow_tolerance_m3_s", 0.02))
    min_sensor_quality = float(policy.get("min_sensor_quality", 0.7))
    min_device_quality = float(policy.get("min_device_quality", 0.8))

    disagreements: list[dict[str, Any]] = []
    devices: dict[str, Any] = {}
    zones: dict[str, Any] = {}
    paths: dict[str, Any] = {}

    # Device reconciliation: runtime executed state is commanded/recorded state; feedback is observed actuator state.
    feedback_devices = (device_feedback or {}).get("devices", {})
    for entity_id, runtime in runtime_state.items():
        executed = dict(runtime.get("executed_state", {})) if isinstance(runtime, dict) else {}
        observed = feedback_devices.get(entity_id)
        resolved = dict(executed)
        runtime_source = (
            str(runtime.get("state_source", "runtime.executed_state"))
            if isinstance(runtime, dict)
            else "runtime.executed_state"
        )
        unconfirmed_target = runtime_source == "committed_target_unconfirmed"
        source = runtime_source
        confidence = 0.0 if unconfirmed_target else (0.75 if executed else 0.0)
        if observed is not None:
            if not isinstance(observed, dict):
                raise ObservationProtocolError(f"device feedback {entity_id} must be object")
            quality = _finite(observed.get("quality", 1.0), f"device {entity_id} quality")
            state = observed.get("state", {})
            if not isinstance(state, dict):
                raise ObservationProtocolError(f"device feedback {entity_id}.state must be object")
            for k, v in state.items():
                if k in executed and executed[k] != v:
                    disagreements.append({
                        "kind": "device_state_mismatch", "entity_id": entity_id, "field": k,
                        "runtime_executed": executed[k], "device_observed": v,
                        "severity": "hard" if quality >= min_device_quality else "warning",
                    })
            if quality >= min_device_quality:
                resolved.update(state)
                source = "device_feedback"
                confidence = min(1.0, quality)
            else:
                confidence = max(confidence, quality * 0.5)

        if unconfirmed_target and source != "device_feedback":
            disagreements.append({
                "kind": "unconfirmed_committed_target",
                "entity_id": entity_id,
                "runtime_target_state": executed,
                "state_source": runtime_source,
                "severity": "hard",
            })

        devices[entity_id] = {
            "state": resolved, "source": source, "confidence": round(confidence, 6),
            "runtime_executed_state": executed,
            "device_observed_state": observed.get("state") if isinstance(observed, dict) else None,
        }

    # Include feedback-only devices explicitly rather than dropping them.
    for entity_id, observed in feedback_devices.items():
        if entity_id in devices: continue
        if not isinstance(observed, dict) or not isinstance(observed.get("state"), dict):
            raise ObservationProtocolError(f"device feedback {entity_id} invalid")
        q = _finite(observed.get("quality", 1.0), f"device {entity_id} quality")
        devices[entity_id] = {"state": dict(observed["state"]), "source": "device_feedback_only", "confidence": min(1.0, q),
                              "runtime_executed_state": {}, "device_observed_state": dict(observed["state"])}
        disagreements.append({"kind":"unexpected_device_feedback","entity_id":entity_id,"severity":"warning"})

    sensor_zones = (sensor_observation or {}).get("zones", {})
    for zone_id, model in solver_feedback.get("zones", {}).items():
        if not isinstance(model, dict):
            raise ObservationProtocolError(f"solver zone {zone_id} must be object")
        s = sensor_zones.get(zone_id)
        resolved = dict(model)
        field_sources = {k:"solver" for k,v in model.items() if v is not None}
        confidence = 0.72
        if s is not None:
            if not isinstance(s, dict):
                raise ObservationProtocolError(f"sensor zone {zone_id} must be object")
            quality = _finite(s.get("quality", 1.0), f"sensor zone {zone_id} quality")
            measurements = s.get("measurements", {})
            if not isinstance(measurements, dict):
                raise ObservationProtocolError(f"sensor zone {zone_id}.measurements must be object")
            tolerances = {"pressure_pa": pressure_tol, "temperature_c": temp_tol, "airflow_in_m3_s": airflow_tol, "airflow_out_m3_s": airflow_tol}
            for field, raw in measurements.items():
                val = _finite(raw, f"sensor {zone_id}.{field}")
                if field in model and model[field] is not None and field in tolerances:
                    residual = val - float(model[field])
                    if abs(residual) > tolerances[field]:
                        disagreements.append({"kind":"model_sensor_residual","zone_id":zone_id,"field":field,
                                              "model":float(model[field]),"sensor":val,"residual":residual,
                                              "tolerance":tolerances[field],
                                              "severity":"hard" if quality >= min_sensor_quality else "warning"})
                if quality >= min_sensor_quality:
                    resolved[field] = val
                    field_sources[field] = "sensor"
            if quality >= min_sensor_quality:
                confidence = min(1.0, 0.75 + 0.25 * quality)
            else:
                confidence = max(0.4, confidence * quality)
        zones[zone_id] = {"state": resolved, "field_sources": field_sources, "confidence": round(confidence,6)}

    # Sensor-only zones are suspicious, never silently promoted to canonical state.
    for zone_id in sensor_zones:
        if zone_id not in zones:
            disagreements.append({"kind":"unknown_sensor_zone","zone_id":zone_id,"severity":"hard"})

    sensor_paths = (sensor_observation or {}).get("flow_paths", {})
    for path_id, model in solver_feedback.get("flow_paths", {}).items():
        if not isinstance(model, dict):
            raise ObservationProtocolError(f"solver path {path_id} must be object")
        resolved = dict(model)
        source = "solver"
        confidence = 0.72
        s = sensor_paths.get(path_id)
        if s is not None:
            if not isinstance(s, dict): raise ObservationProtocolError(f"sensor path {path_id} invalid")
            q = _finite(s.get("quality",1.0), f"sensor path {path_id} quality")
            meas = s.get("measurements", {})
            if not isinstance(meas, dict): raise ObservationProtocolError(f"sensor path {path_id}.measurements invalid")
            if "flow_m3_s" in meas:
                val = _finite(meas["flow_m3_s"], f"sensor path {path_id}.flow_m3_s")
                if model.get("flow_m3_s") is not None and abs(val-float(model["flow_m3_s"])) > airflow_tol:
                    disagreements.append({"kind":"model_sensor_path_residual","flow_path_id":path_id,"field":"flow_m3_s",
                                          "model":float(model["flow_m3_s"]),"sensor":val,"residual":val-float(model["flow_m3_s"]),
                                          "tolerance":airflow_tol,"severity":"hard" if q>=min_sensor_quality else "warning"})
                if q >= min_sensor_quality:
                    resolved["flow_m3_s"] = val; source = "sensor"; confidence = min(1.0,0.75+0.25*q)
        paths[path_id] = {"state":resolved,"source":source,"confidence":round(confidence,6)}

    hard = sum(1 for d in disagreements if d.get("severity") == "hard")
    warning = sum(1 for d in disagreements if d.get("severity") == "warning")
    return {
        "schema": SCHEMA, "case_id": case_id, "step": int(step), "revision": int(revision),
        "devices": devices, "zones": zones, "flow_paths": paths,
        "disagreements": disagreements,
        "summary": {"hard_disagreements": hard, "warnings": warning,
                    "safe_for_control": hard == 0},
        "policy": {"pressure_tolerance_pa":pressure_tol,"temperature_tolerance_c":temp_tol,
                   "airflow_tolerance_m3_s":airflow_tol,"min_sensor_quality":min_sensor_quality,
                   "min_device_quality":min_device_quality},
    }
