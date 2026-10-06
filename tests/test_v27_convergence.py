from spatialruntime.hardware.convergence import *

def test_converged_with_tolerance():
    r=check_convergence(target_state={"open_ratio":.5},observed_state={"open_ratio":.51},tolerances={"open_ratio":.02})
    assert r["converged"]

def test_mismatch_detected():
    r=check_convergence(target_state={"open_ratio":.5},observed_state={"open_ratio":.8},tolerances={"open_ratio":.02})
    assert not r["converged"] and r["mismatched_fields"]==["open_ratio"]

def test_missing_field_not_converged():
    assert not check_convergence(target_state={"open_ratio":.5},observed_state={})["converged"]
