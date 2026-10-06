from __future__ import annotations
from typing import Any
from spatialruntime.hardware.gateway import validate_command_against_capability

class ReviewedGateway:
    """Wraps a gateway adapter and requires the current discovered capability to match reviewed lineage."""
    def __init__(self, gateway: Any, capability_registry: Any):
        self.gateway=gateway; self.registry=capability_registry

    def send(self, command: dict, *, now_ms: int):
        cap=self.gateway.discover(command["device_id"])
        self.registry.verify(cap)
        validate_command_against_capability(command,cap)
        return self.gateway.send(command,now_ms=now_ms)
