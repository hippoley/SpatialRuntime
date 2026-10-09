#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("P0-CLOSURE.v0.1.json")
EXTERNAL_REGISTRY = ROOT / "interop" / "external-results" / "registry.v0.1.json"


def _is_unrelated(repo: object) -> bool:
    return isinstance(repo, str) and "/" in repo and not repo.startswith("hippoley/")


def _external_gate_closed(registry: dict) -> tuple[bool, list[dict]]:
    qualifying: list[dict] = []
    for entry in registry.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("evidence_maturity") != "externally-consumed":
            continue
        if entry.get("external_consumption") is not True:
            continue
        consumer = entry.get("consumer")
        if not isinstance(consumer, dict):
            continue
        if consumer.get("project_owned_evidence") is not True:
            continue
        if not _is_unrelated(consumer.get("repository")):
            continue
        qualifying.append({
            "id": entry.get("id"),
            "repository": consumer.get("repository"),
        })
    return bool(qualifying), qualifying


def verify() -> dict:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    registry = json.loads(EXTERNAL_REGISTRY.read_text(encoding="utf-8"))
    errors: list[str] = []
    rows: list[dict] = []

    for item in doc.get("p0", []):
        p0_id = item.get("id")
        owner = item.get("owner")
        expected = item.get("expected")

        if owner == "repository":
            missing = []
            for rel in item.get("evidence_paths", []):
                path = ROOT / rel
                if not path.is_file():
                    missing.append(rel)
            status = "CLOSED" if not missing else "OPEN"
            if expected == "CLOSED" and missing:
                errors.append(f"{p0_id}: missing evidence paths: {missing}")
            rows.append({
                "id": p0_id,
                "owner": owner,
                "status": status,
                "missing_evidence": missing,
            })
            continue

        if p0_id == "P0-D":
            closed, qualifying = _external_gate_closed(registry)
            rows.append({
                "id": p0_id,
                "owner": owner,
                "status": "CLOSED" if closed else "OPEN_EXTERNAL_GATE",
                "qualifying_evidence": qualifying,
            })
            if expected == "OPEN_UNTIL_EXTERNAL_EVIDENCE" and not closed:
                # This is not a repository failure. It is the explicit external gate.
                pass
            continue

        errors.append(f"{p0_id}: unknown P0 owner/rule")

    repository_p0 = [row for row in rows if row["owner"] == "repository"]
    internal_closed = all(row["status"] == "CLOSED" for row in repository_p0)
    external_open = any(row["status"] == "OPEN_EXTERNAL_GATE" for row in rows)

    return {
        "schema": doc.get("schema"),
        "repository_owned_p0_closed": internal_closed,
        "external_gate_open": external_open,
        "all_p0_closed": internal_closed and not external_open,
        "rows": rows,
        "errors": errors,
    }


def main() -> None:
    report = verify()
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"]:
        raise SystemExit(1)
    if not report["repository_owned_p0_closed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
