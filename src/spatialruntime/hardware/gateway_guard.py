from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from spatialruntime.hardware.contract import HardwareContractError

SCHEMA = "gateway_guard_v2.4"

class GatewayGuardError(HardwareContractError): pass
class CapabilityVerificationError(GatewayGuardError): pass
class TelemetryVerificationError(GatewayGuardError): pass

@dataclass
class GatewayGuard:
    capability_registry: Any
    telemetry_guard: Any
    device_health_provider: Callable[[str], dict[str, Any]] | None = None
    _device_health: dict[str, dict[str, Any]] = field(default_factory=dict)

    def verify_capability(self, capability: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.capability_registry.verify(capability)
        except Exception as exc:
            raise CapabilityVerificationError(str(exc)) from exc

    def verify_telemetry(self, telemetry: dict[str, Any], *, now_ms: int, expected_step: int, expected_revision: int) -> dict[str, Any]:
        try:
            return self.telemetry_guard.ingest(telemetry, now_ms=now_ms, expected_step=expected_step, expected_revision=expected_revision)
        except Exception as exc:
            raise TelemetryVerificationError(str(exc)) from exc

    def device_health(self, device_id: str) -> dict[str, Any]:
        if self.device_health_provider is not None:
            return dict(self.device_health_provider(device_id))
        return dict(self._device_health.get(device_id, {}))

    def update_device_health(self, device_id: str, health: dict[str, Any]) -> None:
        self._device_health[device_id] = dict(health)
