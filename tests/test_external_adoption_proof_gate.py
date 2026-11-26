"""CF-06 must not be closed by forged, unverified or owner-controlled evidence."""
import base64
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "interop" / "external-results"))
import verify_external_adoption as gate

spec = importlib.util.spec_from_file_location("p0_audit", ROOT / "docs" / "verify_p0_closure.py")
p0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p0)

REV = "a" * 40
WORKFLOW_COMMIT = "b" * 40
REPO = "example-org/consumer"

def entry():
    return {
        "id": "real-consumer-candidate",
        "evidence_maturity": "externally-consumed",
        "external_consumption": True,
        "adoption_claim": True,
        "consumer": {
            "project_owned_evidence": True,
            "repository": REPO,
            "workflow_run_id": 42,
            "workflow_run_url": "https://github.com/example-org/consumer/actions/runs/42",
            "workflow_path": ".github/workflows/verify.yml",
            "workflow_commit": WORKFLOW_COMMIT,
            "spatialruntime_commit": REV,
        }
    }

def fake_api(url):
    if "/actions/runs/" in url:
        return {"conclusion": "success", "head_sha": WORKFLOW_COMMIT, "event": "push",
                "repository": {"full_name": REPO}, "path": ".github/workflows/verify.yml"}
    if "/contents/" in url:
        return {"encoding": "base64", "type": "file",
                "content": base64.b64encode(
                    ("steps:\n  - uses: hippoley/SpatialRuntime/interop/conformance@" + REV + "\n").encode()
                ).decode()}
    raise AssertionError("unexpected API request")

class AdoptionGateTests(unittest.TestCase):
    def test_empty_registry_stays_open(self):
        self.assertEqual(p0._external_gate({"entries": []}), (False, []))

    def test_self_asserted_unrelated_repo_is_not_enough(self):
        e = entry()
        e["consumer"].pop("workflow_run_id")
        with patch.object(gate, "_fetch_json", side_effect=AssertionError("should not fetch")):
            self.assertEqual(p0._external_gate({"entries": [e]}), (False, []))

    def test_owner_controlled_repo_rejected_case_insensitively(self):
        e = entry()
        e["consumer"]["repository"] = "HiPpOlEy/anotherrepo"
        e["consumer"]["workflow_run_url"] = "https://github.com/HiPpOlEy/anotherrepo/actions/runs/42"
        self.assertEqual(p0._external_gate({"entries": [e]}), (False, []))

    def test_candidate_without_adoption_claim_stays_open(self):
        e = entry()
        e["adoption_claim"] = False
        self.assertEqual(p0._external_gate({"entries": [e]}), (False, []))

    def test_real_successful_owned_workflow_can_close(self):
        with patch.object(gate, "_fetch_json", side_effect=fake_api):
            closed, facts = p0._external_gate({"entries": [entry()]})
        self.assertTrue(closed)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["repository"], REPO)

    def test_remote_api_unavailable_must_fail_closed(self):
        with patch.object(gate, "_fetch_json", side_effect=gate.Unverified("offline")):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_unrelated_but_failed_run_stays_open(self):
        def failed(url):
            value = fake_api(url)
            if "/actions/runs/" in url:
                value["conclusion"] = "failure"
            return value
        with patch.object(gate, "_fetch_json", side_effect=failed):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_uses_different_revision_stays_open(self):
        def wrong_pin(url):
            value = fake_api(url)
            if "/contents/" in url:
                value["content"] = base64.b64encode(
                    ("  - uses: hippoley/SpatialRuntime/interop/conformance@" + ("c"*40) + "\n").encode()
                ).decode()
            return value
        with patch.object(gate, "_fetch_json", side_effect=wrong_pin):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_workflow_must_belong_to_run(self):
        def unrelated_path(url):
            value = fake_api(url)
            if "/actions/runs/" in url:
                value["path"] = ".github/workflows/other.yml"
            return value
        with patch.object(gate, "_fetch_json", side_effect=unrelated_path):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_wrong_run_commit_stays_open(self):
        def changed(url):
            value = fake_api(url)
            if "/actions/runs/" in url:
                value["head_sha"] = "d" * 40
            return value
        with patch.object(gate, "_fetch_json", side_effect=changed):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

if __name__ == "__main__":
    unittest.main()
