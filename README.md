# SpatialRuntime

**An evidence-preserving executable spatial runtime for AI agents, physics, safety, and real-world device control.**

SpatialRuntime turns a spatial world model into a runtime that can reason about relationships, apply safety constraints, dispatch device commands, reconcile telemetry, and explain why an action was allowed or blocked.

It is intentionally **scene-source agnostic**. A BIM model, CAD/floor-plan parser, manually authored topology, digital twin, SLAM stack, or future 3D reconstruction system can all feed the same runtime contracts.

## What it owns

```text
world snapshot
  -> reviewed spatial relations
  -> transitive relation graph
  -> whole-home safety graph
  -> policy/recovery arbitration
  -> commit gate
  -> ThingModel/Gateway dispatch
  -> ACK + telemetry
  -> convergence/fault recovery
  -> next observation
```

## What it does not own

SpatialRuntime does not reconstruct a 3D scene, train perception models, or define vendor device protocols. Those are adapters.

## Core invariants

- candidate relation != reviewed fact
- inferred relation != executable control rule
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

Hard disagreements stop the pipeline before control. Each trace records:

- `runtime_state_before`
- `runtime_state_before_hash`
- stage-level evidence and decisions
- `next_runtime_state`
- `next_runtime_state_hash`
- full `trace_hash`

That allows a replay validator to verify both trace integrity and cross-step state continuity.

## CLI

Install in editable mode:

```bash
python -m pip install -e '.[dev]'
```

Run the built-in Kitchen/Living scenario and save a replay bundle:

```bash
spatialruntime scenario kitchen-living -o episode.json
```

Strictly validate the saved episode:

```bash
spatialruntime replay episode.json
```

Inspect a compact per-step summary:

```bash
spatialruntime inspect episode.json
```

The replay command returns a non-zero exit code if a trace hash, state hash, step/revision sequence, case ID, or cross-step state chain has been tampered with.

You can also run the package directly:

```bash
python -m spatialruntime scenario kitchen-living -o episode.json
```

## Closed-loop example

The deterministic Kitchen/Living episode runs two timesteps:

1. cooking activates the hood and a reviewed make-up-air window action;
2. hardware feedback is reconciled and the session advances;
3. rain activates a higher-priority safety rule that force-closes the exterior window.

The included gateway is a deterministic contract fixture. The example does **not** claim to drive real hardware.

## Package layout

- `spatialruntime.runtime` - observations, reconciliation, commit gate, RuntimeSession, replay validation
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

The project deliberately keeps perception/reconstruction outside the core runtime. Scene sources are adapters; reviewed spatial semantics and safe execution are the runtime boundary.
