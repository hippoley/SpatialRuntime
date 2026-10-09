# Conformance Changelog

This changelog tracks the public `interop/conformance` consumption surface, not the Python package as a whole.

## Unreleased

No public conformance-surface changes yet.

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
