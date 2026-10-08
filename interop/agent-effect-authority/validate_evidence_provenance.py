import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEVELS = ROOT / "interop" / "agent-effect-authority" / "evidence-provenance.v0.1.json"

_REQUIRED = {
    "source-review": {"implementation_ref", "source_ref"},
    "executed": {
        "implementation_ref",
        "implementation_version_or_commit",
        "probe_id",
        "run_artifact_ref",
    },
    "externally-reproduced": {
        "implementation_ref",
        "implementation_version_or_commit",
        "probe_id",
        "run_artifact_ref",
        "reproducer_identity",
        "reproducer_artifact_ref",
    },
}


def validate_provenance(record):
    level = record.get("evidence_method")
    if level not in _REQUIRED:
        return {"valid": False, "reason": "UNKNOWN_EVIDENCE_METHOD"}

    missing = sorted(
        key for key in _REQUIRED[level]
        if not record.get(key)
    )
    if missing:
        return {
            "valid": False,
            "reason": "MISSING_REQUIRED_PROVENANCE",
            "missing": missing,
        }

    if level == "source-review":
        if record.get("run_artifact_ref") or record.get("reproducer_artifact_ref"):
            return {
                "valid": False,
                "reason": "SOURCE_REVIEW_CANNOT_CLAIM_RUN_ARTIFACT",
            }

    if level == "executed" and record.get("reproducer_artifact_ref"):
        return {
            "valid": False,
            "reason": "EXECUTED_CANNOT_CLAIM_EXTERNAL_REPRODUCTION",
        }

    return {"valid": True, "reason": "PROVENANCE_COMPLETE"}


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("record")
    args = parser.parse_args()

    record = json.loads(Path(args.record).read_text(encoding="utf-8"))
    result = validate_provenance(record)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
