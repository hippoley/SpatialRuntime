from __future__ import annotations

from hashlib import sha256
import json
import subprocess
from typing import Any, Sequence

from spatialruntime.solver.contract import (
    SolverAdapter,
    SolverContractError,
    SolverRequest,
    normalize_solver_feedback,
)


class SolverProcessError(SolverContractError):
    pass


class JsonProcessSolverAdapter(SolverAdapter):
    """Run an explicitly configured local solver process using JSON stdin/stdout.

    No shell is used. The caller must supply argv explicitly. This adapter does not
    infer CONTAM/CFD commands, download binaries, or execute endpoints from scenario JSON.
    """

    def __init__(self, argv: Sequence[str], *, timeout_s: float = 30.0, adapter_id: str = "json-process"):
        if not argv or not all(isinstance(x, str) and x for x in argv):
            raise SolverContractError("argv must be a non-empty string sequence")
        if timeout_s <= 0:
            raise SolverContractError("timeout_s must be > 0")
        self.argv = tuple(argv)
        self.timeout_s = float(timeout_s)
        self.adapter_id = adapter_id

    @property
    def fingerprint(self) -> str:
        body = json.dumps(
            {"argv": list(self.argv), "timeout_s": self.timeout_s, "adapter_id": self.adapter_id},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return sha256(body).hexdigest()

    def solve(self, request: SolverRequest) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                list(self.argv),
                input=json.dumps(request.to_dict(), sort_keys=True),
                text=True,
                capture_output=True,
                timeout=self.timeout_s,
                check=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise SolverProcessError(f"solver executable not found: {self.argv[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise SolverProcessError(f"solver timed out after {self.timeout_s}s") from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise SolverProcessError(
                f"solver exited with code {proc.returncode}: {stderr[:500]}"
            )
        try:
            raw = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise SolverProcessError("solver stdout is not valid JSON") from exc
        return normalize_solver_feedback(
            raw,
            request=request,
            adapter_id=self.adapter_id,
            adapter_fingerprint=self.fingerprint,
        )
