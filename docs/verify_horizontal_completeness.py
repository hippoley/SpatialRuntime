#!/usr/bin/env python3
"""Fail-closed verifier for horizontal User Story completeness.

The product audit remains the longitudinal source of truth. This verifier adds
an orthogonal gate: every story must have all ten required dimensions,
dependency edges must be valid/acyclic, and VERIFIED_CLOSED is forbidden when
any applicable dimension or independent acceptance remains unresolved.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "PRODUCT-BOUNDARY-AUDIT.md"
MATRIX = ROOT / "docs" / "horizontal-completeness.v0.1.json"

REQUIRED_DIMENSIONS = {
    "functional_completeness",
    "state_completeness",
    "integration_completeness",
    "security_correctness",
    "performance_scalability",
    "maintainability",
    "observability_traceability",
    "testability",
    "user_value_completeness",
    "external_compatibility",
}
ALLOWED_DIMENSION_STATUS = {"VERIFIED", "PARTIAL", "MISSING", "N_A", "BLOCKED"}
ALLOWED_CLOSURE = {
    "VERIFIED_CLOSED",
    "PARTIAL",
    "OPEN",
    "HOLD",
    "BLOCKED_FIELD",
    "BLOCKED_EXTERNAL",
    "BLOCKED_UPSTREAM",
}
ALLOWED_VERTICAL = {"DONE", "PARTIAL", "OPEN", "HOLD"}
ALLOWED_ACCEPTANCE = {"VERIFIED", "PARTIAL", "BLOCKED", "MISSING"}


def _story_table() -> dict[str, str]:
    text = AUDIT.read_text(encoding="utf-8")
    start = text.index("## User-story truth table")
    end = text.index("\n## ", start + 4)
    rows = {}
    pattern = re.compile(r"^\|\s*((?:SR|CF|AD)-\d+)\s*\|.*?\|\s*(DONE|PARTIAL|OPEN|HOLD)\s*\|", re.M)
    for story_id, status in pattern.findall(text[start:end]):
        rows[story_id] = status
    return rows


def _repo_evidence_exists(ref: str) -> bool:
    if not ref.startswith("repo:"):
        return True
    rel = ref.removeprefix("repo:")
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        return False
    return (ROOT / rel).exists()


def _validate_evidence(story_id: str, label: str, evidence: object, errors: list[str]) -> None:
    if not isinstance(evidence, list):
        errors.append(f"{story_id} {label}: evidence must be a list")
        return
    for ref in evidence:
        if not isinstance(ref, str) or not ref:
            errors.append(f"{story_id} {label}: invalid evidence reference")
        elif not (ref.startswith("repo:") or ref.startswith("external:https://")):
            errors.append(f"{story_id} {label}: unsupported evidence reference {ref!r}")
        elif not _repo_evidence_exists(ref):
            errors.append(f"{story_id} {label}: repository evidence missing: {ref}")


def _detect_cycle(stories: dict[str, dict]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, path: list[str]) -> list[str] | None:
        if node in visiting:
            idx = path.index(node)
            return path[idx:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        path.append(node)
        for dep in stories[node].get("dependencies", []):
            cycle = visit(dep, path)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in stories:
        cycle = visit(node, [])
        if cycle:
            return cycle
    return None


def verify() -> dict:
    errors: list[str] = []
    doc = json.loads(MATRIX.read_text(encoding="utf-8"))
    vertical = _story_table()
    stories = doc.get("stories")

    if doc.get("schema") != "spatialruntime.horizontal-completeness.v0.1":
        errors.append("schema mismatch")
    if set(doc.get("dimensions", [])) != REQUIRED_DIMENSIONS:
        errors.append("top-level dimensions drift")
    if not isinstance(stories, dict):
        stories = {}
        errors.append("stories must be an object")

    missing = sorted(set(vertical) - set(stories))
    unknown = sorted(set(stories) - set(vertical))
    if missing or unknown:
        errors.append(f"story coverage drift: missing={missing}, unknown={unknown}")

    for story_id, entry in stories.items():
        if not isinstance(entry, dict):
            errors.append(f"{story_id}: story entry must be an object")
            continue

        status = entry.get("vertical_status")
        if status not in ALLOWED_VERTICAL:
            errors.append(f"{story_id}: invalid vertical_status {status!r}")
        elif vertical.get(story_id) != status:
            errors.append(
                f"{story_id}: vertical status drift matrix={status} audit={vertical.get(story_id)}"
            )

        closure = entry.get("horizontal_closure")
        if closure not in ALLOWED_CLOSURE:
            errors.append(f"{story_id}: invalid horizontal_closure {closure!r}")

        deps = entry.get("dependencies")
        if not isinstance(deps, list) or len(deps) != len(set(deps)):
            errors.append(f"{story_id}: dependencies must be a unique list")
            deps = []
        for dep in deps:
            if dep == story_id:
                errors.append(f"{story_id}: self dependency")
            elif dep not in stories:
                errors.append(f"{story_id}: unknown dependency {dep}")

        dimensions = entry.get("dimensions")
        if not isinstance(dimensions, dict):
            errors.append(f"{story_id}: dimensions must be an object")
            continue
        observed = set(dimensions)
        if observed != REQUIRED_DIMENSIONS:
            errors.append(
                f"{story_id}: dimension coverage drift "
                f"missing={sorted(REQUIRED_DIMENSIONS-observed)} "
                f"unknown={sorted(observed-REQUIRED_DIMENSIONS)}"
            )

        unresolved = []
        for dim in REQUIRED_DIMENSIONS & observed:
            item = dimensions[dim]
            if not isinstance(item, dict):
                errors.append(f"{story_id} {dim}: dimension must be an object")
                continue
            dstatus = item.get("status")
            if dstatus not in ALLOWED_DIMENSION_STATUS:
                errors.append(f"{story_id} {dim}: invalid status {dstatus!r}")
                continue
            note = item.get("note")
            if not isinstance(note, str) or not note.strip():
                errors.append(f"{story_id} {dim}: rationale/note required")
            evidence = item.get("evidence")
            _validate_evidence(story_id, dim, evidence, errors)
            if dstatus == "VERIFIED" and not evidence:
                errors.append(f"{story_id} {dim}: VERIFIED requires evidence")
            if dstatus == "N_A" and evidence:
                errors.append(f"{story_id} {dim}: N_A must not carry acceptance evidence")
            if dstatus in {"PARTIAL", "MISSING", "BLOCKED"}:
                unresolved.append(dim)

        acceptance = entry.get("independent_acceptance")
        if not isinstance(acceptance, dict):
            errors.append(f"{story_id}: independent_acceptance must be an object")
            acceptance_status = None
        else:
            acceptance_status = acceptance.get("status")
            if acceptance_status not in ALLOWED_ACCEPTANCE:
                errors.append(f"{story_id}: invalid independent acceptance status")
            _validate_evidence(
                story_id,
                "independent_acceptance",
                acceptance.get("evidence"),
                errors,
            )
            if not isinstance(acceptance.get("note"), str) or not acceptance["note"].strip():
                errors.append(f"{story_id}: independent acceptance note required")

        solution = entry.get("solution_assessment")
        if not isinstance(solution, dict) or solution.get("decision") not in {
            "KEEP", "ADAPT", "REPLACE", "HOLD"
        }:
            errors.append(f"{story_id}: solution_assessment decision missing/invalid")
        elif not isinstance(solution.get("note"), str) or not solution["note"].strip():
            errors.append(f"{story_id}: solution_assessment note required")

        if closure == "VERIFIED_CLOSED":
            if status != "DONE":
                errors.append(f"{story_id}: VERIFIED_CLOSED requires vertical DONE")
            if unresolved:
                errors.append(
                    f"{story_id}: VERIFIED_CLOSED has unresolved dimensions {sorted(unresolved)}"
                )
            if acceptance_status != "VERIFIED":
                errors.append(
                    f"{story_id}: VERIFIED_CLOSED requires independent acceptance VERIFIED"
                )
        elif closure.startswith("BLOCKED_"):
            if not isinstance(entry.get("gate"), str) or not entry["gate"].strip():
                errors.append(f"{story_id}: blocked closure requires explicit gate")
        elif closure == "HOLD":
            if solution.get("decision") != "HOLD":
                errors.append(f"{story_id}: HOLD closure requires HOLD solution assessment")

    if stories:
        cycle = _detect_cycle(stories)
        if cycle:
            errors.append("dependency cycle: " + " -> ".join(cycle))

    verified = sorted(
        story_id for story_id, entry in stories.items()
        if entry.get("horizontal_closure") == "VERIFIED_CLOSED"
    )
    blocked = sorted(
        story_id for story_id, entry in stories.items()
        if str(entry.get("horizontal_closure", "")).startswith("BLOCKED_")
    )
    return {
        "schema": doc.get("schema"),
        "story_count": len(stories),
        "verified_closed": verified,
        "blocked_gates": blocked,
        "errors": errors,
        "horizontal_audit_valid": not errors,
    }


def main() -> None:
    report = verify()
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
