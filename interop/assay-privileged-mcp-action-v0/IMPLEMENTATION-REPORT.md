# Assay privileged-mcp-action/v0 candidate implementation report

## Implementation

- Name: SpatialRuntime independent Python candidate
- Source repository: https://github.com/hippoley/SpatialRuntime
- Successful scored implementation commit: `009de9eccc2ec6cdfe14c75432941fdf9eb1522c`
- Candidate branch head after disclosure/pin correction: `75bd675be8d97710f92fccfdff508a74d4a4cc68`
- Language and runtime: Python 3.12
- Author or organization: hippoley / SpatialRuntime
- Contact: GitHub issue/PR discussion

## Reproduction method

- Mode: `other_disclosed`
- Sequence disclosure: `gen_vectors.py` and public producer fixtures were read before the first candidate implementation was written. This attempt therefore does not satisfy `blind_from_spec` or `from_spec_then_conformance`.
- Materials read before the implementation was frozen:
  - Assay #1840 public reproduction issue
  - `CONFORMANCE-PROTOCOL.md`
  - `docs/profiles/privileged-mcp-action/v0.md`
  - `descriptor.json`
  - public producer contract fixtures needed to recover exact non-claim strings
  - `gen_vectors.py` / canonical outcome-bearing generator material
- Prior relationship to the profile authors: none known
- Funding or compensation: none
- Authorship method: `Assisted-By: OpenAI GPT-5.6 Sol`
- Assisted scope: implementation drafting, test/workflow integration, and review; final claims are bounded by the official scorer output.

## Pinned inputs

- Clean-room pack release: `privileged-mcp-action-v0-candidate.4`
- Pack SHA-256: `sha256:4a3d5a713d424b37eb77ab238e73582e3dd26d42f8b656d0a6216c2993909b72`
- Pack attestation verification: performed successfully in CI before scoring
- Pack-declared source commit: `0c055ead5a2661569d544df4a0df40df90b98e18`
- Source corpus digest: `sha256:cb58ce91863f52e0568742b977f0642158453ec11bbcd25821f9171dccd03342`
- Rendered set digest: `sha256:b2f715408c82346b0928852f0bc6cb11c17dd7e3233395316d764b282080a05c`
- Compatible scorer/action commit used for the successful run: `2c692088d794345235809b038d729e589e339c3d`

## Run lineage

### First attempted official run — harness failure

- Workflow run: `37762433820`
- Result: harness error before candidate execution
- Diagnostic: `invalid clean-room pack: pack contains surplus members`
- Root cause: protocol/README action pin `16ea2b84...` expected 14 cases + 4 outer members, while candidate.4 adds two canonicalization members.
- No normative candidate result was produced.

### First completed official scored run

- Workflow run: `37869812018`
- Artifact id: `11589459426`
- Artifact digest: `sha256:bbb536f94f807ee688ca828448f8de7c116d2f917a2eb78fdd05ccff9b8a46b3`
- Result: **14 / 14 normative matches**
- Mismatches: `0`
- Execution errors: `0`
- Harness errors: `0`
- Review warnings: `0`
- Reproduction mode recorded by scorer: `other_disclosed`

Per-case status was `match` for `case-001` through `case-014`.

## Claim ceiling

This result establishes agreement between this disclosed candidate and Assay's pinned 14-case corpus only.

It does **not** establish:
- implementation independence;
- blind-from-spec reproduction;
- security or compliance;
- complete profile determinacy;
- provider outcomes;
- coverage of profile rules not discriminated by the corpus.

The activation-kit compatibility defect discovered before the successful run is a separate interoperability finding and should not be conflated with the normative 14/14 result.
