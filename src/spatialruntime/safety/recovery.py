from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping

SCHEMA = "fault_recovery_state_v2.8"
ACTION_SCHEMA = "fault_recovery_action_v2.8"

class RecoveryError(RuntimeError): pass
class RecoveryBlocked(RecoveryError): pass

@dataclass
class RecoveryPolicy:
    obstruction_fault_codes: set[int] = field(default_factory=set)
    max_recovery_attempts: int = 1
    release_delta: float = 0.10
    min_position: float = 0.0
    max_position: float = 1.0
    require_stop_capability: bool = True
    require_position_capability: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "RecoveryPolicy":
        d = dict(data or {})
        return cls(
            obstruction_fault_codes={int(x) for x in d.get("obstruction_fault_codes", [])},
            max_recovery_attempts=int(d.get("max_recovery_attempts", 1)),
            release_delta=float(d.get("release_delta", .10)),
            min_position=float(d.get("min_position", 0.0)),
            max_position=float(d.get("max_position", 1.0)),
            require_stop_capability=bool(d.get("require_stop_capability", True)),
            require_position_capability=bool(d.get("require_position_capability", True)),
        )


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _fault_code(telemetry: Mapping[str, Any]) -> int | None:
    h = telemetry.get("health") or {}
    v = h.get("fault_code")
    return None if v is None else int(v)


def _open_ratio(telemetry: Mapping[str, Any]) -> float | None:
    s = telemetry.get("state") or {}
    v = s.get("open_ratio")
    return None if v is None else float(v)


def _supports(capability: Mapping[str, Any], logical: str) -> bool:
    writable = set(capability.get("writable_properties") or [])
    actions = set(capability.get("actions") or [])
    return logical in writable or logical in actions


class RecoveryStateMachine:
    """Deterministic, bounded obstruction/fault recovery.

    It never infers fault semantics. Only explicitly configured obstruction codes can
    trigger automatic release/retry. Unknown faults are latched for manual service.
    """
    def __init__(self, *, entity_id: str, device_id: str, policy: RecoveryPolicy | Mapping[str, Any] | None = None):
        self.entity_id = entity_id
        self.device_id = device_id
        self.policy = policy if isinstance(policy, RecoveryPolicy) else RecoveryPolicy.from_mapping(policy)
        if self.policy.max_recovery_attempts < 0:
            raise RecoveryError("max_recovery_attempts must be >= 0")
        if not (0 < self.policy.release_delta <= 1):
            raise RecoveryError("release_delta must be in (0,1]")
        self.state = "nominal"
        self.recovery_attempts = 0
        self.latched_fault_code: int | None = None
        self.last_command_id: str | None = None
        self.last_target_ratio: float | None = None
        self.last_observed_ratio: float | None = None
        self.history: list[dict[str, Any]] = []

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA, "entity_id": self.entity_id, "device_id": self.device_id,
            "state": self.state, "recovery_attempts": self.recovery_attempts,
            "latched_fault_code": self.latched_fault_code,
            "last_command_id": self.last_command_id,
            "last_target_ratio": self.last_target_ratio,
            "last_observed_ratio": self.last_observed_ratio,
        }

    def observe(self, *, source_step: int, source_revision: int,
                command: Mapping[str, Any] | None,
                telemetry: Mapping[str, Any],
                convergence: Mapping[str, Any] | None,
                capability: Mapping[str, Any]) -> dict[str, Any]:
        if telemetry.get("device_id") != self.device_id:
            raise RecoveryError("telemetry device mismatch")
        code = _fault_code(telemetry)
        observed = _open_ratio(telemetry)
        if observed is not None and not (self.policy.min_position <= observed <= self.policy.max_position):
            raise RecoveryError("observed open_ratio outside policy bounds")
        self.last_observed_ratio = observed
        if command:
            if command.get("device_id") != self.device_id or command.get("entity_id") != self.entity_id:
                raise RecoveryError("command identity mismatch")
            self.last_command_id = command.get("command_id")
            target = (command.get("target_state") or {}).get("open_ratio")
            self.last_target_ratio = None if target is None else float(target)

        converged = bool((convergence or {}).get("converged", False))
        actions: list[dict[str, Any]] = []
        blockers: list[str] = []

        if code in (None, 0) and converged:
            self.state = "nominal"
            self.latched_fault_code = None
            self.recovery_attempts = 0
            result = self._result(source_step, source_revision, actions, blockers)
            self.history.append(result); return result

        if code not in (None, 0) and code not in self.policy.obstruction_fault_codes:
            self.state = "manual_service_required"
            self.latched_fault_code = code
            blockers.append("unknown_or_nonrecoverable_fault")
            result = self._result(source_step, source_revision, actions, blockers)
            self.history.append(result); return result

        # Non-convergence without an explicit configured obstruction code is not
        # enough evidence to move hardware automatically.
        if code not in self.policy.obstruction_fault_codes:
            self.state = "hold_for_diagnosis"
            blockers.append("nonconvergence_without_obstruction_fault")
            result = self._result(source_step, source_revision, actions, blockers)
            self.history.append(result); return result

        self.latched_fault_code = code
        self.state = "obstruction_detected"
        if self.recovery_attempts >= self.policy.max_recovery_attempts:
            self.state = "manual_service_required"
            blockers.append("recovery_attempts_exhausted")
            result = self._result(source_step, source_revision, actions, blockers)
            self.history.append(result); return result

        if self.policy.require_stop_capability and not _supports(capability, "stop"):
            self.state = "manual_service_required"
            blockers.append("stop_capability_missing")
            result = self._result(source_step, source_revision, actions, blockers)
            self.history.append(result); return result

        if self.policy.require_position_capability and not _supports(capability, "open_ratio"):
            self.state = "manual_service_required"
            blockers.append("position_capability_missing")
            result = self._result(source_step, source_revision, actions, blockers)
            self.history.append(result); return result

        actions.append(self._action(source_step, source_revision, "stop", {}, "obstruction_stop"))

        # Release opposite the direction of the failed target, based only on the
        # last observed position and target. If direction cannot be determined, stop.
        if observed is None or self.last_target_ratio is None:
            self.state = "stopped_awaiting_manual_release"
            blockers.append("release_direction_unknown")
            result = self._result(source_step, source_revision, actions, blockers)
            self.history.append(result); return result

        if self.last_target_ratio > observed:
            release = _clamp(observed - self.policy.release_delta, self.policy.min_position, self.policy.max_position)
        elif self.last_target_ratio < observed:
            release = _clamp(observed + self.policy.release_delta, self.policy.min_position, self.policy.max_position)
        else:
            self.state = "stopped_awaiting_manual_release"
            blockers.append("release_direction_unknown")
            result = self._result(source_step, source_revision, actions, blockers)
            self.history.append(result); return result

        self.recovery_attempts += 1
        actions.append(self._action(source_step, source_revision, "set_state", {"open_ratio": release}, "bounded_reverse_release"))
        self.state = "release_pending"
        result = self._result(source_step, source_revision, actions, blockers)
        self.history.append(result); return result

    def confirm_release(self, *, source_step: int, source_revision: int,
                        telemetry: Mapping[str, Any], capability: Mapping[str, Any]) -> dict[str, Any]:
        if self.state != "release_pending":
            raise RecoveryError("release confirmation received outside release_pending")
        code = _fault_code(telemetry)
        observed = _open_ratio(telemetry)
        actions: list[dict[str, Any]] = []
        blockers: list[str] = []
        if code not in (None, 0):
            self.state = "manual_service_required"
            blockers.append("fault_persists_after_release")
        elif self.last_target_ratio is None:
            self.state = "manual_service_required"
            blockers.append("original_target_missing")
        elif not _supports(capability, "open_ratio"):
            self.state = "manual_service_required"
            blockers.append("position_capability_missing")
        else:
            actions.append(self._action(source_step, source_revision, "set_state", {"open_ratio": self.last_target_ratio}, "single_retry_original_target"))
            self.state = "retry_pending"
        self.last_observed_ratio = observed
        result = self._result(source_step, source_revision, actions, blockers)
        self.history.append(result); return result

    def confirm_retry(self, *, source_step: int, source_revision: int,
                      telemetry: Mapping[str, Any], convergence: Mapping[str, Any]) -> dict[str, Any]:
        if self.state != "retry_pending":
            raise RecoveryError("retry confirmation received outside retry_pending")
        code = _fault_code(telemetry)
        self.last_observed_ratio = _open_ratio(telemetry)
        actions: list[dict[str, Any]] = []
        blockers: list[str] = []
        if code in (None, 0) and bool(convergence.get("converged", False)):
            self.state = "nominal"
            self.latched_fault_code = None
            self.recovery_attempts = 0
        else:
            self.state = "manual_service_required"
            self.latched_fault_code = code
            blockers.append("retry_failed_or_fault_persisted")
        result = self._result(source_step, source_revision, actions, blockers)
        self.history.append(result); return result

    def _action(self, step: int, revision: int, kind: str, target_state: Mapping[str, Any], reason: str) -> dict[str, Any]:
        return {"schema":ACTION_SCHEMA,"source_step":int(step),"source_revision":int(revision),
                "entity_id":self.entity_id,"device_id":self.device_id,"kind":kind,
                "target_state":dict(target_state),"reason":reason,"requires_commit_gate":True,
                "recovery_attempt":self.recovery_attempts + (1 if reason=="bounded_reverse_release" else 0)}

    def _result(self, step: int, revision: int, actions: list[dict[str, Any]], blockers: list[str]) -> dict[str, Any]:
        return {"schema":SCHEMA,"source_step":int(step),"source_revision":int(revision),
                "entity_id":self.entity_id,"device_id":self.device_id,"state":self.state,
                "recovery_attempts":self.recovery_attempts,"latched_fault_code":self.latched_fault_code,
                "actions":actions,"blockers":blockers,
                "automatic_motion_allowed":bool(actions) and not blockers}
