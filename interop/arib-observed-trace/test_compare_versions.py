"""Cross-version consumer rejects detached or contradictory raw evidence."""
import copy
import hashlib
import json
import unittest

from compare_versions import ComparisonError, SOURCE, compare, review, bind_report
from consumer import audit

BACKENDS = ("sqlite", "async-sqlite", "advanced-sqlite", "sqlalchemy")

def original(version, observed=2):
    verdict = "violated" if observed > 1 else "held"
    trace = [
        {"seq": i + 1, "store_index": i, "effect_key": "session.history.item",
         "content_digest": "sha256:4e2d445199ec"} for i in range(observed)
    ]
    report = {"bench": "agent-runtime-integrity-bench",
              "environment": {"openai-agents": version}, "skipped_adapters": [],
              "findings": [
                  {"id": "ARIB-REPLAY-001", "scenario": "s2", "adapter": backend,
                   "verdict": verdict,
                   "evidence": {"evidence_kind": "observed_effect_trace",
                                "visible_occurrences": observed, "authorized_effects": 1,
                                "effect_trace": copy.deepcopy(trace)}} for backend in BACKENDS]}
    raw = json.dumps(report, sort_keys=True).encode()
    receipt = audit(report)
    receipt.update({
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "arib_source_commit": SOURCE,
        "sdk_execution": "real_sdk_using_upstream_benchmark",
        "independent_storage_observer": False,
    })
    return receipt, raw

class VersionComparisonTests(unittest.TestCase):
    def test_no_change_is_a_valid_negative_finding(self):
        a, ar = original("0.19.4")
        b, br = original("0.23.1")
        result = compare(a, b, ar, br)
        self.assertEqual(result["changes_detected"], 0)
        self.assertEqual(result["third_party_adoption"], "NOT_EVIDENCED")

    def test_hypothetical_repair_is_detected_not_assumed(self):
        a, ar = original("0.19.4", 2)
        b, br = original("0.23.1", 1)
        result = compare(a, b, ar, br)
        self.assertEqual(result["changes_detected"], 4)

    def test_detached_receipt_is_rejected(self):
        a, ar = original("0.19.4")
        b, br = original("0.23.1")
        with self.assertRaisesRegex(ComparisonError, "binding mismatch"):
            compare(a, b, br, ar)
        with self.assertRaises(ComparisonError):
            compare(a, b)  # no original data cannot prove receipt binding

    def test_tampered_raw_report_is_rejected(self):
        a, ar = original("0.19.4")
        with self.assertRaisesRegex(ComparisonError, "binding mismatch"):
            bind_report(a, ar + b" ")

    def test_self_attested_forged_verdict_is_rejected(self):
        a, ar = original("0.19.4")
        a["adapters"][0]["reported_verdict"] = "held"
        with self.assertRaisesRegex(ComparisonError, "contradicts original report"):
            bind_report(a, ar)

    def test_scope_must_be_bounded(self):
        for name, replacement in (
            ("arib_source_commit", "wrong"),
            ("sdk_execution", "synthetic"),
            ("independent_storage_observer", True),
            ("contract_violation_established", True),
            ("scenario", "other"),
        ):
            r, raw = original("0.19.4")
            r[name] = replacement
            with self.subTest(field=name), self.assertRaises(ComparisonError):
                review(r)

    def test_bad_backend_or_verdict_fails(self):
        for mode in range(7):
            r, raw = original("0.19.4")
            if mode == 0:
                r["adapters"].pop()
            elif mode == 1:
                r["adapters"][0]["adapter"] = "other"
            elif mode == 2:
                r["adapters"][0]["adapter"] = "sqlalchemy"
            elif mode == 3:
                r["adapters"][0]["observed_count"] = True
            elif mode == 4:
                r["adapters"][0]["trace_consistent"] = False
            elif mode == 5:
                r["adapters"][0]["reported_verdict"] = "held"
            else:
                r["input_sha256"] = ""
            with self.subTest(mode=mode), self.assertRaises(ComparisonError):
                review(r)

    def test_same_version_refused(self):
        a, ar = original("0.23.1")
        with self.assertRaises(ComparisonError):
            compare(a, a, ar, ar)

if __name__ == "__main__":
    unittest.main()
