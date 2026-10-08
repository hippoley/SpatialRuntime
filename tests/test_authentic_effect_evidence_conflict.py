import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "interop" / "agent-effect-authority" / "verify_effect_evidence_set.py"
VECTORS = ROOT / "interop" / "agent-effect-authority" / "authentic-evidence-conflict-v0.1.json"

SPEC = importlib.util.spec_from_file_location("verify_effect_evidence_set", MODULE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_conflicting_authentic_evidence_vectors():
    payload = json.loads(VECTORS.read_text(encoding="utf-8"))
    policy = payload["authority_policy"]

    for case in payload["cases"]:
        result = module.evaluate_evidence_set(case["observations"], policy)
        assert result == case["expected"], case["id"]


def test_conflict_blocks_ordinary_continuation():
    payload = json.loads(VECTORS.read_text(encoding="utf-8"))
    case = next(item for item in payload["cases"] if item["id"] == "two-authoritative-sources-conflict")
    result = module.evaluate_evidence_set(case["observations"], payload["authority_policy"])
    assert result["status"] == "CONFLICT"
    assert result["ordinary_continuation"] is False
