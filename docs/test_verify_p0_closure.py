"""Regression tests for P0 completion evidence classification."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("verify_p0_closure", Path(__file__).with_name("verify_p0_closure.py"))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class P0ClosureEvidenceTests(unittest.TestCase):
    def test_failed_acceptance_command_never_passes(self):
        completed = subprocess.CompletedProcess(["test"], 1, stdout="", stderr="failure")
        with patch.object(module.subprocess, "run", return_value=completed):
            self.assertFalse(module._check(["python", "test.py"])["passed"])

    def test_timeout_never_passes(self):
        with patch.object(module.subprocess, "run", side_effect=subprocess.TimeoutExpired("test", 120)):
            result = module._check(["python", "test.py"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["error"], "TimeoutExpired")

    def test_success_is_only_local_command_evidence(self):
        completed = subprocess.CompletedProcess(["test"], 0, stdout="ok", stderr="")
        with patch.object(module.subprocess, "run", return_value=completed):
            self.assertTrue(module._check(["python", "test.py"])["passed"])

    def test_same_owner_never_qualifies_as_external(self):
        self.assertFalse(module._is_unrelated("HiPpOlEy/AnotherRepo"))

    def test_external_gate_requires_project_owned_evidence(self):
        registry = {"entries": [{"id": "x", "evidence_maturity": "externally-consumed",
                    "external_consumption": True, "consumer": {"repository": "other/project",
                    "project_owned_evidence": False}}]}
        self.assertFalse(module._external_gate(registry)[0])


if __name__ == "__main__":
    unittest.main()
