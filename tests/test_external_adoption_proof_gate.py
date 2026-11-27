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
            "workflow_job_id": 99,
            "action_step_name": "Check SpatialRuntime evidence",
            "workflow_run_url": "https://github.com/example-org/consumer/actions/runs/42",
            "workflow_path": ".github/workflows/verify.yml",
            "workflow_commit": WORKFLOW_COMMIT,
            "spatialruntime_commit": REV,
        }
    }

def fake_api(url):
    if "/actions/runs/" in url and "/jobs?" in url:
        return {"total_count": 1, "jobs": [{
            "id": 99, "status": "completed", "conclusion": "success",
            "head_sha": WORKFLOW_COMMIT,
            "steps": [{"name": "Check SpatialRuntime evidence",
                       "status": "completed", "conclusion": "success"}]}]}
    if "/actions/runs/" in url:
        return {"conclusion": "success", "head_sha": WORKFLOW_COMMIT, "event": "push",
                "repository": {"full_name": REPO}, "path": ".github/workflows/verify.yml"}
    if "/contents/" in url:
        return {"encoding": "base64", "type": "file",
                "content": base64.b64encode(
                    ("steps:\n  - name: Check SpatialRuntime evidence\n    uses: hippoley/SpatialRuntime/interop/conformance@" + REV + "\n").encode()
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

    def test_skipped_action_step_is_not_adoption(self):
        def skipped(url):
            value = fake_api(url)
            if "/jobs?" in url:
                value["jobs"][0]["steps"][0]["conclusion"] = "skipped"
            return value
        with patch.object(gate, "_fetch_json", side_effect=skipped):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_successful_workflow_with_no_action_step_is_not_adoption(self):
        def omitted(url):
            value = fake_api(url)
            if "/jobs?" in url:
                value["jobs"][0]["steps"] = [{"name": "Other task", "status": "completed", "conclusion": "success"}]
            return value
        with patch.object(gate, "_fetch_json", side_effect=omitted):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_unrelated_job_is_not_adoption(self):
        def other_job(url):
            value = fake_api(url)
            if "/jobs?" in url:
                value["jobs"][0]["id"] = 100
            return value
        with patch.object(gate, "_fetch_json", side_effect=other_job):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_incomplete_job_page_is_not_adoption(self):
        def truncated(url):
            value = fake_api(url)
            if "/jobs?" in url:
                value["total_count"] = 101
            return value
        with patch.object(gate, "_fetch_json", side_effect=truncated):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_other_step_has_action_but_named_step_does_not(self):
        def wrong_step_source(url):
            value = fake_api(url)
            if "/contents/" in url:
                value["content"] = base64.b64encode((
                    "steps:\\n  - name: Check SpatialRuntime evidence\\n    run: echo done\\n"
                    "  - name: Other skipped action\\n    uses: hippoley/SpatialRuntime/interop/conformance@" + REV + "\\n"
                ).encode()).decode()
            return value
        with patch.object(gate, "_fetch_json", side_effect=wrong_step_source):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_successful_shell_step_printing_pinned_uses_is_not_adoption(self):
        """A green shell command containing Action-looking text is NOT an Action."""
        def disguised(url):
            value = fake_api(url)
            if "/contents/" in url:
                source = ("jobs:\n  evidence:\n    steps:\n"
                          "      - name: Check SpatialRuntime evidence\n"
                          "        run: |\n"
                          "          echo hello\n"
                          "          uses: hippoley/SpatialRuntime/interop/conformance@" + REV + "\n")
                value["content"] = base64.b64encode(source.encode()).decode()
            return value
        with patch.object(gate, "_fetch_json", side_effect=disguised):
            self.assertEqual(p0._external_gate({"entries": [entry()]}), (False, []))

    def test_nested_fake_name_and_use_inside_shell_literal_is_not_adoption(self):
        """Both the step name and its uses key can be text within run: |."""
        source = ("jobs:\n  evidence:\n    steps:\n"
                  "      - name: actual shell task\n"
                  "        run: |\n"
                  "          echo never-use-fake-action\n"
                  "          - name: Check SpatialRuntime evidence\n"
                  "            uses: hippoley/SpatialRuntime/interop/conformance@" + REV + "\n")
        self.assertFalse(gate._source_has_named_action(source, "Check SpatialRuntime evidence", REV))

    def test_real_action_after_unrelated_multiline_shell_is_accepted(self):
        source = ("jobs:\n  evidence:\n    steps:\n"
                  "      - name: unrelated shell\n"
                  "        run: |\n"
                  "          uses: hippoley/SpatialRuntime/interop/conformance@" + REV + "\n"
                  "      - name: Check SpatialRuntime evidence\n"
                  "        uses: hippoley/SpatialRuntime/interop/conformance@" + REV + "\n")
        self.assertTrue(gate._source_has_named_action(source, "Check SpatialRuntime evidence", REV))

    def test_named_shell_step_with_scalar_action_reference_is_rejected(self):
        source = ("steps:\n"
                  "  - name: Check SpatialRuntime evidence\n"
                  "    run: >\n"
                  "      uses: hippoley/SpatialRuntime/interop/conformance@" + REV + "\n")
        self.assertFalse(gate._source_has_named_action(source, "Check SpatialRuntime evidence", REV))

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
