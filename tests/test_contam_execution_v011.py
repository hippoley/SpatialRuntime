from pathlib import Path
import json
import os
import stat

import pytest

from spatialruntime.solver.contract import build_solver_request
from spatialruntime.solver.contam.adapter import ContamProjectSolverAdapter
from spatialruntime.solver.contam.binding import build_binding_registry
from spatialruntime.solver.contam.cli import ContamCliRunner
from spatialruntime.solver.contam.execution import (
    ContamCliResultProvider,
    ContamInputRejected,
    ContamResultArtifactError,
    ExplicitResultArtifacts,
)
from spatialruntime.solver.contam.inventory import parse_prj_inventory

PRJ = """! Section 10: Airflow Elements
1
! nr icon dtype name
1 1 plr_orfc WindowPLR
window opening
0.01 0.14 0.65 1.68 1.2 0.60 30 0 0
-999
! Section 14: Zones
1
! zone records
1 0 0 Kitchen
-999
! Section 16: Airflow Paths
1
! nr flags pzn pzm pe pf pw pa ps
11 0 1 0 1 0 0 0 0
-999
"""


def project_and_registry(tmp_path: Path):
    project = tmp_path / "case.prj"
    project.write_text(PRJ, encoding="utf-8")
    inventory = parse_prj_inventory(project)
    registry = build_binding_registry(
        case_id="case",
        project_path=project,
        inventory=inventory,
        mappings={
            "zones": {
                "zone::kitchen": {"contam_zone_number": 1},
            },
            "flow_paths": {
                "flow::window": {
                    "contam_path_number": 11,
                    "contam_flow_element_number": 1,
                },
            },
        },
    )
    return project, registry


def make_fake_contamx(tmp_path: Path, *, reject_test_input: bool = False, write_result: bool = True):
    exe = tmp_path / "fake-contamx"
    script = f"""#!/usr/bin/env python3
import json
import pathlib
import sys

if '--Version' in sys.argv or '--version' in sys.argv or '-v' in sys.argv:
    print('Fake ContamX 3.4.0.3')
    raise SystemExit(0)

if len(sys.argv) < 2:
    print('missing project', file=sys.stderr)
    raise SystemExit(2)

project = pathlib.Path(sys.argv[1])
if '--TestInput' in sys.argv:
    print('test-input')
    raise SystemExit({3 if reject_test_input else 0})

if {write_result!r}:
    result = project.with_name(project.stem + '.result.json')
    result.write_text(json.dumps({{
        'zones': [
            {{'number': 1, 'pressure_pa': 2.25, 'temperature_c': 22.5, 'ach_1_h': 0.7}}
        ],
        'paths': [
            {{'number': 11, 'flow_m3_s': 0.11, 'pressure_difference_pa': 4.0}}
        ]
    }}), encoding='utf-8')
print('solve-ok')
raise SystemExit(0)
"""
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return exe


def request():
    return build_solver_request(
        case_id="case",
        source_step=2,
        source_revision=2,
        world_state={"window": {"executed_state": {"open_ratio": 0.5}}},
    )


def test_cli_execution_provider_runs_testinput_solve_and_loads_fresh_artifact(tmp_path):
    project, registry = project_and_registry(tmp_path)
    exe = make_fake_contamx(tmp_path)
    runner = ContamCliRunner(executable=str(exe), timeout_s=10)
    artifacts = ExplicitResultArtifacts(api_json="{stem}.result.json")
    provider = ContamCliResultProvider(runner=runner, artifacts=artifacts)

    adapter = ContamProjectSolverAdapter(
        project_path=project,
        binding_registry=registry,
        result_provider=provider,
    )
    feedback = adapter.solve(request())

    assert feedback["zones"]["zone::kitchen"]["pressure_pa"] == 2.25
    assert feedback["flow_paths"]["flow::window"]["flow_m3_s"] == 0.11
    evidence = feedback["metadata"]["native_execution"]
    assert evidence["schema"] == "contam_execution_evidence_v0.11"
    assert evidence["test_input"]["returncode"] == 0
    assert evidence["solve"]["returncode"] == 0
    assert evidence["solve"]["version"] == "Fake ContamX 3.4.0.3"
    assert evidence["binding_revision"] == 0
    assert len(evidence["execution_hash"]) == 64
    assert evidence["artifacts"]["api_json"].endswith("case.result.json")


def test_testinput_rejection_stops_before_solve(tmp_path):
    project, registry = project_and_registry(tmp_path)
    exe = make_fake_contamx(tmp_path, reject_test_input=True)
    runner = ContamCliRunner(executable=str(exe), timeout_s=10)
    provider = ContamCliResultProvider(
        runner=runner,
        artifacts=ExplicitResultArtifacts(api_json="{stem}.result.json"),
    )
    with pytest.raises(ContamInputRejected, match="--TestInput rejected"):
        provider(request(), project, registry)
    assert not (tmp_path / "case.result.json").exists()


def test_stale_result_artifact_is_rejected(tmp_path):
    project, registry = project_and_registry(tmp_path)
    exe = make_fake_contamx(tmp_path, write_result=False)
    result = tmp_path / "case.result.json"
    result.write_text(json.dumps({
        "zones": [{"number": 1, "pressure_pa": 99.0}],
        "paths": [{"number": 11, "flow_m3_s": 99.0}],
    }), encoding="utf-8")

    runner = ContamCliRunner(executable=str(exe), timeout_s=10)
    provider = ContamCliResultProvider(
        runner=runner,
        artifacts=ExplicitResultArtifacts(api_json="{stem}.result.json"),
    )
    with pytest.raises(ContamResultArtifactError, match="stale/unchanged"):
        provider(request(), project, registry)


def test_missing_configured_result_artifact_is_rejected(tmp_path):
    project, registry = project_and_registry(tmp_path)
    exe = make_fake_contamx(tmp_path, write_result=False)
    runner = ContamCliRunner(executable=str(exe), timeout_s=10)
    provider = ContamCliResultProvider(
        runner=runner,
        artifacts=ExplicitResultArtifacts(api_json="{stem}.missing.json"),
    )
    with pytest.raises(ContamResultArtifactError, match="was not produced"):
        provider(request(), project, registry)


def test_non_executable_explicit_path_is_not_available_on_posix(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX executable bit semantics")
    exe = tmp_path / "not-executable"
    exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    exe.chmod(stat.S_IRUSR | stat.S_IWUSR)
    runner = ContamCliRunner(executable=str(exe))
    assert runner.capabilities()["available"] is False
    assert runner.capabilities()["executable"] is None


def test_result_artifact_placeholders_are_explicit_and_relative_to_project(tmp_path):
    project, _ = project_and_registry(tmp_path)
    artifacts = ExplicitResultArtifacts(
        val="{stem}.val",
        path_tsv="exports/{stem}.paths.tsv",
        api_json="{name}.json",
        require_fresh=False,
    )
    paths = artifacts.paths(project)
    assert paths["val"] == tmp_path / "case.val"
    assert paths["path_tsv"] == tmp_path / "exports" / "case.paths.tsv"
    assert paths["api_json"] == tmp_path / "case.prj.json"
