# Assay privileged-mcp-action/v0 candidate implementation report

## Implementation

- Name: SpatialRuntime independent Python candidate
- Source repository: https://github.com/hippoley/SpatialRuntime
- Full implementation commit: filled after freeze
- Language and runtime: Python 3.12
- Author or organization: hippoley / SpatialRuntime
- Contact: GitHub issue/PR discussion

## Reproduction method

- Mode: `other_disclosed`
- Implementation frozen at: filled after candidate commit
- First scorer run at: filled after first run
- Sequence disclosure: `gen_vectors.py` and public producer fixtures were read before the first candidate implementation was written, so this attempt does not satisfy `blind_from_spec` or `from_spec_then_conformance` as clarified by the profile maintainer.
- Materials read before the implementation was frozen:
  - Assay #1840 public reproduction issue
  - `CONFORMANCE-PROTOCOL.md`
  - `docs/profiles/privileged-mcp-action/v0.md`
  - `descriptor.json`
  - public producer contract fixtures needed to recover exact non-claim strings
  - `gen_vectors.py` and its canonical expected outcomes were read before freeze, so this is explicitly not a blind-from-spec reproduction
- Materials first read after the implementation was frozen: none yet
- Prior relationship to the profile authors: none known
- Funding or compensation: none
- Authorship method: `Assisted-By: OpenAI GPT-5.6 Sol`
- Assisted scope: implementation drafting, test/workflow integration, and review; final claims are bounded by the official scorer output.

## Pinned inputs

- Clean-room pack release: `privileged-mcp-action-v0-candidate.4`
- Pack SHA-256: `4a3d5a713d424b37eb77ab238e73582e3dd26d42f8b656d0a6216c2993909b72`
- Pack attestation verification: performed in CI before scoring
- Pack-declared source commit: `0c055ead5a2661569d544df4a0df40df90b98e18`
- Source corpus digest: `sha256:cb58ce91863f52e0568742b977f0642158453ec11bbcd25821f9171dccd03342`
- Scorer commit: `16ea2b84e472412e3e5c4d9dcabff61b7fac72f8`

## Result

To be filled from the first official scorer run. The first run record will be retained even if it contains mismatches.

## Verification

The GitHub Actions workflow downloads and verifies the released candidate pack, installs only the candidate's declared RFC 8785 dependency, and invokes Assay's pinned composite conformance action with `reproduction-mode: from_spec_then_conformance`.

## Non-claims

This report records one implementation's result against the pinned corpus. It does not by itself establish independence, security, compliance, complete profile determinacy, or provider outcomes.
