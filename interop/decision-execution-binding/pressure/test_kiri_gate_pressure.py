"""Test the evidence ceiling without importing or changing Kiri behavior."""
import unittest
from kiri_gate_real_sqlite import run, verify_binding

class KiriPressureTests(unittest.TestCase):
    def test_actual_sqlite_pressure_is_unresolved(self):
        result = run()
        self.assertEqual(result["conformance_result"], "UNRESOLVED")
        self.assertEqual(result["actual_external_function_invocations"], 1)
        self.assertFalse(result["external_project_adoption"])

    def test_unjustified_approval_link_cannot_be_inferred(self):
        doc = {"profile": "decision-execution-binding.v0.1",
               "decisions": [{"decision_id": "d1", "binding_mode": "per_call",
                              "outcome": "allow"}],
               "executions": [{"execution_id": "e1", "tool_call_id": None,
                               "decision_id": None, "scope_binding": "not_checked"}]}
        result = verify_binding(doc)
        self.assertEqual(result["result"], "UNRESOLVED")
        names = {x["code"] for x in result["unresolved"]}
        self.assertIn("UNRESOLVED_DECISION_BINDING", names)

    def test_denied_execution_is_not_misclassified_unresolved(self):
        doc = {"profile": "decision-execution-binding.v0.1",
               "decisions": [{"decision_id": "d1", "binding_mode": "per_call",
                              "outcome": "deny"}],
               "executions": [{"execution_id": "e1", "tool_call_id": "t1",
                               "decision_id": "d1", "scope_binding": "match"}]}
        result = verify_binding(doc)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("DENIED_DECISION_HAS_EXECUTION",
                      {x["code"] for x in result["errors"]})

if __name__ == "__main__":
    unittest.main()
