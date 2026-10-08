# Tool Decision Lifecycle Correlation Profile v0.1

This experimental interop profile checks one narrow property across agent runtimes and telemetry producers:

> Can a pre-execution `gen_ai.tool.call.decision` be correlated to the same observed `execute_tool` lifecycle by `gen_ai.tool.call.id`?

It does **not** define a new ledger, replace OpenTelemetry semantic conventions, or claim that correlated telemetry proves a real-world effect.

## Why this exists

Independent projects already expose different sides of the same boundary:

- OpenTelemetry GenAI PR #535 proposes `gen_ai.tool.call.decision`.
- Devplane already renders its decision log in that proposed OTLP/JSON shape, but explicitly omits `gen_ai.tool.call.id` when its source channel cannot establish the model's call identity.
- Tracelyt uses `tool_call_id` as the observed merge/correlation key for requested → authorized/rejected → completed/failed tool chains.

The interoperability gap is therefore not another event name. It is **correlation completeness**.

## Result classes

- `PASS`: observed decision/execution lifecycle is internally consistent and fully correlatable for the supplied evidence.
- `UNRESOLVED`: at least one decision lacks the correlation identity needed to join it safely. No guessed ID is created.
- `FAIL`: the observed evidence contradicts the lifecycle invariant, for example a `deny` and an `execute_tool` span sharing the same call id.

Important: `NO_EXECUTION_OBSERVED` means exactly that. Sampling, exporter loss, or a different execution channel can hide execution. It is **not** proof that no external effect occurred.

## Run

```bash
python interop/otel-tool-decision-lifecycle/verify.py \
  interop/otel-tool-decision-lifecycle/fixtures/positive-path.otlp.json
```

The Devplane-style fixture intentionally returns `UNRESOLVED`, because its decision record has no model-owned `gen_ai.tool.call.id`. That is a valid and safer result than inventing correlation from timestamps, tool names, or local row ids.


## GitHub Action policy branching

The reusable action exposes structured outputs for this mode, so a caller does not need to parse stdout:

```yaml
- name: Check tool-decision lifecycle
  id: lifecycle
  uses: hippoley/SpatialRuntime/interop/agent-effect-authority@<pinned-sha>
  with:
    mode: tool-decision-lifecycle
    file: telemetry/otlp.json

- name: Require complete correlation for this lane
  if: steps.lifecycle.outputs.lifecycle_result != 'PASS'
  run: |
    echo "correlation status: ${{ steps.lifecycle.outputs.lifecycle_result }}"
    echo "unresolved: ${{ steps.lifecycle.outputs.unresolved_count }}"
    echo "errors: ${{ steps.lifecycle.outputs.error_count }}"
    exit 1
```

Available outputs:

- `lifecycle_result`: `PASS`, `UNRESOLVED`, or `FAIL`;
- `unresolved_count`: decision records that cannot be safely joined to a model-owned call identity;
- `error_count`: observed contradictions or invalid decision values.

The default verifier still exits non-zero only for `FAIL`. This is intentional: a producer that cannot observe a correlation id is not lying or broken. Downstream policy decides whether `UNRESOLVED` is acceptable for that lane.
