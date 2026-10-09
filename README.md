# SpatialRuntime

**An evidence-preserving executable spatial runtime for AI agents, physics, safety, and real-world device control.**

SpatialRuntime turns a spatial world model into a runtime that can reason about relationships, apply safety constraints, dispatch device commands, reconcile telemetry, and explain why an action was allowed or blocked.

It is intentionally **scene-source agnostic**. A BIM model, CAD/floor-plan parser, manually authored topology, digital twin, SLAM stack, or future 3D reconstruction system can all feed the same runtime contracts.

## What it owns

```text
world snapshot
  -> reviewed spatial relations
  -> transitive relation graph
  -> solver adapter
  -> whole-home safety graph
  -> policy/recovery arbitration
  -> commit gate
  -> ThingModel/Gateway dispatch
  -> ACK + telemetry
  -> convergence/fault recovery
  -> next observation
```

## What it does not own

SpatialRuntime does not reconstruct a 3D scene, train perception models, implement a CFD solver, or define vendor device protocols. Those are adapters.

## Core invariants

- candidate relation != reviewed fact
- inferred relation != executable control rule
- solver output is bound to case / step / revision / request hash
- ACK != physical convergence
- proposed action != committed action != observed device state
- recovery cannot bypass safety
- safety-forced motion cannot be weakened by ordinary policy rate limits
- unreviewed rule/source drift fails closed
- durable ledgers survive restart and detect tampering
- an episode transition is valid only when previous `after` state equals next `before` state

## RuntimeSession

`RuntimeSession` is the fail-closed top-level orchestration surface:

```text
solver + sensor + device feedback
  -> reconcile
  -> observation
  -> policy / recovery
  -> whole-home safety
  -> commit gate
  -> optional hardware dispatch
  -> deterministic episode trace
```

Hard disagreements stop the pipeline before control. Each trace records before/after state hashes, stage-level evidence, and the normalized solver feedback used for that exact step.

## Solver adapter contract

Physics is now a plugin boundary.

```text
World state + model + boundary conditions
                ↓
          SolverRequest
                ↓
     SolverAdapter.solve(...)
       ┌────────┴─────────┐
deterministic fixture   external JSON process
       │                  │
       └────────┬─────────┘
                ↓
      normalized solver_feedback
                ↓
          RuntimeSession
```

Every normalized solve result carries:

- `case_id`
- `source_step`
- `source_revision`
- `adapter_id`
- `adapter_fingerprint`
- `request_hash`
- `result_hash`

The included `JsonProcessSolverAdapter` uses an explicit argv list, JSON stdin/stdout, a timeout, and `shell=False`. It does not infer or download solver binaries.

Scenario JSON deliberately supports only `solver.mode = "fixture"`. External solver processes such as CONTAM wrappers must be instantiated explicitly by application code; a scenario file is not permission to execute arbitrary local commands.

## CONTAM project adapter

SpatialRuntime now includes a conservative CONTAM integration layer:

```text
reviewed PRJ
   ↓
native inventory
   ↓
stable zone/path bindings
   ↓
explicit native result provider
   ↓
VAL / TSV / API normalization
   ↓
ContamProjectSolverAdapter
   ↓
solver_feedback_v0.6
   ↓
RuntimeSession
```

Key fail-closed rules:

- required PRJ section markers must be present; the parser does not guess record boundaries
- stable IDs bind to reviewed CONTAM zone/path/flow-element numbers
- project SHA and structural inventory are checked before every solve
- raw binary `.SIM` files are not guessed or decoded; use SimRead/Results Export or an explicit ContamX API wrapper
- conflicting VAL / TSV / API values are rejected rather than silently overwritten
- binding fingerprints are path-independent, so the same reviewed PRJ can be moved between machines without false drift

`ContamCliRunner` can detect or explicitly resolve a ContamX executable and run an already-materialized PRJ with `shell=False`. CI does not currently contain ContamX, so the repository does **not** claim a real ContamX solve yet.

## Conservative CONTAM mutation

SpatialRuntime can now produce a new reviewed PRJ revision by changing only parameters on explicitly understood `plr_orfc` airflow elements.

```text
reviewed PRJ r0
    +
stable flow-path binding
    +
mutation operation
        ↓
mutation plan
        ↓
temporary candidate PRJ
        ↓
re-parse native inventory
        ↓
structural fingerprint unchanged?
        ↓ yes
atomic write PRJ r1
        ↓
mutation report
        ↓
binding registry revision +1
```

The v0.10 mutation layer allows only:

- `area_m2`
- `coef`
- `expt`

It intentionally does **not** mutate CONTAM native IDs, zone/path connectivity, element type, diameter, control topology, or arbitrary record fields.

Mutation is fail-closed:

- the source PRJ must still match the reviewed binding registry
- the mutation plan is hash-bound to the source project and structural inventory
- a plan becomes invalid if the source PRJ changes before apply
- the candidate PRJ is re-parsed before it is committed
- structural inventory must remain identical
- in-place mutation is forbidden; each revision is written to a new PRJ so the previous evidence remains available
- binding revision advances only from an applied mutation report that proves the before/after hashes

A typical application flow is:

```python
plan = build_mutation_plan(
    case_id="home-01",
    source_step=3,
    source_revision=3,
    project_path="case-r0.prj",
    binding_registry=registry,
    inventory=inventory,
    operations=[{
        "kind": "set_flow_path_parameters",
        "flow_path_id": "window::kitchen",
        "parameters": {"area_m2": 0.35},
    }],
)

report = apply_mutation_plan(
    project_path="case-r0.prj",
    output_path="case-r1.prj",
    plan=plan,
)

registry = advance_binding_registry_after_mutation(
    registry,
    before_project_path="case-r0.prj",
    before_inventory=inventory,
    after_project_path="case-r1.prj",
    mutation_report=report,
)
```

This still does **not** claim that ContamX itself has executed in CI. It establishes an auditable PRJ mutation and lineage layer that a real ContamX execution adapter can consume.

## ContamX execution provider

SpatialRuntime now includes an application-side execution provider that connects the reviewed PRJ/binding layer to an explicitly configured ContamX executable.

The execution order is:

```text
reviewed PRJ revision
        ↓
ContamX --TestInput
        ↓ pass
snapshot configured result artifacts
        ↓
ContamX <project.prj>
        ↓
fresh VAL / TSV / API artifacts
        ↓
conflict-safe native result merge
        ↓
stable ID mapping
        ↓
solver_feedback_v0.6
        ↓
RuntimeSession
```

The provider deliberately does not guess result filenames. Applications configure exact paths (with optional `{stem}` / `{name}` placeholders), for example:

```python
runner = ContamCliRunner(executable="/opt/contam/contam-x")
artifacts = ExplicitResultArtifacts(
    api_json="{stem}.result.json",
)

provider = ContamCliResultProvider(
    runner=runner,
    artifacts=artifacts,
    test_input_first=True,
)
```

Freshness is checked around the solve. A pre-existing artifact that is neither replaced nor changed is rejected instead of being reused as if it belonged to the new run.

Execution evidence retained in solver feedback includes:

- source step / revision
- binding revision
- TestInput return code
- solve return code
- ContamX version string
- explicit artifact paths
- execution evidence hash

The NIST CONTAM 3.4 documentation specifies the command-line form as `contam-x [input-file] [options]`, with `--TestInput` for input validation. SpatialRuntime follows that ordering and still invokes subprocesses with `shell=False`.

Real ContamX execution is only available when a compatible executable is installed or `CONTAMX_BIN` is set. Repository CI uses a fake executable to validate the process protocol and does **not** claim to execute NIST ContamX itself.

## Execution manifest

Every scenario-run episode now carries a `runtime_execution_manifest_v0.7` that fingerprints the configuration used to produce the traces:

- scenario spec
- initial runtime state
- entity catalog
- compiled safety graph
- solver mode / adapter ID / adapter fingerprint
- hardware mode / hardware config fingerprint

Replay validates the manifest itself and cross-checks it against trace evidence. Re-hashing a tampered trace is not enough to hide solver drift, safety-graph drift, or initial-state substitution.

```text
scenario spec
   + entity catalog
   + safety graph
   + solver adapter
   + hardware config
          ↓
 execution manifest
          ↓
       episode
          ↓
 strict replay
```

## Preflight drift gate

For pinned runs, create an approved execution plan first:

```bash
spatialruntime plan examples/kitchen_living.scenario.json -o execution.plan.json
```

Then require that exact plan at execution time:

```bash
spatialruntime run examples/kitchen_living.scenario.json \
  --plan execution.plan.json \
  -o episode.json
```

Preflight happens before solver, safety, commit, or hardware stages run. It rejects changes to:

- initial runtime state
- entity catalog
- safety graph
- solver mode / adapter / fingerprint
- hardware mode / fixture bindings
- the plan file itself

The resulting episode records both the approved `preflight_plan_hash` and `preflight_manifest_hash`.

## CLI

Install in editable mode:

```bash
python -m pip install -e '.[dev]'
```

Run the built-in Kitchen/Living scenario:

```bash
spatialruntime scenario kitchen-living -o episode.json
```

Run a scene-source-neutral JSON scenario:

```bash
spatialruntime run examples/kitchen_living.scenario.json -o episode.json
```

Validate and inspect the resulting evidence:

```bash
spatialruntime replay episode.json
spatialruntime inspect episode.json
```

Replay returns a non-zero exit code if trace hashes, state hashes, case identity, step/revision sequence, or cross-step state continuity have been tampered with.

## Closed-loop example

The deterministic Kitchen/Living episode runs two timesteps:

1. solver feedback is normalized and bound to the current session revision;
2. cooking activates the hood and reviewed make-up-air action;
3. hardware feedback is reconciled and the session advances;
4. rain activates a higher-priority safety rule that force-closes the exterior window.

The included solver and gateway are deterministic contract fixtures. The example does **not** claim to run CONTAM, CFD, or real hardware.

## Package layout

- `spatialruntime.runtime` - reconciliation, commit gate, RuntimeSession, replay, scenario runner
- `spatialruntime.solver` - solver request/feedback contract and adapters
- `spatialruntime.hardware` - command contracts, Gateway, telemetry, ThingModel binding
- `spatialruntime.safety` - arbitration, recovery, supervisor, dependency graph
- `spatialruntime.spatial` - relation resolution, review, promotion and compile lineage
- `spatialruntime.scenarios` - replayable reference scenarios
- `spatialruntime.world` - scene-source-neutral world snapshot contract

## Interop conformance surfaces

SpatialRuntime also publishes small, model-independent conformance probes for agent/tool execution boundaries. They are intentionally separate from the spatial runtime API and can be consumed directly from CI.

Current surfaces:

- `interop/agent-effect-authority/` — effect-authority claim, evidence, and cross-runtime semantic mapping checks.
- `interop/otel-tool-decision-lifecycle/` — per-call `gen_ai.tool.call.decision` → `execute_tool` correlation, preserving `UNRESOLVED` when a safe call identity is unavailable.
- `interop/decision-execution-binding/` — separates authorization/approval decision identity from execution identity, including standing 1:N decisions and scope-binding checks.
- `interop/aap-broker-behavior/` — independent AAP Broker Profile Level-1 behavior probe for default-deny, opaque denials, context hygiene, signed-audit evidence, and result-only return; includes negative controls and a pinned spec/reference-implementation gap finding.

Reusable GitHub Action:

```yaml
- id: conformance
  uses: hippoley/SpatialRuntime/interop/agent-effect-authority@<pinned-sha>
  with:
    mode: decision-execution-binding
    file: evidence/decision-execution-binding.json

- if: steps.conformance.outputs.conformance_result != 'PASS'
  run: exit 1
```

Consumers SHOULD pin an immutable commit SHA. `PASS` means only that the supplied evidence satisfies the selected conformance profile; it does not establish real-world effect completion. External projects cited in profile evidence are pressure sources, not adopters or endorsers of SpatialRuntime.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

The project deliberately keeps perception/reconstruction and solver implementations outside the core runtime. Scene sources and physics engines are adapters; reviewed spatial semantics and safe execution are the runtime boundary.
