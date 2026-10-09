#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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

    release_policy = catalog.get("release_policy")
    if not isinstance(release_policy, str) or not release_policy:
        errors.append("catalog missing release_policy")
    else:
        release_path = ROOT / release_policy
        if not release_path.is_file():
            errors.append(f"missing release policy: {release_policy}")
        else:
            release_doc = json.loads(release_path.read_text(encoding="utf-8"))
            if release_doc.get("schema") != "spatialruntime.conformance-release-policy.v0.1":
                errors.append("release policy schema mismatch")
            if release_doc.get("immutable_tags") is not True:
                errors.append("release policy must require immutable tags")

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

        adapter_source = entry.get("external_adapter_source")
        adapter_protocol = entry.get("external_adapter_protocol")
        if adapter_source is not None:
            adapter_path = ROOT / str(adapter_source)
            if not adapter_path.is_file():
                errors.append(f"{mode}: missing external_adapter_source {adapter_source}")
            else:
                adapter_doc = json.loads(adapter_path.read_text(encoding="utf-8"))
                if adapter_doc.get("protocol") != adapter_protocol:
                    errors.append(
                        f"{mode}: adapter protocol {adapter_protocol!r} != "
                        f"{adapter_source}['protocol'] {adapter_doc.get('protocol')!r}"
                    )

        outputs = entry.get("outputs", [])
        if entry.get("structured_action_result") is not True:
            errors.append(
                f"{mode}: canonical Action always exposes conformance_result; "
                "structured_action_result must be true"
            )
        if "conformance_result" not in outputs:
            errors.append(f"{mode}: catalog outputs missing conformance_result")

    action_path = ROOT / str(catalog.get("preferred_action", "")) / "action.yml"
    if action_path.is_file():
        action_text = action_path.read_text(encoding="utf-8")
        action_modes = set(
            re.findall(r"^          ([a-z][a-z0-9.-]*)\)\s*$", action_text, flags=re.MULTILINE)
        )
        catalog_modes = set(seen_modes)
        missing_in_action = sorted(catalog_modes - action_modes)
        undocumented_in_catalog = sorted(action_modes - catalog_modes)
        if missing_in_action:
            errors.append(
                "canonical Action/catalog mode drift: catalog-only "
                + ", ".join(missing_in_action)
            )
        if undocumented_in_catalog:
            errors.append(
                "canonical Action/catalog mode drift: action-only "
                + ", ".join(undocumented_in_catalog)
            )

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
