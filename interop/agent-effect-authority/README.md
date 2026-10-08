# Agent Effect Authority v0.1

**A model-independent authority boundary for consequential agent effects.**

Agent Effect Authority (AEA) is a small interoperability contract for runtimes in which an LLM, planner, workflow, or autonomous agent can propose actions that may mutate software state, external systems, money, infrastructure, or the physical world.

The core rule is deliberately narrow:

```text
proposal != authorization != dispatch != acknowledgement != effect evidence
```

A stronger model does not remove this boundary. It makes the boundary more important.

## Why this exists

Modern agent stacks are getting better at generating plans and tool calls. The durable problem is different:

- Who owns the canonical effect identity?
- Was the action actually authorized?
- Did transport succeed but the real effect remain unknown?
- Is a retry the same logical effect or a duplicate mutation?
- Was compensation requested, or actually verified?
- What state is authoritative for the next decision?

AEA makes those questions implementation-neutral.

## Lifecycle

```text
agent/model proposal
      ↓
runtime-owned effect identity
      ↓
effect classification
      ↓
policy / approval / authorization
      ↓
dispatch attempt
      ↓
transport evidence
      ↓
authoritative reconciliation
   ↙       ↓        ↘
confirmed contradicted unresolved
      ↓
optional compensation
      ↓
authoritative reconciliation
      ↓
fresh state becomes next decision origin
```

## Requirements

The normative requirement IDs live in [manifest.json](manifest.json):

- `AEA-001` proposal is not authority
- `AEA-002` logical effect identity is runtime-owned
- `AEA-003` effect class is known before execution
- `AEA-004` authorization is explicit and separate
- `AEA-005` transport evidence is not effect evidence
- `AEA-006` unresolved outcome is first-class
- `AEA-007` retry identity prevents duplicate intent
- `AEA-008` compensation, when supported, is a distinct linked effect
- `AEA-009` fresh authoritative state closes the loop

## Capability applicability

AEA is a boundary contract, not a feature checklist.

In particular, **compensation is optional**. A runtime may safely implement reconciliation, manual recovery, or a fail-closed unresolved state without implementing compensation or saga orchestration. If compensation exists, AEA-008 requires it to remain a distinct, linked effect whose requested / dispatched / acknowledged / verified states are not conflated. A runtime that does not support compensation must not present reconciliation or retry as if rollback occurred.

This clarification came from testing the contract against an independent public runtime design that implements durable UNKNOWN reconciliation while deliberately keeping automatic compensation out of scope.

## Portable conformance claim

A downstream runtime does not need SpatialRuntime code. It can publish a small JSON claim mapping every AEA requirement to implementation-owned evidence.

See [claim.example.json](claim.example.json).

Validate the envelope:

```bash
python interop/agent-effect-authority/verify_claim.py \
  interop/agent-effect-authority/claim.example.json
```

The verifier checks completeness, version alignment, and requirement applicability. Required requirements must be `PASS` with evidence. A conditional requirement may be `NOT_APPLICABLE` only with an explicit rationale and no PASS evidence. The verifier does **not** pretend to audit whether a downstream's evidence is true.

## Emerging design pressure: identity before nondeterminism

A current durable-runtime pressure case is crash/replay around a nondeterministic action-formation step. If a logical effect identity is created only after replaying a model or other nondeterministic component, the regenerated effect-bearing arguments may differ and the runtime can lose the ability to recognize the replay as the same real-world intent.

AEA v0.1 already requires runtime-owned logical effect identity and retry identity preservation, but it does **not yet** normatively require a particular persistence point. The LangGraph #8039 recovery discussion is recorded in the case matrix as evidence pressure for a possible future rule: bind and durably retain logical effect identity before the first replayable nondeterministic boundary that can alter consequential action semantics.

A related boundary is receiver-side deduplication: admission of an idempotency key is not the same as authoritative evidence that the effect completed. A receiver that crashes after admission but before completion can otherwise turn duplicate prevention into effect loss.

This section is intentionally non-normative until more independent implementations support or challenge the rule.

## Reference evidence already exercised publicly

AEA is extracted from working boundaries rather than invented only as prose:

- **SpatialRuntime**: proposed action != committed action != observed device state; ACK != physical convergence; commit gate + reconciliation.
- **AirTrajectory**: public lost-ACK / authoritative-readback reconciliation vectors exercise confirmed, contradicted, and unresolved physical effects.
- **Contextual Edge SLU / NLUSLOT**: runtime-owned commit authority, stale-context compare-and-swap, and model proposals without mutation authority.

The intent is not to force those implementations on downstreams. They are the source of the failure cases that shaped the contract.

## Cross-protocol convergence

The same authority/evidence boundary is now visible in independent protocol work:

- **MCP #3394** reproduces a mutating `tools/call` whose external effect commits before the response is lost; an application retry with a fresh JSON-RPC request id can execute the effect again. Independent follow-up reproductions also show that reserving a key alone can prevent a duplicate while still leaving the final outcome unknown.
- **A2A #1987** is the v1.1 idempotency/safe-retry epic. Its protocol-level deduplication work closes an important task-creation hole, while still leaving a separate question: whether a downstream external effect actually completed.

AEA treats these as related but distinct layers: retry identity, transport/task deduplication, and authoritative external-effect evidence should not be collapsed into one guarantee.

These references are pressure evidence only; they do not imply MCP or A2A adoption of AEA.

## Relationship to observability standards

AEA is not an observability standard. It is an execution/conformance boundary that can supply reference scenarios to observability work.

In particular, an observability system should be able to represent without conflation:

- effect intent vs effect outcome;
- logical effect ID vs attempt ID;
- approval pending vs authorized;
- transport success vs authoritative effect evidence;
- unresolved effect vs failed effect;
- compensation requested vs compensation verified.

This is intentionally compatible with ongoing OpenTelemetry GenAI discussions around durable runtime state transitions and external effects, without claiming that AEA field names belong in OpenTelemetry.

## What this does not claim

AEA v0.1 does not claim:

- that an agent chose the correct action;
- that a model is accurate;
- that a policy is sufficient;
- that a device or external system is trustworthy;
- that a self-declared downstream claim has been independently audited.

It only defines the authority/evidence boundary that such systems can implement and test.
