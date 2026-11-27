# External distribution handoff: SpatialRuntime → awesome-verified-agents

**Prepared:** 2026-11-27 (UTC+8). **Status:** PATCH PREPARED — NOT SUBMITTED. The connected GitHub integration returned HTTP 403 when attempting to create an upstream branch in `tonydzi/awesome-verified-agents`. No upstream PR, review or acceptance is claimed.

## Why this is a better next node

The directory's contributor bar asks for a publicly inspectable post-run artifact, a concrete limitation, one project per PR, a verified license/stars/last-commit date, and a reason for section choice. SpatialRuntime now supplies a model-independent conformance Action and independently inspectable GitHub CI receipts. Being listed would improve discoverability, but would **not** be an unrelated CI consumer or close CF-06.

**Proposed section:** Output verification, not Runtime enforcement. SpatialRuntime checks the submitted agent evidence after the fact. Its Action can block downstream CI when configured for PASS-only, but this does **not** make it an inline tool-call prevention runtime.

**Project:** `hippoley/SpatialRuntime` (self-submission by project owner). **License:** MIT. **Stars:** 1. **Last push date:** 2026-11-27 (checked against the GitHub repository API on the preparation date). Refresh stars and last commit date when the upstream PR is actually opened.

**Duplicate check:** no `SpatialRuntime` or `hippoley` entry in upstream README at the inspected `main` snapshot `f045cbce588efe3e3b119ffe1f57d630f96e2b7e`.

**Exact one-row patch:** [`awesome-verified-agents-single-project.patch`](awesome-verified-agents-single-project.patch). The patch is targeted at upstream README and has not been applied to that repository.

## Evidence a reviewer can inspect

1. [Canonical Action definition](https://github.com/hippoley/SpatialRuntime/blob/a62e595314f83cd359bbf6a8923b585d0449a41e/interop/conformance/action.yml) — the output is `PASS`, `UNRESOLVED` or `FAIL`, with an opt-in `require_result: PASS` release gate. Its reference-only suite PASS is not allowed to authorize a strict release.
2. [Actual composite-Action execution](https://github.com/hippoley/SpatialRuntime/actions/runs/45925090480) — positive and negative execution branches, not only static unit tests.
3. [ARIB real SDK cross-version receipt](https://github.com/hippoley/SpatialRuntime/blob/314a32796a94f73654cfe42259060f50e935f1e0/interop/external-results/runs/arib-cross-version-2026-11-26.json) — 0.19.4 versus 0.23.1 observed behavior under a pinned benchmark; no claimed third-party adoption.
4. [Kiri Gate actual SQLite evidence boundary](https://github.com/hippoley/SpatialRuntime/blob/314a32796a94f73654cfe42259060f50e935f1e0/interop/external-results/runs/kiri-durable-binding-2026-11-26.json) — one durable approval, one completed effect, but historical binding remains `UNRESOLVED`.

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

Upstream accepts one-project pull requests. The GitHub connector cannot create an upstream branch or fork. To actually submit, an authorized account needs to fork `tonydzi/awesome-verified-agents`, apply the one-row patch, refresh source metadata, then create a PR against upstream `main`. That external action has **not** been done in this round.

**Stop rule:** if the curator rejects the project as too broad or lacking independent consumers, preserve the explicit objection as real demand-side evidence. Do not solve a distribution/review failure by creating another new conformance profile.
