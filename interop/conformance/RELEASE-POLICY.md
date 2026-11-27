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

Consumers SHOULD pin an immutable conformance tag for released snapshots. Use an exact commit SHA only for evidence that predates a release or intentionally targets another historical revision. Pinning `main` is not reproducible evidence.

## Current state

The first release is published:

- tag: `conformance-v0.1.0`
- commit: `6d8e0d4a5c9c665e10dad853ab6aadc280db6b55`
- release page: `SpatialRuntime Conformance v0.1.0`
- release asset: `conformance-release.json`
- release workflow run: `37878503867`

The annotated tag contains the exact release manifest. The public Release page carries the same manifest as an asset. This closes AD-03 at the distribution/pinning layer; it does not promote profile semantic maturity or prove unrelated adoption.

## Next candidate (not yet published)

The additive public Action gate/receipt features and correctness hardening since the first release are documented under `CHANGELOG.md#unreleased` as a potential `conformance-v0.2.0` MINOR release. A green main branch or changelog entry does **not** create a release. Any published tag needs a new immutable release target, a generated manifest from that **exact** target and the required release checks. Until publication, consumers needing the new strict gate and durable binding receipts must use the already verified immutable commit `76407b7a29e552dd4d5d2ede8c29b6065d4fb0d1` rather than the older `conformance-v0.1.0` tag.

## Read-only v0.2.0 candidate evidence (automatic after green main CI or manual)

The [conformance-v02-candidate workflow](../../.github/workflows/conformance-v02-candidate.yml) is a **read-only, non-publishing** release-readiness check. It records a candidate automatically after a successful **push-triggered CI on this repository's `main`** (never on an untrusted PR), and also permits explicit manual dispatch on `main`. It binds its checkout to the precise successful CI's `head_sha`, rechecks the current branch head and that successful push CI, rejects an existing `conformance-v0.2.0` tag, reruns the catalog, registry, maturity, P0 and release-contract validators, and uploads a manifest + SHA-256 digest + `STATUS=UNPUBLISHED_CANDIDATE`.

A successful candidate run **is not** a published Git tag, an immutable GitHub Release, a signature, independent conformance certification or unrelated adoption. Its Actions artifact is retention-limited. Publishing a later approved release requires a **separate** explicitly authorized tagging/publishing operation against exactly the validated commit, with independent checks of the tag target and released asset. The current ChatGPT GitHub integration does not expose a tag or GitHub Release creation operation. If `main` changes between the candidate run and publication, generate and validate a new candidate rather than reusing the stale one.
