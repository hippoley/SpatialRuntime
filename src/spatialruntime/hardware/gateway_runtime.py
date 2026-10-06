from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

FROM_GATEWAY_SCHEMA = "gateway_runtime_v2.4"

class GatewayRuntimeError(RuntimeError): pass

@dataclass
class GatewayRuntime:
    adapter: Any
    guard: Any
    command_ledger: Any
    device_feedback_transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None

    def dispatch_command(self, command: dict[str, Any], *, now_ms: int) -> dict[str, Any]:
        if command.get("schema") != "hardware_command_v2.0":
            raise GatewayRuntimeError("invalid hardware command schema")
        cap = self.adapter.discover(command["device_id"])
        self.guard.verify_capability(cap)
        responses = self.adapter.send(command, now_ms=now_ms)
        for evt in responses:
            self.command_ledger.ingest_event(evt, expected_step=command["source_step"],
                                             expected_revision=command["source_revision"])
        return self.command_ledger.snapshot(command["command_id"])

    def ingest_telemetry(self, telemetry: dict[str, Any], *, now_ms: int, expected_step: int, expected_revision: int) -> dict[str, Any]:
        verified = self.guard.verify_telemetry(telemetry, now_ms=now_ms, expected_step=expected_step,
                                               expected_revision=expected_revision)
        if self.device_feedback_transform is not None:
            verified = self.device_feedback_transform(verified)
        return verified
