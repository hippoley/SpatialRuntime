# Horizontal Completeness Audit

Status date: 2026-10-09

This audit is the second closure layer for SpatialRuntime User Stories.

- **Vertical closure** asks whether the original user goal, implementation and acceptance contract are satisfied.
- **Horizontal closure** asks whether the implementation is complete enough across its applicable system dimensions and dependencies to be trusted in the real product.

A story may be vertically `DONE` and still fail horizontal closure. Only stories that pass both layers may be labelled **Verified Closed**.

Machine-readable truth lives in `docs/horizontal-completeness.v0.1.json`.
CI/P0 verification is implemented by `docs/verify_horizontal_completeness.py`.

## Required dimensions

Every User Story must explicitly classify:

1. functional completeness;
2. state completeness;
3. integration completeness;
4. security/correctness;
5. performance/scalability;
6. maintainability;
7. observability/traceability;
8. testability;
9. user-value completeness;
10. external compatibility.

Allowed dimension states:

- `VERIFIED`
- `PARTIAL`
- `MISSING`
- `BLOCKED`
- `N_A`

`N_A` is valid only with a reason. Pure documentation/versioning stories, for example, do not acquire fake throughput SLOs merely to make the matrix look full.

## Verified Closed rule

`VERIFIED_CLOSED` is accepted only when:

- the longitudinal Product Boundary Audit says `DONE`;
- every applicable dimension is `VERIFIED`;
- all non-applicable dimensions are explicitly `N_A` with rationale;
- independent acceptance is `VERIFIED`;
- every dependency references another known User Story;
- the dependency graph is acyclic;
- no field/external/upstream gate remains.

The verifier rejects false closure, missing dimensions, nonexistent repository evidence, status drift, dependency cycles and missing gates.

## Dependency / impact model

Important dependency chains include:

```text
SR-01 deterministic runtime
  ├─ SR-02 solver boundary
  │    └─ SR-03 CONTAM binding
  │         └─ SR-04 real ContamX evidence
  ├─ SR-08 application assembly
  │    └─ SR-05 physical convergence
  │         └─ SR-06 unresolved-effect restart/reconcile
  └─ SR-09 live resume ───────────────────────────────┘

CF-01 neutral conformance
  ├─ CF-02 external verifier adapter
  │    └─ CF-08 official scorer
  │         └─ CF-07 upstream corpus influence
  ├─ CF-03 catalog
  │    ├─ CF-04 safe quickstart
  │    └─ AD-03 released pinning
  └─ CF-05 evidence registry

CF-01 + CF-03 + CF-04 + AD-03
  └─ CF-06 unrelated external consumption
```

Changes to a parent story therefore require regression review of its dependent stories even when the child files did not change.

## Current closure classification

| Story group | Horizontal result | Meaning |
|---|---|---|
| SR-01/02/03/08/09 | Verified Closed | repository-owned runtime contracts have executable acceptance evidence |
| SR-04 | Blocked Field | owned AirTrajectory supplies real ContamX grounding; duplicating it in this repo is not automatically valuable |
| SR-05/06 | Blocked Field | only real actuator movement, authoritative readback and unresolved-effect restart evidence can close them |
| SR-07 | Blocked External | owned scene integration exists; unrelated BIM/CAD/SLAM consumption is still required |
| CF-01/02/03/04/05/08/09 | Verified Closed | neutral conformance, evidence classification and externally observed review/scorer paths have evidence |
| CF-06 | Blocked External | no unrelated repository depends on the canonical released conformance surface yet |
| CF-07 | Blocked Upstream | Assay Stage-3 needs upstream maintainer judgment/adoption |
| CF-10/11 | Hold | do not build parallel standards or observability semantics without a concrete upstream consumer |
| AD-01..07 | Verified Closed | repository positioning, canonical surface, release, maturity and result-semantics contracts are internally closed |

This classification deliberately does **not** convert field or external gates into an internal feature backlog.

## Latest mature-solution benchmark

### Release provenance

Use GitHub Artifact Attestations / Sigstore and SLSA provenance semantics rather than inventing a private signing system.

Decision: **ADAPT**, not replace the existing release contract.

The existing tag + manifest remains the distribution identity; provenance attestation strengthens how consumers verify where and how an artifact was produced.

### Durable execution and external effects

Temporal is a mature durable-execution system with event history and replay. Its own external-operation guidance still uses at-least-once execution and recommends idempotent handlers.

Decision: **KEEP BOUNDARY**.

SpatialRuntime should not become another Temporal. It should retain the narrower layer Temporal and other workflow engines still need at external-effect boundaries: logical effect identity, authoritative readback, unresolved outcome, reconciliation and evidence lineage. A future consumer may use SpatialRuntime beside Temporal rather than instead of it.

### Observability

Use OpenTelemetry for telemetry naming and correlation.

Decision: **KEEP SCOPE**.

Telemetry success, span completion or tool-result recording must not silently become authoritative physical/external-effect truth. The closed OpenTelemetry contribution is retained as a scope result rather than reopened through new vocabulary.

### Scene interchange

For a real BIM consumer, prefer the current buildingSMART IFC 4.3 family. For large 3D/DCC composition workflows, prefer OpenUSD.

Decision: **ADAPT ON DEMAND**.

Do not add IFC/OpenUSD adapters without an actual consumer mapping/round-trip requirement. The scene-neutral WorldSnapshot boundary is retained until a real integration can test semantic loss, source drift and round-trip behavior.

## Independent falsification

The horizontal verifier has adversarial tests that deliberately attempt to create false closure:

- remove one required dimension;
- mark a field-blocked hardware story `VERIFIED_CLOSED`;
- introduce a dependency cycle;
- point verified evidence at a nonexistent repository path;
- make the matrix vertical status disagree with the longitudinal audit.

Each mutation must fail.

This is intentionally different from implementation tests. The verifier is testing the **truthfulness of the closure claim** itself.

## P0 integration

Horizontal completeness is `P0-F` in `docs/P0-CLOSURE.v0.1.json`.

Therefore the existing repository P0 verifier now executes:

```text
horizontal adversarial tests
        +
horizontal completeness verifier
        ↓
P0-F
        ↓
repository P0 local verification
```

No separate CI-only assertion is required: the existing CI step that runs `docs/verify_p0_closure.py` inherits P0-F and fails closed.

## Investment rule

A non-DONE story does not automatically authorize more code.

Internal development is justified only when it:

- closes a repository-owned gap;
- removes measured consumer friction;
- fixes a discovered regression;
- improves credential/evidence integrity;
- or is required by a concrete field/upstream/external gate.

Otherwise preserve the gate and wait for reality.
