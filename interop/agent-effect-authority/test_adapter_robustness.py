"""Regression cases for untrusted external conformance adapters."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("run_conformance.py")
SPEC = importlib.util.spec_from_file_location("run_conformance_under_test", SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

CASE = {"id": "probe", "observation": {}}


class AdapterRobustnessTests(unittest.TestCase):
    def call(self):
        return module._call_adapter("python fake_adapter.py", "suite-v0", {}, CASE)

    def test_timeout_is_a_failed_verdict_not_an_unbounded_run(self):
        with patch.object(module.subprocess, "run", side_effect=subprocess.TimeoutExpired("adapter", 15)) as run:
            result = self.call()
        self.assertEqual(result["reason"], "TIMEOUT")
        self.assertEqual(result["status"], "ADAPTER_ERROR")
        self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_missing_adapter_is_a_failed_verdict(self):
        with patch.object(module.subprocess, "run", side_effect=FileNotFoundError("python")):
            self.assertEqual(self.call()["reason"], "INVOCATION_ERROR")

    def test_non_object_json_is_not_a_valid_verdict(self):
        with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "[]", "")):
            self.assertEqual(self.call()["reason"], "INVALID_VERDICT_SHAPE")

    def test_missing_status_is_not_a_valid_verdict(self):
        with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps({"reason": "none"}), "")):
            self.assertEqual(self.call()["reason"], "INVALID_VERDICT_SHAPE")

    def test_bad_shape_never_matches_expected(self):
        self.assertFalse(module._matches_expected([], {"status": "CONFIRMED"}))
        self.assertFalse(module._matches_expected(None, {"status": "CONFIRMED"}))

    def test_valid_verdict_passes_through(self):
        verdict = {"status": "UNRESOLVED", "reason": "MISSING_EVIDENCE"}
        with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(verdict), "")):
            self.assertEqual(self.call(), verdict)


if __name__ == "__main__":
    unittest.main()
