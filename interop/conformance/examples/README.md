# External consumer quickstart

The copyable [github-action.yml](github-action.yml) now runs a **bundled-reference smoke check**. It needs no invented consumer evidence file and no unfinished adapter. It pins the published `conformance-v0.1.0` release tag. Use an exact commit SHA only when reproducing older historical evidence.

## First execution: smoke only

1. Copy `github-action.yml` to `.github/workflows/agent-conformance.yml`.
2. Run it under GitHub Actions with Python 3.12 and inspect the emitted JSON artifact.
3. Treat green output strictly as verification of SpatialRuntime's **own** bundled reference evaluator, **not** your project's effect correctness or independent adoption.

## Second execution: your verifier (the actual consumer gate)

After your project's verifier exists, replace the `bundle` step's inputs with:

```yaml
with:
  mode: effect-evidence-bundle
  adapter_command: python scripts/effect_verifier_adapter.py
  report_path: artifacts/effect-evidence-conformance.json
```

Copy [effect_verifier_adapter.py](effect_verifier_adapter.py) to `scripts/` and replace its intentionally unresolved stub with a real adapter to *your own* verifier. The stub always returns `UNRESOLVED`; a workflow requiring `PASS` **must fail** until genuine verification is implemented. Do not mark a missing or indeterminate effect as success to turn CI green.

Record the calling repository and implementation revision, pinned SpatialRuntime release/tag (or historical commit), workflow run, and retained artifact. Only an unrelated repository running its own actual verifier or binding evidence can support CF-06; running the reference smoke job alone cannot.

For consumers checking decision/execution binding instead, supply a project-owned evidence JSON file and choose `mode: decision-execution-binding-v0.2` with `file: <your-evidence-path>`. A missing evidence file is never an acceptable success case.
