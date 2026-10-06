from __future__ import annotations

from typing import Any, Mapping
import math

from spatialruntime.hardware.contract import HardwareContractError

SCHEMA = "command_convergence_v2.7"

class ConvergenceError(HardwareContractError): pass


def _numeric_close(a: Any, b: Any, tol: float) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        af, bf = float(a), float(b)
        return math.isfinite(af) and math.isfinite(bf) and abs(af - bf) <= tol
    return a == b


def check_convergence(*, target_state: Mapping[str, Any], observed_state: Mapping[str, Any],
                      tolerances: Mapping[str, float] | None = None) -> dict[str, Any]:
    if not isinstance(target_state, Mapping) or not isinstance(observed_state, Mapping):
        raise ConvergenceError("target_state/observed_state must be objects")
    tolerances = dict(tolerances or {})
    fields: dict[str, Any] = {}
    mismatches = []
    for key, expected in target_state.items():
        if key not in observed_state:
            fields[key] = {"status": "missing", "expected": expected}
            mismatches.append(key)
            continue
        actual = observed_state[key]
        tol = float(tolerances.get(key, 0.0))
        ok = _numeric_close(expected, actual, tol)
        fields[key] = {"status": "matched" if ok else "mismatch", "expected": expected,
                       "actual": actual, "tolerance": tol}
        if not ok:
            mismatches.append(key)
    return {"schema": SCHEMA, "converged": not mismatches, "fields": fields,
            "mismatched_fields": mismatches}
