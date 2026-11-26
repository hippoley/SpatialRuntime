# ARIB observed effect trace — independent consumer

This small interoperability probe lives in **SpatialRuntime** and consumes evidence from [tonydzi/agent-runtime-integrity-bench](https://github.com/tonydzi/agent-runtime-integrity-bench). It is not a new conformance standard or a production SDK.

## Why this exists

In [ARIB issue #1](https://github.com/tonydzi/agent-runtime-integrity-bench/issues/1), hippoley identified an effect-cardinality gap: a repeated write to the *right* location with the *right* value can pass resource-scope and value-fidelity checks while violating an authorized count. The ARIB maintainer incorporated observed, ordered replay effects into the actual benchmark at [`c7b9ba1`](https://github.com/tonydzi/agent-runtime-integrity-bench/commit/c7b9ba15c3cde310a25b9d4249fcc8e3ff0d63d9), recording that external review in the source. This consumer reads those reports **without importing ARIB judgment code**.

## Three different evidence levels

1. `verify_upstream.py`: checks a Git-blob-pinned historical report; **report-level only**.
2. `arib-live-sdk-replay.yml`: runs ARIB's pinned original harness against a **real** installed `openai-agents` SDK and uses this consumer on the newly produced JSON. This is **not an independently implemented SDK observer**.
3. `arib-cross-version-replay.yml`: executes two SDK versions using the **same benchmark source**, then compares consumer receipts. It detects changed recorded behavior but does **not** establish an SDK breach of contract, cryptographic identity, or a physical outcome.

## Public reproducibility

- [Initial successful real SDK replay on 0.23.1](https://github.com/hippoley/SpatialRuntime/actions/runs/45777104529)
- [Independent published-report read](https://github.com/hippoley/SpatialRuntime/actions/runs/45775723936)
- [Two-version 0.19.4 vs 0.23.1 SDK run](https://github.com/hippoley/SpatialRuntime/actions/runs/45779215233)

The two-version run showed **two reported durable effects against a budget of one** in all four backends for both tested versions. Those results come from the actual ARIB SDK benchmark, under its configured fault and tested dependencies. This is **not** an independent proof that `openai-agents` promises exactly-once delivery.

## Exit codes / failures

ARIB's runtime exit 0 = all measured invariants held; 1 = measured violations (valid evidence); 4 or unexpected exits = broken harness. The CI correctly treats 0/1 as produced reports to be evaluated, not as assertions that the SDK is safe.

The first two local-to-CI attempts are retained as negative provenance:
- [Missing `sqlalchemy[asyncio]` / greenlet](https://github.com/hippoley/SpatialRuntime/actions/runs/45776860947)
- [Bash `-e` misclassified the expected exit 1](https://github.com/hippoley/SpatialRuntime/actions/runs/45776958026)

Neither is a finding about the runtime; both were harness failures repaired without changing upstream test behavior.

## User Stories and evidence ceiling

| ID | User Story | Current disposition |
| --- | --- | --- |
| ARIB-01 | Independently evaluate reported replay cardinality and order | **Done**, local mutations and CI |
| ARIB-02 | Bind to an exact published ARIB report object | **Done**, pinned Git blob |
| ARIB-03 | Run actual SDK adapters rather than read historical files | **Done on Ubuntu/Python 3.12**, four adapters |
| ARIB-04 | Compare two real SDK releases without assuming improvement | **Implemented; acceptance requires green comparison CI** |
| ARIB-05 | Independently observe the durable storage layer | **Open**: ARIB test itself remains the observer |
| ARIB-06 | Authenticate a producer/signer independently | **Open** |
| ARIB-07 | Cross-platform field confidence | **Open** beyond current Ubuntu CI |
| ARIB-08 | Unrelated downstream project actually pins and consumes this interface | **Open**, do not count own repos |
| ARIB-09 | Stable standalone interface/version migration promise | **Hold** until real external demand |

### Stop / pivot rule

Do not create a new top-level conformance brand or claim product adoption from this PR. If no unrelated team uses this probe or supplies a falsifying counterexample after substantive review, keep it as a completed evidence-bearing experiment and redirect engineering investment to the upstream maintainer’s next specific defect or an unrelated consumer's requirements.

**The public negative evidence is as important as a green job:** two versions did not exhibit a replay-dedup improvement in the tested setup. Preserve old artifacts; never rewrite historical reports to match the latest SDK.
