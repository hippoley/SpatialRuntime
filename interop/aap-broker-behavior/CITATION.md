# Citation and adoption note — AAP broker behavior v0.1

Profile: `aap-broker-behavior.v0.1`

SpatialRuntime integration commit:

`8258dff69de5ad22f16d9af713f53d7411ca1a1c`

This profile is an **independent experimental conformance probe**, not an official OpenA2A or IETF conformance suite.

## What can be cited

The stable claim of v0.1 is:

> A broker implementation can expose implementation-specific behavior through a small adapter, while the independent harness evaluates a shared set of AAP Broker Profile Level-1 runtime invariants.

The current invariant subset covers:

- default-deny;
- same opaque agent-visible denial across multiple failure classes;
- no credential/backend/provider canary material in the agent-visible response;
- denied operations do not execute;
- successful operations return the operation result;
- audit evidence is present, credential-free, and independently verified as signed.

## Pinned upstream evidence used for v0.1

AAP specification source originally inspected:

`opena2a-standards/agent-authorization-protocol@fb66195a9c2a4a40f91595da14673d11bb8c01e7`

Secretless reference implementation source inspected for the signed-audit finding:

`opena2a-org/secretless-ai@93cce83eefedb9a889b31bf4ffd6055a68dcee83`

AIM latest security-status cross-check used to validate the family-level mismatch:

`opena2a-org/agent-identity-management@3a66faab4b9953521f840a84caa8fb0bd048176a`

At that AIM revision, `SECURITY.md` still states that `audit_logs` is not append-only at the database layer and is not cryptographically signed.

## Adoption boundary

A new broker does **not** import SpatialRuntime runtime code.

It provides an adapter that accepts the profile scenario envelope and emits the normalized observation envelope defined by:

`adapter-protocol.v0.1.json`

The harness then decides PASS/FAIL.

This separation is intentional: the reusable asset is the behavioral conformance boundary, not a dependency on one broker implementation or one model stack.

## Evidence maturity

Current state:

- executable profile: yes;
- positive self-test adapter: yes;
- hostile negative controls: yes;
- CI: yes;
- public repository: yes;
- independent external broker adapter: **not yet**;
- third-party maintainer acceptance/adoption: **not yet**.

The last two items are the threshold for upgrading this from an independent probe to externally demonstrated interoperability evidence.
