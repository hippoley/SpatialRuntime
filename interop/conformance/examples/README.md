# External consumer quickstart

This directory is a copy-oriented integration example for repositories that want to run SpatialRuntime conformance without importing SpatialRuntime code.

Files:

- `github-action.yml` — two CI patterns:
  - validate a decision→execution binding claim;
  - run the hostile effect-evidence bundle against a third-party verifier.
- `effect_verifier_adapter.py` — stdin/stdout adapter stub.

Before use:

1. The sample workflow is pinned to immutable SpatialRuntime commit `ce7cce687e623ed16f9c60db782bed05e9b117ba` (not a stable release tag). Verify this revision against your requirements before upgrading it.
2. Copy the workflow into your repository's `.github/workflows/` directory and install the adapter at `scripts/effect_verifier_adapter.py` if you keep the second job.
3. For `decision-execution-binding`, provide your own evidence JSON.
4. For `effect-evidence-bundle`, replace the adapter stub's unresolved verdict with a call into your own verifier.

The stub deliberately returns `UNRESOLVED`; copying the example must not manufacture a passing conformance claim.
