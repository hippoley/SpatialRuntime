#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATURITY = ROOT / "interop" / "conformance-maturity.v0.1.json"
CATALOG = ROOT / "interop" / "conformance" / "manifest.v0.1.json"

SEMANTIC = {"experimental", "candidate", "stable", "deprecated"}
EVIDENCE = {
    "self-tested",
    "external-source-reviewed",
    "externally-executed",
    "externally-reproduced",
    "externally-consumed",
}


def main() -> None:
    maturity = json.loads(MATURITY.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    errors: list[str] = []

    catalog_modes = [p.get("mode") for p in catalog.get("profiles", [])]
    catalog_modes = [m for m in catalog_modes if isinstance(m, str) and m]
    counts: Counter[str] = Counter()

    for index, surface in enumerate(maturity.get("surfaces", [])):
        sid = surface.get("id", f"surfaces[{index}]")
        if surface.get("semantic_maturity") not in SEMANTIC:
            errors.append(f"{sid}: invalid semantic_maturity")
        if surface.get("evidence_maturity") not in EVIDENCE:
            errors.append(f"{sid}: invalid evidence_maturity")
        modes = surface.get("catalog_modes", [])
        if not isinstance(modes, list):
            errors.append(f"{sid}: catalog_modes must be a list")
            continue
        for mode in modes:
            if not isinstance(mode, str) or not mode:
                errors.append(f"{sid}: invalid catalog mode {mode!r}")
                continue
            counts[mode] += 1

    for mode in catalog_modes:
        if counts[mode] == 0:
            errors.append(f"{mode}: missing maturity coverage")
        elif counts[mode] > 1:
            errors.append(f"{mode}: maturity coverage duplicated {counts[mode]} times")

    unknown = sorted(set(counts) - set(catalog_modes))
    if unknown:
        errors.append("maturity references unknown catalog modes: " + ", ".join(unknown))

    if errors:
        raise SystemExit("\n".join(errors))

    print(json.dumps({
        "schema": maturity.get("schema"),
        "catalog_modes": len(catalog_modes),
        "covered_once": sorted(catalog_modes),
        "status": "PASS",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
