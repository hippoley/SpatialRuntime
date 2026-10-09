# Conformance release policy

SpatialRuntime's neutral `interop/conformance` surface is intended to become a dependency boundary, so release semantics must be explicit before unrelated consumers rely on it.

## Current state

There is **no published conformance release yet**. Until one exists, consumers must pin an immutable commit SHA. Do not use `main` for historical evidence.

The first release must happen only after the public result semantics and catalog contract are internally consistent and CI-backed.

## Tag format

`conformance-vMAJOR.MINOR.PATCH`

Tags are immutable.

## Compatibility

- **PATCH** — no intentional semantic change to existing modes or documented result meanings. A patch may tighten a false-positive behavior when the old behavior contradicted the documented claim ceiling.
- **MINOR** — additive modes, outputs, vectors, or profile versions. Existing documented modes remain available.
- **MAJOR** — breaking mode removal, incompatible input/output changes, or intentional result-semantic changes.

## Deprecation

A deprecated mode stays in the machine-readable catalog with migration guidance for at least one published minor release before removal.

## Pinning

For normal CI, prefer an immutable conformance release tag once releases exist. For strongest historical reproducibility, pin the exact commit SHA.

Never use a moving branch such as `main` as the evidence identity for a historical conformance result.

Machine-readable form: `release-policy.v0.1.json`.
