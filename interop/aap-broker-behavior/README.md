# Independent AAP broker-behavior conformance probe

This directory is an **independent experimental harness** for a behavioral subset of OpenA2A Agent Authorization Protocol (AAP) Broker Profile Level 1.

It is not an OpenA2A project, not an IETF conformance claim, and not a replacement for `opena2a-standards/aap-conformance`.

## Why this exists

The official `aap-conformance` suite explicitly covers token canonical form and verifier behavior and explicitly lists broker-profile runtime behavior as **not covered**.

AAP Broker Profile Level 1 includes runtime properties such as:

- default-deny;
- context hygiene;
- opaque denials;
- ephemeral-worker credential confinement;
- signed audit;
- returning only the operation result to the agent.

Those are behavioral properties, not token-byte properties.

## Pinned upstream source

- `opena2a-standards/agent-authorization-protocol@fb66195a9c2a4a40f91595da14673d11bb8c01e7`
- `AAP-BROKER-PROFILE.md`
- broker profile `0.4.1-draft`

## Adapter boundary

A broker implementation stays independent. The harness sends one JSON scenario on stdin and expects one normalized observation on stdout.

The adapter drives the implementation under test. The harness decides PASS/FAIL.

## Current vectors

- unknown grant → opaque deny, no execution;
- policy deny → the same agent-visible opaque deny;
- provider failure → the same agent-visible opaque deny;
- success → operation result only, with no canary credential/backend/provider material visible to the agent.

Every path also requires signed broker-side audit evidence without credential material.

## Run

```bash
python interop/aap-broker-behavior/run_conformance.py \
  --adapter-command "python interop/aap-broker-behavior/examples/reference_adapter.py"
```

The reference adapter is only a deterministic harness self-test. It is **not** an AAP broker implementation.

## Strategic boundary

This work deliberately complements, rather than duplicates, the official token conformance suite:

```text
AAP token conformance
        +
broker behavioral conformance
        ↓
decision → enforcement → execution evidence
```

That boundary remains useful even if AAP evolves, because the adapter-based harness can be mapped to another authorization protocol without requiring the implementation to import SpatialRuntime.


## Audit integrity evidence boundary

The harness does not standardize AAP's audit-signature wire format.

A broker adapter is responsible for **independently verifying** its implementation-specific audit integrity mechanism and returning structured evidence:

```json
{
  "integrity_evidence": {
    "kind": "signature",
    "verified": true,
    "key_id": "implementation-specific-key-id",
    "record_digest": "sha256:<digest of the verified record>"
  }
}
```

A bare `"signed": true` assertion is rejected.

For this profile's literal Level-1 **signed audit** requirement:

- `kind=signature` is required;
- `verified=true` is required;
- a non-empty key id is required;
- the verification must be bound to a concrete record digest.

A hash chain may establish tamper evidence, but this experimental profile does not silently reinterpret “signed audit” as “hash-chained audit”.

The deterministic reference adapter uses synthetic integrity evidence only to self-test the harness wiring. It is not evidence about a real broker.
