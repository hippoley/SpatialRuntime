from __future__ import annotations

import csv
import io
import math
import re
import json
from pathlib import Path
from typing import Any, Mapping

from spatialruntime.solver.contam.binding import reverse_lookup

SCHEMA = "contam_native_result_v0.9"


class ResultError(RuntimeError):
    pass


class ResultParseError(ResultError):
    pass


class ResultProtocolError(ResultError):
    pass


class ResultBindingError(ResultError):
    pass


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise ResultParseError(f"expected numeric value, got {value!r}") from exc
    if not math.isfinite(x):
        raise ResultParseError(f"non-finite numeric value: {value!r}")
    return x


def parse_val_airflow_summary(text: str) -> dict[str, Any]:
    lines = [ln.rstrip("\r\n") for ln in text.splitlines()]
    out: dict[str, Any] = {
        "schema": "contam_val_airflow_summary_v0.9",
        "building": {},
        "weather": {},
        "zones": [],
        "source_format": "VAL",
    }
    scalar_patterns = {
        "ambient_temperature_c": r"^\s*Ambient\s+T:\s*([-+0-9.eE]+)",
        "barometric_pressure_pa": r"^\s*Pressure:\s*([-+0-9.eE]+)",
        "wind_speed_m_s": r"^\s*Wind\s+spd:\s*([-+0-9.eE]+)",
        "wind_direction_deg": r"^\s*Wind\s+dir:\s*([-+0-9.eE]+)",
        "building_ach_1_h": r"^\s*Bldg\s+ACH:\s*([-+0-9.eE]+)",
    }
    for line in lines:
        for key, pattern in scalar_patterns.items():
            m = re.search(pattern, line, re.I)
            if m:
                target = out["building"] if key.startswith("building_") else out["weather"]
                target[key] = _num(m.group(1))

    header_idx = None
    for i, line in enumerate(lines):
        low = re.sub(r"\s+", " ", line.strip().lower())
        if low.startswith("zone ") and "p [pa]" in low and "vol [m^3]" in low:
            header_idx = i
            break
    if header_idx is not None:
        for line in lines[header_idx + 1 :]:
            if not line.strip():
                if out["zones"]:
                    break
                continue
            if re.match(r"^\s*[A-Za-z][A-Za-z ]*:", line):
                break
            parts = re.split(r"\s+|\t+", line.strip())
            if not parts or not re.fullmatch(r"[-+]?\d+", parts[0]):
                continue
            if len(parts) < 10:
                raise ResultParseError(
                    f"recognised VAL zone row has {len(parts)} fields, expected >=10"
                )
            out["zones"].append({
                "native_zone_number": int(parts[0]),
                "condition": parts[1],
                "supply_ach": _num(parts[2]),
                "return_exhaust_ach": _num(parts[3]),
                "outdoor_system_ach": _num(parts[4]),
                "outdoor_total_ach": _num(parts[5]),
                "circulation_total_ach": _num(parts[6]),
                "pressure_pa": _num(parts[7]),
                "temperature_c": _num(parts[8]),
                "volume_m3": _num(parts[9]),
            })
    return out


def parse_path_export_tsv(text: str) -> dict[str, Any]:
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    if not rows:
        raise ResultParseError("path export has no tab-delimited data rows")

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")

    headers = {norm(k): k for k in rows[0].keys() if k is not None}
    pkey = next(
        (headers[k] for k in ("path", "path_number", "path_nr", "nr") if k in headers),
        None,
    )
    if pkey is None:
        raise ResultParseError("path export missing path/path_number column")
    fvol = next(
        (headers[k] for k in ("flow_m3_s", "volumetric_flow_m3_s", "airflow_m3_s") if k in headers),
        None,
    )
    fmass = next(
        (headers[k] for k in ("flow_kg_s", "mass_flow_kg_s") if k in headers),
        None,
    )
    dpkey = next(
        (headers[k] for k in ("pressure_difference_pa", "dp_pa", "delta_p_pa") if k in headers),
        None,
    )
    if fvol is None and fmass is None:
        raise ResultParseError("path export requires flow_m3_s or flow_kg_s")

    out = []
    for row in rows:
        try:
            pnum = int(str(row[pkey]).strip())
        except Exception as exc:
            raise ResultParseError(f"invalid native path number: {row.get(pkey)!r}") from exc
        item = {"native_path_number": pnum}
        if fvol is not None:
            item["flow_m3_s"] = _num(row.get(fvol))
        if fmass is not None:
            item["mass_flow_kg_s"] = _num(row.get(fmass))
        if dpkey is not None:
            item["delta_pressure_pa"] = _num(row.get(dpkey))
        out.append(item)
    return {"schema": SCHEMA, "source_format": "tabular_export", "paths": out, "zones": []}


def normalize_api_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    zones = payload.get("zones", [])
    paths = payload.get("paths", [])
    if not isinstance(zones, list) or not isinstance(paths, list):
        raise ResultProtocolError("API result zones/paths must be arrays")
    seen_zones: set[int] = set()
    seen_paths: set[int] = set()
    zout = []
    pout = []

    for zone in zones:
        if not isinstance(zone, Mapping) or not isinstance(zone.get("number"), int):
            raise ResultProtocolError(f"invalid API zone result: {zone!r}")
        number = int(zone["number"])
        if number in seen_zones:
            raise ResultProtocolError(f"duplicate API zone number {number}")
        seen_zones.add(number)
        item = {"native_zone_number": number}
        for key in (
            "pressure_pa",
            "temperature_c",
            "airflow_in_m3_s",
            "airflow_out_m3_s",
            "ach_1_h",
        ):
            if key in zone:
                item[key] = _num(zone.get(key))
        zout.append(item)

    for path in paths:
        if not isinstance(path, Mapping) or not isinstance(path.get("number"), int):
            raise ResultProtocolError(f"invalid API path result: {path!r}")
        number = int(path["number"])
        if number in seen_paths:
            raise ResultProtocolError(f"duplicate API path number {number}")
        seen_paths.add(number)
        item = {"native_path_number": number}
        for src, dst in (
            ("flow_m3_s", "flow_m3_s"),
            ("flow_kg_s", "mass_flow_kg_s"),
            ("pressure_difference_pa", "delta_pressure_pa"),
        ):
            if src in path:
                item[dst] = _num(path.get(src))
        pout.append(item)

    return {"schema": SCHEMA, "source_format": "api_json", "zones": zout, "paths": pout}


def map_native_results_to_stable(
    native: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    strict: bool = True,
) -> dict[str, Any]:
    rev = reverse_lookup(registry)
    stable_zones: dict[str, Any] = {}
    stable_paths: dict[str, Any] = {}
    unmapped = {"zones": [], "paths": []}

    for zone in native.get("zones", []):
        number = str(zone["native_zone_number"])
        stable_id = rev["zones"].get(number)
        if stable_id is None:
            unmapped["zones"].append(int(number))
            continue
        stable_zones[stable_id] = {
            k: v for k, v in zone.items() if k != "native_zone_number"
        }

    for path in native.get("paths", []):
        number = str(path["native_path_number"])
        stable_id = rev["flow_paths"].get(number)
        if stable_id is None:
            unmapped["paths"].append(int(number))
            continue
        stable_paths[stable_id] = {
            k: v for k, v in path.items() if k != "native_path_number"
        }

    if strict and (unmapped["zones"] or unmapped["paths"]):
        raise ResultBindingError(f"unmapped native results: {unmapped}")
    return {
        "zones": stable_zones,
        "flow_paths": stable_paths,
        "unmapped_native": unmapped,
    }


def merge_result_sources(
    *,
    val: Mapping[str, Any] | None = None,
    path_export: Mapping[str, Any] | None = None,
    api: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    zone_by_num: dict[int, dict[str, Any]] = {}
    path_by_num: dict[int, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []

    def merge_item(
        dst: dict[int, dict[str, Any]],
        src: Mapping[str, Any],
        identity_key: str,
        kind: str,
    ) -> None:
        ident = int(src[identity_key])
        target = dst.setdefault(ident, {identity_key: ident})
        for key, value in src.items():
            if key == identity_key or value is None:
                continue
            if key in target and target[key] is not None and target[key] != value:
                conflicts.append({
                    "kind": kind,
                    "native_number": ident,
                    "field": key,
                    "existing": target[key],
                    "incoming": value,
                })
            else:
                target[key] = value

    if val:
        for zone in val.get("zones", []):
            merge_item(zone_by_num, zone, "native_zone_number", "zone")
    if path_export:
        for path in path_export.get("paths", []):
            merge_item(path_by_num, path, "native_path_number", "path")
    if api:
        for zone in api.get("zones", []):
            merge_item(zone_by_num, zone, "native_zone_number", "zone")
        for path in api.get("paths", []):
            merge_item(path_by_num, path, "native_path_number", "path")

    if conflicts:
        raise ResultProtocolError(f"conflicting result sources: {conflicts}")
    return {
        "schema": SCHEMA,
        "source_format": "merged",
        "zones": list(zone_by_num.values()),
        "paths": list(path_by_num.values()),
    }


def parse_result_file(path: str | Path, *, kind: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    if kind == "val":
        return parse_val_airflow_summary(p.read_text(errors="replace"))
    if kind == "path_tsv":
        return parse_path_export_tsv(p.read_text(errors="replace"))
    if kind == "api_json":
        payload = json.loads(p.read_text())
        if not isinstance(payload, Mapping):
            raise ResultProtocolError("API JSON result root must be object")
        return normalize_api_result(payload)
    if kind == "sim_binary":
        raise ResultParseError(
            "raw .SIM is binary; use NIST SimRead/Results Export or a ContamX API wrapper "
            "instead of guessing its binary layout"
        )
    raise ValueError(f"unknown result kind {kind!r}")
