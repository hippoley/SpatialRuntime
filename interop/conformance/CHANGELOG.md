# Conformance Changelog

This changelog tracks the public `interop/conformance` consumption surface, not the Python package as a whole.

## Unreleased

### Added

- neutral `interop/conformance` Action entry point;
- machine-readable conformance catalog;
- effect-evidence external-adapter bundle;
- structured PASS / UNRESOLVED / FAIL outputs;
- durable report path support;
- decision/execution binding profiles;
- tool-decision lifecycle correlation;
- external-results evidence registry and evidence-maturity discipline.

### Compatibility

- `interop/agent-effect-authority` remains a compatibility Action path.
- Existing profile identifiers remain versioned independently from the future release tag.

### Release blocker

No immutable `conformance-v*` tag exists yet.

The first tag must follow `RELEASE-POLICY.md` and pin an exact Git commit after CI and release-manifest verification pass.
