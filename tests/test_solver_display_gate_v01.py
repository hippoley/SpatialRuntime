"""Adversarial conformance: do not display stale/tampered simulations as current."""
from copy import deepcopy
import pytest
from spatialruntime.solver.contract import build_solver_request, normalize_solver_feedback
from spatialruntime.solver.display_gate import StalePhysicalResult, verify_displayable_solver_result


def evidence():
    req = build_solver_request(
        case_id="kitchen-window", source_step=3, source_revision=18,
        world_state={"window_opening_fraction": 0.45},
        model={"opening_id": "w1", "adjacent_spaces": ["kitchen", "outdoor"]},
        boundary_conditions={"wind_speed_m_s": 2.5},
    )
    fb = normalize_solver_feedback(
        {"zones": {"kitchen": {"ach_1_h": 1.2}}, "flow_paths": {}, "metadata": {"solver_version": "fixture"}},
        request=req, adapter_id="fixture", adapter_fingerprint="fixture-sha",
    )
    args = dict(request=req, current_building_revision=18,
                current_request_hash=req.request_hash,
                expected_adapter_id="fixture", expected_adapter_fingerprint="fixture-sha")
    return fb, args


def test_valid_simulation_is_not_device_execution_evidence():
    fb, args = evidence()
    receipt = verify_displayable_solver_result(fb, **args)
    assert receipt["displayable"] is True
    assert receipt["classification"] == "simulation_only"


@pytest.mark.parametrize("mutation", ["revision", "request", "adapter", "tamper", "missing", "step"])
def test_fail_closed_on_stale_or_unverifiable_result(mutation):
    fb, args = evidence()
    fb = deepcopy(fb)
    if mutation == "revision":
        args["current_building_revision"] = 19
    elif mutation == "request":
        args["current_request_hash"] = "other-boundary-conditions"
    elif mutation == "adapter":
        fb["solver_provenance"]["adapter_id"] = "unknown"
    elif mutation == "tamper":
        fb["zones"]["kitchen"]["ach_1_h"] = 99
    elif mutation == "missing":
        del fb["solver_provenance"]
    elif mutation == "step":
        fb["source_step"] = 4
    with pytest.raises(StalePhysicalResult):
        verify_displayable_solver_result(fb, **args)
