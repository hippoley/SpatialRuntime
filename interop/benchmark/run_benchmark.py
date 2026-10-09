#!/usr/bin/env python3
"""Run and score the released consequential-effects benchmark.

This scorer intentionally separates:
- implementation conformance on executable scored cases;
- executable requirement coverage;
- pressure/motivation coverage;
- synthetic mutant discrimination;
- corpus identity.

A high pass rate cannot hide missing executable requirement coverage.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "interop" / "benchmark"
AEA = ROOT / "interop" / "agent-effect-authority"

REQUIREMENTS = BENCH / "requirements.v0.1.json"
CASES = BENCH / "cases.v0.1.json"
MUTANTS = BENCH / "mutants.v0.1.json"
PRESSURE = AEA / "case-matrix-v0.1.json"
VECTOR_FILES = {
    "iev-adversarial-v0.1": AEA / "iev-adversarial-vectors.v0.1.json",
    "authentic-evidence-conflict-v0.1": AEA / "authentic-evidence-conflict-v0.1.json",
}
CORPUS_FILES = [REQUIREMENTS, CASES, MUTANTS, PRESSURE, *VECTOR_FILES.values()]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_runner():
    path = AEA / "run_conformance.py"
    spec = importlib.util.spec_from_file_location("aea_run_conformance", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _case_key(suite: str, case_id: str) -> str:
    return f"{suite}::{case_id}"


def _canonical_expected() -> dict[str, dict]:
    out = {}
    for suite, path in VECTOR_FILES.items():
        payload = _load_json(path)
        for case in payload["cases"]:
            key = _case_key(suite, case["id"])
            if key in out:
                raise ValueError(f"duplicate executable case: {key}")
            out[key] = case["expected"]
    return out


def _corpus_digest() -> str:
    h = hashlib.sha256()
    for path in sorted(CORPUS_FILES, key=lambda p: str(p.relative_to(ROOT))):
        rel = str(path.relative_to(ROOT)).encode()
        h.update(rel)
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def score(adapter_command: str | None = None) -> dict:
    req = _load_json(REQUIREMENTS)
    cases_doc = _load_json(CASES)
    mutants_doc = _load_json(MUTANTS)
    pressure_doc = _load_json(PRESSURE)

    requirement_ids = [row["id"] for row in req["requirements"]]
    requirement_set = set(requirement_ids)
    if len(requirement_ids) != len(requirement_set):
        raise ValueError("duplicate benchmark requirement id")

    scored_cases = cases_doc["scored_cases"]
    scored_by_key = {}
    executable_requirements = set()
    for row in scored_cases:
        key = _case_key(row["suite"], row["case_id"])
        if key in scored_by_key:
            raise ValueError(f"duplicate benchmark case mapping: {key}")
        unknown = set(row["requirements"]) - requirement_set
        if unknown:
            raise ValueError(f"{key}: unknown requirements {sorted(unknown)}")
        scored_by_key[key] = row
        executable_requirements.update(row["requirements"])

    canonical = _canonical_expected()
    missing_cases = sorted(set(scored_by_key) - set(canonical))
    if missing_cases:
        raise ValueError(f"benchmark maps unknown executable cases: {missing_cases}")

    pressure_requirements = set()
    pressure_case_count = 0
    pressure_counts = Counter()
    for domain in pressure_doc["domains"]:
        for case in domain["pressure_cases"]:
            pressure_case_count += 1
            unknown = set(case["requirements"]) - requirement_set
            if unknown:
                raise ValueError(
                    f"pressure case {domain['id']}/{case['case']}: unknown requirements {sorted(unknown)}"
                )
            pressure_requirements.update(case["requirements"])
            pressure_counts.update(case["requirements"])

    runner = _load_runner()
    run = runner.run(adapter_command=adapter_command)
    observed = {
        _case_key(row["suite"], row["case_id"]): row
        for row in run["results"]
    }

    scored_results = []
    for key, meta in scored_by_key.items():
        row = observed.get(key)
        if row is None:
            scored_results.append({
                "case": key,
                "pass": False,
                "error": "NOT_MEASURED",
                "requirements": meta["requirements"],
            })
        else:
            scored_results.append({
                "case": key,
                "pass": bool(row["pass"]),
                "expected": row["expected"],
                "observed": row["observed"],
                "requirements": meta["requirements"],
                "outcome_class": meta["outcome_class"],
                "polarity": meta["polarity"],
            })

    passed = sum(1 for row in scored_results if row["pass"])
    failed = len(scored_results) - passed

    mutant_results = []
    for mutant in mutants_doc["mutants"]:
        killed_by = []
        invalid_probes = []
        for probe in mutant["probes"]:
            key = _case_key(probe["suite"], probe["case_id"])
            expected = canonical.get(key)
            if expected is None or key not in scored_by_key:
                invalid_probes.append(key)
                continue
            if probe["faulty_verdict"] != expected:
                killed_by.append(key)
        mutant_results.append({
            "id": mutant["id"],
            "killed": bool(killed_by) and not invalid_probes,
            "killed_by": killed_by,
            "invalid_probes": invalid_probes,
        })

    killed = sum(1 for row in mutant_results if row["killed"])
    balance = Counter(row["polarity"] for row in scored_cases)
    outcome_classes = {row["outcome_class"] for row in scored_cases}
    targets = cases_doc["balance_targets"]
    balance_ok = (
        balance["positive"] >= targets["minimum_positive"]
        and balance["negative"] >= targets["minimum_negative"]
        and balance["adversarial"] >= targets["minimum_adversarial"]
        and len(outcome_classes) >= targets["minimum_outcome_classes"]
    )

    pressure_complete = pressure_requirements == requirement_set
    all_mutants_killed = killed == len(mutant_results)
    implementation_pass = failed == 0
    benchmark_integrity = (
        implementation_pass
        and pressure_complete
        and balance_ok
        and all_mutants_killed
    )

    executable_missing = [rid for rid in requirement_ids if rid not in executable_requirements]
    pressure_missing = [rid for rid in requirement_ids if rid not in pressure_requirements]
    executable_counts = Counter()
    for row in scored_cases:
        executable_counts.update(row["requirements"])
    requirement_distribution = [
        {
            "id": rid,
            "executable_cases": executable_counts[rid],
            "pressure_cases": pressure_counts[rid],
            "gap": pressure_counts[rid] - executable_counts[rid],
        }
        for rid in requirement_ids
    ]
    growth_priorities = sorted(
        [
            row for row in requirement_distribution
            if row["executable_cases"] == 0 and row["pressure_cases"] > 0
        ],
        key=lambda row: (-row["pressure_cases"], row["id"]),
    )

    return {
        "benchmark": req["benchmark"],
        "profile": req["profile"],
        "corpus_digest": _corpus_digest(),
        "adapter_mode": bool(adapter_command),
        "benchmark_integrity_result": "PASS" if benchmark_integrity else "FAIL",
        "implementation_result": "PASS" if implementation_pass else "FAIL",
        "scored_cases": {
            "passed": passed,
            "failed": failed,
            "total": len(scored_results),
            "results": scored_results,
        },
        "executable_requirement_coverage": {
            "covered": len(executable_requirements),
            "total": len(requirement_ids),
            "rate": len(executable_requirements) / len(requirement_ids),
            "covered_ids": [rid for rid in requirement_ids if rid in executable_requirements],
            "missing_ids": executable_missing,
            "full_profile_executable_coverage": not executable_missing,
        },
        "pressure_requirement_coverage": {
            "covered": len(pressure_requirements),
            "total": len(requirement_ids),
            "rate": len(pressure_requirements) / len(requirement_ids),
            "pressure_cases": pressure_case_count,
            "missing_ids": pressure_missing,
        },
        "requirement_distribution": requirement_distribution,
        "dataset_growth_priorities": growth_priorities,
        "case_balance": {
            "positive": balance["positive"],
            "negative": balance["negative"],
            "adversarial": balance["adversarial"],
            "outcome_classes": len(outcome_classes),
            "targets_met": balance_ok,
        },
        "synthetic_discrimination": {
            "killed": killed,
            "total": len(mutant_results),
            "kill_rate": killed / len(mutant_results) if mutant_results else 0.0,
            "mutants": mutant_results,
        },
        "claim_ceiling": [
            "Implementation PASS means only that all currently scored executable benchmark cases matched.",
            "Pressure coverage is not executable coverage.",
            "Synthetic mutant kill rate is a corpus sensitivity control, not an external implementation result.",
            "Full AEA conformance is not claimed while executable requirement coverage is incomplete.",
        ],
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter-command")
    parser.add_argument("--report")
    args = parser.parse_args()

    report = score(adapter_command=args.adapter_command)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report["benchmark_integrity_result"] == "PASS" else 1)


if __name__ == "__main__":
    main()
