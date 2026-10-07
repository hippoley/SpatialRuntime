from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from spatialruntime.solver.contam.cli import (
    ContamCliRunner,
    ContamCliUnavailable,
)
from spatialruntime.solver.contam.results import (
    ResultParseError,
    merge_result_sources,
    parse_result_file,
)
from spatialruntime.solver.contract import SolverRequest

SCHEMA = "contam_execution_evidence_v0.11"


class ContamExecutionError(RuntimeError):
    pass


class ContamExecutionUnavailable(ContamExecutionError):
    pass


class ContamInputRejected(ContamExecutionError):
    pass


class ContamSolveFailed(ContamExecutionError):
    pass


class ContamResultArtifactError(ContamExecutionError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class _ArtifactSnapshot:
    exists: bool
    mtime_ns: int | None
    size: int | None
    sha256: str | None


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class ExplicitResultArtifacts:
    """Load explicitly named CONTAM result exports.

    Paths may be absolute or relative to the PRJ directory. Supported placeholders:
    {stem} = PRJ filename without suffix, {name} = full PRJ filename.

    No result filename is guessed.
    """

    def __init__(
        self,
        *,
        val: str | Path | None = None,
        path_tsv: str | Path | None = None,
        api_json: str | Path | None = None,
        require_fresh: bool = True,
    ):
        self.specs = {
            "val": str(val) if val is not None else None,
            "path_tsv": str(path_tsv) if path_tsv is not None else None,
            "api_json": str(api_json) if api_json is not None else None,
        }
        if not any(self.specs.values()):
            raise ValueError("at least one explicit CONTAM result artifact is required")
        self.require_fresh = bool(require_fresh)

    def _resolve(self, project_path: Path, kind: str) -> Path | None:
        raw = self.specs[kind]
        if raw is None:
            return None
        rendered = raw.format(stem=project_path.stem, name=project_path.name)
        p = Path(rendered)
        return p if p.is_absolute() else project_path.parent / p

    def paths(self, project_path: str | Path) -> dict[str, Path]:
        p = Path(project_path)
        return {
            kind: resolved
            for kind in self.specs
            if (resolved := self._resolve(p, kind)) is not None
        }

    def snapshot(self, project_path: str | Path) -> dict[str, _ArtifactSnapshot]:
        out: dict[str, _ArtifactSnapshot] = {}
        for kind, path in self.paths(project_path).items():
            if not path.is_file():
                out[kind] = _ArtifactSnapshot(False, None, None, None)
                continue
            stat = path.stat()
            out[kind] = _ArtifactSnapshot(
                True,
                stat.st_mtime_ns,
                stat.st_size,
                _sha256_file(path),
            )
        return out

    def _assert_fresh(
        self,
        *,
        kind: str,
        path: Path,
        before: _ArtifactSnapshot | None,
    ) -> None:
        if not path.is_file():
            raise ContamResultArtifactError(
                f"configured CONTAM result artifact was not produced: {path}"
            )
        if not self.require_fresh:
            return
        stat = path.stat()
        after = _ArtifactSnapshot(True, stat.st_mtime_ns, stat.st_size, _sha256_file(path))
        if before is None or not before.exists:
            return
        if (
            after.mtime_ns == before.mtime_ns
            and after.size == before.size
            and after.sha256 == before.sha256
        ):
            raise ContamResultArtifactError(
                f"CONTAM result artifact is stale/unchanged after solve: {kind}={path}"
            )

    def load(
        self,
        project_path: str | Path,
        *,
        before: Mapping[str, _ArtifactSnapshot] | None = None,
    ) -> dict[str, Any]:
        sources: dict[str, Mapping[str, Any] | None] = {
            "val": None,
            "path_export": None,
            "api": None,
        }
        paths = self.paths(project_path)
        for kind, path in paths.items():
            self._assert_fresh(
                kind=kind,
                path=path,
                before=(before or {}).get(kind),
            )
            try:
                parsed = parse_result_file(path, kind=kind)
            except (ResultParseError, json.JSONDecodeError) as exc:
                raise ContamResultArtifactError(
                    f"failed to parse CONTAM result artifact {kind}={path}: {exc}"
                ) from exc
            if kind == "val":
                sources["val"] = parsed
            elif kind == "path_tsv":
                sources["path_export"] = parsed
            elif kind == "api_json":
                sources["api"] = parsed

        merged = merge_result_sources(
            val=sources["val"],
            path_export=sources["path_export"],
            api=sources["api"],
        )
        merged["artifact_paths"] = {k: str(v) for k, v in paths.items()}
        return merged


class ContamCliResultProvider:
    """Application-side native result provider for ContamProjectSolverAdapter.

    It performs optional --TestInput validation, runs ContamX, then reads only
    explicitly configured result artifacts. It never guesses or parses raw .SIM.
    """

    def __init__(
        self,
        *,
        runner: ContamCliRunner,
        artifacts: ExplicitResultArtifacts,
        test_input_first: bool = True,
    ):
        self.runner = runner
        self.artifacts = artifacts
        self.test_input_first = bool(test_input_first)

    def __call__(
        self,
        request: SolverRequest,
        project_path: Path,
        binding_registry: Mapping[str, Any],
    ) -> dict[str, Any]:
        caps = self.runner.capabilities()
        if not caps.get("available"):
            raise ContamExecutionUnavailable(
                "ContamX executable is unavailable; install it or set CONTAMX_BIN"
            )

        test_report = None
        if self.test_input_first:
            try:
                test_report = self.runner.run_project(project_path, test_input_only=True)
            except ContamCliUnavailable as exc:
                raise ContamExecutionUnavailable(str(exc)) from exc
            if not test_report.get("ok"):
                raise ContamInputRejected(
                    "ContamX --TestInput rejected the PRJ: "
                    + (test_report.get("stderr") or test_report.get("stdout") or "")[:1000]
                )

        before = self.artifacts.snapshot(project_path)
        try:
            run_report = self.runner.run_project(project_path, test_input_only=False)
        except ContamCliUnavailable as exc:
            raise ContamExecutionUnavailable(str(exc)) from exc
        if not run_report.get("ok"):
            raise ContamSolveFailed(
                "ContamX solve failed: "
                + (run_report.get("stderr") or run_report.get("stdout") or "")[:1000]
            )

        native = self.artifacts.load(project_path, before=before)
        evidence = {
            "schema": SCHEMA,
            "case_id": request.case_id,
            "source_step": request.source_step,
            "source_revision": request.source_revision,
            "binding_revision": int(binding_registry.get("revision", 0)),
            "test_input": (
                {
                    "returncode": test_report.get("returncode"),
                    "elapsed_s": test_report.get("elapsed_s"),
                    "version": test_report.get("version"),
                }
                if test_report is not None
                else None
            ),
            "solve": {
                "returncode": run_report.get("returncode"),
                "elapsed_s": run_report.get("elapsed_s"),
                "version": run_report.get("version"),
            },
            "artifacts": native.get("artifact_paths", {}),
        }
        evidence["execution_hash"] = _digest(evidence)
        native["execution"] = evidence
        native["source_format"] = "contam_cli_explicit_artifacts"
        return native
