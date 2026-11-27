# Conformance Changelog

This changelog tracks the public `interop/conformance` consumption surface, not the Python package as a whole.

## Unreleased

No new public conformance contract changes since the v0.2.0 release. New changes must be recorded here before the next version is published.

## conformance-v0.2.0 — 2026-11-27 (PUBLISHED)

This MINOR release was published as an [annotated Git tag and public GitHub Release](https://github.com/hippoley/SpatialRuntime/releases/tag/conformance-v0.2.0) at immutable source commit `8668ba93ad689fea5957de46d98cd138d8ac7865`. The published `conformance-release.json` asset has SHA-256 `25ed96cb44c66d2d62f3372ac663ffd3e6d3f41fb21a4024e31f169eac047e13`. [Explicit owner-authorized publication](https://github.com/hippoley/SpatialRuntime/actions/runs/45967018782) and a [real published-tag three-state consumer test](https://github.com/hippoley/SpatialRuntime/actions/runs/45967304233) succeeded. These are owner-controlled runs, not evidence of an unrelated adopter.

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
- **Post-release status:** the immutable annotated tag, public manifest asset and digest have been checked. The published Action independently passed a self-owned three-state consumer test. Unrelated third-party adoption remains open in Issue #14; release packaging does not certify external physical effects.


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
