# Decision → Execution Binding Conformance v0.1

This experimental profile verifies a narrow interoperability invariant:

> Authorization/approval **decision identity** and tool **execution identity** are different things, and their binding may be 1:1 or 1:N.

It does not define an authorization protocol, an effect ledger, or a new OpenTelemetry namespace.

## External pressure behind the profile

Three independent systems expose the same identity split:

- **CoSAI AITF** defines an authorization/approval decision identity separately from **Tool Execution ID**, and requires `identity.approval.scope_binding.result` to say whether the approved operation still covers the arguments actually executed.
- **Devplane** records standing `allow_always` / `reject_always` decisions and explicitly notes that later calls covered by a standing decision may never produce another decision record.
- **Tracelyt** preserves permanent-vs-temporary decision source while still correlating individual tool lifecycle events by `tool_call_id`.

The portable question is therefore not “what is the one correlation id?” It is:

```text
decision_id / approval scope
        │ covers 1..N
        ▼
tool_call_id / execution_id
        │
        ▼
execution / effect evidence
```

## Result classes

- `PASS` — supplied decision→execution bindings are internally consistent and scope binding was checked.
- `UNRESOLVED` — a binding or scope check is missing/unknown.
- `FAIL` — evidence contradicts the declared binding, e.g. a per-call decision reused across two calls, a denied decision followed by an execution, or scope mismatch.

## Why this is separate from the tool-decision lifecycle profile

`otel-tool-decision-lifecycle.v0.1` checks a **per-call telemetry lifecycle** using `gen_ai.tool.call.id`.

This profile handles the layer above it: a decision can have its own identity and may cover multiple calls. A standing grant must not be flattened into one fake tool-call id.

## Example

```json
{
  "profile": "decision-execution-binding.v0.1",
  "decisions": [
    {
      "decision_id": "standing-1",
      "binding_mode": "standing",
      "outcome": "allow"
    }
  ],
  "executions": [
    {
      "execution_id": "exec-1",
      "tool_call_id": "call-1",
      "decision_id": "standing-1",
      "scope_binding": "match"
    },
    {
      "execution_id": "exec-2",
      "tool_call_id": "call-2",
      "decision_id": "standing-1",
      "scope_binding": "match"
    }
  ]
}
```

A PASS here still does **not** prove that an external real-world effect occurred. It only validates the supplied decision/execution binding evidence.


## Pinned evidence anchors

The profile is an independent conformance artifact; the projects below have **not** adopted or endorsed it. They are frozen pressure sources explaining why decision and execution identity cannot safely be collapsed:

- `cosai-oasis/ws2-defenders@b8dbec1c35262194ae78f1dbc973ba6d513524cb`
  - `telemetry/aitf/spec/semantic-conventions/attributes-registry.md`
  - `telemetry/build-telemetry/data/fields.yaml`
- `hupe1980/devplane@055b414af45b373339164dc349901757e44b3147`
  - `src/core/genai.rs`
  - `site/content/docs/decisions.md`
- `ajkumar-13/Tracelyt@b99ebbe165c51682c3ef08b201c811526d5ded08`
  - `src/harness_engine/adapters/claude_code/otel_logs.py`
  - `docs/specs/SPEC-01-telemetry-and-execution-graph.md`

This evidence establishes independent pressure on the identity/cardinality model. It does not establish source-project conformance, dependency, or endorsement.


## v0.2: temporal validity and execution-attempt evidence

`decision-execution-binding.v0.2` is additive. v0.1 remains unchanged for historical claims.

v0.2 adds optional decision and execution timestamps:

- decision `decided_at`;
- decision `valid_until`;
- execution `started_at`.

When a decision supplies a temporal window, the verifier distinguishes:

- execution begins inside the window → may PASS when the other binding evidence passes;
- execution begins before the decision → `FAIL / EXECUTION_PRECEDES_DECISION`;
- execution begins at or after expiry → `FAIL / DECISION_EXPIRED_BEFORE_EXECUTION`;
- no execution-start evidence → `UNRESOLVED`, never silently PASS.

The existing per-call cardinality rule still applies: one `per_call` decision cannot authorize two execution attempts.

### External pressure: Agent Approval Protocol v1

Agent Approval Protocol v1 is mapped as an independent pressure source, not an adopter:

`mappings/agent-approval-protocol-v1.json`

The mapping uses:

```text
AAP approval request id  -> decision_id
AAP Idempotency-Key      -> execution-attempt / tool_call_id
AAP tool+server+arguments -> scope_binding evidence
AAP decision.expires_at  -> valid_until
actual tool start         -> started_at
```

AAP defines the approval-provider plane and leaves execution tracking to the adapter/harness. v0.2 deliberately stays on that boundary: it can verify supplied approval→execution evidence, but it does not claim the provider proves external effect completion.

### Reusable GitHub Action

Downstream CI can pin a SpatialRuntime revision and run:

```yaml
- name: Verify decision/execution binding v0.2
  uses: hippoley/SpatialRuntime/interop/agent-effect-authority@<pinned-sha>
  with:
    mode: decision-execution-binding-v0.2
    file: evidence/decision-execution.json
```

Pin an immutable commit rather than `main` for historical evidence.
