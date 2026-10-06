from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping

SCHEMA = "safety_supervisor_decision_v3.0"

class SafetySupervisorError(RuntimeError): pass
class StaleSafetyContextError(SafetySupervisorError): pass

@dataclass(frozen=True)
class SafetyPolicy:
    max_wind_m_s_for_opening: float = 12.0
    max_abs_pressure_pa_for_motion: float = 80.0
    wet_values: frozenset[Any] = field(default_factory=lambda: frozenset({True, 1, "wet", "rain", "raining"}))
    emergency_close_ratio: float = 0.0
    maintenance_lock_blocks_all_motion: bool = True
    child_lock_blocks_opening: bool = True
    allow_emergency_close_during_fault: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "SafetyPolicy":
        d = dict(data or {})
        return cls(
            max_wind_m_s_for_opening=float(d.get("max_wind_m_s_for_opening", 12.0)),
            max_abs_pressure_pa_for_motion=float(d.get("max_abs_pressure_pa_for_motion", 80.0)),
            wet_values=frozenset(d.get("wet_values", [True, 1, "wet", "rain", "raining"])),
            emergency_close_ratio=float(d.get("emergency_close_ratio", 0.0)),
            maintenance_lock_blocks_all_motion=bool(d.get("maintenance_lock_blocks_all_motion", True)),
            child_lock_blocks_opening=bool(d.get("child_lock_blocks_opening", True)),
            allow_emergency_close_during_fault=bool(d.get("allow_emergency_close_during_fault", True)),
        )


def _state_ratio(runtime_state: Mapping[str, Any], entity_id: str) -> float | None:
    ent = runtime_state.get(entity_id) or {}
    st = ent.get("executed_state") or {}
    v = st.get("open_ratio")
    return None if v is None else float(v)


def _target_ratio(change: Mapping[str, Any] | None, current: float | None) -> float | None:
    if not isinstance(change, Mapping): return current
    if "open_ratio" not in change: return current
    x = float(change["open_ratio"])
    if not 0.0 <= x <= 1.0:
        raise SafetySupervisorError("open_ratio outside [0,1]")
    return x


def _is_wet(value: Any, policy: SafetyPolicy) -> bool:
    if isinstance(value, str):
        value = value.strip().lower()
    return value in policy.wet_values


def _sensor(safety_context: Mapping[str, Any], name: str) -> Any:
    sensors = safety_context.get("sensors") or {}
    item = sensors.get(name)
    if isinstance(item, Mapping):
        if item.get("quality") is not None and float(item["quality"]) < 0.5:
            return None
        return item.get("value")
    return item


def supervise_actions(*, source_step: int, source_revision: int,
                      proposed_action: Mapping[str, Any], runtime_state: Mapping[str, Any],
                      safety_context: Mapping[str, Any], policy: SafetyPolicy | Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Arbitrate policy/recovery actions under physical safety interlocks.

    Priority (highest first): emergency close > maintenance lock > hard mechanical fault >
    environmental interlocks > child/opening lock > normal requested action.
    The function never invents unsupported recovery actions; it only denies/overrides requests.
    """
    p = policy if isinstance(policy, SafetyPolicy) else SafetyPolicy.from_mapping(policy)
    if int(proposed_action.get("source_step", -1)) != int(source_step) or int(proposed_action.get("source_revision", -1)) != int(source_revision):
        raise StaleSafetyContextError("proposed action step/revision mismatch")
    if int(safety_context.get("source_step", -1)) != int(source_step) or int(safety_context.get("source_revision", -1)) != int(source_revision):
        raise StaleSafetyContextError("safety context step/revision mismatch")
    changes = proposed_action.get("changes") or {}
    if not isinstance(changes, Mapping):
        raise SafetySupervisorError("proposed_action.changes must be object")

    emergency = bool(safety_context.get("emergency_close", False))
    maintenance_lock = bool(safety_context.get("maintenance_lock", False))
    child_lock = bool(safety_context.get("child_lock", False))
    rain = _sensor(safety_context, "rain")
    wind = _sensor(safety_context, "wind_m_s")
    pressure = _sensor(safety_context, "abs_pressure_diff_pa")
    hard_fault_entities = set(safety_context.get("hard_fault_entities") or [])

    decisions: dict[str, Any] = {}
    emitted_changes: dict[str, Any] = {}
    events: list[dict[str, Any]] = []

    entity_ids = set(changes)
    # Emergency close may need to act even if policy did not mention a window.
    if emergency:
        entity_ids |= {eid for eid,v in runtime_state.items() if "open_ratio" in ((v or {}).get("executed_state") or {})}

    for entity_id in sorted(entity_ids):
        if entity_id not in runtime_state:
            decisions[entity_id] = {"decision":"reject","reason":"unknown_entity"}
            continue
        current = _state_ratio(runtime_state, entity_id)
        requested = changes.get(entity_id)
        target = _target_ratio(requested, current)

        # 1. Emergency close is the strongest automatic override, but if a hard
        # fault exists we only permit it when explicitly configured.
        if emergency and current is not None:
            if entity_id in hard_fault_entities and not p.allow_emergency_close_during_fault:
                decisions[entity_id] = {"decision":"hold","reason":"hard_fault_blocks_emergency_motion","executed_state":{"open_ratio":current}}
            else:
                emitted_changes[entity_id] = {"open_ratio": p.emergency_close_ratio}
                decisions[entity_id] = {"decision":"override_close","reason":"emergency_close","requested":requested,"committed_change":{"open_ratio":p.emergency_close_ratio}}
                events.append({"entity_id":entity_id,"priority":100,"rule":"emergency_close"})
            continue

        # 2. Maintenance lock means no automatic motion.
        if maintenance_lock and p.maintenance_lock_blocks_all_motion and current is not None and target != current:
            decisions[entity_id] = {"decision":"hold","reason":"maintenance_lock","executed_state":{"open_ratio":current}}
            events.append({"entity_id":entity_id,"priority":90,"rule":"maintenance_lock"})
            continue

        # 3. Hard device/mechanical fault blocks normal motion.
        if entity_id in hard_fault_entities and current is not None and target != current:
            decisions[entity_id] = {"decision":"hold","reason":"hard_fault","executed_state":{"open_ratio":current}}
            events.append({"entity_id":entity_id,"priority":80,"rule":"hard_fault"})
            continue

        opening = current is not None and target is not None and target > current
        any_motion = current is not None and target is not None and target != current

        # 4. Environmental interlocks.
        if opening and _is_wet(rain, p):
            decisions[entity_id] = {"decision":"hold","reason":"rain_interlock","executed_state":{"open_ratio":current}}
            events.append({"entity_id":entity_id,"priority":70,"rule":"rain_interlock"})
            continue
        if opening and wind is not None and float(wind) > p.max_wind_m_s_for_opening:
            decisions[entity_id] = {"decision":"hold","reason":"high_wind_interlock","executed_state":{"open_ratio":current}}
            events.append({"entity_id":entity_id,"priority":70,"rule":"high_wind_interlock","observed":float(wind)})
            continue
        if any_motion and pressure is not None and abs(float(pressure)) > p.max_abs_pressure_pa_for_motion:
            decisions[entity_id] = {"decision":"hold","reason":"pressure_interlock","executed_state":{"open_ratio":current}}
            events.append({"entity_id":entity_id,"priority":70,"rule":"pressure_interlock","observed":float(pressure)})
            continue

        # 5. Child lock blocks opening, but permits closing.
        if child_lock and p.child_lock_blocks_opening and opening:
            decisions[entity_id] = {"decision":"hold","reason":"child_lock","executed_state":{"open_ratio":current}}
            events.append({"entity_id":entity_id,"priority":60,"rule":"child_lock"})
            continue

        if isinstance(requested, Mapping):
            emitted_changes[entity_id] = dict(requested)
            decisions[entity_id] = {"decision":"allow","requested":dict(requested)}
        else:
            decisions[entity_id] = {"decision":"noop"}

    return {
        "schema": SCHEMA,
        "source_step": int(source_step),
        "source_revision": int(source_revision),
        "input_action_kind": proposed_action.get("kind", "policy"),
        "changes": emitted_changes,
        "decisions": decisions,
        "events": sorted(events, key=lambda x:(-x["priority"], x["entity_id"])),
        "summary": {
            "allowed_or_overridden": len(emitted_changes),
            "blocked": sum(1 for d in decisions.values() if d.get("decision") in {"hold","reject"}),
            "emergency_override": emergency,
            "safe_to_forward": all(d.get("decision") != "reject" for d in decisions.values()),
        },
        "policy": {
            "max_wind_m_s_for_opening": p.max_wind_m_s_for_opening,
            "max_abs_pressure_pa_for_motion": p.max_abs_pressure_pa_for_motion,
            "emergency_close_ratio": p.emergency_close_ratio,
        },
    }
