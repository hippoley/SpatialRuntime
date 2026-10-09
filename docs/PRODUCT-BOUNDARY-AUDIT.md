# SpatialRuntime Product Boundary and User-Story Audit

Status date: 2026-10-09

## Executive decision

SpatialRuntime currently contains two product lanes:

1. **Executable Spatial Runtime**
   - scene/world state
   - safety/recovery
   - solver adapters
   - hardware dispatch/reconciliation
   - replay/provenance

2. **Agent Conformance / Interoperability Lab**
   - effect-evidence conformance
   - decision/execution binding
   - tool lifecycle correlation
   - cross-runtime mappings
   - external standards probes

These lanes share the same correctness philosophy but serve different users.

The repository must not imply that progress in one lane proves maturity in the other.

### Current strategic priority

The conformance/interoperability lane is the active external-adoption lane.

The spatial runtime remains:
- a real implementation source for failure cases;
- a reference implementation for physical-effect grounding;
- a maintained runtime;
- **not** the primary growth surface until a real external spatial-runtime consumer or hardware deployment creates new demand.

## User-story truth table

Legend:
- DONE = implemented and exercised by repository tests/CI
- PARTIAL = implementation exists but an external/real-world condition is not yet satisfied
- OPEN = user-visible value is not yet delivered
- HOLD = deliberately not expanded without external demand

| ID | User story | Status | Evidence / gap |
|---|---|---|---|
| SR-01 | As an application, I can execute a deterministic spatial runtime episode with reconciliation, safety, commit gating, and replay | DONE | RuntimeSession + scenario/replay tests |
| SR-02 | As an application, I can plug in solver output without letting a scenario file execute arbitrary local commands | DONE | fixture mode + explicit solver adapter boundary |
| SR-03 | As a CONTAM user, I can bind a reviewed PRJ and safely mutate understood flow parameters | DONE | parser/binding/mutation lineage |
| SR-04 | As a CONTAM user, I can prove a real ContamX solve in repository CI | PARTIAL | SpatialRuntime CI remains fixture-only, but owned downstream AirTrajectory executes official `contamxpy==0.0.9` + real NIST/generated PRJ on Windows CI while pinning SpatialRuntime `d123ab9a...`; this is grounding evidence, not repository-local proof |
| SR-05 | As a hardware user, I can dispatch through a real gateway/device fleet and prove physical convergence | PARTIAL | SpatialRuntime gateway/ledger contracts exist; WindowPilot has a real CWDS-CA01 hardware/identity/write-gate path, but its own claim ceiling still withholds physical τ₀ until a real window movement is measured |
| SR-06 | As an operator, I can prove durable restart/recovery behavior against real device-side uncertainty | PARTIAL | durable ledger/reconciliation logic exists and owned downstream hardware contracts are stronger, but no field-grade restart/recovery evidence from a real device deployment is frozen yet |
| SR-07 | As a scene-source consumer, I can use the same reviewed world model from an unrelated BIM/CAD/SLAM integration | PARTIAL | owned scene-source repo `interior-kitchen-original` exports `spatialruntime_world_snapshot_v1`, imports SpatialRuntime `WorldSnapshot`, validates handoff hashes, and rejects stale source drift in CI; unrelated BIM/CAD/SLAM consumption is still missing |
| SR-08 | As an application, I can inject a real solver/gateway into the same closed loop without making scenario JSON executable | DONE | PR #63 merged as `10b5c2e81a8ea3565ed801e522f2ca06acb2c6d8`; explicit application assembly injects solver/gateway/ledger/bindings from code, fingerprints them in the execution manifest, and keeps executable dependency config out of scenario data |
| SR-09 | As an operator, I can rebuild a live RuntimeSession from a validated saved episode and continue safely | DONE | PR #64 merged as `ce7cce687e623ed16f9c60db782bed05e9b117ba`; resume validates bundle/manifest, rebinds catalog and safety-graph fingerprints, restores history/state/step/revision, and preserves fail-closed hardware-incomplete uncertainty |
| CF-01 | As a runtime author, I can run conformance checks without adopting SpatialRuntime internals | DONE | neutral Action is canonical; declaration-only modes no longer manufacture semantic PASS |
| CF-02 | As a runtime author, I can plug my own verifier into hostile effect-evidence vectors | DONE | external adapter protocol and bundle are on main |
| CF-03 | As a consumer, I can discover available conformance modes and versions machine-readably | DONE | machine-readable catalog merged via PR #49 |
| CF-04 | As a consumer, I can copy one minimal workflow and get a safe default that cannot manufacture PASS | DONE | quickstart merged via PR #49; adapter stub defaults to UNRESOLVED |
| CF-05 | As a maintainer, I can distinguish source review from executed/reproduced evidence | DONE | `interop/external-results/registry.v0.1.json` records method, run, artifact digest, maturity, acknowledgment and adoption ceiling; CF-06 separately tracks unrelated consumption |
| CF-06 | As an unrelated project, I can pin SpatialRuntime and use it in my CI/release process | OPEN | issue #14 remains the adoption gate |
| CF-07 | As a standards/profile author, I can use SpatialRuntime hostile vectors to increase my own corpus discrimination | PARTIAL | Assay maintainer explicitly acknowledged the candidate attempt, froze the profile pending our first run, and said the Stage-3 origin/code proposal would be reviewed after that result; the 14/14 run is now complete, but substantive vector review/adoption is still pending |
| CF-08 | As an external profile author, I can run a SpatialRuntime candidate against my official scorer | DONE | Assay official scorer completed 14/14 with method `other_disclosed`; claim ceiling excludes blind independence |
| CF-09 | As an observability maintainer, I can review a precise tool-execution vs external-effect boundary upstream | DONE | OpenTelemetry maintainer `lmolkova` gave substantive `CHANGES_REQUESTED` review on #588; the proposal was narrowed in direct response at fork commit `38a2ecf7...` |
| CF-10 | As a standards community, I can reuse a SpatialRuntime reporting/provenance format | HOLD | do not invent a parallel standard; align to upstream communities |
| CF-11 | As an upstream observability project, I can accept/merge a clarified tool-result vs external-observation boundary | HOLD | OpenTelemetry #588 received two rounds of substantive maintainer review; the maintainer did not see a concrete instrumentation/telemetry-consumer use for the distinction, so the PR was closed rather than forcing execution-reconciliation semantics into the span convention |
| AD-01 | As a new visitor, I can understand within one screen what this repo is for today | DONE | root README now presents the two product lanes and current external-adoption priority |
| AD-02 | As a consumer, I know which entry point is canonical and which are compatibility aliases | DONE | `interop/conformance` is canonical and now exposes the current v0.2 binding mode; AEA path remains a compatibility surface |
| AD-03 | As a consumer, I can pin a released version/tag rather than an arbitrary commit | PARTIAL | release/tag semantics, changelog, deprecation policy and machine checks are defined; no immutable `conformance-v*` tag exists yet |
| AD-04 | As a reviewer, I can see maturity level per conformance surface | DONE | every canonical mode is mapped exactly once in the maturity registry and CI rejects drift |
| AD-05 | As a maintainer, I know when to stop expanding a profile and switch nodes | DONE | explicit stop/switch criteria now govern investment decisions |
| AD-06 | As a consumer, I can distinguish declaration validity from independently verified conformance | DONE | envelope-only modes expose `validation_result` + `assessment_scope=envelope_only` and remain conformance UNRESOLVED |
| AD-07 | As a consumer, I know neutral Action runner prerequisites before adoption | DONE | catalog + README declare bash and Python >=3.10 requirements |

## What is actually finished

The repository is already strong in:
- fail-closed runtime/session mechanics;
- deterministic replay and state continuity;
- explicit solver and hardware boundaries;
- explicit application-side dependency assembly for real solver/gateway adapters;
- evidence/authority separation;
- hostile conformance vectors;
- adapter-based verifier integration;
- decision/execution identity separation;
- explicit non-claims.

These should be preserved.

## What is overbuilt relative to external value

### 1. Multiple overlapping conformance names

Current surfaces include:
- Agent Effect Authority
- effect-evidence
- tool-decision lifecycle
- decision-execution binding
- additional standards probes

Problem:
- each is defensible individually;
- collectively they raise adoption cost and look like a private ontology.

Action:
- keep internal profile names;
- make `interop/conformance` the single public consumption surface;
- do not add another top-level public brand without unrelated consumer demand.

### 2. Analyst-authored semantic mappings

Mappings are useful evidence pressure but are not adoption.

Action:
- freeze new mapping work unless:
  1. a mapped maintainer reviews it;
  2. it changes a verifier/vector;
  3. it unlocks an upstream contribution.

### 3. Spatial runtime expansion without new real consumer

The spatial lane has enough architecture to serve as grounding.

The 2026-10-09 re-audit found two closure gaps rather than new subsystems:
- explicit application assembly — closed by PR #63;
- live session resume — closed by PR #64.

Both repository-owned closure gaps are now complete. Return to the spatial expansion freeze.

Action:
- no new large spatial subsystem until at least one trigger exists:
  - unrelated consumer integration;
  - real hardware deployment;
  - real solver deployment;
  - a concrete bug blocking AirTrajectory/HomeAI usage.

## Machine-verifiable P0 state

The repository-owned P0 closure claim is now enforced by:

- `docs/P0-CLOSURE.v0.1.json`
- `docs/verify_p0_closure.py`
- repository CI

The verifier treats P0-A/B/C/D/E as repository-owned closure gates and fails CI if their required evidence artifacts disappear.

Current machine truth:

```text
repository_p0_closed = true
external_adoption_gate = OPEN
```

The external adoption gate is not a P0 item. No amount of same-owner code, same-owner CI, analyst-authored mappings, or documentation may satisfy it.

## Repository-owned P0 closure — COMPLETE

### P0-A — Canonical external entry point

Completed via PR #49:
- `interop/conformance/action.yml`
- machine-readable manifest
- copy-paste quickstart
- external adapter command
- legacy path remains compatible

Success:
- one documented entry point for all third-party use.

### P0-B — Evidence artifact retention

Every external compatibility workflow must produce:
- implementation/version/commit;
- profile/vector version;
- run identity;
- machine-readable report;
- evidence method;
- immutable artifact reference when available.

Queued workflow is not executed evidence. OpenAdapt #38 and AgentX #39 have completed successful executed probes; Assay has a completed official scored run under `other_disclosed`.

Because GitHub Actions artifacts expire, the first three external execution reports are also retained under `interop/external-results/runs/` and bound from the registry by Git blob SHA. The original workflow run/artifact ID/digest remains recorded as execution provenance; the Git-retained JSON is the long-lived machine-readable copy.

### P0-C — Maturity matrix

Every profile must declare one of:
- experimental
- candidate
- stable
- deprecated

and independently:
- self-tested
- external-source-reviewed
- externally-executed
- externally-reproduced
- externally-consumed

These axes must not be conflated.

### External Exit Gate — First unrelated consumer

Issue #14 remains the only unrelated-adoption gate that matters. It is deliberately outside P0 because it requires an independent project to consume or falsify a canonical SpatialRuntime surface.

Do not close it for:
- our own second repository;
- our own workflow;
- analyst-authored mappings;
- upstream discussions that do not consume SpatialRuntime.

Profile-specific adoption issue #47 is closed as superseded by #14.

### P0-D — Explicit application assembly — COMPLETED

Closed by PR #63.

The runtime can now inject solver/gateway/ledger/device bindings from application code into one evidence-preserving closed loop while scenario JSON remains inert.

This closes a genuine runtime product gap without reopening arbitrary executable configuration.

### P0-E — Live RuntimeSession resume — COMPLETED

Closed by PR #64, merge commit:

`ce7cce687e623ed16f9c60db782bed05e9b117ba`

Resume requires:
- bundle/trace integrity;
- execution manifest present;
- exact entity-catalog fingerprint;
- exact safety-graph fingerprint;
- only resumable final statuses.

A hardware-incomplete resume preserves `committed_target_unconfirmed` and remains fail-closed until fresh device evidence arrives.

## P1 gaps

### P1-A — Release lifecycle — PARTIAL

Implemented:
- `interop/conformance/RELEASE-POLICY.md`
- `interop/conformance/CHANGELOG.md`
- `interop/conformance/release-contract.v0.1.json`
- `interop/conformance/verify_release_contract.py`
- deterministic `prepare_release.py`
- CI validation

Remaining external gate:
- create the first immutable `conformance-v*` Git tag/release at an exact green commit.

Until that Git ref exists, consumers must continue pinning immutable commit SHAs.

### P1-B — External-results registry — COMPLETED

Implemented:

- `interop/external-results/registry.v0.1.json`
- `interop/external-results/schema.v0.1.json`
- `interop/external-results/verify_registry.py`
- CI validation

The first registry entries freeze OpenAdapt, AgentX and Assay execution lineage including implementation/profile revision, workflow run, artifact id/digest, evidence method, observed result, acknowledgment state and adoption claim ceiling.

For externally-executed or stronger evidence, the registry also requires a repository-retained raw report whose Git blob SHA is verified in CI. This prevents a 90-day Actions artifact retention window from erasing 6–12 month evidence.

The validator rejects an `adoption_claim=true` unless evidence maturity is `externally-consumed` and unrelated project-owned consumer evidence exists.

This closes the evidence-classification user story. It does **not** close CF-06; no unrelated consumer is claimed.

### P1-C — Root README product split — COMPLETED

Root README now presents:
1. Conformance / interoperability — preferred external adoption path.
2. Executable spatial runtime — reference/grounding runtime.

The two product lanes and their separate maturity claims are explicit on the first screen.

## Stop / switch criteria

A line is downgraded when two or more apply:
- no unrelated response after two high-quality, non-spammy contacts;
- no new discriminating behavior is discovered;
- work only adds private vocabulary;
- result can only be validated by our own tests;
- upstream already owns the same concept more strongly;
- method contamination prevents the identity claim we wanted;
- next increment does not improve adoption, citation, review, or external correctness.

A line is upgraded when one or more occur:
- unrelated maintainer asks for follow-up;
- upstream merges or cites the artifact;
- unrelated implementation runs the verifier;
- a vector changes an upstream corpus/spec/test;
- an external scorer produces a durable result;
- a standards group gives a concrete contribution path.

## Strategic north star

The durable identity is not:

> creator of a large private agent framework

It is:

> maintainer/contributor of reproducible conformance evidence for consequential agent execution, grounded by real runtime and physical-system experience.

SpatialRuntime should remain the implementation home only while that structure reduces friction. If conformance adoption eventually becomes independently valuable enough, repository separation can be reconsidered based on actual consumers rather than aesthetics.


## Owned downstream grounding evidence

Machine-readable grounding evidence lives at:

`interop/owned-downstream-evidence/registry.v0.1.json`

It is intentionally separate from `interop/external-results/registry.v0.1.json`.

Owned repositories can prove real execution and reduce architecture-to-reality risk, but they do **not** satisfy the unrelated-adoption gate in issue #14.


## External-only closure gates

The stories below cannot be made DONE by adding more SpatialRuntime code.

| Story | What closes it | What does not close it |
|---|---|---|
| SR-04 | durable public real ContamX execution evidence | parser/fake executable only |
| SR-05 | real gateway/device command + ACK + authoritative convergence evidence | mock/fixture feedback |
| SR-06 | restart while a real device effect is unresolved, with durable reconciliation evidence | local session resume or deterministic journal replay without field device uncertainty |
| SR-07 | unrelated BIM/CAD/SLAM consumer of the reviewed world boundary | owned downstream repo |
| CF-06 | unrelated repo pins/consumes SpatialRuntime in its own process | stars, mentions, same-owner consumers |
| CF-07 | upstream maintainer accepts the vector/test/finding | our proposal alone |
| CF-11 | HOLD unless a future instrumentation consumer supplies a concrete use case that changes the usefulness test | another wording-only attempt |
| AD-03 | real immutable `conformance-v*` tag/release | policy/docs/branch names |

Internal work on these stories is limited to making the external experiment reproducible, preserving evidence, fixing discovered bugs, and reducing integration friction.


## 2026-10-09 OpenTelemetry scope result

OpenTelemetry GenAI PR #588 is a useful negative result rather than an adoption failure to hide.

The maintainer review established a boundary:

- `gen_ai.tool.call.result` plus existing error/span-status semantics already cover the instrumented tool call;
- the proposed distinction about authoritative external-effect confirmation did not give instrumentation authors or telemetry consumers a concrete additional action;
- after two review rounds, the PR was closed instead of adding execution-reconciliation terminology to an observability convention.

Implication:

> External-effect truth, reconciliation, and ambiguous-outcome handling remain a runtime/execution-evidence concern unless a future observability use case demonstrates a capturable signal and a concrete telemetry-consumer action.

Do not reopen this OpenTelemetry line for wording alone.
