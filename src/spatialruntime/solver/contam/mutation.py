from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from spatialruntime.solver.contam.binding import (
    BindingDriftError,
    BindingValidationError,
    assert_binding_fresh,
    structural_digest,
)
from spatialruntime.solver.contam.inventory import parse_prj_inventory, sha256_file

PLAN_SCHEMA = "contam_mutation_plan_v0.10"
REPORT_SCHEMA = "contam_mutation_report_v0.10"

_ALLOWED = {"area_m2", "coef", "expt"}


class MutationError(RuntimeError):
    pass


class UnsupportedMutation(MutationError):
    pass


class MutationValidationError(MutationError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def mutation_plan_hash(plan: Mapping[str, Any]) -> str:
    body = {k: v for k, v in plan.items() if k != "plan_hash"}
    return sha256(_canonical(body).encode()).hexdigest()


def _finite(value: Any, label: str) -> float:
    try:
        x = float(value)
    except Exception as exc:
        raise MutationValidationError(f"{label} must be numeric") from exc
    if not math.isfinite(x):
        raise MutationValidationError(f"{label} must be finite")
    return x


def _validate_parameter(name: str, value: Any) -> float:
    x = _finite(value, name)
    if name in {"area_m2", "coef"} and x < 0:
        raise MutationValidationError(f"{name} must be >= 0")
    if name == "expt" and x <= 0:
        raise MutationValidationError("expt must be > 0")
    return x


def _element_index(inventory: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {int(x["number"]): x for x in inventory.get("flow_elements", [])}


def build_mutation_plan(
    *,
    case_id: str,
    source_step: int,
    source_revision: int,
    project_path: str | Path,
    binding_registry: Mapping[str, Any],
    inventory: Mapping[str, Any],
    operations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    assert_binding_fresh(binding_registry, project_path, inventory)
    if binding_registry.get("case_id") != case_id:
        raise MutationValidationError("case_id does not match binding registry")
    if not operations:
        raise MutationValidationError("at least one mutation operation is required")

    elements = _element_index(inventory)
    edits: list[dict[str, Any]] = []
    seen_elements: set[int] = set()

    for i, op in enumerate(operations):
        if not isinstance(op, Mapping):
            raise MutationValidationError(f"operation[{i}] must be object")
        if op.get("kind") != "set_flow_path_parameters":
            raise UnsupportedMutation(f"unsupported operation kind: {op.get('kind')}")
        stable_id = op.get("flow_path_id")
        if not isinstance(stable_id, str) or not stable_id:
            raise MutationValidationError(f"operation[{i}].flow_path_id required")
        binding = (binding_registry.get("flow_paths") or {}).get(stable_id)
        if not isinstance(binding, Mapping):
            raise MutationValidationError(f"unknown stable flow path: {stable_id}")
        enum = int(binding["contam_flow_element_number"])
        if enum in seen_elements:
            raise MutationValidationError(
                f"multiple operations target CONTAM flow element {enum}"
            )
        seen_elements.add(enum)

        element = elements.get(enum)
        if element is None:
            raise MutationValidationError(f"flow element {enum} absent from inventory")
        mutable = element.get("mutable_record")
        if not mutable or mutable.get("kind") != "plr_orfc":
            raise UnsupportedMutation(
                f"{stable_id}: flow element {enum} dtype={element.get('dtype')} is not safely mutable"
            )

        requested = op.get("parameters")
        if not isinstance(requested, Mapping) or not requested:
            raise MutationValidationError(f"{stable_id}: parameters must be non-empty object")
        unknown = sorted(set(requested) - _ALLOWED)
        if unknown:
            raise UnsupportedMutation(
                f"{stable_id}: unsupported mutable parameters {unknown}; allowed={sorted(_ALLOWED)}"
            )

        before = dict(element.get("parameters") or {})
        after = dict(before)
        for key, value in requested.items():
            after[key] = _validate_parameter(key, value)

        edits.append({
            "flow_path_id": stable_id,
            "contam_path_number": int(binding["contam_path_number"]),
            "contam_flow_element_number": enum,
            "line": int(mutable["line"]),
            "record_kind": "plr_orfc",
            "before": before,
            "after": after,
        })

    plan = {
        "schema": PLAN_SCHEMA,
        "case_id": case_id,
        "source_step": int(source_step),
        "source_revision": int(source_revision),
        "binding_revision": int(binding_registry.get("revision", 0)),
        "expected_project_sha256": sha256_file(project_path),
        "expected_structural_inventory_sha256": structural_digest(inventory),
        "edits": edits,
    }
    plan["plan_hash"] = mutation_plan_hash(plan)
    return plan


def validate_mutation_plan(plan: Mapping[str, Any]) -> None:
    if plan.get("schema") != PLAN_SCHEMA:
        raise MutationValidationError(f"expected {PLAN_SCHEMA}")
    if plan.get("plan_hash") != mutation_plan_hash(plan):
        raise MutationValidationError("mutation plan hash mismatch")
    edits = plan.get("edits")
    if not isinstance(edits, list) or not edits:
        raise MutationValidationError("mutation plan edits must be non-empty array")
    seen_lines: set[int] = set()
    for edit in edits:
        if not isinstance(edit, Mapping):
            raise MutationValidationError("mutation edit must be object")
        if edit.get("record_kind") != "plr_orfc":
            raise UnsupportedMutation("only plr_orfc mutation is supported")
        line = int(edit.get("line", 0))
        if line <= 0 or line in seen_lines:
            raise MutationValidationError("invalid or duplicate mutation line")
        seen_lines.add(line)


def _format_plr(parameters: Mapping[str, Any]) -> str:
    return " ".join([
        f"{float(parameters['lam']):.8g}",
        f"{float(parameters['turb']):.8g}",
        f"{float(parameters['expt']):.8g}",
        f"{float(parameters['area_m2']):.8g}",
        f"{float(parameters['diameter_m']):.8g}",
        f"{float(parameters['coef']):.8g}",
        f"{float(parameters['reynolds']):.8g}",
        str(int(parameters["u_A"])),
        str(int(parameters["u_D"])),
    ])


def apply_mutation_plan(
    *,
    project_path: str | Path,
    output_path: str | Path,
    plan: Mapping[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    validate_mutation_plan(plan)
    src = Path(project_path)
    dst = Path(output_path)
    if not src.is_file():
        raise FileNotFoundError(src)
    if not dry_run and src.resolve() == dst.resolve():
        raise MutationValidationError(
            "in-place CONTAM mutation is forbidden; write a new PRJ revision to preserve lineage"
        )

    before_sha = sha256_file(src)
    if before_sha != plan.get("expected_project_sha256"):
        raise BindingDriftError("CONTAM project changed after mutation plan was built")

    before_inventory = parse_prj_inventory(src)
    before_struct = structural_digest(before_inventory)
    if before_struct != plan.get("expected_structural_inventory_sha256"):
        raise BindingDriftError("CONTAM structural inventory changed after mutation plan was built")

    raw = src.read_text(errors="strict")
    newline = "\r\n" if "\r\n" in raw else "\n"
    had_final_newline = raw.endswith(("\n", "\r"))
    lines = raw.splitlines()
    changes: list[dict[str, Any]] = []

    for edit in plan["edits"]:
        idx = int(edit["line"]) - 1
        if idx < 0 or idx >= len(lines):
            raise MutationValidationError(f"mutation line out of range: {edit['line']}")
        old_tokens = lines[idx].split()
        if len(old_tokens) < 9:
            raise MutationValidationError(
                f"target line {edit['line']} no longer looks like plr_orfc"
            )
        current_inventory = next(
            (
                x for x in before_inventory.get("flow_elements", [])
                if int(x["number"]) == int(edit["contam_flow_element_number"])
            ),
            None,
        )
        if current_inventory is None or dict(current_inventory.get("parameters") or {}) != dict(edit["before"]):
            raise BindingDriftError(
                f"flow element {edit['contam_flow_element_number']} parameters changed after plan"
            )
        new_line = _format_plr(edit["after"])
        changes.append({
            "flow_path_id": edit["flow_path_id"],
            "contam_flow_element_number": edit["contam_flow_element_number"],
            "line": int(edit["line"]),
            "before_line": lines[idx],
            "after_line": new_line,
            "before": edit["before"],
            "after": edit["after"],
        })
        lines[idx] = new_line

    candidate = newline.join(lines) + (newline if had_final_newline else "")
    with tempfile.TemporaryDirectory(prefix="spatialruntime-contam-") as td:
        candidate_path = Path(td) / src.name
        candidate_path.write_text(candidate, encoding="utf-8", newline="")
        after_inventory = parse_prj_inventory(candidate_path)
        after_struct = structural_digest(after_inventory)
        if after_struct != before_struct:
            raise BindingDriftError(
                "approved mutation changed CONTAM native structural identity/connectivity"
            )
        after_sha = sha256_file(candidate_path)
        if after_sha == before_sha:
            raise MutationValidationError("mutation produced no project content change")

        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            temp_out = dst.with_name(dst.name + ".tmp")
            temp_out.write_bytes(candidate_path.read_bytes())
            temp_out.replace(dst)

    report = {
        "schema": REPORT_SCHEMA,
        "case_id": plan.get("case_id"),
        "source_step": int(plan.get("source_step", 0)),
        "source_revision": int(plan.get("source_revision", 0)),
        "binding_revision_before": int(plan.get("binding_revision", 0)),
        "plan_hash": plan["plan_hash"],
        "dry_run": bool(dry_run),
        "applied": not dry_run,
        "source_project": str(src),
        "output_project": None if dry_run else str(dst),
        "before_project_sha256": before_sha,
        "after_project_sha256": after_sha,
        "before_structural_inventory_sha256": before_struct,
        "after_structural_inventory_sha256": after_struct,
        "change_count": len(changes),
        "changes": changes,
    }
    return report
