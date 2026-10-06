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
- unreviewed rule/source drift fails closed
- durable ledgers survive restart and detect tampering

## Package layout

- `spatialruntime.runtime` - observations, reconciliation, commit gate
- `spatialruntime.hardware` - command contracts, Gateway, telemetry, ThingModel binding
- `spatialruntime.safety` - arbitration, recovery, supervisor, dependency graph
- `spatialruntime.spatial` - relation resolution, review, promotion and compile lineage
- `spatialruntime.world` - scene-source-neutral world snapshot contract

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

The initial extraction preserves the battle-tested runtime modules while removing the original scene-reconstruction bridge from the core project.
