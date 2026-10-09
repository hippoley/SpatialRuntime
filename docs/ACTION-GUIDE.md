# Action Guide — Close the Adoption Funnel

This file is execution order, not a backlog.

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

No architecture expansion for hypothetical future scene sources.

## 6. Adoption close condition

The project enters the next identity tier only when issue #14 is satisfied by an unrelated repository.

Until then, stars, self-consumption and our own cross-repo use are supporting signals, not the goal.


## 7. Truth-preserving result semantics

Do not translate a successful parser/envelope check into a stronger conformance claim.

For envelope-only modes:
- declaration valid -> `validation_result=PASS`;
- assurance scope -> `assessment_scope=envelope_only`;
- evidence/semantic truth not independently established -> `conformance_result=UNRESOLVED`.

A green process exit is transport/execution success, not automatically semantic PASS.

## 8. Release only after contract truth is stable

The conformance release policy is machine-readable at:
`interop/conformance/release-policy.v0.1.json`.

Before the first immutable `conformance-vMAJOR.MINOR.PATCH` tag:
- canonical Action/catalog/maturity validators must pass;
- envelope-only modes must retain their non-PASS claim ceiling;
- CHANGELOG must describe any result-semantic correction;
- no release may point at a commit whose public contract is known to be misleading.

Until then, consumers pin immutable commit SHAs.

## 9. External-dependent user stories are gates, not fake backlog completion

The following cannot be self-declared DONE:
- SR-04 real ContamX execution;
- SR-05 real gateway/device convergence;
- SR-06 production restart/reconciliation evidence;
- SR-07 unrelated scene-source integration;
- CF-06 unrelated conformance consumption;
- CF-07 upstream vector/corpus adoption;
- CF-09 upstream observability review/acceptance.

For these stories, the repository may improve adapters, evidence capture, or reproducibility, but status changes only when the named external condition actually occurs.
