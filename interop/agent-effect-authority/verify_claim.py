#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "manifest.json"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: expected non-empty string")
    return value.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("claim", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    manifest = load(args.manifest)
    claim = load(args.claim)

    spec = text(manifest.get("spec"), "manifest.spec")
    if claim.get("spec") != spec:
        raise ValueError(f"claim spec mismatch: {claim.get('spec')!r} != {spec!r}")

    implementation = claim.get("implementation")
    if not isinstance(implementation, dict):
        raise ValueError("implementation: expected object")
    name = text(implementation.get("name"), "implementation.name")
    version = text(implementation.get("version"), "implementation.version")

    manifest_reqs = manifest.get("requirements")
    if not isinstance(manifest_reqs, list) or not manifest_reqs:
        raise ValueError("manifest.requirements: expected non-empty list")
    manifest_by_id = {
        text(r.get("id"), "manifest.requirements[].id"): r
        for r in manifest_reqs
    }
    required = set(manifest_by_id)

    claims = claim.get("requirements")
    if not isinstance(claims, list):
        raise ValueError("claim.requirements: expected list")

    by_id = {}
    for item in claims:
        if not isinstance(item, dict):
            raise ValueError("claim.requirements[]: expected object")
        req_id = text(item.get("id"), "claim.requirements[].id")
        if req_id in by_id:
            raise ValueError(f"duplicate requirement: {req_id}")
        by_id[req_id] = item

    unknown = set(by_id) - required
    missing = required - set(by_id)
    if unknown:
        raise ValueError(f"unknown requirements: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing requirements: {sorted(missing)}")

    not_applicable = []
    for req_id in sorted(required):
        item = by_id[req_id]
        status = item.get("status")
        applicability = manifest_by_id[req_id].get("applicability", "required")

        if status == "NOT_APPLICABLE":
            if applicability != "conditional":
                raise ValueError(
                    f"{req_id}: NOT_APPLICABLE is allowed only for conditional requirements"
                )
            rationale = text(item.get("rationale"), f"{req_id}.rationale")
            not_applicable.append({"id": req_id, "rationale": rationale})
            evidence = item.get("evidence", [])
            if evidence not in (None, []):
                raise ValueError(
                    f"{req_id}: NOT_APPLICABLE claims must not attach PASS evidence"
                )
            continue

        if status != "PASS":
            raise ValueError(
                f"{req_id}: status must be PASS"
                + (" or NOT_APPLICABLE" if applicability == "conditional" else "")
            )

        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{req_id}: evidence must be non-empty")
        for i, ref in enumerate(evidence):
            if not isinstance(ref, dict):
                raise ValueError(f"{req_id}.evidence[{i}]: expected object")
            text(ref.get("type"), f"{req_id}.evidence[{i}].type")
            text(ref.get("ref"), f"{req_id}.evidence[{i}].ref")

    print(json.dumps({
        "spec": spec,
        "implementation": {"name": name, "version": version},
        "requirements": len(required),
        "not_applicable": not_applicable,
        "claim_envelope": "PASS",
        "evidence_truth_verified": False
    }, indent=2))


if __name__ == "__main__":
    main()
