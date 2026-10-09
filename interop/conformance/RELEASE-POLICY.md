# Conformance Release Lifecycle

SpatialRuntime conformance is consumed by CI and evidence workflows, so release semantics must be stricter than package marketing versions.

## Tag namespace

Stable conformance releases use:

```text
conformance-vMAJOR.MINOR.PATCH
```

Examples:

- `conformance-v0.1.0`
- `conformance-v0.1.1`
- `conformance-v1.0.0`

The Python package version is a separate product lane and does not define the conformance contract version.

## Compatibility rules

- **PATCH**: bug fix or verifier hardening that does not intentionally change a previously valid evidence envelope into a different semantic class except to fix an explicitly documented correctness defect.
- **MINOR**: additive mode/profile/input/output capability; existing pinned modes remain usable.
- **MAJOR**: intentional breaking change to a public mode, result semantics, required evidence, or Action input/output contract.

Profiles keep their own version identifiers. A release tag is a distribution snapshot that pins a compatible set of profiles and the neutral Action.

## Stable-release requirements

A conformance release may be tagged only when:

1. `interop/conformance/verify_catalog.py` passes;
2. the external-results registry validator passes;
3. repository CI is green on supported Python versions;
4. every included public mode appears in the machine-readable catalog;
5. PASS / UNRESOLVED / FAIL semantics are unchanged or migration notes are provided;
6. compatibility aliases retained by the release are listed;
7. the release manifest records the exact Git commit;
8. any semantic maturity claim is supported by `interop/conformance-maturity.v0.1.json`.

A profile may remain `experimental` inside a release. Release packaging does not promote semantic maturity.

## Deprecation

A public mode is never silently removed.

For a deprecated mode:

1. mark it `deprecated` in maturity metadata;
2. add migration guidance to `CHANGELOG.md`;
3. keep the compatibility path for at least one MINOR release after the deprecation notice;
4. remove only in the next MAJOR release or later.

Security/correctness exceptions may fail closed immediately, but the changelog must identify the previous unsafe behavior and the replacement path.

## Pinning

Consumers SHOULD pin an immutable conformance tag after the first release exists.

Until then, consumers MUST pin an immutable commit SHA. Pinning `main` is not reproducible evidence.

## Current state

The lifecycle contract is defined, but no immutable conformance tag has been created yet.

Therefore AD-03 remains **PARTIAL**, not DONE.
