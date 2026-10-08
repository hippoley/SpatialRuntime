#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = Path(__file__).with_name("manifest.v0.1.json")


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    errors: list[str] = []

    preferred = ROOT / str(catalog.get("preferred_action", "")) / "action.yml"
    if not preferred.is_file():
        errors.append(f"preferred_action missing action.yml: {preferred.relative_to(ROOT)}")

    for rel in catalog.get("legacy_compatible_actions", []):
        path = ROOT / str(rel) / "action.yml"
        if not path.is_file():
            errors.append(f"legacy action missing action.yml: {path.relative_to(ROOT)}")

    seen_modes: set[str] = set()
    for index, entry in enumerate(catalog.get("profiles", [])):
        mode = entry.get("mode")
        if not isinstance(mode, str) or not mode:
            errors.append(f"profiles[{index}] missing mode")
            continue
        if mode in seen_modes:
            errors.append(f"duplicate mode: {mode}")
        seen_modes.add(mode)

        entrypoint = ROOT / str(entry.get("entrypoint", ""))
        if not entrypoint.is_file():
            errors.append(f"{mode}: missing entrypoint {entry.get('entrypoint')}")

        source = ROOT / str(entry.get("profile_source", ""))
        key = entry.get("profile_key")
        expected = entry.get("profile")
        if not source.is_file():
            errors.append(f"{mode}: missing profile_source {entry.get('profile_source')}")
            continue
        if not isinstance(key, str) or not key:
            errors.append(f"{mode}: missing profile_key")
            continue

        source_doc = json.loads(source.read_text(encoding="utf-8"))
        actual = source_doc.get(key)
        if actual != expected:
            errors.append(
                f"{mode}: catalog profile {expected!r} != "
                f"{entry.get('profile_source')}[{key!r}] {actual!r}"
            )

        outputs = entry.get("outputs", [])
        if entry.get("structured_action_result") is True and "conformance_result" not in outputs:
            errors.append(f"{mode}: structured mode missing conformance_result output")

    if errors:
        raise SystemExit("\n".join(errors))

    print(
        json.dumps(
            {
                "catalog": catalog.get("schema"),
                "profiles": len(catalog.get("profiles", [])),
                "modes": sorted(seen_modes),
                "status": "PASS",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
