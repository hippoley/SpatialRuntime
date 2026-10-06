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

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

The project deliberately keeps perception/reconstruction and solver implementations outside the core runtime. Scene sources and physics engines are adapters; reviewed spatial semantics and safe execution are the runtime boundary.
