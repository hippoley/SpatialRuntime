from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable, Mapping
import math

from spatialruntime.hardware.contract import HardwareContractError, _canonical
from spatialruntime.hardware.gateway import TransportResponse

PROFILE_SCHEMA = "thingmodel_binding_profile_v2.5"
DESCRIPTOR_SCHEMA = "thingmodel_device_descriptor_v2.5"


class ThingModelBindingError(HardwareContractError): pass
class ThingModelDescriptorError(ThingModelBindingError): pass
class ThingModelCodecError(ThingModelBindingError): pass
class ThingModelBackendError(ThingModelBindingError): pass


def _finite(v: Any, label: str) -> float:
    try:
        x = float(v)
    except Exception as exc:
        raise ThingModelCodecError(f"{label} must be numeric") from exc
    if not math.isfinite(x):
        raise ThingModelCodecError(f"{label} must be finite")
    return x


def binding_profile_fingerprint(profile: Mapping[str, Any]) -> str:
    body = {k: profile.get(k) for k in (
        "schema", "profile_id", "thing_model", "logical_to_native", "native_to_logical",
        "blocking_fault_codes", "online_property", "fault_property",
    )}
    return sha256(_canonical(body).encode()).hexdigest()


def normalize_profile(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ThingModelBindingError("profile must be object")
    profile_id = raw.get("profile_id")
    thing_model = raw.get("thing_model")
    if not isinstance(profile_id, str) or not profile_id:
        raise ThingModelBindingError("profile_id required")
    if not isinstance(thing_model, str) or not thing_model:
        raise ThingModelBindingError("thing_model required")
    bindings = raw.get("properties")
    if not isinstance(bindings, Mapping) or not bindings:
        raise ThingModelBindingError("properties mapping required")

    logical_to_native: dict[str, dict[str, Any]] = {}
    native_to_logical: dict[str, str] = {}
    for logical, spec in bindings.items():
        if not isinstance(logical, str) or not logical or not isinstance(spec, Mapping):
            raise ThingModelBindingError("invalid property binding")
        native = spec.get("native")
        if not isinstance(native, str) or not native:
            raise ThingModelBindingError(f"native property required for {logical}")
        if native in native_to_logical:
            raise ThingModelBindingError(f"native property bound twice: {native}")
        codec = spec.get("codec", "identity")
        if codec not in {"identity", "linear"}:
            raise ThingModelBindingError(f"unsupported codec for {logical}: {codec}")
        entry = {"native": native, "codec": codec}
        if codec == "linear":
            scale = _finite(spec.get("scale"), f"{logical}.scale")
            offset = _finite(spec.get("offset", 0.0), f"{logical}.offset")
            if scale == 0:
                raise ThingModelBindingError(f"{logical}.scale cannot be zero")
            entry.update({"scale": scale, "offset": offset})
        if "min" in spec:
            entry["min"] = _finite(spec["min"], f"{logical}.min")
        if "max" in spec:
            entry["max"] = _finite(spec["max"], f"{logical}.max")
        if "min" in entry and "max" in entry and entry["min"] > entry["max"]:
            raise ThingModelBindingError(f"{logical} min > max")
        logical_to_native[logical] = entry
        native_to_logical[native] = logical

    blocking_fault_codes = raw.get("blocking_fault_codes", [])
    if not isinstance(blocking_fault_codes, list):
        raise ThingModelBindingError("blocking_fault_codes must be list")
    out = {
        "schema": PROFILE_SCHEMA,
        "profile_id": profile_id,
        "thing_model": thing_model,
        "logical_to_native": logical_to_native,
        "native_to_logical": native_to_logical,
        "online_property": raw.get("online_property"),
        "fault_property": raw.get("fault_property"),
        "blocking_fault_codes": list(blocking_fault_codes),
    }
    out["fingerprint"] = binding_profile_fingerprint(out)
    return out


def _encode(logical: str, value: Any, spec: Mapping[str, Any]) -> Any:
    if isinstance(value, bool):
        if spec.get("codec") != "identity":
            raise ThingModelCodecError(f"boolean {logical} only supports identity codec")
        return value
    if spec.get("codec") == "identity":
        if isinstance(value, (int, float)):
            x = _finite(value, logical)
            if "min" in spec and x < float(spec["min"]):
                raise ThingModelCodecError(f"{logical} below minimum")
            if "max" in spec and x > float(spec["max"]):
                raise ThingModelCodecError(f"{logical} above maximum")
        return value
    x = _finite(value, logical)
    if "min" in spec and x < float(spec["min"]):
        raise ThingModelCodecError(f"{logical} below minimum")
    if "max" in spec and x > float(spec["max"]):
        raise ThingModelCodecError(f"{logical} above maximum")
    return x * float(spec["scale"]) + float(spec["offset"])


def _decode(logical: str, value: Any, spec: Mapping[str, Any]) -> Any:
    if spec.get("codec") == "identity":
        return value
    x = _finite(value, spec["native"])
    return (x - float(spec["offset"])) / float(spec["scale"])


def encode_state(logical_state: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(logical_state, Mapping) or not logical_state:
        raise ThingModelCodecError("logical_state must be non-empty object")
    out: dict[str, Any] = {}
    bindings = profile["logical_to_native"]
    for logical, value in logical_state.items():
        spec = bindings.get(logical)
        if spec is None:
            raise ThingModelCodecError(f"no native binding for logical property: {logical}")
        out[spec["native"]] = _encode(logical, value, spec)
    return out


def decode_state(native_state: Mapping[str, Any], profile: Mapping[str, Any], *, include_unbound: bool = False) -> dict[str, Any]:
    if not isinstance(native_state, Mapping):
        raise ThingModelCodecError("native_state must be object")
    out: dict[str, Any] = {}
    reverse = profile["native_to_logical"]
    for native, value in native_state.items():
        logical = reverse.get(native)
        if logical is None:
            if include_unbound:
                out[native] = value
            continue
        spec = profile["logical_to_native"][logical]
        out[logical] = _decode(logical, value, spec)
    return out


@dataclass(frozen=True)
class BackendResult:
    status_code: int
    body: Mapping[str, Any]


class ThingModelBackendBinding:
    """Adapts an existing ThingModelBackend to the generic gateway transport contract.

    All vendor/backend details are injected. This module never guesses endpoints, topics,
    authentication or vendor property names.
    """
    def __init__(self, *, gateway_id: str, profile: Mapping[str, Any],
                 describe_device: Callable[[str], BackendResult],
                 write_properties: Callable[[str, Mapping[str, Any], str], BackendResult]):
        self.gateway_id = gateway_id
        self.profile = normalize_profile(profile) if profile.get("schema") != PROFILE_SCHEMA else dict(profile)
        self._describe_device = describe_device
        self._write_properties = write_properties

    def discover_transport(self, req: dict[str, Any]) -> TransportResponse:
        dev = req["device_id"]
        result = self._describe_device(dev)
        if result.status_code < 200 or result.status_code >= 300:
            return TransportResponse(result.status_code, result.body)
        desc = result.body
        if not isinstance(desc, Mapping):
            return TransportResponse(502, {"error": "descriptor_not_object"})
        if desc.get("device_id") not in (None, dev):
            return TransportResponse(502, {"error": "descriptor_device_mismatch"})
        if desc.get("thing_model") != self.profile["thing_model"]:
            return TransportResponse(409, {"error": "thing_model_mismatch", "actual": desc.get("thing_model")})
        native_writable = set(desc.get("writable_properties", []))
        native_readable = set(desc.get("readable_properties", []))
        logical_writable = sorted(
            logical for logical, spec in self.profile["logical_to_native"].items()
            if spec["native"] in native_writable
        )
        logical_readable = sorted(
            logical for logical, spec in self.profile["logical_to_native"].items()
            if spec["native"] in native_readable
        )
        body = {
            "device_id": dev,
            "thing_model": self.profile["thing_model"],
            "writable_properties": logical_writable,
            "readable_properties": logical_readable,
            "supports_command_id": bool(desc.get("supports_command_id", False)),
            "supports_ack": bool(desc.get("supports_ack", False)),
            "supports_state_feedback": bool(desc.get("supports_state_feedback", False)),
            "binding_profile_id": self.profile["profile_id"],
            "binding_profile_fingerprint": self.profile["fingerprint"],
        }
        return TransportResponse(200, body)

    def command_transport(self, req: dict[str, Any]) -> TransportResponse:
        try:
            native_target = encode_state(req["target_state"], self.profile)
        except ThingModelBindingError as exc:
            return TransportResponse(422, {"error": type(exc).__name__, "message": str(exc)})
        result = self._write_properties(req["device_id"], native_target, req["command_id"])
        if result.status_code < 200 or result.status_code >= 300:
            return TransportResponse(result.status_code, result.body)
        body = result.body
        if not isinstance(body, Mapping):
            return TransportResponse(502, {"error": "write_response_not_object"})
        status = body.get("status", "accepted")
        out: dict[str, Any] = {
            "command_id": body.get("command_id", req["command_id"]),
            "status": status,
        }
        if body.get("reason") is not None:
            out["reason"] = body["reason"]
        if body.get("event_at_ms") is not None:
            out["event_at_ms"] = body["event_at_ms"]
        if body.get("state_at_ms") is not None:
            out["state_at_ms"] = body["state_at_ms"]
        if body.get("state") is not None:
            try:
                out["state"] = decode_state(body["state"], self.profile)
            except ThingModelBindingError as exc:
                return TransportResponse(502, {"error": type(exc).__name__, "message": str(exc)})
        return TransportResponse(200, out)

    def normalize_telemetry(self, raw: Mapping[str, Any], *, source_step: int, source_revision: int) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            raise ThingModelDescriptorError("telemetry must be object")
        dev = raw.get("device_id")
        state = raw.get("state")
        if not isinstance(dev, str) or not dev or not isinstance(state, Mapping):
            raise ThingModelDescriptorError("telemetry device_id/state required")
        logical = decode_state(state, self.profile)
        health: dict[str, Any] = {}
        online_prop = self.profile.get("online_property")
        fault_prop = self.profile.get("fault_property")
        if online_prop and online_prop in state:
            health["online"] = bool(state[online_prop])
        if fault_prop and fault_prop in state:
            health["fault_code"] = state[fault_prop]
        return {
            "schema": "device_telemetry_v2.4",
            "source_step": int(source_step),
            "source_revision": int(source_revision),
            "device_id": dev,
            "sequence": int(raw["sequence"]),
            "observed_at_ms": int(raw["observed_at_ms"]),
            "state": logical,
            "quality": float(raw.get("quality", 1.0)),
            "command_id": raw.get("command_id"),
            "health": health,
            "binding_profile_id": self.profile["profile_id"],
            "binding_profile_fingerprint": self.profile["fingerprint"],
        }
