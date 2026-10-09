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

    def test_empty_expected_cannot_pass(self):
        self.assertFalse(module._matches_expected({"status": "CONFIRMED"}, {}))

    def test_non_dict_expected_cannot_pass(self):
        self.assertFalse(module._matches_expected({"status": "CONFIRMED"}, None))

    def test_empty_vector_suite_is_rejected(self):
        with patch.object(module.Path, "read_text", return_value=json.dumps({"authority_policy": {}, "cases": []})):
            with self.assertRaisesRegex(ValueError, "nonempty cases"):
                module._run_suite([], "iev-adversarial-v0.1", "mock.json")

    def test_duplicate_case_ids_are_rejected(self):
        case = {"id": "duplicate", "observation": {}, "expected": {"status": "UNRESOLVED"}}
        doc = {"authority_policy": {}, "cases": [case, case]}
        with patch.object(module.Path, "read_text", return_value=json.dumps(doc)):
            with self.assertRaisesRegex(ValueError, "duplicate case id"):
                module._run_suite([], "iev-adversarial-v0.1", "mock.json")

    def test_bad_shape_never_matches_expected(self):
        self.assertFalse(module._matches_expected([], {"status": "CONFIRMED"}))
        self.assertFalse(module._matches_expected(None, {"status": "CONFIRMED"}))

    def test_invalid_json_is_a_failed_verdict(self):
        with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "not-json", "")):
            self.assertEqual(self.call()["reason"], "INVALID_JSON")

    def test_nonzero_exit_is_a_failed_verdict(self):
        with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 9, "", "failed")):
            result = self.call()
        self.assertEqual(result["reason"], "NONZERO_EXIT")
        self.assertEqual(result["returncode"], 9)

    def test_real_subprocess_adapter_roundtrip(self):
        import shlex
        import sys
        command = shlex.join([sys.executable, "-c", "import json,sys; json.load(sys.stdin); print(json.dumps({'status':'UNRESOLVED','reason':'NO_EVIDENCE'}))"])
        verdict = module._call_adapter(command, "suite-v0", {}, CASE)
        self.assertEqual(verdict, {"status": "UNRESOLVED", "reason": "NO_EVIDENCE"})

    def test_valid_verdict_passes_through(self):
        verdict = {"status": "UNRESOLVED", "reason": "MISSING_EVIDENCE"}
        with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(verdict), "")):
            self.assertEqual(self.call(), verdict)


if __name__ == "__main__":
    unittest.main()
