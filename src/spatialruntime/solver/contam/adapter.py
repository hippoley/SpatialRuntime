from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from spatialruntime.solver.contract import (
    SolverAdapter,
    SolverContractError,
    SolverRequest,
    normalize_solver_feedback,
    payload_hash,
)
from spatialruntime.solver.contam.binding import (
    assert_binding_fresh,
    registry_fingerprint,
)
from spatialruntime.solver.contam.inventory import parse_prj_inventory, sha256_file
from spatialruntime.solver.contam.results import map_native_results_to_stable

NativeResultProvider = Callable[[SolverRequest, Path, Mapping[str, Any]], Mapping[str, Any]]


class ContamAdapterError(SolverContractError):
    pass


class ContamProjectSolverAdapter(SolverAdapter):
    """Bind a reviewed CONTAM PRJ + native registry to SpatialRuntime's solver protocol.

    The injected result_provider owns native CONTAM execution/export. This adapter
    deliberately does not invent a PRJ mutation grammar or parse raw .SIM binaries.
    """

    adapter_id = "contam-project-v0.9"

    def __init__(
        self,
        *,
        project_path: str | Path,
        binding_registry: Mapping[str, Any],
        result_provider: NativeResultProvider,
        strict_binding: bool = True,
    ):
        self.project_path = Path(project_path)
        if not self.project_path.is_file():
            raise FileNotFoundError(self.project_path)
        if not callable(result_provider):
            raise ContamAdapterError("result_provider must be callable")
        self.binding_registry = dict(binding_registry)
        self.result_provider = result_provider
        self.strict_binding = bool(strict_binding)
        self.inventory = parse_prj_inventory(self.project_path)
        assert_binding_fresh(self.binding_registry, self.project_path, self.inventory)

    @property
    def fingerprint(self) -> str:
        return payload_hash({
            "adapter_id": self.adapter_id,
            "project_sha256": sha256_file(self.project_path),
            "structural_inventory_sha256": self.binding_registry["project"][
                "structural_inventory_sha256"
            ],
            "binding_registry_fingerprint": registry_fingerprint(self.binding_registry),
            "strict_binding": self.strict_binding,
        })

    def solve(self, request: SolverRequest) -> dict[str, Any]:
        assert_binding_fresh(self.binding_registry, self.project_path, self.inventory)
        native = self.result_provider(request, self.project_path, self.binding_registry)
        if not isinstance(native, Mapping):
            raise ContamAdapterError("CONTAM result_provider must return object")

        mapped = map_native_results_to_stable(
            native,
            self.binding_registry,
            strict=self.strict_binding,
        )
        raw = {
            "case_id": request.case_id,
            "source_step": request.source_step,
            "source_revision": request.source_revision,
            "zones": mapped["zones"],
            "flow_paths": mapped["flow_paths"],
            "metadata": {
                "engine": "CONTAM",
                "project_sha256": sha256_file(self.project_path),
                "binding_registry_fingerprint": registry_fingerprint(
                    self.binding_registry
                ),
                "binding_revision": int(self.binding_registry.get("revision", 0)),
                "native_result_source": native.get("source_format"),
                "native_execution": native.get("execution"),
                "unmapped_native": mapped["unmapped_native"],
            },
        }
        return normalize_solver_feedback(
            raw,
            request=request,
            adapter_id=self.adapter_id,
            adapter_fingerprint=self.fingerprint,
        )
