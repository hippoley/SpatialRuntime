#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
REGISTRY = HERE / "registry.v0.1.json"
SCHEMA = HERE / "schema.v0.1.json"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
MATURITY = {
    "self-tested",
    "external-source-reviewed",
    "externally-executed",
    "externally-reproduced",
    "externally-consumed",
}
ACK = {"none", "unknown", "explicit"}


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def verify(doc: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    _require(
        doc.get("schema") == "spatialruntime.external-results-registry.v0.1",
        "registry schema mismatch",
        errors,
    )
    entries = doc.get("entries")
    _require(isinstance(entries, list), "entries must be a list", errors)
    if not isinstance(entries, list):
        entries = []

    seen: set[str] = set()
    maturity_counts: dict[str, int] = {key: 0 for key in MATURITY}

    for index, entry in enumerate(entries):
        prefix = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be object")
            continue

        entry_id = entry.get("id")
        _require(isinstance(entry_id, str) and bool(entry_id), f"{prefix}.id required", errors)
        if isinstance(entry_id, str):
            _require(entry_id not in seen, f"duplicate id: {entry_id}", errors)
            seen.add(entry_id)

        impl = entry.get("implementation")
        _require(isinstance(impl, dict), f"{prefix}.implementation required", errors)
        if isinstance(impl, dict):
            _require(
                isinstance(impl.get("repository"), str) and "/" in impl.get("repository", ""),
                f"{prefix}.implementation.repository must be owner/repo",
                errors,
            )
            kind = impl.get("locator_kind")
            revision = impl.get("revision")
            _require(kind in {"git_commit", "package_version"}, f"{prefix}.locator_kind invalid", errors)
            if kind == "git_commit":
                _require(
                    isinstance(revision, str) and bool(SHA40.fullmatch(revision)),
                    f"{prefix}.implementation.revision must be 40-hex git commit",
                    errors,
                )
            elif kind == "package_version":
                _require(
                    isinstance(revision, str) and bool(revision),
                    f"{prefix}.package revision required",
                    errors,
                )

        sr = entry.get("spatialruntime")
        _require(isinstance(sr, dict), f"{prefix}.spatialruntime required", errors)
        if isinstance(sr, dict):
            _require(
                isinstance(sr.get("probe"), str) and bool(sr.get("probe")),
                f"{prefix}.spatialruntime.probe required",
                errors,
            )
            _require(
                isinstance(sr.get("probe_revision"), str)
                and bool(SHA40.fullmatch(sr.get("probe_revision", ""))),
                f"{prefix}.spatialruntime.probe_revision must be 40-hex",
                errors,
            )

        execution = entry.get("execution")
        _require(isinstance(execution, dict), f"{prefix}.execution required", errors)
        if isinstance(execution, dict):
            _require(
                isinstance(execution.get("workflow_run_id"), int)
                and execution["workflow_run_id"] > 0,
                f"{prefix}.workflow_run_id invalid",
                errors,
            )
            _require(
                isinstance(execution.get("artifact_id"), int)
                and execution["artifact_id"] > 0,
                f"{prefix}.artifact_id invalid",
                errors,
            )
            _require(
                isinstance(execution.get("artifact_name"), str)
                and bool(execution["artifact_name"]),
                f"{prefix}.artifact_name required",
                errors,
            )
            _require(
                isinstance(execution.get("artifact_digest"), str)
                and bool(DIGEST.fullmatch(execution["artifact_digest"])),
                f"{prefix}.artifact_digest invalid",
                errors,
            )
            expected_url = (
                "https://github.com/hippoley/SpatialRuntime/actions/runs/"
                + str(execution.get("workflow_run_id"))
            )
            _require(
                execution.get("workflow_url") == expected_url,
                f"{prefix}.workflow_url does not match workflow_run_id",
                errors,
            )

        maturity = entry.get("evidence_maturity")
        _require(maturity in MATURITY, f"{prefix}.evidence_maturity invalid", errors)
        if maturity in MATURITY:
            maturity_counts[maturity] += 1

        _require(
            entry.get("source_project_acknowledgment") in ACK,
            f"{prefix}.source_project_acknowledgment invalid",
            errors,
        )
        _require(
            isinstance(entry.get("external_consumption"), bool),
            f"{prefix}.external_consumption must be boolean",
            errors,
        )
        _require(
            isinstance(entry.get("adoption_claim"), bool),
            f"{prefix}.adoption_claim must be boolean",
            errors,
        )
        _require(
            isinstance(entry.get("nonclaims"), list) and len(entry.get("nonclaims", [])) > 0,
            f"{prefix}.nonclaims must be non-empty list",
            errors,
        )

        if maturity == "externally-reproduced":
            reproducer = entry.get("reproducer")
            _require(
                isinstance(reproducer, dict)
                and reproducer.get("unrelated") is True
                and isinstance(reproducer.get("public_evidence"), str),
                f"{prefix}: externally-reproduced requires unrelated public reproducer evidence",
                errors,
            )

        if maturity == "externally-consumed" or entry.get("external_consumption") is True:
            consumer = entry.get("consumer")
            _require(
                isinstance(consumer, dict)
                and consumer.get("project_owned_evidence") is True
                and isinstance(consumer.get("repository"), str)
                and not consumer.get("repository", "").startswith("hippoley/"),
                f"{prefix}: external consumption requires unrelated project-owned evidence",
                errors,
            )

        retained = entry.get("retained_report")
        if maturity in {"externally-executed", "externally-reproduced", "externally-consumed"}:
            _require(
                isinstance(retained, dict),
                f"{prefix}: retained_report required for durable external evidence",
                errors,
            )
            if isinstance(retained, dict):
                rel = retained.get("path")
                blob_sha = retained.get("git_blob_sha")
                _require(
                    isinstance(rel, str) and bool(rel),
                    f"{prefix}.retained_report.path required",
                    errors,
                )
                _require(
                    isinstance(blob_sha, str) and bool(SHA40.fullmatch(blob_sha)),
                    f"{prefix}.retained_report.git_blob_sha must be 40-hex",
                    errors,
                )
                if isinstance(rel, str) and rel:
                    report_path = ROOT / rel
                    _require(
                        report_path.is_file(),
                        f"{prefix}: retained report missing: {rel}",
                        errors,
                    )
                    if report_path.is_file() and isinstance(blob_sha, str):
                        actual_blob = _git_blob_sha(report_path)
                        _require(
                            actual_blob == blob_sha,
                            f"{prefix}: retained report blob drift: {actual_blob} != {blob_sha}",
                            errors,
                        )
                _require(
                    retained.get("retention") == "git_history",
                    f"{prefix}.retained_report.retention must be git_history",
                    errors,
                )
                _require(
                    retained.get("source_artifact_digest")
                    == (entry.get("execution") or {}).get("artifact_digest"),
                    f"{prefix}: retained report must bind original artifact digest",
                    errors,
                )

        if entry.get("adoption_claim") is True:
            _require(
                maturity == "externally-consumed"
                and entry.get("external_consumption") is True,
                f"{prefix}: adoption claim requires externally-consumed evidence",
                errors,
            )

    return {
        "schema": doc.get("schema"),
        "entries": len(entries),
        "maturity_counts": maturity_counts,
        "valid": not errors,
        "errors": errors,
    }


def main() -> None:
    json.loads(SCHEMA.read_text(encoding="utf-8"))
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    report = verify(doc)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
