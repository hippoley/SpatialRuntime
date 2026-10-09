# Finding: AAP Level 1 requires signed audit, but Secretless current audit path is unsigned

Status: external pressure finding, not an upstream bug report yet.

## Pinned evidence

Reference implementation:

- repository: `opena2a-org/secretless-ai`
- revision: `93cce83eefedb9a889b31bf4ffd6055a68dcee83`

Specification:

- repository: `opena2a-standards/agent-authorization-protocol`
- revision: `fb66195a9c2a4a40f91595da14673d11bb8c01e7`
- document: `AAP-BROKER-PROFILE.md`
- version: `0.4.1-draft`

## Normative requirement

AAP Broker Profile §6.7 says every verification, decision, resolution, and denial MUST be written to a **signed audit log**.

Level 1 in §13 includes **signed audit** as a conformance requirement.

## Reference implementation observation

At the pinned Secretless revision:

- `src/broker/audit.ts` implements `AuditLogger` as append-only JSONL.
- `AuditLogger.log()` serializes `AuditEntry` with `JSON.stringify(entry)` and `appendFileSync`.
- No signature, MAC, hash chain, signature field, or verifier is present in that path.
- `src/broker/grant-resolver.ts` describes the path in comments as the existing “signed audit path”.
- `src/broker/aap-conformance.test.ts` names one test “the signed audit log records the decision but never the scoped token”, but the assertions only verify:
  - a grant audit event exists;
  - the decision is recorded;
  - the scoped token is absent.

The test does not cryptographically verify an audit signature.

Repository-wide searches at this revision found no separate audit signature or verification implementation.

## Why this matters

Append-only is useful but is not the same property as signed audit.

Without a verifiable signature/MAC/chain, a broker can satisfy the current in-repo test while failing the Level-1 property stated by the Broker Profile.

That creates a spec/reference-implementation/conformance gap:

```text
spec says signed
      ↓
implementation writes unsigned JSONL
      ↓
test calls it signed but does not verify signing
```

## SpatialRuntime harness behavior

`aap-broker-behavior.v0.1` intentionally requires the adapter to return:

```json
{
  "audit": {
    "present": true,
    "signed": true,
    "contains_credential_material": false
  }
}
```

The adapter contract defines `signed=true` as an independently verified property, not the observation that a signature-looking field exists.

A Secretless adapter against the pinned revision should therefore report `signed=false` unless another verification path is added.

## Non-claim

This finding does not claim the AAP specification is wrong.

It does not claim append-only audit is useless.

It only records that the pinned reference implementation does not currently demonstrate the Level-1 **signed audit** property it is described as providing.


## AIM cross-check

AAP §6.7 says implementations SHOULD reuse the existing signed-audit path of OpenA2A AIM rather than build a new one.

That assumption does not match AIM's current published security status.

Pinned AIM evidence:

- repository: `opena2a-org/agent-identity-management`
- current revision re-checked: `3a66faab4b9953521f840a84caa8fb0bd048176a`
- earlier revision initially inspected: `6fc4318fffe25a49968bea51c0ea813e2ba8e850`
- document: `SECURITY.md`

AIM's FedRAMP AC-2 / AU-9 mapping states that:

- the `audit_logs` table records actions and is access-controlled;
- it is **not append-only at the database layer**;
- it is **not cryptographically signed**;
- a tamper-evident signing scheme is not currently implemented.

The same AU-9 statement remains present at the current revision above: the audit table is not append-only and is not cryptographically signed.

This changes the shape of the gap.

It is not merely:

```text
Secretless forgot to wire an existing AIM signed-audit primitive
```

The current family-level state is closer to:

```text
AAP normative text requires signed audit
        ↓
AAP text points at an existing AIM signed-audit path
        ↓
AIM security documentation says that capability is not implemented
        ↓
Secretless writes append-only JSONL and its conformance test does not verify signing
```

Possible upstream resolutions therefore include either:

1. implement and reuse a cryptographically verifiable audit path; or
2. correct the Broker Profile language / Level-1 claim so it does not refer to a capability that does not currently exist.

This finding deliberately does not choose between those policy/design options. The executable harness only preserves the evidence requirement: if Level 1 continues to require signed audit, an adapter must independently verify that property before reporting `signed=true`.
