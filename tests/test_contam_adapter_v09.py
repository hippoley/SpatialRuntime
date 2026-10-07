from pathlib import Path

import pytest

from spatialruntime.solver.contract import build_solver_request
from spatialruntime.solver.contam.adapter import ContamProjectSolverAdapter
from spatialruntime.solver.contam.binding import (
    BindingDriftError,
    BindingValidationError,
    build_binding_registry,
    registry_fingerprint,
)
from spatialruntime.solver.contam.inventory import (
    UnsupportedProjectFormat,
    parse_prj_inventory,
)
from spatialruntime.solver.contam.cli import ContamCliRunner
from spatialruntime.solver.contam.results import (
    ResultBindingError,
    ResultParseError,
    ResultProtocolError,
    map_native_results_to_stable,
    merge_result_sources,
    normalize_api_result,
    parse_path_export_tsv,
    parse_result_file,
    parse_val_airflow_summary,
)

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

VAL = """Airflow Summary for	case.prj

Ambient T:	20.0	C
Pressure:	101325	Pa
Wind spd:	1.5	m/s
Wind dir:	180	deg

Bldg ACH:	0.75

Zones:	2 flows [ACH]
zone C/U Supply Ret/Exh OA sys OA tot Circ tot P [Pa] T [C] Vol [m^3]
1 C 0.10 0.20 0.05 0.30 0.00 2.5 22.0 35.0
2 C 0.00 0.10 0.00 0.15 0.00 -1.2 21.5 50.0

"""

TSV = """path_number	flow_m3_s	dp_pa
11	0.12	4.2
12	-0.08	-1.5
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


def test_inventory_extracts_native_ids_and_mutable_record(tmp_path):
    project, inventory, _ = project_and_registry(tmp_path)
    assert [z["number"] for z in inventory["zones"]] == [1, 2]
    assert inventory["flow_paths"][0]["flow_element_number"] == 1
    assert inventory["flow_elements"][0]["dtype"] == "plr_orfc"
    assert inventory["flow_elements"][0]["mutable_record"]["line"] > 0
    assert inventory["project"]["path"] == str(project)


def test_unknown_prj_format_fails_closed(tmp_path):
    project = tmp_path / "bad.prj"
    project.write_text("random text", encoding="utf-8")
    with pytest.raises(UnsupportedProjectFormat):
        parse_prj_inventory(project)


def test_binding_rejects_unknown_or_duplicate_native_ids(tmp_path):
    project = tmp_path / "case.prj"
    project.write_text(PRJ, encoding="utf-8")
    inventory = parse_prj_inventory(project)
    with pytest.raises(BindingValidationError):
        build_binding_registry(
            case_id="case",
            project_path=project,
            inventory=inventory,
            mappings={
                "zones": {
                    "a": {"contam_zone_number": 1},
                    "b": {"contam_zone_number": 1},
                },
                "flow_paths": {},
            },
        )


def test_result_parsers_map_val_and_path_export(tmp_path):
    _, _, registry = project_and_registry(tmp_path)
    val = parse_val_airflow_summary(VAL)
    paths = parse_path_export_tsv(TSV)
    merged = merge_result_sources(val=val, path_export=paths)
    mapped = map_native_results_to_stable(merged, registry)

    assert val["building"]["building_ach_1_h"] == 0.75
    assert mapped["zones"]["zone::kitchen"]["pressure_pa"] == 2.5
    assert mapped["flow_paths"]["flow::window"]["flow_m3_s"] == 0.12
    assert mapped["flow_paths"]["flow::door"]["delta_pressure_pa"] == -1.5


def test_conflicting_result_sources_fail_closed():
    val = parse_val_airflow_summary(VAL)
    api = normalize_api_result({
        "zones": [{"number": 1, "pressure_pa": 3.0}],
        "paths": [],
    })
    with pytest.raises(ResultProtocolError, match="conflicting result sources"):
        merge_result_sources(val=val, api=api)


def test_unmapped_native_result_is_rejected(tmp_path):
    _, _, registry = project_and_registry(tmp_path)
    native = {
        "zones": [{"native_zone_number": 99, "pressure_pa": 0.0}],
        "paths": [],
    }
    with pytest.raises(ResultBindingError):
        map_native_results_to_stable(native, registry, strict=True)


def test_raw_sim_is_explicitly_rejected(tmp_path):
    sim = tmp_path / "case.sim"
    sim.write_bytes(b"\x00\x01")
    with pytest.raises(ResultParseError, match="raw .SIM is binary"):
        parse_result_file(sim, kind="sim_binary")


def test_contam_project_adapter_normalizes_native_results(tmp_path):
    project, _, registry = project_and_registry(tmp_path)

    def provider(request, project_path, binding_registry):
        assert project_path == project
        assert binding_registry["case_id"] == "case"
        return normalize_api_result({
            "zones": [
                {
                    "number": 1,
                    "pressure_pa": 2.5,
                    "temperature_c": 22.0,
                    "airflow_in_m3_s": 0.2,
                    "airflow_out_m3_s": 0.1,
                    "ach_1_h": 0.75,
                },
                {
                    "number": 2,
                    "pressure_pa": -1.2,
                    "temperature_c": 21.5,
                },
            ],
            "paths": [
                {"number": 11, "flow_m3_s": 0.12, "pressure_difference_pa": 4.2},
                {"number": 12, "flow_m3_s": -0.08, "pressure_difference_pa": -1.5},
            ],
        })

    adapter = ContamProjectSolverAdapter(
        project_path=project,
        binding_registry=registry,
        result_provider=provider,
    )
    request = build_solver_request(
        case_id="case",
        source_step=4,
        source_revision=9,
        world_state={"window": {"executed_state": {"open_ratio": 0.5}}},
        model={"contam": {"binding_revision": 0}},
        boundary_conditions={"wind_speed_m_s": 1.5},
    )
    feedback = adapter.solve(request)

    assert feedback["schema"] == "solver_feedback_v0.6"
    assert feedback["source_step"] == 4
    assert feedback["source_revision"] == 9
    assert feedback["zones"]["zone::kitchen"]["pressure_pa"] == 2.5
    assert feedback["flow_paths"]["flow::window"]["flow_m3_s"] == 0.12
    assert feedback["metadata"]["engine"] == "CONTAM"
    assert feedback["solver_provenance"]["adapter_id"] == "contam-project-v0.9"
    assert len(feedback["solver_provenance"]["adapter_fingerprint"]) == 64


def test_adapter_fails_if_project_changes_after_binding(tmp_path):
    project, _, registry = project_and_registry(tmp_path)

    def provider(request, project_path, binding_registry):
        return {"source_format": "api_json", "zones": [], "paths": []}

    adapter = ContamProjectSolverAdapter(
        project_path=project,
        binding_registry=registry,
        result_provider=provider,
        strict_binding=False,
    )
    project.write_text(PRJ + "\n! changed after review\n", encoding="utf-8")

    request = build_solver_request(
        case_id="case",
        source_step=0,
        source_revision=0,
        world_state={},
    )
    with pytest.raises(BindingDriftError, match="project content changed"):
        adapter.solve(request)


def test_binding_fingerprint_is_portable_across_project_paths(tmp_path):
    p1 = tmp_path / "a.prj"
    p2 = tmp_path / "nested" / "b.prj"
    p2.parent.mkdir()
    p1.write_text(PRJ, encoding="utf-8")
    p2.write_text(PRJ, encoding="utf-8")
    inv1 = parse_prj_inventory(p1)
    inv2 = parse_prj_inventory(p2)
    mappings = {
        "zones": {"zone::kitchen": {"contam_zone_number": 1}},
        "flow_paths": {
            "flow::window": {
                "contam_path_number": 11,
                "contam_flow_element_number": 1,
            }
        },
    }
    r1 = build_binding_registry(
        case_id="case", project_path=p1, inventory=inv1, mappings=mappings
    )
    r2 = build_binding_registry(
        case_id="case", project_path=p2, inventory=inv2, mappings=mappings
    )
    assert r1["project"]["path"] != r2["project"]["path"]
    assert registry_fingerprint(r1) == registry_fingerprint(r2)


def test_explicit_missing_contam_executable_reports_unavailable(tmp_path):
    runner = ContamCliRunner(executable=str(tmp_path / "missing-contamx"))
    caps = runner.capabilities()
    assert caps["available"] is False
    assert caps["executable"] is None


def test_inventory_accepts_count_prefixed_contam_sections(tmp_path):
    project = tmp_path / "count-prefixed.prj"
    project.write_text(
        """ContamW 3.4.0.4 0
count-prefixed.prj
-999
2 ! flow elements:
1 23 plr_orfc element_D1
AirTrajectory generated simple orifice
0.01 0.14 0.65 1.68 1.2 0.60 30 0 0
2 23 plr_orfc element_W1
AirTrajectory generated simple orifice
0.02 0.20 0.65 1.00 1.0 0.65 30 0 0
-999
0 ! control nodes:
-999
2 ! zones:
! Z# f s# c# k# l# relHt Vol T0 P0 name
1 3 0 0 0 1 0 35 295.15 0 living
2 3 0 0 0 1 0 30 295.15 0 bedroom
-999
2 ! flow paths:
! P# f n# m# e#
1 0 1 2 1
2 1 1 -1 2
-999
""",
        encoding="utf-8",
    )
    inventory = parse_prj_inventory(project)

    assert [z["number"] for z in inventory["zones"]] == [1, 2]
    assert [p["number"] for p in inventory["flow_paths"]] == [1, 2]
    assert [e["number"] for e in inventory["flow_elements"]] == [1, 2]
    assert inventory["flow_paths"][1]["flow_element_number"] == 2
    assert inventory["flow_elements"][0]["dtype"] == "plr_orfc"
