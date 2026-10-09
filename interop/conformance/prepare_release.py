#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "manifest.v0.1.json"
CONTRACT = HERE / "release-contract.v0.1.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    pattern = re.compile(contract["tag_pattern"])
    if pattern.fullmatch(args.tag) is None:
        raise SystemExit(f"tag does not match release contract: {args.tag}")
    if re.fullmatch(r"[0-9a-f]{40}", args.commit) is None:
        raise SystemExit("commit must be an exact 40-hex Git commit")

    modes = sorted(
        entry["mode"]
        for entry in catalog.get("profiles", [])
        if isinstance(entry, dict) and isinstance(entry.get("mode"), str)
    )
    manifest = {
        "schema": "spatialruntime.conformance-release-manifest.v0.1",
        "tag": args.tag,
        "commit": args.commit,
        "catalog_schema": catalog.get("schema"),
        "included_modes": modes,
        "compatibility_aliases": list(catalog.get("legacy_compatible_actions", [])),
        "preferred_action": catalog.get("preferred_action"),
        "changelog": "interop/conformance/CHANGELOG.md",
        "semantic_maturity_source": "interop/conformance-maturity.v0.1.json",
        "evidence_registry": "interop/external-results/registry.v0.1.json",
        "note": "Generating this manifest does not create or prove the Git tag.",
    }

    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
