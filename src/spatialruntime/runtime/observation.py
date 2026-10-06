from __future__ import annotations
from typing import Any

SCHEMA = "windowpilot_observation_v1.8"

class ObservationBuildError(RuntimeError): pass


def build_observation(reconciled: dict[str, Any], *, allow_degraded: bool = False) -> dict[str, Any]:
    if reconciled.get("schema") != "physical_state_reconcile_v1.7":
        raise ObservationBuildError("expected physical_state_reconcile_v1.7")
    summary = reconciled.get("summary", {})
    if not summary.get("safe_for_control", False) and not allow_degraded:
        raise ObservationBuildError("reconciled state has hard disagreements; control observation blocked")

    zones = {}
    for zid, item in reconciled.get("zones", {}).items():
        state = item.get("state", {})
        zones[zid] = {
            "pressure_pa": state.get("pressure_pa"),
            "temperature_c": state.get("temperature_c"),
            "ach_1_h": state.get("ach_1_h"),
            "airflow_in_m3_s": state.get("airflow_in_m3_s"),
            "airflow_out_m3_s": state.get("airflow_out_m3_s"),
            "confidence": item.get("confidence"),
            "field_sources": item.get("field_sources", {}),
        }
    devices = {eid:{"state":v.get("state",{}),"confidence":v.get("confidence"),"source":v.get("source")}
               for eid,v in reconciled.get("devices",{}).items()}
    paths = {pid:{"flow_m3_s":v.get("state",{}).get("flow_m3_s"),
                  "pressure_difference_pa":v.get("state",{}).get("pressure_difference_pa"),
                  "confidence":v.get("confidence"),"source":v.get("source")}
             for pid,v in reconciled.get("flow_paths",{}).items()}
    return {
        "schema": SCHEMA,
        "case_id": reconciled.get("case_id"),
        "step": reconciled.get("step"),
        "revision": reconciled.get("revision"),
        "zones": zones, "devices": devices, "flow_paths": paths,
        "quality": {"safe_for_control": summary.get("safe_for_control",False),
                    "hard_disagreements": summary.get("hard_disagreements",0),
                    "warnings": summary.get("warnings",0),
                    "degraded": not summary.get("safe_for_control",False)},
        "disagreement_digest": reconciled.get("disagreements",[]),
    }
