#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("P0-CLOSURE.v0.1.json")
EXTERNAL_REGISTRY = ROOT / "interop" / "external-results" / "registry.v0.1.json"


def _is_unrelated(repo: object) -> bool:
    return isinstance(repo, str) and "/" in repo and not repo.startswith("hippoley/")


def _external_gate(registry: dict) -> tuple[bool, list[dict]]:
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
        if item.get("owner") != "repository":
            errors.append(f"{p0_id}: repository P0 manifest may not contain external-owned gates")
            continue

        missing = []
        for rel in item.get("evidence_paths", []):
            if not (ROOT / rel).is_file():
                missing.append(rel)
        status = "CLOSED" if not missing else "OPEN"
        if item.get("expected") == "CLOSED" and missing:
            errors.append(f"{p0_id}: missing evidence paths: {missing}")
        rows.append({
            "id": p0_id,
            "status": status,
            "missing_evidence": missing,
        })

    repository_p0_closed = bool(rows) and all(row["status"] == "CLOSED" for row in rows)

    external_closed, qualifying = _external_gate(registry)
    external = doc.get("external_exit_gate", {})
    external_status = "CLOSED" if external_closed else "OPEN_EXTERNAL_GATE"

    return {
        "schema": doc.get("schema"),
        "repository_p0_closed": repository_p0_closed,
        "external_adoption_gate": {
            "id": external.get("id"),
            "status": external_status,
            "qualifying_evidence": qualifying,
        },
        "rows": rows,
        "errors": errors,
    }


def main() -> None:
    report = verify()
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"] or not report["repository_p0_closed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
