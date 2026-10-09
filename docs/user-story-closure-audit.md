# SpatialRuntime User Story Closure Audit

Status vocabulary:

- **CLOSED** — repository-owned executable evidence exists on `main`.
- **IN_REVIEW** — implementation and tests exist on an open PR but are not yet on `main`.
- **EXTERNAL_GATE** — repository code path exists, but the remaining proof depends on an external environment, binary, device, or independently maintained consumer.
- **OPEN** — repository-owned product/runtime behavior is still missing.

This document audits user stories at the level of end-to-end operator value, not file/class existence.

## 1. World / scene input

### US-01 — Accept source-neutral scene/topology data without inventing unsupported relations
**Status: CLOSED**

Evidence:
- `spatial/autocompile.py`
- `spatial/relation_graph.py`
- `spatial/resolver.py`
- `spatial/review.py`
- `spatial/promotion.py`
- tests `test_v36_*` through `test_v43_*`

The runtime only promotes explicit or provenance-backed spatial facts and leaves unresolved facade/room/coverage relationships unresolved instead of guessing.

### US-02 — Bind an external scene/topology source to a reviewed safety graph with source lineage
**Status: CLOSED**

Evidence:
- `spatial/compile_lineage.py`
- `spatial/reviewed_compile.py`
- source fingerprints for scene/topology/sensor bindings/templates
- tests for deterministic compile lineage, review and promotion

Remaining boundary:
- parsing proprietary CAD/BIM/2D formats is intentionally outside SpatialRuntime. The accepted boundary is normalized scene/topology data.

## 2. Solver / physical model

### US-03 — Run the runtime against a deterministic solver contract
**Status: CLOSED**

Evidence:
- `solver/contract.py`
- `solver/fixture.py`
- request/result provenance and adapter fingerprinting

### US-04 — Run explicitly configured external solver processes without scenario-controlled arbitrary execution
**Status: CLOSED**

Evidence:
- `JsonProcessSolverAdapter`
- explicit argv, `shell=False`, timeout, JSON stdin/stdout
- scenario JSON cannot choose executable/process arguments

### US-05 — Bind reviewed CONTAM projects and native result artifacts to stable runtime entities
**Status: CLOSED**

Evidence:
- `solver/contam/adapter.py`
- project inventory and binding registry
- explicit result-artifact parsing
- fresh-artifact checks
- mapping from native IDs to stable runtime IDs
- CONTAM mutation/inventory/execution tests

### US-06 — Demonstrate a real NIST ContamX solve in public CI/evidence
**Status: EXTERNAL_GATE**

Repository capability:
- `ContamCliRunner`
- `ContamCliResultProvider`
- executable discovery via installed binary or `CONTAMX_BIN`
- optional `--TestInput` validation
- execution evidence hash and explicit result artifact loading

Missing proof:
- repository CI intentionally uses a fake executable and does not claim a NIST ContamX run.

Closure evidence required:
- a pinned ContamX version;
- a reviewed PRJ/binding registry;
- actual execution report;
- fresh exported result artifact;
- replayable SpatialRuntime episode bundle.

## 3. Runtime assembly

### US-07 — Assemble real solver/gateway dependencies into the same closed loop without making scenario JSON executable
**Status: CLOSED**

Evidence:
- PR #63 merged
- merge commit `10b5c2e81a8ea3565ed801e522f2ca06acb2c6d8`

The new application assembly layer injects runtime dependencies from application code while keeping scenario JSON inert.

Expected closed-loop path:

```text
injected SolverAdapter
→ reconcile
→ safety
→ commit gate
→ injected gateway
→ command ledger
→ device feedback
→ next runtime state
→ replayable execution manifest
```

The PR also proves a `DurableCommandLedger` can be injected and recovered.

## 4. Safety and authority

### US-08 — Prevent policy actions from bypassing higher-priority safety constraints
**Status: CLOSED**

Evidence:
- safety dependency graph
- action arbitration
- supervisor
- commit gate
- safety override tests

### US-09 — Keep proposal, commit, dispatch, acknowledgement and observed effect distinct
**Status: CLOSED**

Evidence:
- RuntimeSession stage trace
- Agent Effect Authority contracts
- tool-decision lifecycle profile
- decision→execution binding profiles
- effect evidence profiles

### US-10 — Reject stale step/revision evidence and stale commits
**Status: CLOSED**

Evidence:
- reconciler envelope validation
- commit gate
- replay trace-chain validation
- hardware-event step/revision validation

## 5. Hardware / device execution

### US-11 — Dispatch through a transport-neutral real gateway contract
**Status: CLOSED**

Evidence:
- `ThingModelGatewayAdapter`
- injected discover/command transports
- normalized capabilities
- command-id idempotency requirement
- ACK/state-feedback normalization

This is a production integration contract, not a claim that CI drives physical hardware.

### US-12 — Detect capability/ThingModel drift before unsafe dispatch
**Status: CLOSED**

Evidence:
- capability registry / reviewed gateway
- capability fingerprints
- drift tests

### US-13 — Handle retries, ACK timeout, feedback timeout and duplicate command replay safely
**Status: CLOSED**

Evidence:
- `CommandLedger`
- deterministic command IDs
- idempotent batch registration
- retry/timeout logic
- duplicate-event suppression

### US-14 — Persist hardware command state across process restart
**Status: CLOSED**

Evidence:
- `DurableCommandLedger`
- append-only hash-chained journal
- replay-based recovery
- integrity verification

### US-15 — Persist fault-recovery state across restart
**Status: CLOSED**

Evidence:
- `DurableRecoveryStateMachine`
- recovery journal integrity tests
- manual-service latch survives restart
- recovery-attempt count survives restart

### US-16 — Demonstrate the gateway contract against a real physical device
**Status: EXTERNAL_GATE**

Missing proof is environmental, not a missing adapter abstraction.

Closure evidence required:
- device/gateway identity;
- capability snapshot/fingerprint;
- one accepted command;
- ACK;
- fresh measured state feedback;
- command/reconciliation episode bundle;
- restart/retry behavior for at least one lost-ACK or delayed-feedback case.

## 6. Reconciliation / physical truth

### US-17 — Never promote a commanded target to confirmed physical state without feedback
**Status: CLOSED**

Evidence:
- `committed_target_unconfirmed`
- hard `unconfirmed_committed_target` disagreement
- observation blocks until fresh device feedback arrives

### US-18 — Reconcile model/sensor/device disagreement explicitly
**Status: CLOSED**

Evidence:
- `state_reconciler.py`
- quality thresholds
- hard vs warning disagreement classes
- observation blocking

### US-19 — Detect convergence / device health / recovery conditions
**Status: CLOSED**

Evidence:
- hardware convergence
- device health
- fault recovery
- safety-lineage tests

## 7. Replay / restart

### US-20 — Produce tamper-detectable replayable episode bundles
**Status: CLOSED**

Evidence:
- trace hashes
- state hashes
- bundle hash
- manifest hash
- cross-step chain verification
- CLI replay / inspect

### US-21 — Resume a live RuntimeSession from a validated saved bundle
**Status: IN_REVIEW — PR #64**

PR:
- https://github.com/hippoley/SpatialRuntime/pull/64

Resume requires:
- valid bundle;
- execution manifest;
- exact entity-catalog fingerprint;
- exact safety-graph fingerprint;
- terminal trace status `completed` or `hardware_incomplete`.

A resumed hardware-incomplete state remains fail-closed until fresh device evidence reconciles the unconfirmed target.

## 8. Conformance infrastructure

### US-22 — Let another implementation use SpatialRuntime conformance without importing the runtime
**Status: CLOSED**

Evidence:
- adapter protocols
- hostile conformance bundles
- reusable GitHub Action
- machine-readable catalog
- PASS / UNRESOLVED / FAIL semantics

### US-23 — Model approval/authorization decision identity separately from execution identity
**Status: CLOSED**

Evidence:
- `decision-execution-binding.v0.1`
- standing 1:N decision support
- per-call reuse rejection

### US-24 — Bind temporal approval authority to an actual execution attempt
**Status: CLOSED**

Evidence:
- `decision-execution-binding.v0.2`
- decision `decided_at` / `valid_until`
- execution `started_at`
- expiry/reuse/scope-mismatch vectors
- Agent Approval Protocol pressure mapping

### US-25 — Independently test broker runtime behavior beyond token-only authorization conformance
**Status: CLOSED**

Evidence:
- `aap-broker-behavior.v0.1`
- opaque denial vectors
- context-leak negative controls
- signed-audit evidence requirement
- pinned spec/reference-implementation finding

## 9. External adoption

### US-26 — An unrelated repository consumes a pinned SpatialRuntime conformance surface
**Status: OPEN**

Tracker:
- issue #14

Same-maintainer cross-repo consumption proves portability but does not satisfy this story.

Closure threshold:
- unrelated repo pins Action/verifier/profile and publishes reproducible PASS, UNRESOLVED, FAIL, or counterexample evidence.

### US-27 — A second independent broker runs AAP behavior vectors
**Status: OPEN**

Tracker:
- issue #47

A failing second implementation still counts as valuable interoperability evidence if the run is reproducible and correctly attributed.

## 10. Current highest-value gaps

The repository does **not** need another large internal profile before these are addressed.

Priority order:

1. merge/validate PR #64 — restartable live runtime;
2. produce one real ContamX evidence bundle;
3. produce one real device/gateway evidence bundle;
4. obtain one unrelated conformance consumer or falsification contribution.

Items 3–5 are external evidence gates. More internal abstractions have sharply lower marginal value until one of those gates moves.

## 11. Exit discipline

A line should be downgraded when:

- three concrete external integration attempts produce no maintainer response, adoption, counterexample, or independent run;
- a stronger upstream standard fully absorbs the same invariant and offers a better governance node;
- maintaining a local profile becomes mostly vocabulary work rather than executable evidence;
- a new protocol/runtime offers a materially stronger path to independent adoption.

The long-term asset is not a specific protocol name. It is the reusable evidence boundary:

```text
world evidence
→ decision authority
→ exact/temporal execution binding
→ dispatch
→ effect evidence
→ reconciliation
→ replay / restart
→ independent conformance
```
