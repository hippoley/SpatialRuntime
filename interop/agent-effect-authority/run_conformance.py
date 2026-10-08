import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "interop" / "agent-effect-authority"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


single = _load("verify_effect_observation", "verify_effect_observation.py")
multi = _load("verify_effect_evidence_set", "verify_effect_evidence_set.py")


def run():
    results = []

    single_vectors = json.loads(
        (BASE / "iev-adversarial-vectors.v0.1.json").read_text(encoding="utf-8")
    )
    policy = single_vectors["authority_policy"]
    for case in single_vectors["cases"]:
        observed = single.evaluate_observation(case["observation"], policy)
        results.append({
            "suite": "iev-adversarial-v0.1",
            "case_id": case["id"],
            "expected": case["expected"],
            "observed": observed,
            "pass": observed == case["expected"],
        })

    conflict_vectors = json.loads(
        (BASE / "authentic-evidence-conflict-v0.1.json").read_text(encoding="utf-8")
    )
    policy = conflict_vectors["authority_policy"]
    for case in conflict_vectors["cases"]:
        observed = multi.evaluate_evidence_set(case["observations"], policy)
        results.append({
            "suite": "authentic-evidence-conflict-v0.1",
            "case_id": case["id"],
            "expected": case["expected"],
            "observed": observed,
            "pass": observed == case["expected"],
        })

    passed = sum(1 for row in results if row["pass"])
    summary = {
        "conformance_bundle": "effect-evidence-v0.1",
        "passed": passed,
        "failed": len(results) - passed,
        "total": len(results),
        "results": results,
    }
    return summary


def main():
    summary = run()
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
