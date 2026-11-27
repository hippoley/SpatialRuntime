"""The binding CLI must retain actionable receipts even when verification fails."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "interop" / "decision-execution-binding"


class DurableBindingReportTests(unittest.TestCase):
    def _check(self, script, fixture, expected_result, expected_returncode):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested" / "assessment.json"
            cmd = [
                sys.executable, str(BINDING / script),
                str(BINDING / "fixtures" / fixture),
                "--report", str(output),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, expected_returncode, proc.stderr)
            self.assertTrue(output.is_file(), f"missing receipt: {proc.stdout} {proc.stderr}")
            saved = json.loads(output.read_text(encoding="utf-8"))
            printed = json.loads(proc.stdout)
            self.assertEqual(saved, printed, "printed and retained assessment disagree")
            self.assertEqual(saved["result"], expected_result)
            self.assertIs(saved["external_effect_confirmation"], False)
            self.assertIsInstance(saved["errors"], list)
            self.assertIsInstance(saved["unresolved"], list)
            self.assertIsInstance(saved["executions"], list)
            return saved

    def test_v01_pass_receipt(self):
        self._check("verify.py", "per-call-pass.json", "PASS", 0)

    def test_v01_unresolved_receipt(self):
        report = self._check("verify.py", "standing-not-checked.json", "UNRESOLVED", 0)
        self.assertTrue(report["unresolved"])

    def test_v01_fail_receipt_survives_failure_exit(self):
        report = self._check("verify.py", "deny-with-execution.json", "FAIL", 1)
        self.assertTrue(report["errors"])

    def test_v02_temporal_pass_receipt(self):
        report = self._check("verify_v0_2.py", "aap-approval-pass.json", "PASS", 0)
        self.assertEqual(report["profile"], "decision-execution-binding.v0.2")


if __name__ == "__main__":
    unittest.main()
