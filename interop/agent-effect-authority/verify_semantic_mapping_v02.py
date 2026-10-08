#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

RELATIONS = {"equivalent","source_stronger","source_weaker","overlaps","orthogonal","unknown"}
TARGET_PREFIXES = ("AEA-", "AEE2-")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def nonempty(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: expected non-empty string")
    return value.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mapping", type=Path)
    args = parser.parse_args()

    doc = load(args.mapping)
    if doc.get("mapping_spec") != "effect-authority.semantic-mapping.v0.2":
        raise ValueError("mapping_spec mismatch")

    source = doc.get("source")
    if not isinstance(source, dict):
        raise ValueError("source: expected object")
    repository = nonempty(source.get("repository"), "source.repository")
    revision = nonempty(source.get("revision"), "source.revision")
    snapshot_date = nonempty(source.get("snapshot_date"), "source.snapshot_date")

    mappings = doc.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        raise ValueError("mappings: expected non-empty list")

    seen = set()
    counts = {relation: 0 for relation in RELATIONS}
    evidence_count = 0
    for i, row in enumerate(mappings):
        if not isinstance(row, dict):
            raise ValueError(f"mappings[{i}]: expected object")
        target = nonempty(row.get("target"), f"mappings[{i}].target")
        if not target.startswith(TARGET_PREFIXES):
            raise ValueError(f"{target}: unsupported target namespace")
        if target in seen:
            raise ValueError(f"duplicate target: {target}")
        seen.add(target)

        relation = nonempty(row.get("relation"), f"{target}.relation")
        if relation not in RELATIONS:
            raise ValueError(f"{target}: unsupported relation {relation!r}")
        counts[relation] += 1
        nonempty(row.get("summary"), f"{target}.summary")
        nonempty(row.get("caveat"), f"{target}.caveat")

        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{target}: evidence must be non-empty")
        for j, item in enumerate(evidence):
            if not isinstance(item, dict):
                raise ValueError(f"{target}.evidence[{j}]: expected object")
            immutable_url = nonempty(item.get("immutable_url"), f"{target}.evidence[{j}].immutable_url")
            if revision not in immutable_url:
                raise ValueError(f"{target}.evidence[{j}]: immutable_url must contain pinned source revision")
            excerpt = nonempty(item.get("excerpt"), f"{target}.evidence[{j}].excerpt")
            expected = nonempty(item.get("excerpt_sha256"), f"{target}.evidence[{j}].excerpt_sha256")
            actual = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
            if actual != expected:
                raise ValueError(f"{target}.evidence[{j}]: excerpt_sha256 mismatch")
            nonempty(item.get("claim"), f"{target}.evidence[{j}].claim")
            evidence_count += 1

    declaration = doc.get("declaration")
    if not isinstance(declaration, dict):
        raise ValueError("declaration: expected object")
    if declaration.get("source_project_adoption") is not False:
        raise ValueError("declaration.source_project_adoption must be false")
    if declaration.get("source_project_endorsement") is not False:
        raise ValueError("declaration.source_project_endorsement must be false")
    nonempty(declaration.get("limitations"), "declaration.limitations")

    print(json.dumps({
        "mapping_spec": doc["mapping_spec"],
        "source": {"repository": repository, "revision": revision, "snapshot_date": snapshot_date},
        "targets": len(seen),
        "evidence_items": evidence_count,
        "relations": {k: v for k, v in sorted(counts.items()) if v},
        "mapping_envelope": "PASS",
        "excerpt_integrity_verified": True,
        "source_project_adoption": False,
        "semantic_truth_verified": False
    }, indent=2))


if __name__ == "__main__":
    main()
