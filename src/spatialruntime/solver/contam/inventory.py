from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

SCHEMA = "contam_native_inventory_v0.9"


class InventoryError(RuntimeError):
    pass


class UnsupportedProjectFormat(InventoryError):
    pass


SECTION_PATTERNS = {
    "flow_elements": re.compile(r"airflow\s+elements", re.I),
    "zones": re.compile(r"\bzones?\b", re.I),
    "flow_paths": re.compile(r"airflow\s+paths", re.I),
    "controls": re.compile(r"control\s+(nodes?|elements?|section)", re.I),
    "mechanical": re.compile(r"(simple\s+air\s+handling|\bAHS\b|mechanical)", re.I),
}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_sections(lines: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("!"):
            continue
        for name, pattern in SECTION_PATTERNS.items():
            if pattern.search(line):
                found.setdefault(name, i)
    return found


def _data_lines(lines: list[str], start: int):
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if not s or s.startswith("!"):
            continue
        yield i, s


def _simple_records(lines: list[str], section_line: int, expected_min_tokens: int, label: str):
    gen = _data_lines(lines, section_line + 1)
    try:
        count_i, count_line = next(gen)
        count = int(count_line.split()[0])
    except Exception as exc:
        raise InventoryError(f"invalid {label} count") from exc
    out = []
    cur = count_i + 1
    while len(out) < count and cur < len(lines):
        s = lines[cur].strip()
        cur += 1
        if not s or s.startswith("!"):
            continue
        if s.startswith("-999"):
            break
        toks = s.split()
        if len(toks) < expected_min_tokens or not toks[0].lstrip("+-").isdigit():
            continue
        out.append((cur, toks))
    if len(out) != count:
        raise InventoryError(f"{label}: expected {count} records, found {len(out)}")
    return out


def parse_prj_inventory(path: str | Path) -> dict[str, Any]:
    """Conservative CONTAM PRJ inventory reader.

    Only documented/comment-delimited structural sections are parsed. If required
    markers are absent, this function fails instead of guessing record boundaries.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    lines = p.read_text(errors="replace").splitlines()
    sections = _find_sections(lines)
    required = {"zones", "flow_paths", "flow_elements"}
    if not required <= set(sections):
        raise UnsupportedProjectFormat(
            "could not locate Zones/Airflow Paths/Airflow Elements section headers"
        )

    inventory: dict[str, Any] = {
        "schema": SCHEMA,
        "project": {"path": str(p), "sha256": sha256_file(p)},
        "zones": [],
        "flow_paths": [],
        "flow_elements": [],
        "controls": [],
        "mechanical": [],
        "parser": {"mode": "conservative_prj_v0.9", "sections": sections},
    }

    start = sections["flow_elements"] + 1
    gen = _data_lines(lines, start)
    try:
        count_i, count_line = next(gen)
        count = int(count_line.split()[0])
    except Exception as exc:
        raise InventoryError("invalid airflow element count") from exc

    cursor = count_i + 1
    for _ in range(count):
        while cursor < len(lines) and (
            not lines[cursor].strip() or lines[cursor].lstrip().startswith("!")
        ):
            cursor += 1
        if cursor >= len(lines):
            raise InventoryError("truncated airflow element section")
        header_line = cursor
        parts = lines[cursor].split(maxsplit=3)
        if len(parts) < 3:
            raise InventoryError(f"bad airflow element header at line {cursor + 1}")
        try:
            number = int(parts[0])
        except ValueError as exc:
            raise InventoryError(f"bad airflow element number at line {cursor + 1}") from exc
        dtype = parts[2]
        name = parts[3] if len(parts) > 3 else f"afe_{number}"
        cursor += 1

        description = lines[cursor].rstrip() if cursor < len(lines) else ""
        cursor += 1
        item: dict[str, Any] = {
            "number": number,
            "name": name,
            "dtype": dtype,
            "description": description,
            "source": {"header_line": header_line + 1},
            "mutable_record": None,
        }

        if dtype == "plr_orfc":
            while cursor < len(lines) and (
                not lines[cursor].strip() or lines[cursor].lstrip().startswith("!")
            ):
                cursor += 1
            if cursor >= len(lines):
                raise InventoryError("truncated plr_orfc record")
            values = lines[cursor].split()
            if len(values) < 9:
                raise InventoryError(f"plr_orfc data line too short at {cursor + 1}")
            item["parameters"] = {
                "lam": float(values[0]),
                "turb": float(values[1]),
                "expt": float(values[2]),
                "area_m2": float(values[3]),
                "diameter_m": float(values[4]),
                "coef": float(values[5]),
                "reynolds": float(values[6]),
                "u_A": int(values[7]),
                "u_D": int(values[8]),
            }
            item["mutable_record"] = {
                "kind": "plr_orfc",
                "line": cursor + 1,
                "token_count": len(values),
            }
            cursor += 1
        else:
            expected = number + 1
            while cursor < len(lines):
                s = lines[cursor].strip()
                if s.startswith("-999"):
                    break
                toks = s.split(maxsplit=3)
                if toks and toks[0].isdigit() and int(toks[0]) == expected and len(toks) >= 3:
                    break
                cursor += 1
        inventory["flow_elements"].append(item)

    for line_no, toks in _simple_records(lines, sections["zones"], 2, "zones"):
        inventory["zones"].append({
            "number": int(toks[0]),
            "name": toks[-1] if len(toks) > 1 else f"zone_{toks[0]}",
            "raw_tokens": toks,
            "source": {"line": line_no},
        })

    for line_no, toks in _simple_records(lines, sections["flow_paths"], 5, "flow_paths"):
        inventory["flow_paths"].append({
            "number": int(toks[0]),
            "zone_n": int(toks[2]),
            "zone_m": int(toks[3]),
            "flow_element_number": int(toks[4]),
            "name": f"path_{toks[0]}",
            "raw_tokens": toks,
            "source": {"line": line_no},
        })

    return inventory
