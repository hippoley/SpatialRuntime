# SpatialRuntime Direction

## Mission

SpatialRuntime is a scene-source-neutral **Executable Spatial Runtime**.

Its job is to turn spatial evidence and device state into a reviewed, provenance-preserving world model that can drive:

- room/opening/device topology,
- physics and airflow simulation adapters,
- Agent observations and actions,
- whole-home safety interlocks,
- ThingModel/Gateway dispatch,
- hardware ACK/telemetry/recovery,
- closed-loop state reconciliation.

## Core pipeline

```text
Spatial source (BIM / CAD / floor plan / SLAM / digital twin / authored topology)
      ↓
Spatial geometry + entities
      ↓
Reviewed topology / spatial relations
      ↓
Executable Spatial World Model
      ↓
Physics + sensors + device state
      ↓
Agent / recovery policy
      ↓
Whole-home safety compiler
      ↓
Commit / ThingModel / Gateway
      ↓
Real device
      ↓
Telemetry / feedback
      ↓
Reconciled next world state
```

## Core property

The central property is **evidence-preserving executability**.

Every relation that may eventually affect a real device is classified as one of:

1. explicit source fact,
2. geometry-derived candidate,
3. reviewed relation,
4. transitive derived semantic,
5. operational candidate requiring approval,
6. executable safety/control rule.

The runtime must answer both *what should happen* and *why it is allowed to happen*.

## Non-goals

- Do not silently infer missing safety-critical semantics.
- Do not treat visual similarity as device identity.
- Do not equate Agent intent with executed state.
- Do not equate ACK with physical convergence.
- Do not let recovery logic bypass safety policy.
- Do not reuse spatial/safety bindings after source drift without revalidation.

## North-star demo

A multi-room closed loop where the same world model drives:

1. UI / spatial representation,
2. physics topology and flow paths,
3. Agent observations/actions,
4. safety dependency graph,
5. ThingModel/Gateway commands,
6. device/sensor reconciliation.
