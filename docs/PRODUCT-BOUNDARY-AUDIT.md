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
| SR-04 | As a CONTAM user, I can prove a real ContamX solve in repository CI | OPEN | CI explicitly uses fake executable; no real ContamX claim |
| SR-05 | As a hardware user, I can dispatch through a real gateway/device fleet and prove physical convergence | PARTIAL | gateway/ledger contracts exist; repository examples remain fixture/mock-oriented |
| SR-06 | As an operator, I can prove durable restart/recovery behavior against real device-side uncertainty | PARTIAL | durable ledger/reconciliation logic exists; no unrelated production deployment evidence |
| SR-07 | As a scene-source consumer, I can use the same reviewed world model from an unrelated BIM/CAD/SLAM integration | OPEN | architecture supports adapters, but no unrelated scene-source integration is recorded |
| CF-01 | As a runtime author, I can run stable conformance checks without adopting SpatialRuntime internals | DONE | neutral `interop/conformance` Action merged via PR #49; legacy AEA path retained for compatibility |
| CF-02 | As a runtime author, I can plug my own verifier into hostile effect-evidence vectors | DONE | external adapter protocol and bundle are on main |
| CF-03 | As a consumer, I can discover available conformance modes and versions machine-readably | DONE | machine-readable catalog merged via PR #49 |
| CF-04 | As a consumer, I can copy one minimal workflow and get a safe default that cannot manufacture PASS | DONE | quickstart merged via PR #49; adapter stub defaults to UNRESOLVED |
| CF-05 | As a maintainer, I can distinguish source review from executed/reproduced evidence | DONE | `interop/external-results/registry.v0.1.json` records method, run, artifact digest, maturity, acknowledgment and adoption ceiling; CF-06 separately tracks unrelated consumption |
| CF-06 | As an unrelated project, I can pin SpatialRuntime and use it in my CI/release process | OPEN | issue #14 remains the adoption gate |
| CF-07 | As a standards/profile author, I can use SpatialRuntime hostile vectors to increase my own corpus discrimination | PARTIAL | Assay Stage-3 proposal published; not yet adopted upstream |
| CF-08 | As an external profile author, I can run a SpatialRuntime candidate against my official scorer | DONE | Assay official scorer completed 14/14 with method `other_disclosed`; claim ceiling excludes blind independence |
| CF-09 | As an observability maintainer, I can review a precise tool-execution vs external-effect boundary upstream | PARTIAL | OpenTelemetry #588 open; no human review yet |
| CF-10 | As a standards community, I can reuse a SpatialRuntime reporting/provenance format | HOLD | do not invent a parallel standard; align to upstream communities |
| AD-01 | As a new visitor, I can understand within one screen what this repo is for today | DONE | root README now presents the two product lanes and current external-adoption priority |
| AD-02 | As a consumer, I know which entry point is canonical and which are compatibility aliases | DONE | `interop/conformance` is canonical and now exposes the current v0.2 binding mode; AEA path remains a compatibility surface |
| AD-03 | As a consumer, I can pin a released version/tag rather than an arbitrary commit | PARTIAL | release/tag semantics, changelog, deprecation policy and machine checks are defined; no immutable `conformance-v*` tag exists yet |
| AD-04 | As a reviewer, I can see maturity level per conformance surface | DONE | `interop/conformance-maturity.v0.1.json` added by this audit |
| AD-05 | As a maintainer, I know when to stop expanding a profile and switch nodes | DONE | explicit stop/switch criteria now govern investment decisions |

## What is actually finished

The repository is already strong in:
- fail-closed runtime/session mechanics;
- deterministic replay and state continuity;
- explicit solver and hardware boundaries;
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

Action:
- no new large spatial subsystem until at least one trigger exists:
  - unrelated consumer integration;
  - real hardware deployment;
  - real solver deployment;
  - a concrete bug blocking AirTrajectory/HomeAI usage.

## P0 gaps to close before adding new profiles

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

### P0-D — First unrelated consumer

Issue #14 remains the only adoption gate that matters.

Do not close it for:
- our own second repository;
- our own workflow;
- analyst-authored mappings;
- upstream discussions that do not consume SpatialRuntime.

## P1 gaps

### P1-A — Release lifecycle — PARTIAL

Implemented:

- `interop/conformance/RELEASE-POLICY.md`
- `interop/conformance/CHANGELOG.md`
- `interop/conformance/release-contract.v0.1.json`
- `interop/conformance/verify_release_contract.py`
- CI validation

Defined:

- `conformance-vMAJOR.MINOR.PATCH` tag namespace;
- PATCH / MINOR / MAJOR compatibility rules;
- required release checks;
- deprecation window and migration rules;
- separation between package version, profile version and conformance release version.

Remaining tooling/external gate:

- create the first immutable `conformance-v*` Git tag/release.

Until that tag exists, consumers must continue pinning immutable commit SHAs.

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


## External-only closure gates

The stories below cannot be made DONE by adding more SpatialRuntime code. Closing them requires evidence from a system outside the repository or an immutable external repository operation.

| Story | What closes it | What does **not** close it |
|---|---|---|
| SR-04 real ContamX | CI or a durable public run executes a real compatible ContamX binary and preserves solver/result evidence | fake executable, parser tests, command-shape tests |
| SR-05 real hardware convergence | a real gateway/device run preserves command id, ACK, authoritative state feedback and convergence evidence | MockGateway, DeterministicGatewayFixture, synthetic state feedback |
| SR-06 restart under real uncertainty | process restart occurs while a real device effect is unresolved and recovery/reconciliation evidence survives | replaying only deterministic journal fixtures |
| SR-07 unrelated scene source | a BIM/CAD/SLAM integration not maintained by hippoley consumes the reviewed world/spatial compile boundary | another hippoley repository or hand-authored fixture |
| CF-06 unrelated consumer | an unrelated repository pins the Action/verifier/profile in its own CI, release, evidence or review flow | stars, mentions, our own downstream repos |
| CF-07 upstream corpus adoption | an upstream profile/corpus maintainer accepts a vector/test/finding into their project | our own proposal branch or analyst mapping |
| CF-09 observability review | an upstream observability maintainer provides substantive review/merge/citation of the boundary | comments authored only by hippoley |
| AD-03 immutable release | a real `conformance-v*` tag/release is created at an exact commit | release policy alone, mutable branch names |

### Internal closure rule

For these stories, SpatialRuntime work is limited to:
- making the external experiment reproducible;
- preserving evidence;
- fixing bugs exposed by the experiment;
- reducing integration friction.

Do **not** add architecture solely to make the status table look more complete.
