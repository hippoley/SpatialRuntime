"""Regression tests for P0 completion evidence classification."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
import unittest.mock
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

    def test_missing_story_in_manifest_blocks_global_closure(self):
        manifest = {"schema": "test", "p0": []}
        manifest_path = unittest.mock.Mock()
        manifest_path.read_text.return_value = __import__("json").dumps(manifest)
        registry_path = unittest.mock.Mock()
        registry_path.read_text.return_value = '{"entries": []}'
        with patch.object(module, "MANIFEST", manifest_path), \
             patch.object(module, "EXTERNAL_REGISTRY", registry_path):
            result = module.verify()
        self.assertFalse(result["repository_p0_locally_verified"])
        self.assertTrue(any("coverage drift" in error for error in result["errors"]))

    def test_duplicate_story_id_blocks_global_closure(self):
        manifest = {"schema": "test", "p0": [{"id": "P0-A", "owner": "repository", "evidence_paths": []}] * 2}
        manifest_path = unittest.mock.Mock()
        manifest_path.read_text.return_value = __import__("json").dumps(manifest)
        registry_path = unittest.mock.Mock()
        registry_path.read_text.return_value = '{"entries": []}'
        with patch.object(module, "MANIFEST", manifest_path), \
             patch.object(module, "EXTERNAL_REGISTRY", registry_path), \
             patch.object(module, "_check", return_value={"passed": True}):
            result = module.verify()
        self.assertFalse(result["repository_p0_locally_verified"])
        self.assertTrue(any("duplicate ids" in error for error in result["errors"]))

    def test_external_gate_requires_project_owned_evidence(self):
        registry = {"entries": [{"id": "x", "evidence_maturity": "externally-consumed",
                    "external_consumption": True, "consumer": {"repository": "other/project",
                    "project_owned_evidence": False}}]}
        self.assertFalse(module._external_gate(registry)[0])


if __name__ == "__main__":
    unittest.main()
