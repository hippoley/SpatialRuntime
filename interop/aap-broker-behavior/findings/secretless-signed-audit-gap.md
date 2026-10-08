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
