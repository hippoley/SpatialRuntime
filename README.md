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

Hard disagreements stop the pipeline before control. Every completed step produces a trace with an integrity hash and an explicit next runtime state.

## Closed-loop example

The repository includes a deterministic Kitchen/Living demo:

```bash
python examples/kitchen_living_closed_loop.py
```

It runs two timesteps:

1. cooking activates the hood and a reviewed make-up-air window action;
2. rain activates a higher-priority safety rule that force-closes the exterior window.

The included gateway is a deterministic contract fixture. The example does **not** claim to drive real hardware.

## Package layout

- `spatialruntime.runtime` - observations, reconciliation, commit gate, RuntimeSession
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
