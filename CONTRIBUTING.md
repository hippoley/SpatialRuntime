# Contributing to SpatialRuntime

SpatialRuntime is most useful when contributions reduce uncertainty about consequential agent execution across real runtimes.

The highest-value contributions are not new private vocabulary. They are reproducible evidence that makes an existing boundary easier to compare, falsify, or consume.

## High-value contribution shapes

1. **Counterexample / falsification vector**
   - show a real runtime, protocol, or trace shape that an existing verifier misclassifies;
   - pin the external source revision;
   - include the smallest reproducible input that demonstrates the disagreement.

2. **External consumer integration**
   - pin `interop/conformance` by immutable SpatialRuntime commit or release;
   - run it against implementation-owned evidence;
   - preserve the first machine-readable result, including FAIL or UNRESOLVED.

3. **Official scorer / corpus result**
   - disclose method and authorship;
   - preserve failed harness runs as well as successful runs;
   - state the narrowest claim the scorer actually establishes.

4. **Adapter to an unrelated runtime**
   - keep production internals outside SpatialRuntime;
   - normalize only the evidence needed by an existing profile;
   - do not manufacture missing identity, provenance, or effect confirmation.

5. **Runtime correctness bug**
   - especially lost-ACK, ambiguous retry, decision/execution identity collapse, stale evidence, or reconciliation failures.

## Evidence requirements

A strong contribution normally includes:

- repository + immutable revision for every external source;
- exact profile/mode/version under test;
- first observed result, not only the final green result;
- machine-readable fixture/report where practical;
- explicit non-claims;
- whether AI assistance was used when it materially shaped the artifact.

A source project being discussed or mapped does **not** imply that it adopted, endorsed, or violated SpatialRuntime.

## What usually should not become a new profile

Please do not start with a new top-level profile name if the same evidence can:

- extend an existing hostile-vector corpus;
- expose a missing result state;
- refine a binding rule;
- add a new adapter;
- or demonstrate an incompatibility against an existing surface.

New public profile brands should be demand-driven by an external interoperability need.

## Public entry point

The canonical external surface is:

`interop/conformance`

The legacy `interop/agent-effect-authority` Action remains a compatibility path.

See:
- `interop/conformance/README.md`
- `interop/conformance/manifest.v0.1.json`
- `interop/conformance-maturity.v0.1.json`
- `interop/external-results/registry.v0.1.json`

## Result discipline

A process exit of zero is not automatically semantic conformance.

In particular, declaration/envelope validation must not be presented as independent verification of evidence truth. Preserve PASS / UNRESOLVED / FAIL and the profile's claim ceiling exactly as produced.

## Pull requests

Keep changes narrow enough that the evidence delta is reviewable. If a contribution changes a verifier because of an external counterexample, include the counterexample as a pinned regression fixture whenever licensing and size permit.

The preferred outcome is not “more code.” It is a smaller gap between what the repository claims and what an unrelated implementation can actually demonstrate.
