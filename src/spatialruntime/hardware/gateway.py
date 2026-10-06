from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from spatialruntime.hardware.contract import EVENT_SCHEMA, HardwareContractError, DeviceOfflineError, _canonical

CAPABILITY_SCHEMA = "gateway_capability_v2.2"
TRANSPORT_REQUEST_SCHEMA = "gateway_transport_request_v2.2"
TRANSPORT_RESPONSE_SCHEMA = "gateway_transport_response_v2.2"


class GatewayAdapterError(HardwareContractError): pass
class GatewayAuthenticationError(GatewayAdapterError): pass
class GatewayProtocolError(GatewayAdapterError): pass
class DeviceCapabilityError(GatewayAdapterError): pass
class GatewayTransportError(GatewayAdapterError): pass


def capability_fingerprint(capability: Mapping[str, Any]) -> str:
    body = {k: capability.get(k) for k in (
        "schema", "gateway_id", "device_id", "thing_model", "writable_properties",
        "readable_properties", "supports_command_id", "supports_ack", "supports_state_feedback"
    )}
    return sha256(_canonical(body).encode()).hexdigest()


def normalize_capability(raw: Mapping[str, Any], *, gateway_id: str, device_id: str) -> dict[str, Any]:
    if raw.get("device_id") not in (None, device_id):
        raise GatewayProtocolError("capability device_id mismatch")
    writable = raw.get("writable_properties", [])
    readable = raw.get("readable_properties", [])
    if not isinstance(writable, list) or not all(isinstance(x, str) and x for x in writable):
        raise GatewayProtocolError("writable_properties must be string list")
    if not isinstance(readable, list) or not all(isinstance(x, str) and x for x in readable):
        raise GatewayProtocolError("readable_properties must be string list")
    out = {
        "schema": CAPABILITY_SCHEMA,
        "gateway_id": gateway_id,
        "device_id": device_id,
        "thing_model": raw.get("thing_model"),
        "writable_properties": sorted(set(writable)),
        "readable_properties": sorted(set(readable)),
        "supports_command_id": bool(raw.get("supports_command_id", False)),
        "supports_ack": bool(raw.get("supports_ack", False)),
        "supports_state_feedback": bool(raw.get("supports_state_feedback", False)),
    }
    out["fingerprint"] = capability_fingerprint(out)
    return out


def validate_command_against_capability(command: Mapping[str, Any], capability: Mapping[str, Any]) -> None:
    if command.get("device_id") != capability.get("device_id"):
        raise DeviceCapabilityError("command/capability device mismatch")
    if command.get("gateway_id") not in (None, capability.get("gateway_id")):
        raise DeviceCapabilityError("command/capability gateway mismatch")
    target = command.get("target_state")
    if not isinstance(target, dict) or not target:
        raise DeviceCapabilityError("target_state must be non-empty object")
    allowed = set(capability.get("writable_properties", []))
    unknown = sorted(set(target) - allowed)
    if unknown:
        raise DeviceCapabilityError(f"target properties not writable: {unknown}")
    if not capability.get("supports_command_id", False):
        raise DeviceCapabilityError("gateway/device does not advertise command_id idempotency")
    if not capability.get("supports_ack", False):
        raise DeviceCapabilityError("gateway/device does not advertise ACK support")
    if not capability.get("supports_state_feedback", False):
        raise DeviceCapabilityError("gateway/device does not advertise state feedback")


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    body: Mapping[str, Any]


class ThingModelGatewayAdapter:
    """Adapter over an injected transport callable.

    The transport callable is deliberately abstract: production code can bind HTTP/MQTT/RPC,
    while tests use deterministic fixtures. No endpoint or vendor payload shape is guessed here.
    """
    def __init__(self, *, gateway_id: str,
                 discover_transport: Callable[[dict[str, Any]], TransportResponse],
                 command_transport: Callable[[dict[str, Any]], TransportResponse]):
        self.gateway_id = gateway_id
        self._discover_transport = discover_transport
        self._command_transport = command_transport
        self._capabilities: dict[str, dict[str, Any]] = {}

    def discover(self, device_id: str) -> dict[str, Any]:
        req = {"schema": TRANSPORT_REQUEST_SCHEMA, "operation": "discover",
               "gateway_id": self.gateway_id, "device_id": device_id}
        resp = self._discover_transport(req)
        self._raise_for_transport(resp, operation="discover")
        cap = normalize_capability(resp.body, gateway_id=self.gateway_id, device_id=device_id)
        self._capabilities[device_id] = cap
        return cap

    def get_cached_capability(self, device_id: str) -> dict[str, Any] | None:
        return self._capabilities.get(device_id)

    def send(self, command: dict[str, Any], *, now_ms: int) -> list[dict[str, Any]]:
        if command.get("gateway_id") not in (None, self.gateway_id):
            raise GatewayProtocolError("command routed to wrong gateway")
        device_id = command["device_id"]
        cap = self._capabilities.get(device_id) or self.discover(device_id)
        validate_command_against_capability(command, cap)
        req = {
            "schema": TRANSPORT_REQUEST_SCHEMA,
            "operation": "command",
            "gateway_id": self.gateway_id,
            "device_id": device_id,
            "command_id": command["command_id"],
            "source_step": command["source_step"],
            "source_revision": command["source_revision"],
            "target_state": dict(command["target_state"]),
        }
        resp = self._command_transport(req)
        self._raise_for_transport(resp, operation="command")
        return self._normalize_command_response(command, resp.body, now_ms=now_ms)

    def _raise_for_transport(self, resp: TransportResponse, *, operation: str) -> None:
        if resp.status_code in (401, 403):
            raise GatewayAuthenticationError(f"gateway authentication failed during {operation}")
        if resp.status_code in (404, 410, 503):
            raise DeviceOfflineError(f"device/gateway unavailable during {operation}")
        if resp.status_code < 200 or resp.status_code >= 300:
            raise GatewayTransportError(f"gateway transport status {resp.status_code} during {operation}")
        if not isinstance(resp.body, Mapping):
            raise GatewayProtocolError("gateway response body must be object")

    def _normalize_command_response(self, command: Mapping[str, Any], body: Mapping[str, Any], *, now_ms: int) -> list[dict[str, Any]]:
        if body.get("command_id") not in (None, command["command_id"]):
            raise GatewayProtocolError("gateway command_id mismatch")
        status = body.get("status")
        if status not in {"accepted", "rejected", "offline"}:
            raise GatewayProtocolError(f"unsupported gateway status: {status}")
        base = {
            "schema": EVENT_SCHEMA,
            "command_id": command["command_id"],
            "source_step": command["source_step"],
            "source_revision": command["source_revision"],
            "entity_id": command["entity_id"],
            "device_id": command["device_id"],
        }
        at = int(body.get("event_at_ms", now_ms))
        if status == "offline":
            return [{**base, "kind": "offline", "event_at_ms": at}]
        ack = {**base, "kind": "ack", "accepted": status == "accepted", "event_at_ms": at}
        if status == "rejected":
            ack["reason"] = body.get("reason") or "gateway_rejected"
            return [ack]
        events = [ack]
        state = body.get("state")
        if state is not None:
            if not isinstance(state, Mapping):
                raise GatewayProtocolError("gateway state must be object")
            events.append({**base, "kind": "state_feedback", "state": dict(state),
                           "event_at_ms": int(body.get("state_at_ms", at))})
        return events


class DeterministicGatewayFixture:
    """Transport fixture emulating a ThingModel/Gateway payload, not real hardware."""
    def __init__(self, *, capabilities: dict[str, dict[str, Any]], offline: set[str] | None = None,
                 reject: set[str] | None = None, state_overrides: dict[str, dict[str, Any]] | None = None):
        self.capabilities = capabilities
        self.offline = set(offline or ())
        self.reject = set(reject or ())
        self.state_overrides = dict(state_overrides or {})
        self.command_calls: list[dict[str, Any]] = []

    def discover_transport(self, req: dict[str, Any]) -> TransportResponse:
        dev = req["device_id"]
        if dev in self.offline or dev not in self.capabilities:
            return TransportResponse(404, {"error": "offline"})
        return TransportResponse(200, {"device_id": dev, **self.capabilities[dev]})

    def command_transport(self, req: dict[str, Any]) -> TransportResponse:
        self.command_calls.append(dict(req))
        dev = req["device_id"]
        if dev in self.offline:
            return TransportResponse(503, {"error": "offline"})
        if dev in self.reject:
            return TransportResponse(200, {"command_id": req["command_id"], "status": "rejected", "reason": "fixture_reject"})
        state = self.state_overrides.get(dev, req["target_state"])
        return TransportResponse(200, {"command_id": req["command_id"], "status": "accepted", "state": state})
