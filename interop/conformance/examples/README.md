# External consumer quickstart

This directory is a copy-oriented integration example for repositories that want to run SpatialRuntime conformance without importing SpatialRuntime code.

Files:

- `github-action.yml` — two CI patterns:
  - validate a decision→execution binding claim;
  - run the hostile effect-evidence bundle against a third-party verifier.
- `effect_verifier_adapter.py` — stdin/stdout adapter stub.

Before use:

1. Replace `<PINNED_SPATIALRUNTIME_SHA>` with an immutable commit that contains the neutral `interop/conformance` Action.
2. Copy the workflow into your repository's `.github/workflows/` directory.
3. For `decision-execution-binding`, provide your own evidence JSON.
4. For `effect-evidence-bundle`, replace the adapter stub's unresolved verdict with a call into your own verifier.

The stub deliberately returns `UNRESOLVED`; copying the example must not manufacture a passing conformance claim.
