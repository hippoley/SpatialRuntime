from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from spatialruntime.hardware.contract import HardwareContractError

HEALTH_SCHEMA = "device_health_snapshot_v2.6"

class DeviceHealthError(HardwareContractError): pass
class DeviceHealthBlocked(DeviceHealthError): pass


@dataclass(frozen=True)
class HealthPolicy:
    require_online: bool = True
    block_on_fault: bool = True
    min_quality: float = 0.8


def evaluate_device_health(*, telemetry: Mapping[str, Any], profile: Mapping[str, Any],
                           policy: HealthPolicy | None = None) -> dict[str, Any]:
    policy = policy or HealthPolicy()
    q = float(telemetry.get("quality", 1.0))
    if not (0.0 <= q <= 1.0):
        raise DeviceHealthError("invalid telemetry quality")
    health = telemetry.get("health", {})
    if not isinstance(health, Mapping):
        raise DeviceHealthError("telemetry health must be object")
    online = health.get("online")
    fault_code = health.get("fault_code")
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if q < policy.min_quality:
        blockers.append({"kind": "low_telemetry_quality", "quality": q, "required": policy.min_quality})
    if policy.require_online:
        if online is False:
            blockers.append({"kind": "device_offline"})
        elif online is None:
            warnings.append({"kind": "online_status_unknown"})
    blocking_codes = set(profile.get("blocking_fault_codes", []))
    if policy.block_on_fault and fault_code in blocking_codes:
        blockers.append({"kind": "blocking_fault", "fault_code": fault_code})
    elif fault_code not in (None, 0, "0", "OK", "ok"):
        warnings.append({"kind": "nonblocking_or_unknown_fault", "fault_code": fault_code})
    return {
        "schema": HEALTH_SCHEMA,
        "device_id": telemetry.get("device_id"),
        "sequence": telemetry.get("sequence"),
        "observed_at_ms": telemetry.get("observed_at_ms"),
        "online": online,
        "fault_code": fault_code,
        "quality": q,
        "blocking": bool(blockers),
        "blockers": blockers,
        "warnings": warnings,
    }


def assert_device_healthy(*, telemetry: Mapping[str, Any], profile: Mapping[str, Any],
                          policy: HealthPolicy | None = None) -> dict[str, Any]:
    snap = evaluate_device_health(telemetry=telemetry, profile=profile, policy=policy)
    if snap["blocking"]:
        raise DeviceHealthBlocked(str(snap["blockers"]))
    return snap
