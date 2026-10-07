from pathlib import Path

import pytest

from spatialruntime.solver.contract import build_solver_request
from spatialruntime.solver.contam.adapter import ContamProjectSolverAdapter
from spatialruntime.solver.contam.binding import (
    BindingDriftError,
    BindingValidationError,
    advance_binding_registry_after_mutation,
    build_binding_registry,
    registry_fingerprint,
)
from spatialruntime.solver.contam.inventory import parse_prj_inventory
from spatialruntime.solver.contam.mutation import (
    MutationValidationError,
    UnsupportedMutation,
    apply_mutation_plan,
    build_mutation_plan,
)
from spatialruntime.solver.contam.results import normalize_api_result

PRJ = """! Section 10: Airflow Elements
2
! nr icon dtype name
1 1 plr_orfc WindowPLR
window opening
0.01 0.14 0.65 1.68 1.2 0.60 30 0 0
2 1 plr_orfc DoorPLR
door opening
0.02 0.20 0.65 1.89 1.0 0.65 30 0 0
-999
! Section 14: Zones
2
! zone records
1 0 0 Kitchen
2 0 0 Living
-999
! Section 16: Airflow Paths
2
! nr flags pzn pzm pe pf pw pa ps
11 0 1 0 1 0 0 0 0
12 0 1 2 2 0 0 0 0
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
                "zone::living": {"contam_zone_number": 2},
            },
            "flow_paths": {
                "flow::window": {
                    "contam_path_number": 11,
                    "contam_flow_element_number": 1,
                },
                "flow::door": {
                    "contam_path_number": 12,
                    "contam_flow_element_number": 2,
                },
            },
        },
    )
    return project, inventory, registry


def test_build_and_apply_mutation_preserves_native_structure(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    plan = build_mutation_plan(
        case_id="case",
        source_step=4,
        source_revision=9,
        project_path=project,
        binding_registry=registry,
        inventory=inventory,
        operations=[{
            "kind": "set_flow_path_parameters",
            "flow_path_id": "flow::window",
            "parameters": {
                "area_m2": 0.42,
                "coef": 0.55,
                "expt": 0.62,
            },
        }],
    )
    output = tmp_path / "case-r1.prj"
    report = apply_mutation_plan(
        project_path=project,
        output_path=output,
        plan=plan,
    )

    assert report["applied"] is True
    assert report["change_count"] == 1
    assert report["before_project_sha256"] != report["after_project_sha256"]
    assert (
        report["before_structural_inventory_sha256"]
        == report["after_structural_inventory_sha256"]
    )
    assert output.exists()

    after = parse_prj_inventory(output)
    element = next(x for x in after["flow_elements"] if x["number"] == 1)
    assert element["parameters"]["area_m2"] == 0.42
    assert element["parameters"]["coef"] == 0.55
    assert element["parameters"]["expt"] == 0.62

    assert [z["number"] for z in after["zones"]] == [1, 2]
    assert [p["number"] for p in after["flow_paths"]] == [11, 12]
    assert [e["number"] for e in after["flow_elements"]] == [1, 2]


def test_dry_run_proves_candidate_without_writing_output(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    plan = build_mutation_plan(
        case_id="case",
        source_step=0,
        source_revision=0,
        project_path=project,
        binding_registry=registry,
        inventory=inventory,
        operations=[{
            "kind": "set_flow_path_parameters",
            "flow_path_id": "flow::window",
            "parameters": {"area_m2": 0.2},
        }],
    )
    output = tmp_path / "should-not-exist.prj"
    report = apply_mutation_plan(
        project_path=project,
        output_path=output,
        plan=plan,
        dry_run=True,
    )
    assert report["applied"] is False
    assert report["dry_run"] is True
    assert report["output_project"] is None
    assert not output.exists()
    assert report["before_project_sha256"] != report["after_project_sha256"]


def test_mutation_rejects_unknown_or_structural_parameters(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    with pytest.raises(UnsupportedMutation, match="unsupported mutable parameters"):
        build_mutation_plan(
            case_id="case",
            source_step=0,
            source_revision=0,
            project_path=project,
            binding_registry=registry,
            inventory=inventory,
            operations=[{
                "kind": "set_flow_path_parameters",
                "flow_path_id": "flow::window",
                "parameters": {"diameter_m": 2.0},
            }],
        )


def test_mutation_rejects_invalid_physical_values(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    with pytest.raises(MutationValidationError, match="area_m2 must be >= 0"):
        build_mutation_plan(
            case_id="case",
            source_step=0,
            source_revision=0,
            project_path=project,
            binding_registry=registry,
            inventory=inventory,
            operations=[{
                "kind": "set_flow_path_parameters",
                "flow_path_id": "flow::window",
                "parameters": {"area_m2": -0.1},
            }],
        )


def test_duplicate_operations_against_same_native_element_fail(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    with pytest.raises(MutationValidationError, match="multiple operations target"):
        build_mutation_plan(
            case_id="case",
            source_step=0,
            source_revision=0,
            project_path=project,
            binding_registry=registry,
            inventory=inventory,
            operations=[
                {
                    "kind": "set_flow_path_parameters",
                    "flow_path_id": "flow::window",
                    "parameters": {"area_m2": 0.2},
                },
                {
                    "kind": "set_flow_path_parameters",
                    "flow_path_id": "flow::window",
                    "parameters": {"coef": 0.5},
                },
            ],
        )


def test_plan_fails_if_source_prj_drifts_before_apply(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    plan = build_mutation_plan(
        case_id="case",
        source_step=0,
        source_revision=0,
        project_path=project,
        binding_registry=registry,
        inventory=inventory,
        operations=[{
            "kind": "set_flow_path_parameters",
            "flow_path_id": "flow::window",
            "parameters": {"area_m2": 0.2},
        }],
    )
    project.write_text(PRJ + "\n! drift\n", encoding="utf-8")
    with pytest.raises(BindingDriftError, match="changed after mutation plan"):
        apply_mutation_plan(
            project_path=project,
            output_path=tmp_path / "out.prj",
            plan=plan,
        )


def test_binding_registry_advances_only_after_applied_mutation(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    before_fp = registry_fingerprint(registry)
    plan = build_mutation_plan(
        case_id="case",
        source_step=2,
        source_revision=5,
        project_path=project,
        binding_registry=registry,
        inventory=inventory,
        operations=[{
            "kind": "set_flow_path_parameters",
            "flow_path_id": "flow::window",
            "parameters": {"area_m2": 0.3},
        }],
    )
    output = tmp_path / "case-r1.prj"
    report = apply_mutation_plan(
        project_path=project,
        output_path=output,
        plan=plan,
    )
    advanced = advance_binding_registry_after_mutation(
        registry,
        before_project_path=project,
        before_inventory=inventory,
        after_project_path=output,
        mutation_report=report,
    )

    assert advanced["revision"] == 1
    assert advanced["project"]["sha256"] == report["after_project_sha256"]
    assert advanced["project"]["structural_inventory_sha256"] == report[
        "after_structural_inventory_sha256"
    ]
    assert advanced["lineage"][-1]["revision"] == 0
    assert advanced["lineage"][-1]["source_step"] == 2
    assert advanced["lineage"][-1]["source_revision"] == 5
    assert registry_fingerprint(advanced) != before_fp


def test_dry_run_cannot_advance_binding_registry(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    plan = build_mutation_plan(
        case_id="case",
        source_step=0,
        source_revision=0,
        project_path=project,
        binding_registry=registry,
        inventory=inventory,
        operations=[{
            "kind": "set_flow_path_parameters",
            "flow_path_id": "flow::window",
            "parameters": {"area_m2": 0.3},
        }],
    )
    report = apply_mutation_plan(
        project_path=project,
        output_path=tmp_path / "case-r1.prj",
        plan=plan,
        dry_run=True,
    )
    with pytest.raises(BindingValidationError, match="does not prove an applied mutation"):
        advance_binding_registry_after_mutation(
            registry,
            before_project_path=project,
            before_inventory=inventory,
            after_project_path=project,
            mutation_report=report,
        )


def test_advanced_registry_is_accepted_by_contam_adapter(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    plan = build_mutation_plan(
        case_id="case",
        source_step=0,
        source_revision=0,
        project_path=project,
        binding_registry=registry,
        inventory=inventory,
        operations=[{
            "kind": "set_flow_path_parameters",
            "flow_path_id": "flow::window",
            "parameters": {"area_m2": 0.25},
        }],
    )
    output = tmp_path / "case-r1.prj"
    report = apply_mutation_plan(
        project_path=project,
        output_path=output,
        plan=plan,
    )
    advanced = advance_binding_registry_after_mutation(
        registry,
        before_project_path=project,
        before_inventory=inventory,
        after_project_path=output,
        mutation_report=report,
    )

    def provider(request, project_path, binding_registry):
        assert binding_registry["revision"] == 1
        return normalize_api_result({
            "zones": [{"number": 1, "pressure_pa": 1.0}],
            "paths": [{"number": 11, "flow_m3_s": 0.04}],
        })

    adapter = ContamProjectSolverAdapter(
        project_path=output,
        binding_registry=advanced,
        result_provider=provider,
        strict_binding=False,
    )
    request = build_solver_request(
        case_id="case",
        source_step=1,
        source_revision=1,
        world_state={},
    )
    feedback = adapter.solve(request)
    assert feedback["metadata"]["engine"] == "CONTAM"
    assert feedback["flow_paths"]["flow::window"]["flow_m3_s"] == 0.04
    assert feedback["solver_provenance"]["adapter_id"] == "contam-project-v0.9"


def test_in_place_mutation_is_forbidden_to_preserve_before_evidence(tmp_path):
    project, inventory, registry = project_and_registry(tmp_path)
    plan = build_mutation_plan(
        case_id="case",
        source_step=0,
        source_revision=0,
        project_path=project,
        binding_registry=registry,
        inventory=inventory,
        operations=[{
            "kind": "set_flow_path_parameters",
            "flow_path_id": "flow::window",
            "parameters": {"area_m2": 0.2},
        }],
    )
    with pytest.raises(MutationValidationError, match="in-place CONTAM mutation is forbidden"):
        apply_mutation_plan(
            project_path=project,
            output_path=project,
            plan=plan,
        )
