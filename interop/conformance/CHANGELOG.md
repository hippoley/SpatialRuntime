# Conformance changelog

This changelog tracks the public `interop/conformance` contract independently from the Python package version.

## Unreleased

### Correctness

- Envelope-only `claim`, `mapping`, and `mapping-v0.2` modes no longer promote declaration validity to conformance `PASS`.
- Those modes expose `validation_result` and `assessment_scope=envelope_only`, while conformance remains `UNRESOLVED` unless truth is independently established.
- The machine-readable catalog is checked against the canonical Action and maturity registry.

### Adoption contract

- Runner prerequisites are declared machine-readably.
- A release policy is now part of the canonical catalog.
- No immutable conformance release tag has been published yet.

The first release should be cut only after these correctness changes are merged and CI is green.
