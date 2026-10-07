from __future__ import annotations

from hashlib import sha256
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from spatialruntime.solver.contam.inventory import parse_prj_inventory, sha256_file

SCHEMA = "contam_binding_registry_v0.9"


class BindingError(RuntimeError):
    pass


class BindingDriftError(BindingError):
    pass


class BindingValidationError(BindingError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def structural_inventory(inventory: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "zones": [
            {"number": x.get("number"), "name": x.get("name")}
            for x in inventory.get("zones", [])
        ],
        "flow_paths": [
            {
                "number": x.get("number"),
                "zone_n": x.get("zone_n"),
                "zone_m": x.get("zone_m"),
                "flow_element_number": x.get("flow_element_number"),
            }
            for x in inventory.get("flow_paths", [])
        ],
        "flow_elements": [
            {"number": x.get("number"), "name": x.get("name"), "dtype": x.get("dtype")}
            for x in inventory.get("flow_elements", [])
        ],
    }


def structural_digest(inventory: Mapping[str, Any]) -> str:
    return sha256(_canonical(structural_inventory(inventory)).encode()).hexdigest()


def _index(items: list[dict[str, Any]], key: str) -> dict[Any, dict[str, Any]]:
    out = {}
    for item in items:
        value = item.get(key)
        if value is None:
            raise BindingValidationError(f"inventory item missing {key}: {item}")
        if value in out:
            raise BindingValidationError(f"duplicate native {key}: {value}")
        out[value] = item
    return out


def validate_binding_registry(registry: Mapping[str, Any], inventory: Mapping[str, Any]) -> None:
    if registry.get("schema") != SCHEMA:
        raise BindingValidationError(f"expected {SCHEMA}")
    native_zones = _index(list(inventory.get("zones", [])), "number")
    native_paths = _index(list(inventory.get("flow_paths", [])), "number")
    native_elements = _index(list(inventory.get("flow_elements", [])), "number")

    seen_zones: set[int] = set()
    for stable_id, binding in (registry.get("zones") or {}).items():
        number = binding.get("contam_zone_number")
        if number not in native_zones:
            raise BindingValidationError(f"{stable_id}: unknown CONTAM zone number {number}")
        if number in seen_zones:
            raise BindingValidationError(f"duplicate zone binding to native zone {number}")
        seen_zones.add(number)

    seen_paths: set[int] = set()
    for stable_id, binding in (registry.get("flow_paths") or {}).items():
        pnum = binding.get("contam_path_number")
        enum = binding.get("contam_flow_element_number")
        if pnum not in native_paths:
            raise BindingValidationError(f"{stable_id}: unknown CONTAM path number {pnum}")
        if enum not in native_elements:
            raise BindingValidationError(
                f"{stable_id}: unknown CONTAM flow element number {enum}"
            )
        if pnum in seen_paths:
            raise BindingValidationError(f"duplicate flow-path binding to native path {pnum}")
        seen_paths.add(pnum)


def build_binding_registry(
    *,
    case_id: str,
    project_path: str | Path,
    inventory: Mapping[str, Any],
    mappings: Mapping[str, Any],
) -> dict[str, Any]:
    p = Path(project_path)
    if not p.is_file():
        raise FileNotFoundError(p)
    out = {
        "schema": SCHEMA,
        "case_id": case_id,
        "revision": 0,
        "project": {
            "path": str(p),
            "sha256": sha256_file(p),
            "structural_inventory_sha256": structural_digest(inventory),
        },
        "zones": dict(mappings.get("zones") or {}),
        "flow_paths": dict(mappings.get("flow_paths") or {}),
        "lineage": [],
    }
    validate_binding_registry(out, inventory)
    return out


def assert_binding_fresh(
    registry: Mapping[str, Any],
    project_path: str | Path,
    inventory: Mapping[str, Any],
) -> None:
    validate_binding_registry(registry, inventory)
    project = registry.get("project") or {}
    if project.get("sha256") != sha256_file(project_path):
        raise BindingDriftError("CONTAM project content changed; binding review required")
    if project.get("structural_inventory_sha256") != structural_digest(inventory):
        raise BindingDriftError(
            "CONTAM structural inventory changed; binding review required"
        )


def reverse_lookup(registry: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    return {
        "zones": {
            str(v["contam_zone_number"]): k
            for k, v in (registry.get("zones") or {}).items()
        },
        "flow_paths": {
            str(v["contam_path_number"]): k
            for k, v in (registry.get("flow_paths") or {}).items()
        },
    }


def registry_fingerprint(registry: Mapping[str, Any]) -> str:
    project = registry.get("project") or {}
    body = {
        "schema": registry.get("schema"),
        "case_id": registry.get("case_id"),
        "revision": registry.get("revision"),
        "project": {
            "sha256": project.get("sha256"),
            "structural_inventory_sha256": project.get("structural_inventory_sha256"),
        },
        "zones": registry.get("zones") or {},
        "flow_paths": registry.get("flow_paths") or {},
    }
    return sha256(_canonical(body).encode()).hexdigest()


def advance_binding_registry_after_mutation(
    registry: Mapping[str, Any],
    *,
    before_project_path: str | Path,
    before_inventory: Mapping[str, Any],
    after_project_path: str | Path,
    mutation_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Advance a reviewed binding registry after a proven non-structural PRJ mutation."""
    assert_binding_fresh(registry, before_project_path, before_inventory)
    if mutation_report.get("schema") != "contam_mutation_report_v0.10":
        raise BindingValidationError("expected contam_mutation_report_v0.10")
    if not mutation_report.get("applied") or mutation_report.get("dry_run"):
        raise BindingValidationError("mutation report does not prove an applied mutation")
    if int(mutation_report.get("change_count", 0)) <= 0:
        raise BindingValidationError("mutation report has no committed changes")
    if int(mutation_report.get("binding_revision_before", -1)) != int(registry.get("revision", 0)):
        raise BindingDriftError("mutation report binding revision does not match registry")
    if mutation_report.get("before_project_sha256") != registry.get("project", {}).get("sha256"):
        raise BindingDriftError("mutation report before-project hash does not match registry")
    if mutation_report.get("before_structural_inventory_sha256") != structural_digest(before_inventory):
        raise BindingDriftError("mutation report before structural fingerprint mismatch")

    after_path = Path(after_project_path)
    if not after_path.is_file():
        raise FileNotFoundError(after_path)
    after_sha = sha256_file(after_path)
    if mutation_report.get("after_project_sha256") != after_sha:
        raise BindingDriftError("mutation report after-project hash does not match output file")
    after_inventory = parse_prj_inventory(after_path)
    after_struct = structural_digest(after_inventory)

    before_struct = structural_digest(before_inventory)
    if after_struct != before_struct:
        raise BindingDriftError(
            "approved mutation changed native structural identity/connectivity; "
            "binding review required"
        )
    if mutation_report.get("after_structural_inventory_sha256") != after_struct:
        raise BindingDriftError("mutation report after structural fingerprint mismatch")

    out = deepcopy(dict(registry))
    lineage = list(out.get("lineage") or [])
    lineage.append({
        "revision": int(registry.get("revision", 0)),
        "project_sha256": registry["project"]["sha256"],
        "mutation_schema": mutation_report.get("schema"),
        "mutation_plan_hash": mutation_report.get("plan_hash"),
        "change_count": int(mutation_report.get("change_count", 0)),
        "source_step": mutation_report.get("source_step"),
        "source_revision": mutation_report.get("source_revision"),
    })
    out["lineage"] = lineage
    out["revision"] = int(registry.get("revision", 0)) + 1
    out["project"] = {
        **dict(out.get("project") or {}),
        "path": str(after_path),
        "sha256": after_sha,
        "structural_inventory_sha256": after_struct,
    }
    validate_binding_registry(out, after_inventory)
    return out
