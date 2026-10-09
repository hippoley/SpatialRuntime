# Action Guide — Close the Adoption Funnel

This file is execution order, not a backlog.

## 0. Re-audit decision — internal runtime closure is complete

The 2026-10-09 end-to-end re-audit found two repository-owned runtime closure gaps and both are now closed:

- PR #63: explicit application assembly for injected solver/gateway dependencies;
- PR #64: live RuntimeSession resume from validated episode bundles.

Do **not** treat this as permission to restart spatial architecture expansion.

The spatial lane now returns to maintenance/grounding mode.

Current investment order:

1. **CF-06 unrelated consumer / falsification contribution**
   - highest identity transition;
   - closes the gap between “we built a verifier” and “another project depends on the boundary”.

2. **SR-05/SR-06 real device convergence + unresolved-effect restart evidence**
   - highest reality grounding if physical access exists;
   - one measured window/device movement with ACK + authoritative feedback + restart/reconcile evidence is worth more than another internal profile.

3. **SR-04 durable real ContamX evidence**
   - owned downstream AirTrajectory already supplies real Windows/ContamX grounding;
   - improve retention/public reproducibility only when it adds evidence quality, not architecture.

4. **CF-07 upstream vector/corpus acceptance**
   - Assay Stage-3 is already scoped to a measured discrimination gap;
   - advance only on maintainer review/adoption, not by adding private variants.

Switch away from any line when two high-quality external attempts produce no maintainer response, consumer run, counterexample, citation, or upstream path.


## 0.5 Two-layer closure gate

Every User Story now has two acceptance layers:

1. longitudinal requirement closure in `PRODUCT-BOUNDARY-AUDIT.md`;
2. horizontal system closure in `horizontal-completeness.v0.1.json`.

Do not call a story **Verified Closed** unless both layers pass.

Before adding code to a PARTIAL/OPEN story, classify the blocker as repository-owned, field, unrelated-external, or upstream-governance. Field/external/upstream gates do not become internal feature work merely because they remain open.

The P0 verifier executes the horizontal adversarial acceptance checks through P0-F.

## 1. Stop creating new public profile brands

Until CF-06 is closed:
- new adversarial cases may extend existing profiles;
- external standards probes are allowed when they target a measured external gap;
- no new top-level public conformance vocabulary.

## 2. One external entry point is canonical — COMPLETED

Merged via PR #49:

- neutral `interop/conformance` Action path;
- machine-readable manifest;
- safe copy-paste example;
- external adapter mode;
- structured outputs;
- README points to the neutral path first.

Do not reopen this design unless an unrelated consumer demonstrates a concrete incompatibility.

## 3. Preserve external-result evidence

Canonical registry:

`interop/external-results/registry.v0.1.json`

For each external probe:
- keep the first run;
- never rewrite a mismatch out of history;
- record source commit and profile commit;
- record workflow run + artifact id + digest;
- distinguish queued, executed, reproduced, consumed, and acknowledged evidence;
- never set `adoption_claim=true` without unrelated project-owned consumption evidence.

CI runs `interop/external-results/verify_registry.py`.

## 4. Drive only demand-side external work

Priority order:
1. explicit upstream corpus/spec gap;
2. maintainer-requested test/reproduction;
3. external runtime with missing conformance coverage;
4. standards discussion with a concrete artifact slot;
5. analyst-only mapping work.

## 5. Freeze spatial expansion

Spatial runtime receives only:
- bug fixes;
- regression tests;
- integration work required by a real downstream;
- real ContamX/hardware evidence when available.

The explicit application assembly and live-session resume closure work is complete. No further repository-owned spatial P0 remains from the 2026-10-09 re-audit.

No architecture expansion for hypothetical future scene sources.

## 6. Repository P0 is machine-closed; adoption is an external exit gate

`docs/verify_p0_closure.py` enforces that every repository-owned P0 remains backed by its evidence artifacts in CI. The project enters the next identity tier only when issue #14 is satisfied by an unrelated repository.

Until then, stars, self-consumption and our own cross-repo use are supporting signals, not the goal.

Do not relabel CF-06 as unfinished P0. The repository cannot honestly self-manufacture an unrelated consumer.


## 7. Release discipline — first release completed

`conformance-v0.1.0` is published at green commit `6d8e0d4a5c9c665e10dad853ab6aadc280db6b55`, with an annotated-tag manifest and a GitHub Release asset.

For future releases, keep the same gate:
1. repository CI green;
2. catalog / external-results / release-contract / P0 validators green;
3. release manifest generated for the exact target commit;
4. tag never moved after publication;
5. compatibility/migration notes updated before any semantic change.

Release packaging remains separate from semantic maturity and unrelated adoption.


## 7.5 No synthetic P2 feature backlog

After the first released consumption boundary, the repository does not create a P2 feature queue merely from PARTIAL user-story labels.

Residual gates are handled by their evidence owner:

- field hardware gates wait for real device movement/restart evidence;
- unrelated-adoption gates wait for unrelated project-owned use or falsification;
- upstream gates wait for maintainer review/corpus/spec/test changes;
- owned-downstream grounding is preserved without duplicating the same integration in this repository.

P2 work is allowed only when it increases credential integrity or removes demonstrated consumer friction without changing the claim ceiling. Release-manifest attestation is an example of valid P2 hardening; another private conformance vocabulary is not.

## 8. Do not compete with generic protocol formalization

Adjacent work has already established a strong spec-to-formal-analysis lane:

- AgentRFC / AgentConform (arXiv:2603.23801): normative-clause extraction, typed Protocol IR, TLA+ compilation/model checking, and counterexample replay against live SDKs;
- AgentThread (arXiv:2606.28690): source-linked protocol/responsibility analysis across multiple protocols and composed deployments.

SpatialRuntime should **not** build a parallel generic Protocol IR, TLA+ compiler, or broad protocol-security taxonomy unless an external consumer explicitly requires integration with those artifacts.

Our differentiating layer is narrower and closer to consequential execution:

- logical effect identity across retries/replay;
- decision/authorization versus execution binding;
- ambiguous external outcomes as first-class state;
- authoritative readback/effect evidence;
- physical and other external side effects;
- durable evidence lineage and reproducible hostile vectors;
- cross-runtime consumer-facing CI that preserves claim ceilings.

Use formal-protocol projects as upstream/adjacent sources of counterexamples and responsibility boundaries; contribute executable reality evidence where it is missing rather than cloning their formal-analysis stack.

### Current external node

ANP's protocol repository already publishes ANP-02 scenario vectors whose status is explicitly design-only and asks SDK/product runners to retain actual execution evidence separately. Issue #105 proposes the first bounded Python SDK runner over that canonical corpus.

Investment rule for this node:
- wait for ANP maintainer direction before writing implementation code;
- if accepted, contribute the smallest runner/report contract that consumes their vectors;
- do not introduce SpatialRuntime vocabulary into ANP;
- do not call illustrative implementation-policy scenarios protocol conformance;
- stop if maintainers prefer another testing path or if an equivalent runner lands first.


## 9. Closed node: OpenTelemetry execute_tool clarification

OpenTelemetry GenAI PR #588 received two rounds of substantive maintainer review and was closed after the maintainer still did not see a concrete instrumentation-author or telemetry-consumer use for the external-effect-confirmation distinction.

Treat this as a scope result:

- do not reopen with different wording;
- do not add OTel-specific fields or semantics in SpatialRuntime;
- keep effect truth / reconciliation in the runtime-evidence layer;
- only re-enter observability work if a future concrete consumer can name both:
  1. a signal the instrumentation can actually capture, and
  2. an action a telemetry consumer would take from that signal.

Current external attention moves to:
1. ANP #105 — SDK execution of existing scenario vectors, if maintainers accept the contribution direction;
2. Assay Stage-3 vector review/adoption;
3. CF-06 — unrelated consumption/falsification of the neutral conformance surface.
