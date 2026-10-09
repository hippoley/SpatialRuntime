import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "interop" / "benchmark" / "run_benchmark.py"

SPEC = importlib.util.spec_from_file_location("run_consequential_benchmark", RUNNER)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def test_builtin_benchmark_truth_ceiling():
    report = module.score()

    assert report["benchmark_integrity_result"] == "PASS"
    assert report["implementation_result"] == "PASS"
    assert report["scored_cases"]["passed"] == 11
    assert report["scored_cases"]["failed"] == 0
    assert report["scored_cases"]["total"] == 11

    coverage = report["executable_requirement_coverage"]
    assert coverage["covered"] == 4
    assert coverage["total"] == 9
    assert coverage["covered_ids"] == ["AEA-002", "AEA-005", "AEA-006", "AEA-009"]
    assert coverage["missing_ids"] == ["AEA-001", "AEA-003", "AEA-004", "AEA-007", "AEA-008"]
    assert coverage["full_profile_executable_coverage"] is False

    pressure = report["pressure_requirement_coverage"]
    assert pressure["covered"] == 9
    assert pressure["total"] == 9
    assert pressure["missing_ids"] == []

    discrimination = report["synthetic_discrimination"]
    assert discrimination["killed"] == 6
    assert discrimination["total"] == 6
    assert discrimination["kill_rate"] == 1.0


def test_dataset_balance_is_explicit_not_accidental():
    report = module.score()
    balance = report["case_balance"]
    assert balance["positive"] >= 2
    assert balance["negative"] >= 4
    assert balance["adversarial"] >= 2
    assert balance["outcome_classes"] >= 8
    assert balance["targets_met"] is True


def test_corpus_digest_is_content_addressed():
    report = module.score()
    digest = report["corpus_digest"]
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


def test_pressure_only_cases_never_inflate_executable_coverage():
    report = module.score()
    assert report["pressure_requirement_coverage"]["covered"] > report["executable_requirement_coverage"]["covered"]
    assert report["executable_requirement_coverage"]["full_profile_executable_coverage"] is False
