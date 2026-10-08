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

## Modes

- `claim`
- `mapping`
- `mapping-v0.2`
- `tool-decision-lifecycle`
- `decision-execution-binding`
- `effect-evidence-v0.2`

The Action delegates to the existing verifier implementations rather than duplicating their rules.

A successful process exit does not always mean `PASS`: profiles may intentionally return `UNRESOLVED` when evidence is incomplete. Use structured outputs when available and choose policy in the caller.
