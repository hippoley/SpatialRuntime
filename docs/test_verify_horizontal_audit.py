import importlib.util
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location("horizontal",Path(__file__).with_name("verify_horizontal_audit.py"))
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

def story():
    return {"id":"P0-A","vertical":"unverified","horizontal":{d:{"status":"unverified","evidence":[]} for d in m.DIMENSIONS}}

class HorizontalAuditTests(unittest.TestCase):
    def test_complete_inventory_can_remain_unverified(self):
        self.assertEqual(m.audit({"stories":[story()]},{"P0-A"}),[])
    def test_missing_dimension_fails(self):
        s=story();s["horizontal"].pop("security")
        self.assertTrue(m.audit({"stories":[s]},{"P0-A"}))
    def test_unsupported_verified_claim_fails(self):
        s=story();s["closure"]="VERIFIED_CLOSED"
        self.assertTrue(m.audit({"stories":[s]},{"P0-A"}))
    def test_verified_dimension_requires_evidence(self):
        s=story();s["horizontal"]["testing"]["status"]="verified"
        self.assertTrue(m.audit({"stories":[s]},{"P0-A"}))
    def test_not_applicable_requires_rationale(self):
        s=story();s["horizontal"]["performance"]["status"]="not_applicable"
        self.assertTrue(m.audit({"stories":[s]},{"P0-A"}))
    def test_missing_story_fails(self):
        self.assertTrue(m.audit({"stories":[]},{"P0-A"}))
    def test_duplicate_story_fails(self):
        self.assertTrue(m.audit({"stories":[story(),story()]},{"P0-A"}))

if __name__=="__main__":
    unittest.main()
