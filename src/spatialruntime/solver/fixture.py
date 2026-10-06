from __future__ import annotations

from typing import Any, Mapping

from spatialruntime.solver.contract import (
    SolverAdapter,
    SolverRequest,
    normalize_solver_feedback,
    payload_hash,
)


class DeterministicSolverAdapter(SolverAdapter):
    adapter_id = "deterministic-fixture"

    def __init__(self, *, zones: Mapping[str, Mapping[str, Any]] | None = None,
                 flow_paths: Mapping[str, Mapping[str, Any]] | None = None):
        self._zones = {k: dict(v) for k, v in (zones or {}).items()}
        self._flow_paths = {k: dict(v) for k, v in (flow_paths or {}).items()}

    @property
    def fingerprint(self) -> str:
        return payload_hash({
            "adapter_id": self.adapter_id,
            "zones": self._zones,
            "flow_paths": self._flow_paths,
        })

    def solve(self, request: SolverRequest) -> dict[str, Any]:
        raw = {
            "zones": {k: dict(v) for k, v in self._zones.items()},
            "flow_paths": {k: dict(v) for k, v in self._flow_paths.items()},
            "metadata": {"fixture": True},
        }
        return normalize_solver_feedback(
            raw,
            request=request,
            adapter_id=self.adapter_id,
            adapter_fingerprint=self.fingerprint,
        )
