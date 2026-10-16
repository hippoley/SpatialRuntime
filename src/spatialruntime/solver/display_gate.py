"""Strict display gate tying a solver result to its exact building/request revision.

This is a verification boundary, not a physics solver and not an execution ACK.
"""
from __future__ import annotations

from typing import Any, Mapping
from spatialruntime.solver.contract import SolverRequest, FEEDBACK_SCHEMA, payload_hash


class StalePhysicalResult(ValueError):
    """A result cannot be represented as current physical evidence."""


def verify_displayable_solver_result(
    feedback: Mapping[str, Any], *,
    request: SolverRequest,
    current_building_revision: int,
    current_request_hash: str,
    expected_adapter_id: str,
    expected_adapter_fingerprint: str,
) -> dict[str, Any]:
    """Fail closed on missing provenance, stale geometry or result tampering.

    Caller must supply an independently held current request hash; never derive it
    from the received feedback. This proves consistency, not numerical accuracy.
    """
    if feedback.get("schema") != FEEDBACK_SCHEMA:
        raise StalePhysicalResult("unsupported feedback schema")
    if request.source_revision != current_building_revision:
        raise StalePhysicalResult("building revision drift")
    if request.request_hash != current_request_hash:
        raise StalePhysicalResult("boundary or model request drift")
    for key, expected in (
        ("case_id", request.case_id),
        ("source_step", request.source_step),
        ("source_revision", request.source_revision),
    ):
        if feedback.get(key) != expected:
            raise StalePhysicalResult(f"feedback {key} mismatch")
    provenance = feedback.get("solver_provenance")
    if not isinstance(provenance, Mapping):
        raise StalePhysicalResult("missing solver provenance")
    for key, expected in (
        ("request_hash", request.request_hash),
        ("adapter_id", expected_adapter_id),
        ("adapter_fingerprint", expected_adapter_fingerprint),
    ):
        if provenance.get(key) != expected:
            raise StalePhysicalResult(f"solver provenance {key} mismatch")
    for name in ("zones", "flow_paths", "metadata"):
        if not isinstance(feedback.get(name), Mapping):
            raise StalePhysicalResult(f"missing or invalid {name}")
    result_body = {k: feedback[k] for k in ("zones", "flow_paths", "metadata")}
    if provenance.get("result_hash") != payload_hash(result_body):
        raise StalePhysicalResult("solver result payload changed")
    return {
        "displayable": True,
        "classification": "simulation_only",
        "building_revision": request.source_revision,
        "source_step": request.source_step,
        "request_hash": request.request_hash,
        "result_hash": provenance["result_hash"],
        "adapter_id": expected_adapter_id,
    }
