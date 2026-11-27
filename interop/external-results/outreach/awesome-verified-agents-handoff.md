# External distribution handoff: SpatialRuntime → awesome-verified-agents

**Updated:** 2026-11-27 (UTC+8). **Status:** [external resource suggestion #16](https://github.com/tonydzi/awesome-verified-agents/issues/16) delivered, **human curator review received**, single-row patch corrected; **normal upstream Fork → PR still NOT SUBMITTED**. The GitHub connection cannot create a fork and upstream branch creation returned 403. Curator acceptance of the evidence bar is not a merged directory entry or independent CI consumption.

## Why this is a better next node

The directory's contributor bar asks for a publicly inspectable post-run artifact, a concrete limitation, one project per PR, a verified license/stars/last-commit date, and a reason for section choice. SpatialRuntime now supplies a model-independent conformance Action and independently inspectable GitHub CI receipts. Being listed would improve discoverability, but would **not** be an unrelated CI consumer or close CF-06.

**Curator-confirmed section:** Output verification, not Runtime enforcement. The listing points specifically to the **SpatialRuntime Conformance Action and its inspectable receipts**, rather than treating the entire spatial-runtime and hardware-control product as verified. SpatialRuntime checks the submitted agent evidence after the fact. Its Action can block downstream CI when configured for PASS-only, but this does **not** make it an inline tool-call prevention runtime.

**Project:** `hippoley/SpatialRuntime` (self-submission by project owner). **License:** MIT. **Stars:** 1. **Last push date:** 2026-11-27 (checked against the GitHub repository API on the preparation date). Refresh stars and last commit date when the upstream PR is actually opened.

**Duplicate check:** no `SpatialRuntime` or `hippoley` entry in upstream README at the original inspected `main` snapshot `f045cbce588efe3e3b119ffe1f57d630f96e2b7e`, and still absent when revisited on 2026-11-27. Refresh before a real PR.

**Exact corrected one-row patch (adds self-submission `†` and directly links Action + receipt):** [`awesome-verified-agents-single-project.patch`](awesome-verified-agents-single-project.patch). The patch is targeted at upstream README and has not been applied to that repository.

## Evidence a reviewer can inspect

1. [Canonical Action definition](https://github.com/hippoley/SpatialRuntime/blob/a62e595314f83cd359bbf6a8923b585d0449a41e/interop/conformance/action.yml) — the output is `PASS`, `UNRESOLVED` or `FAIL`, with an opt-in `require_result: PASS` release gate. Its reference-only suite PASS is not allowed to authorize a strict release.
2. [Actual composite-Action execution](https://github.com/hippoley/SpatialRuntime/actions/runs/45925090480) — positive and negative execution branches, not only static unit tests.
3. [ARIB real SDK cross-version receipt](https://github.com/hippoley/SpatialRuntime/blob/314a32796a94f73654cfe42259060f50e935f1e0/interop/external-results/runs/arib-cross-version-2026-11-26.json) — 0.19.4 versus 0.23.1 observed behavior under a pinned benchmark; no claimed third-party adoption.
4. [Kiri Gate actual SQLite evidence boundary](https://github.com/hippoley/SpatialRuntime/blob/314a32796a94f73654cfe42259060f50e935f1e0/interop/external-results/runs/kiri-durable-binding-2026-11-26.json) — one durable approval, one completed effect, but historical binding remains `UNRESOLVED`.

## Actual external review and immutable upstream citation

- [Curator's technical review on suggestion #16](https://github.com/tonydzi/awesome-verified-agents/issues/16#issuecomment-7211071705): acceptance of the inspectable evidence bar, selection of **Output verification**, one exact scope objection and a requirement for a normal fork/PR. **No independent run** was performed by the curator.
- [Scope clarification response](https://github.com/tonydzi/awesome-verified-agents/issues/16#issuecomment-7211886014): confirmed the corrected action-only scope, the upstream fork permission boundary and self-submission marker.
- [ARIB upstream merged citation](https://github.com/tonydzi/agent-runtime-integrity-bench/commit/ba96925e3f041ec4215eea991f1cc3a9aec2abd3): the unrelated maintainer directly referenced the permanent ARIB SDK version-comparison JSON in its public **Consumers** section, explicitly stating the maintainer has **not rerun** the result. This is a durable **external reference**, not external consumption of the SpatialRuntime GitHub Action.
- [Source maintainer wording confirmed](https://github.com/tonydzi/agent-runtime-integrity-bench/issues/1#issuecomment-7211885336): no silent expansion to an independent storage oracle or SDK exactly-once guarantee.

**Reviewer-facing row scope:** the patch adds *SpatialRuntime Conformance Action* with a direct link to `interop/conformance`, a real Action run, the correct MIT/1-star/2026-11-27 snapshot, the `†` owner-submission marker, and explicit nonclaims about producer authenticity and physical-effect truth. It does not imply the curator has independently reproduced or certified the project.

## Suggested upstream PR body (self-submission)

> **Title:** Add SpatialRuntime — tri-state agent execution-evidence conformance Action
>
> This is a self-submission: I maintain `hippoley/SpatialRuntime`. I propose one entry under **Output verification** because its canonical GitHub Action checks supplied decision-to-execution and effect-evidence records and leaves inspectable `PASS` / `UNRESOLVED` / `FAIL` results. There is a pinned, opt-in PASS-only release gate; the bundled reference evaluator cannot authorize such a gate without an external adapter.
>
> **Artifact:** real GitHub Actions run with PASS, UNRESOLVED and FAIL branches, plus long-lived JSON receipts from actual SDK and SQLite interoperability experiments (see links above).
>
> **Boundary:** the checks do not independently observe physical effects or authenticate all producer assertions. Successful repository-owned tests are not independent adoption.
>
> **Metadata:** MIT, 1 star, last commit 2026-11-27 (refresh immediately before opening PR). I checked upstream README for the project name and URL and found no duplicate at preparation time. I selected Output verification because this is an evidence judgment rather than in-path runtime enforcement.
>
> One-row README patch attached.

## Concrete next action / blocked boundary

Upstream requires one-project pull requests, and a curator has explicitly confirmed the prepared Action-only row meets the evidence bar once submitted through that route. The GitHub connector cannot create an upstream branch or fork. To actually submit, an authorized account needs to fork `tonydzi/awesome-verified-agents`, apply the one-row patch, refresh source metadata, then create a PR against upstream `main`. That external action has **not** been done in this round.

**Stop rule:** if the curator rejects the project as too broad or lacking independent consumers, preserve the explicit objection as real demand-side evidence. Do not solve a distribution/review failure by creating another new conformance profile.
