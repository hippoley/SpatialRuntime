# Conformance Changelog

This changelog tracks the public `interop/conformance` consumption surface, not the Python package as a whole.

## Unreleased — candidate scope for conformance-v0.2.0 (NOT TAGGED OR PUBLISHED)

The next MINOR release candidate includes the following already merged functionality. This changelog is **release preparation**, not a new Git tag, GitHub Release, or external adoption claim.

### Added

- Opt-in `require_result: PASS` Action input for blocking release gates, while retaining the previous nonblocking UNRESOLVED observation default (PR #91).
- Durable full JSON `report_path` for `decision-execution-binding` v0.1/v0.2, including UNRESOLVED and FAIL findings; real Composite Action uploads and tests (PR #98).
- First-screen, copyable current Action CI example with immutable SHA and unconditional artifact retention (PR #100).

### Correctness and security fixes

- Strict release gates reject `effect-evidence-bundle` reference-only smoke PASS without a caller-owned adapter (PR #93).
- External adoption claims no longer close from self-authored registry fields alone: require unrelated repository run, pinned workflow and actual successful Action step (PRs #90, #95).
- Reject `uses:` strings fabricated inside `run: |` or other workflow block scalar text (PR #97).
- Persist ARIB real-SDK cross-version and Kiri SQLite evidence with Git blob digests (PR #89).

### Compatibility and assurance limits

- Existing profile mode identifiers remain unchanged; historical `conformance-v0.1.0` stays pinned as published.
- `interop/agent-effect-authority` remains a compatibility entrypoint.
- Correctness-hardening may reject previously unsafe self-attested adoption claims; this is intentional and documented.
- `PASS` is an assessment of supplied records, **not** producer authentication, independent physical effect confirmation, or proof of external adoption.
- **Release blocker:** publish a `conformance-v0.2.0` tag and manifest only after validating catalog, registry, maturity, supported Python CI, versioned CHANGELOG and current immutable release SHA. No tag is created by this changelog edit.


## conformance-v0.1.0 — 2026-10-09

First immutable distribution snapshot of the neutral conformance Action/catalog.

### Added

- neutral `interop/conformance` Action entry point;
- machine-readable conformance catalog;
- effect-evidence external-adapter bundle;
- structured PASS / UNRESOLVED / FAIL outputs;
- durable report path support;
- decision/execution binding profiles;
- tool-decision lifecycle correlation;
- external-results evidence registry and evidence-maturity discipline;
- machine-verified repository P0 closure;
- release manifest generation and green-main release gate.

### Compatibility

- `interop/agent-effect-authority` remains a compatibility Action path.
- Existing profile identifiers remain versioned independently from the release tag.
- Distribution release does not promote experimental profile semantics.
- Unrelated external adoption remains tracked separately by CF-06 / issue #14.

### Release evidence

- tag: `conformance-v0.1.0`
- release commit: `6d8e0d4a5c9c665e10dad853ab6aadc280db6b55`
- release workflow run: `37878503867`
- release manifest asset digest: `sha256:a567aa55052c055a174891037d65c5d72a09dea2ece2fc9e963b0675397994dc`
