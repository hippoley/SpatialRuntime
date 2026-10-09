from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).with_name("verify_horizontal_completeness.py")
SPEC = importlib.util.spec_from_file_location("horizontal_verify", MODULE_PATH)
assert SPEC and SPEC.loader
hv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hv)


class HorizontalCompletenessVerifierTests(unittest.TestCase):
    def setUp(self):
        self.base_doc = json.loads(hv.MATRIX.read_text(encoding="utf-8"))
        self.base_audit = hv.AUDIT.read_text(encoding="utf-8")

    def _verify(self, doc, audit=None):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            matrix = root / "matrix.json"
            audit_file = root / "audit.md"
            matrix.write_text(json.dumps(doc), encoding="utf-8")
            audit_file.write_text(audit or self.base_audit, encoding="utf-8")
            old_matrix, old_audit = hv.MATRIX, hv.AUDIT
            hv.MATRIX, hv.AUDIT = matrix, audit_file
            try:
                return hv.verify()
            finally:
                hv.MATRIX, hv.AUDIT = old_matrix, old_audit

    def test_current_matrix_is_valid(self):
        report = hv.verify()
        self.assertTrue(report["horizontal_audit_valid"], report["errors"])

    def test_missing_dimension_is_rejected(self):
        doc = copy.deepcopy(self.base_doc)
        del doc["stories"]["SR-01"]["dimensions"]["testability"]
        report = self._verify(doc)
        self.assertFalse(report["horizontal_audit_valid"])
        self.assertTrue(any("dimension coverage drift" in e for e in report["errors"]))

    def test_false_verified_closed_is_rejected(self):
        doc = copy.deepcopy(self.base_doc)
        doc["stories"]["SR-05"]["horizontal_closure"] = "VERIFIED_CLOSED"
        doc["stories"]["SR-05"]["vertical_status"] = "DONE"
        audit = self.base_audit.replace(
            "| SR-05 | As a hardware user, I can dispatch through a real gateway/device fleet and prove physical convergence | PARTIAL |",
            "| SR-05 | As a hardware user, I can dispatch through a real gateway/device fleet and prove physical convergence | DONE |",
        )
        report = self._verify(doc, audit=audit)
        self.assertFalse(report["horizontal_audit_valid"])
        self.assertTrue(any("unresolved dimensions" in e for e in report["errors"]))

    def test_dependency_cycle_is_rejected(self):
        doc = copy.deepcopy(self.base_doc)
        doc["stories"]["SR-01"]["dependencies"] = ["SR-09"]
        report = self._verify(doc)
        self.assertFalse(report["horizontal_audit_valid"])
        self.assertTrue(any("dependency cycle" in e for e in report["errors"]))

    def test_missing_repository_evidence_is_rejected(self):
        doc = copy.deepcopy(self.base_doc)
        doc["stories"]["CF-01"]["dimensions"]["functional_completeness"]["evidence"] = [
            "repo:this/path/does/not/exist"
        ]
        report = self._verify(doc)
        self.assertFalse(report["horizontal_audit_valid"])
        self.assertTrue(any("repository evidence missing" in e for e in report["errors"]))

    def test_vertical_status_drift_is_rejected(self):
        doc = copy.deepcopy(self.base_doc)
        doc["stories"]["CF-06"]["vertical_status"] = "DONE"
        report = self._verify(doc)
        self.assertFalse(report["horizontal_audit_valid"])
        self.assertTrue(any("vertical status drift" in e for e in report["errors"]))


    def test_generic_ci_alone_cannot_prove_verified_dimension(self):
        doc = copy.deepcopy(self.base_doc)
        doc["stories"]["CF-01"]["dimensions"]["functional_completeness"]["evidence"] = [
            "repo:.github/workflows/ci.yml"
        ]
        report = self._verify(doc)
        self.assertFalse(report["horizontal_audit_valid"])
        self.assertTrue(any("generic CI" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main()
