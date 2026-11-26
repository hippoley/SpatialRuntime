"""Contract and mutation checks for the real-SDK cross-version comparator."""
import copy
import unittest
from compare_versions import ComparisonError,compare,review,SOURCE

def receipt(version,observed=2):
    verdict="violated" if observed>1 else "held"
    return {"arib_source_commit":SOURCE,"sdk_execution":"real_sdk_using_upstream_benchmark",
        "independent_storage_observer":False,"contract_violation_established":False,
        "scenario":"ARIB-REPLAY-001","runtime_version":version,
        "adapters":[{"adapter":name,"observed_count":observed,
            "authorized_budget":1,"reported_verdict":verdict,"trace_consistent":True}
            for name in ("sqlite","async-sqlite","advanced-sqlite","sqlalchemy")]}

class VersionComparisonTests(unittest.TestCase):
    def test_no_improvement_is_a_valid_finding(self):
        d=compare(receipt("0.19.4"),receipt("0.23.1"))
        self.assertEqual(d["changes_detected"],0)
        self.assertEqual(d["third_party_adoption"],"NOT_EVIDENCED")

    def test_improvement_is_detected_not_assumed(self):
        a,b=receipt("0.19.4"),receipt("0.23.1")
        b["adapters"][0]["observed_count"]=1
        b["adapters"][0]["reported_verdict"]="held"
        d=compare(a,b)
        self.assertEqual(d["changes_detected"],1)
        self.assertTrue(d["comparisons"][3]["behavior_changed"])

    def test_source_or_scope_drift_fails(self):
        for key,val in (("arib_source_commit","bad"),("sdk_execution","synthetic"),
                        ("independent_storage_observer",True),
                        ("contract_violation_established",True),
                        ("scenario","not-s2")):
            r=receipt("0.19.4");r[key]=val
            with self.subTest(key=key),self.assertRaises(ComparisonError):
                review(r)

    def test_bad_backends_fail(self):
        for case in range(6):
            r=receipt("0.19.4")
            if case==0:r["adapters"].pop()
            if case==1:r["adapters"][0]["adapter"]="other"
            if case==2:r["adapters"][0]["adapter"]="sqlalchemy"
            if case==3:r["adapters"][0]["observed_count"]=True
            if case==4:r["adapters"][0]["trace_consistent"]=False
            if case==5:r["adapters"][0]["reported_verdict"]="held"
            with self.subTest(case=case),self.assertRaises(ComparisonError):
                review(r)

    def test_same_version_rejected(self):
        with self.assertRaises(ComparisonError):
            compare(receipt("0.23.1"),receipt("0.23.1"))

if __name__ == "__main__":
    unittest.main()
