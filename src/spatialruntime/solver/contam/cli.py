from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


class ContamCliError(RuntimeError):
    pass


class ContamCliUnavailable(ContamCliError):
    pass


class ContamCliTimeout(ContamCliError):
    pass


class ContamCliRunner:
    """Explicit ContamX CLI runner for already-materialized PRJ files."""

    def __init__(self, executable: str | None = None, *, timeout_s: float = 120.0):
        self.executable = executable or self.detect_executable()
        self.timeout_s = float(timeout_s)
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")

    @staticmethod
    def detect_executable() -> str | None:
        env = os.environ.get("CONTAMX_BIN")
        if env and Path(env).is_file():
            return env
        for candidate in ("contamx3", "contam-x", "contamx3.exe", "contam-x.exe"):
            found = shutil.which(candidate)
            if found:
                return found
        return None

    def version(self) -> str | None:
        if not self.executable:
            return None
        for flag in ("--Version", "--version", "-v"):
            try:
                cp = subprocess.run(
                    [self.executable, flag],
                    text=True,
                    capture_output=True,
                    timeout=10,
                    check=False,
                    shell=False,
                )
            except Exception:
                continue
            text = (cp.stdout + "\n" + cp.stderr).strip()
            if text:
                return text.splitlines()[0][:300]
        return None

    def run_project(self, project_path: str | Path, *, test_input_only: bool = False) -> dict[str, Any]:
        if not self.executable:
            raise ContamCliUnavailable(
                "ContamX executable not found; set CONTAMX_BIN or install ContamX"
            )
        project = Path(project_path)
        if not project.is_file():
            raise FileNotFoundError(project)
        command = [self.executable, str(project)]
        if test_input_only:
            command.append("--TestInput")
        started = time.monotonic()
        try:
            cp = subprocess.run(
                command,
                cwd=str(project.parent),
                text=True,
                capture_output=True,
                timeout=self.timeout_s,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContamCliTimeout(
                f"ContamX timed out after {self.timeout_s}s"
            ) from exc
        return {
            "schema": "contam_cli_run_v0.9",
            "command": command,
            "returncode": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
            "elapsed_s": time.monotonic() - started,
            "version": self.version(),
            "project": str(project),
            "ok": cp.returncode == 0,
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "schema": "contam_cli_capabilities_v0.9",
            "available": bool(self.executable),
            "executable": self.executable,
            "version": self.version() if self.executable else None,
        }
