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

4. **AD-03 immutable conformance release tag**
   - reduces adoption friction;
   - useful only after an exact green commit is selected;
   - does not count as external adoption.

Switch away from any line when two high-quality external attempts produce no maintainer response, consumer run, counterexample, citation, or upstream path.


## 1. Stop creating new public profile brands

Until AD-03 and CF-06 are closed:
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

## 6. Adoption close condition

The project enters the next identity tier only when issue #14 is satisfied by an unrelated repository.

Until then, stars, self-consumption and our own cross-repo use are supporting signals, not the goal.


## 7. Release discipline

AD-03 remains PARTIAL until a real immutable `conformance-v*` tag exists.

Before creating a tag:
1. repository CI is green;
2. `verify_catalog.py` passes;
3. `verify_registry.py` passes;
4. `verify_release_contract.py` passes;
5. generate the release manifest with `prepare_release.py` for the exact commit;
6. review `CHANGELOG.md`;
7. create the immutable tag/release.

A branch name or package version is not a conformance release.


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
