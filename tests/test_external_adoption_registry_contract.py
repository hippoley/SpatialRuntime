"""Registry-level adoption fields and remote closure must remain separate."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "interop" / "external-results"
sys.path.insert(0, str(REGISTRY_DIR))
import verify_registry as verifier

REGISTRY = json.loads((REGISTRY_DIR / "registry.v0.1.json").read_text())

class RegistryAdoptionTests(unittest.TestCase):
    def candidate(self):
        doc = copy.deepcopy(REGISTRY)
        e = doc["entries"][0]
        e["evidence_maturity"] = "externally-consumed"
        e["external_consumption"] = True
        e["adoption_claim"] = True
        e["consumer"] = {"project_owned_evidence": True, "repository": "outside-lab/runtime",
                         "workflow_run_id": 123, "workflow_run_url": "https://github.com/outside-lab/runtime/actions/runs/123",
                         "workflow_path": ".github/workflows/conformance.yml",
                         "workflow_commit": "a"*40, "spatialruntime_commit": "b"*40}
        return doc

    def test_existing_real_registry_stays_valid(self):
        self.assertTrue(verifier.verify(copy.deepcopy(REGISTRY))["valid"])

    def test_self_asserted_adoption_without_run_link_is_invalid(self):
        doc = self.candidate()
        del doc["entries"][0]["consumer"]["workflow_run_url"]
        self.assertFalse(verifier.verify(doc)["valid"])

    def test_self_asserted_adoption_without_pinned_revision_is_invalid(self):
        doc = self.candidate()
        del doc["entries"][0]["consumer"]["spatialruntime_commit"]
        self.assertFalse(verifier.verify(doc)["valid"])

    def test_owner_controlled_consumer_is_invalid(self):
        doc = self.candidate()
        doc["entries"][0]["consumer"]["repository"] = "HiPpOlEy/fake"
        self.assertFalse(verifier.verify(doc)["valid"])

    def test_candidate_can_be_structurally_valid_but_not_remotely_proven(self):
        result = verifier.verify(self.candidate())
        self.assertTrue(result["valid"], result["errors"])
        # A different, remote-authenticated gate is needed to CLOSE CF-06.
        # Merely syntactically valid registry data does not count as adoption.

if __name__ == "__main__":
    unittest.main()
