#!/usr/bin/env python3
"""Validate completeness claims without treating inventory as proof of execution."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = {"function","state","integration","security","performance","maintenance","traceability","testing","user_value","external_compatibility"}
VALID = {"verified","partial","unverified","blocked","not_applicable"}

def audit(data: dict, required: set[str]) -> list[str]:
    errors = []
    stories = data.get("stories")
    if not isinstance(stories, list):
        return ["stories must be a list"]
    ids = [s.get("id") for s in stories if isinstance(s, dict)]
    if len(ids) != len(stories) or len(ids) != len(set(ids)) or set(ids) != required:
        errors.append("story coverage mismatch, duplicate, or malformed story")
    for item in stories:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        horizontal = item.get("horizontal")
        if not isinstance(horizontal, dict) or set(horizontal) != DIMENSIONS:
            errors.append(f"{sid}: dimension coverage mismatch")
            continue
        completed = item.get("vertical") == "verified"
        for name, value in horizontal.items():
            if not isinstance(value, dict) or value.get("status") not in VALID:
                errors.append(f"{sid}/{name}: invalid status")
                completed = False
                continue
            status = value["status"]
            if status == "verified":
                evidence = value.get("evidence")
                if not isinstance(evidence, list) or not evidence or not all(
                    isinstance(entry, dict)
                    and isinstance(entry.get("source"), str)
                    and entry["source"].strip()
                    and entry.get("result") == "PASS"
                    for entry in evidence
                ):
                    errors.append(f"{sid}/{name}: verified requires structured passing evidence")
            if status == "not_applicable" and not value.get("rationale"):
                errors.append(f"{sid}/{name}: N/A without rationale")
            if status not in ("verified","not_applicable"):
                completed = False
        if item.get("closure") == "VERIFIED_CLOSED" and (not completed or errors):
            errors.append(f"{sid}: unsupported VERIFIED_CLOSED claim")
        if item.get("closure") == "VERIFIED_CLOSED" and not (
            isinstance(item.get("vertical_evidence"), list)
            and item["vertical_evidence"]
            and all(
                isinstance(e, dict) and e.get("result") == "PASS" and e.get("source")
                for e in item["vertical_evidence"]
            )
        ):
            errors.append(f"{sid}: missing vertical execution evidence")
    return errors

def main():
    data = json.loads((ROOT/"docs/HORIZONTAL-AUDIT.v0.1.json").read_text())
    p0 = json.loads((ROOT/"docs/P0-CLOSURE.v0.1.json").read_text())
    errors = audit(data, {row["id"] for row in p0["p0"]})
    print(json.dumps({"status":"PASS" if not errors else "FAIL","inventoried":len(data["stories"]),"verified_closed":sum(s.get("closure")=="VERIFIED_CLOSED" for s in data["stories"]),"errors":errors},indent=2))
    if errors:
        raise SystemExit(1)

if __name__=="__main__":
    main()
