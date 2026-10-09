# SpatialRuntime Interop Conformance Action

This is the neutral consumption entry point for SpatialRuntime's model-independent interoperability checks.

It deliberately does **not** require a caller to adopt the Agent Effect Authority name or architecture. Existing `interop/agent-effect-authority` consumers remain supported; this path is an additive compatibility surface.

## Example

```yaml
- name: Verify decision → execution binding
  id: conformance
  uses: hippoley/SpatialRuntime/interop/conformance@<pinned-sha>
  with:
    mode: decision-execution-binding
    file: evidence/decision-execution-binding.json

- name: Require resolved conformance
  if: steps.conformance.outputs.conformance_result != 'PASS'
  run: exit 1
```

Consumers should pin an immutable commit SHA.

Runtime prerequisites: the composite Action expects `bash` and `python >= 3.10` to already be available on the runner. It does not install Python. External adapter commands may require additional consumer-owned dependencies. These prerequisites are also declared in the machine-readable catalog.

## Modes

- `claim`
- `mapping`
- `mapping-v0.2`
- `tool-decision-lifecycle`
- `decision-execution-binding`
- `decision-execution-binding-v0.2`
- `effect-evidence-bundle`
- `effect-evidence-v0.2`

The Action delegates to the existing verifier implementations rather than duplicating their rules.

A successful process exit does not always mean `PASS`. In particular, `claim`, `mapping`, and `mapping-v0.2` are **envelope-only validation modes**: a well-formed declaration returns `validation_result=PASS`, `assessment_scope=envelope_only`, and `conformance_result=UNRESOLVED` because the Action does not independently verify the downstream evidence or analyst interpretation. Evidence-bearing profiles may also return `UNRESOLVED` when evidence is incomplete. Consumers should gate on the structured output that matches the assurance they actually need.

## Machine-readable catalog

`manifest.v0.1.json` lists the currently exposed Action modes, profile versions, verifier entry points, structured outputs, and result semantics.

This catalog is descriptive: it does not override the profile files or verifier behavior. Consumers should still pin an immutable SpatialRuntime commit SHA.

`verify_catalog.py` checks that every catalog mode points to an existing verifier, that its declared profile/version matches the source artifact exactly, and that structured modes expose `conformance_result`. Repository CI runs this check to prevent catalog drift.

## External verifier mode

The neutral Action can test a third-party effect-evidence verifier without importing SpatialRuntime code.

The adapter contract is `effect-evidence-adapter.v0.1`: one JSON envelope on stdin, one JSON verdict on stdout.

```yaml
- name: Run hostile effect-evidence vectors against our verifier
  id: effect_evidence
  uses: hippoley/SpatialRuntime/interop/conformance@<pinned-sha>
  with:
    mode: effect-evidence-bundle
    adapter_command: python scripts/my_effect_verifier_adapter.py
    report_path: artifacts/effect-evidence-conformance.json

- name: Preserve conformance evidence
  uses: actions/upload-artifact@v4
  with:
    name: effect-evidence-conformance
    path: ${{ steps.effect_evidence.outputs.report_path }}
```

If `adapter_command` is omitted, the bundle runs against SpatialRuntime's built-in evaluator.

This is a conformance harness boundary, not a standardized production API.

For `effect-evidence-bundle`, the Action exposes:

- `conformance_result`: `PASS` or `FAIL`;
- `passed_count`;
- `failed_count`;
- `total_count`;
- `report_path` when a durable JSON report was requested.

A green check without a retained run report is useful for CI gating but weaker historical evidence. For durable compatibility claims, retain the JSON report together with the pinned SpatialRuntime commit and implementation revision.

## Consumer quickstart

Copy-oriented examples live under `interop/conformance/examples/`:

- `github-action.yml` — minimal CI wiring for a binding claim or external verifier bundle;
- `effect_verifier_adapter.py` — safe adapter stub that returns `UNRESOLVED` until a real verifier is wired;
- `README.md` — integration steps.

The quickstart intentionally has no default passing adapter.


## Temporal binding example

`decision-execution-binding-v0.2` adds decision validity windows and execution-start evidence without changing v0.1:

```yaml
- name: Verify temporal approval → execution binding
  id: binding
  uses: hippoley/SpatialRuntime/interop/conformance@<pinned-sha>
  with:
    mode: decision-execution-binding-v0.2
    file: evidence/decision-execution-v0.2.json
```

The result remains `PASS`, `UNRESOLVED`, or `FAIL`. Missing execution-start evidence is unresolved; execution outside the approved window fails.
