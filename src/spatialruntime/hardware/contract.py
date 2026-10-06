from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import time
from typing import Any, Callable

COMMAND_SCHEMA = "hardware_command_v2.0"
EVENT_SCHEMA = "hardware_event_v2.0"
DISPATCH_SCHEMA = "hardware_dispatch_batch_v2.0"


class HardwareContractError(RuntimeError): pass
class UnsafeDispatchError(HardwareContractError): pass
class StaleHardwareEventError(HardwareContractError): pass
class CommandConflictError(HardwareContractError): pass
class DeviceOfflineError(HardwareContractError): pass


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deterministic_command_id(*, case_id: str, source_step: int, source_revision: int,
                             entity_id: str, target_state: dict[str, Any]) -> str:
    payload = {
        "case_id": case_id,
        "source_step": int(source_step),
        "source_revision": int(source_revision),
        "entity_id": entity_id,
        "target_state": target_state,
    }
    return "cmd_" + sha256(_canonical(payload).encode()).hexdigest()[:24]


def build_dispatch_batch(*, case_id: str, commit_decision: dict[str, Any],
                         device_bindings: dict[str, dict[str, Any]],
                         now_ms: int | None = None, ack_timeout_ms: int = 1500,
                         feedback_timeout_ms: int = 5000, max_attempts: int = 3) -> dict[str, Any]:
    if commit_decision.get("schema") != "physical_commit_decision_v1.9":
        raise HardwareContractError("expected physical_commit_decision_v1.9")
    if not commit_decision.get("summary", {}).get("ready_to_dispatch", False):
        raise UnsafeDispatchError("commit decision is not ready_to_dispatch")
    if ack_timeout_ms <= 0 or feedback_timeout_ms <= 0 or max_attempts < 1:
        raise HardwareContractError("invalid retry/timeout policy")
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    source_step = int(commit_decision["source_step"])
    source_revision = int(commit_decision["source_revision"])
    commands = []
    for entity_id, decision in commit_decision.get("decisions", {}).items():
        if not str(decision.get("decision", "")).startswith("commit"):
            continue
        binding = device_bindings.get(entity_id)
        if not binding:
            raise HardwareContractError(f"missing device binding for {entity_id}")
        target = dict(decision.get("executed_state", {}))
        cmd_id = deterministic_command_id(case_id=case_id, source_step=source_step,
                                          source_revision=source_revision, entity_id=entity_id,
                                          target_state=target)
        commands.append({
            "schema": COMMAND_SCHEMA,
            "command_id": cmd_id,
            "case_id": case_id,
            "source_step": source_step,
            "source_revision": source_revision,
            "entity_id": entity_id,
            "device_id": binding["device_id"],
            "gateway_id": binding.get("gateway_id"),
            "thing_model": binding.get("thing_model"),
            "target_state": target,
            "requested_change": decision.get("requested_change"),
            "created_at_ms": now_ms,
            "ack_deadline_ms": now_ms + int(ack_timeout_ms),
            "feedback_deadline_ms": now_ms + int(feedback_timeout_ms),
            "retry_policy": {"max_attempts": int(max_attempts), "ack_timeout_ms": int(ack_timeout_ms)},
        })
    return {"schema": DISPATCH_SCHEMA, "case_id": case_id, "source_step": source_step,
            "source_revision": source_revision, "commands": commands,
            "summary": {"command_count": len(commands)}}



def _semantic_command_payload(command: dict[str, Any]) -> dict[str, Any]:
    """Fields that define command identity; transport timing is intentionally excluded."""
    return {k: command.get(k) for k in (
        "schema","command_id","case_id","source_step","source_revision",
        "entity_id","device_id","gateway_id","thing_model","target_state","requested_change"
    )}

@dataclass
class CommandRecord:
    command: dict[str, Any]
    status: str = "pending"
    attempts: int = 0
    first_dispatch_ms: int | None = None
    last_dispatch_ms: int | None = None
    ack_ms: int | None = None
    feedback_ms: int | None = None
    actual_state: dict[str, Any] | None = None
    last_error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


class CommandLedger:
    """In-memory protocol ledger. Persistence is intentionally separated for v2.1."""
    def __init__(self):
        self.records: dict[str, CommandRecord] = {}

    def register_batch(self, batch: dict[str, Any]) -> None:
        if batch.get("schema") != DISPATCH_SCHEMA:
            raise HardwareContractError("invalid dispatch batch schema")
        for cmd in batch.get("commands", []):
            cid = cmd["command_id"]
            existing = self.records.get(cid)
            if existing:
                if _canonical(_semantic_command_payload(existing.command)) != _canonical(_semantic_command_payload(cmd)):
                    raise CommandConflictError(f"command_id payload conflict: {cid}")
                continue  # exact idempotent replay
            self.records[cid] = CommandRecord(command=cmd)

    def mark_dispatched(self, command_id: str, *, now_ms: int) -> dict[str, Any]:
        rec = self._get(command_id)
        if rec.status in {"confirmed", "failed", "cancelled"}:
            return self.snapshot(command_id)
        max_attempts = int(rec.command["retry_policy"]["max_attempts"])
        if rec.attempts >= max_attempts:
            rec.status = "failed"; rec.last_error = "max_attempts_exhausted"
            return self.snapshot(command_id)
        rec.attempts += 1
        rec.first_dispatch_ms = rec.first_dispatch_ms or int(now_ms)
        rec.last_dispatch_ms = int(now_ms)
        rec.status = "dispatched"
        return self.snapshot(command_id)

    def ingest_event(self, event: dict[str, Any], *, expected_step: int, expected_revision: int) -> dict[str, Any]:
        if event.get("schema") != EVENT_SCHEMA:
            raise HardwareContractError("invalid hardware event schema")
        cid = event.get("command_id")
        rec = self._get(cid)
        cmd = rec.command
        if int(event.get("source_step", -1)) != int(expected_step) or int(event.get("source_revision", -1)) != int(expected_revision):
            raise StaleHardwareEventError("hardware event step/revision mismatch")
        if int(cmd["source_step"]) != int(expected_step) or int(cmd["source_revision"]) != int(expected_revision):
            raise StaleHardwareEventError("command no longer belongs to active revision")
        if event.get("entity_id") != cmd["entity_id"] or event.get("device_id") != cmd["device_id"]:
            raise HardwareContractError("event identity does not match command")
        digest = sha256(_canonical(event).encode()).hexdigest()
        if any(e.get("_digest") == digest for e in rec.events):
            return self.snapshot(cid)
        evt = dict(event); evt["_digest"] = digest; rec.events.append(evt)
        kind = event.get("kind")
        at = int(event.get("event_at_ms", 0))
        if kind == "ack":
            accepted = bool(event.get("accepted", False))
            if not accepted:
                rec.status = "failed"; rec.last_error = event.get("reason") or "device_rejected"
            elif rec.status not in {"confirmed", "failed"}:
                rec.ack_ms = at; rec.status = "acked"
        elif kind == "state_feedback":
            state = event.get("state")
            if not isinstance(state, dict):
                raise HardwareContractError("state_feedback.state must be object")
            rec.feedback_ms = at; rec.actual_state = dict(state); rec.status = "confirmed"
        elif kind == "offline":
            rec.status = "failed"; rec.last_error = "device_offline"
        else:
            raise HardwareContractError(f"unsupported event kind: {kind}")
        return self.snapshot(cid)

    def due_retries(self, *, now_ms: int) -> list[str]:
        due = []
        for cid, rec in self.records.items():
            if rec.status != "dispatched" or rec.last_dispatch_ms is None:
                continue
            timeout = int(rec.command["retry_policy"]["ack_timeout_ms"])
            if int(now_ms) - rec.last_dispatch_ms >= timeout:
                if rec.attempts < int(rec.command["retry_policy"]["max_attempts"]):
                    due.append(cid)
                else:
                    rec.status = "failed"; rec.last_error = "ack_timeout_max_attempts"
        return due

    def feedback_timeouts(self, *, now_ms: int) -> list[str]:
        failed = []
        for cid, rec in self.records.items():
            if rec.status != "acked":
                continue
            if int(now_ms) >= int(rec.command["feedback_deadline_ms"]):
                rec.status = "failed"; rec.last_error = "state_feedback_timeout"; failed.append(cid)
        return failed

    def build_device_feedback(self, *, case_id: str, source_step: int, source_revision: int) -> dict[str, Any]:
        devices = {}
        incomplete = []
        for cid, rec in self.records.items():
            c = rec.command
            if c["case_id"] != case_id or int(c["source_step"]) != int(source_step) or int(c["source_revision"]) != int(source_revision):
                continue
            if rec.status == "confirmed" and rec.actual_state is not None:
                devices[c["entity_id"]] = {
                    "quality": 1.0,
                    "state": rec.actual_state,
                    "device_id": c["device_id"],
                    "command_id": cid,
                    "transport_status": rec.status,
                }
            else:
                incomplete.append({"command_id": cid, "entity_id": c["entity_id"], "status": rec.status, "error": rec.last_error})
        return {"schema":"device_feedback_v2.0","case_id":case_id,"source_step":int(source_step),
                "source_revision":int(source_revision),"devices":devices,"incomplete":incomplete,
                "complete":len(incomplete)==0}

    def snapshot(self, command_id: str) -> dict[str, Any]:
        r = self._get(command_id)
        return {"command_id":command_id,"status":r.status,"attempts":r.attempts,
                "ack_ms":r.ack_ms,"feedback_ms":r.feedback_ms,"actual_state":r.actual_state,
                "last_error":r.last_error,"entity_id":r.command["entity_id"],"device_id":r.command["device_id"]}

    def _get(self, command_id: str) -> CommandRecord:
        if command_id not in self.records:
            raise HardwareContractError(f"unknown command_id: {command_id}")
        return self.records[command_id]


class MockGateway:
    """Deterministic transport fixture for contract testing, not a hardware simulator."""
    def __init__(self, *, offline_devices: set[str] | None = None):
        self.offline_devices = set(offline_devices or set())
        self.seen: set[str] = set()

    def send(self, command: dict[str, Any], *, now_ms: int) -> list[dict[str, Any]]:
        base = {"schema":EVENT_SCHEMA,"command_id":command["command_id"],"source_step":command["source_step"],
                "source_revision":command["source_revision"],"entity_id":command["entity_id"],"device_id":command["device_id"]}
        if command["device_id"] in self.offline_devices:
            return [{**base,"kind":"offline","event_at_ms":now_ms}]
        self.seen.add(command["command_id"])
        return [
            {**base,"kind":"ack","accepted":True,"event_at_ms":now_ms+10},
            {**base,"kind":"state_feedback","state":dict(command["target_state"]),"event_at_ms":now_ms+50},
        ]
