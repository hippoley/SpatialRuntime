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
