"""Mutation tests for the independent ARIB producer-report consumer."""
import copy
import unittest
from consumer import EvidenceError, check_replay, audit, load_strict

BASE = {"id": "ARIB-REPLAY-001", "scenario": "s2", "adapter": "sqlite",
        "verdict": "violated", "evidence": {
            "visible_occurrences": 2, "authorized_effects": 1,
            "evidence_kind": "observed_effect_trace",
            "effect_trace": [
                {"seq": 1, "store_index": 0, "effect_key": "session.history.item",
                 "content_digest": "sha256:4e2d445199ec"},
                {"seq": 2, "store_index": 1, "effect_key": "session.history.item",
                 "content_digest": "sha256:4e2d445199ec"}]}}

class Tests(unittest.TestCase):
    def test_reported_duplicate_is_over_budget(self):
        self.assertEqual(check_replay(copy.deepcopy(BASE))["reported_verdict"], "violated")

    def test_single_effect_is_held(self):
        row = copy.deepcopy(BASE)
        row["evidence"]["effect_trace"].pop()
        row["evidence"]["visible_occurrences"] = 1
        row["verdict"] = "held"
        self.assertEqual(check_replay(row)["reported_verdict"], "held")

    def test_complete_four_backends(self):
        findings = []
        for name in ("sqlite", "async-sqlite", "advanced-sqlite", "sqlalchemy"):
            item = copy.deepcopy(BASE)
            item["adapter"] = name
            findings.append(item)
        report = {"bench": "agent-runtime-integrity-bench",
                  "environment": {"openai-agents": "0.23.1"},
                  "skipped_adapters": [], "findings": findings}
        result = audit(report)
        self.assertEqual(len(result["adapters"]), 4)
        self.assertFalse(result["independent_sdk_reexecution"])

    def test_malformed_duplicate_json(self):
        with self.assertRaises(EvidenceError):
            load_strict(b'{"x":1,"x":2}')

    def test_mutations_fail_closed(self):
        changes = (
            lambda x: x["evidence"].update(visible_occurrences=1),
            lambda x: x["evidence"].update(authorized_effects=True),
            lambda x: x["evidence"].update(evidence_kind="self_report_only"),
            lambda x: x["evidence"]["effect_trace"][1].update(seq=1),
            lambda x: x["evidence"]["effect_trace"][1].update(store_index=0),
            lambda x: x["evidence"]["effect_trace"][1].update(effect_key="different"),
            lambda x: x["evidence"]["effect_trace"][1].update(content_digest="sha256:000000000000"),
            lambda x: x.update(verdict="held"),
            lambda x: x["evidence"].update(authorized_effects=3),
            lambda x: x.update(adapter="other"),
        )
        for index, change in enumerate(changes):
            row = copy.deepcopy(BASE)
            change(row)
            with self.subTest(index=index), self.assertRaises(EvidenceError):
                check_replay(row)

if __name__ == "__main__":
    unittest.main()
