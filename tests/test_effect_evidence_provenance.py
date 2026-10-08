import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "interop" / "agent-effect-authority" / "validate_evidence_provenance.py"

SPEC = importlib.util.spec_from_file_location("validate_evidence_provenance", VALIDATOR)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_source_review_requires_source_and_cannot_claim_execution():
    good = module.validate_provenance({
        "evidence_method": "source-review",
        "implementation_ref": "studivox/agentx@0.1.1",
        "source_ref": "src/verification/verifier-engine.ts@9da8cb8",
    })
    assert good["valid"] is True

    bad = module.validate_provenance({
        "evidence_method": "source-review",
        "implementation_ref": "studivox/agentx@0.1.1",
        "source_ref": "src/verification/verifier-engine.ts@9da8cb8",
        "run_artifact_ref": "run://not-allowed",
    })
    assert bad == {
        "valid": False,
        "reason": "SOURCE_REVIEW_CANNOT_CLAIM_RUN_ARTIFACT",
    }


def test_executed_requires_real_run_artifact():
    result = module.validate_provenance({
        "evidence_method": "executed",
        "implementation_ref": "OpenAdaptAI/openadapt-flow",
        "implementation_version_or_commit": "6e4e4ed",
        "probe_id": "effect-evidence-taxonomy-v0.1",
    })
    assert result["valid"] is False
    assert result["reason"] == "MISSING_REQUIRED_PROVENANCE"
    assert "run_artifact_ref" in result["missing"]


def test_external_reproduction_requires_independent_identity_and_artifact():
    result = module.validate_provenance({
        "evidence_method": "externally-reproduced",
        "implementation_ref": "OpenAdaptAI/openadapt-flow",
        "implementation_version_or_commit": "6e4e4ed",
        "probe_id": "effect-evidence-taxonomy-v0.1",
        "run_artifact_ref": "github-actions://owner/run/1",
    })
    assert result["valid"] is False
    assert set(result["missing"]) == {
        "reproducer_identity",
        "reproducer_artifact_ref",
    }
