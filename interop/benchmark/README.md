# Consequential Effects Benchmark v0.1

This benchmark measures the **current executable discrimination and requirement coverage** of SpatialRuntime's consequential-effect conformance corpus.

It is intentionally not a leaderboard and it does not convert pressure evidence into executable proof.

## Why this exists

The repository previously had:

- AEA requirements;
- cross-domain pressure cases;
- executable effect-evidence vectors;
- an external-adapter runner;
- external scorer evidence.

Those artifacts were useful but answered different questions. A raw `11/11 PASS` could not tell a consumer whether all nine AEA requirements were actually exercised by executable cases.

The benchmark separates those questions.

## Four metrics

### 1. Scored executable cases

Only cases in `cases.v0.1.json -> scored_cases` move the implementation result.

Current baseline:

```text
11 / 11 executable cases pass
```

This is not the same as full AEA coverage.

### 2. Executable requirement coverage

A requirement counts only when at least one **scored executable case** explicitly maps to it.

Current baseline:

```text
4 / 9 requirements executable
AEA-002 AEA-005 AEA-006 AEA-009

missing:
AEA-001 AEA-003 AEA-004 AEA-007 AEA-008
```

This is the most important dataset-growth signal. New vectors should preferentially close one of these missing requirements or kill a new realistic mutant.

### 3. Pressure requirement coverage

`case-matrix-v0.1.json` records independently motivated real-world pressure cases.

Current pressure coverage is 9/9 requirements, but **pressure cases are not scored** until an implementation-neutral executable vector exists.

Examples now include:

- lost ACK / physical readback;
- LangGraph replay;
- MCP lost-response retry;
- A2A retry identity;
- LangChain ambiguous transport retry after a committed mutation;
- Google ADK parallel partial-success followed by sibling failure.

### 4. Synthetic discrimination

`mutants.v0.1.json` defines concrete incorrect semantics such as:

- trusting self-declared authority;
- accepting stale readback;
- promoting transport ACK into effect truth;
- accepting pre-attempt observation;
- collapsing conflicting authoritative evidence;
- merging observations from different logical effects.

The benchmark reports whether the scored corpus can distinguish each defect.

These are **synthetic sensitivity controls**, not external implementation results.

## Requirement-set design

The benchmark borrows a mature idea from the MCP conformance project: a released requirement set should be frozen separately from a suite that may continue growing.

MCP's framework distinguishes:

- a frozen requirement set;
- scenarios that keep growing;
- not-scored cases;
- expected failures owned by implementations.

SpatialRuntime uses the same high-level discipline without copying MCP implementation code:

```text
requirements.v0.1.json  -> frozen scoring contract
cases.v0.1.json         -> scored executable mapping
case-matrix-v0.1.json   -> growing pressure corpus, not scored
mutants.v0.1.json       -> benchmark sensitivity controls
```

The MCP conformance package is MIT licensed. This benchmark only adopts the design principle; it does not vendor its runner.

## Running

Built-in reference verifier:

```bash
python interop/benchmark/run_benchmark.py
```

External verifier adapter:

```bash
python interop/benchmark/run_benchmark.py \
  --adapter-command 'python scripts/my_effect_verifier_adapter.py' \
  --report artifacts/consequential-effects-benchmark.json
```

The external command uses the existing `effect-evidence-adapter.v0.1` protocol.

## Dataset admission rule

A new case should be added only when it does at least one of the following:

1. adds executable coverage for a previously uncovered requirement;
2. kills a realistic mutant not killed by the current corpus;
3. represents a materially distinct outcome class or concurrency/recovery topology;
4. is required by an unrelated consumer/upstream conformance issue;
5. converts an independently motivated pressure case into a reproducible executable vector.

Do not add near-duplicate cases merely to increase dataset size.

## Current dataset growth priority

The benchmark reports requirement-level skew instead of treating case count as progress.

Current scored distribution:

```text
AEA-006  10 executable cases
AEA-009   9
AEA-005   2
AEA-002   1
AEA-001   0
AEA-003   0
AEA-004   0
AEA-007   0
AEA-008   0
```

Among requirements with zero executable coverage, current independent pressure counts rank the next work as:

```text
1. AEA-007 retry identity              10 pressure cases
2. AEA-003 prospective effect class     4
3. AEA-004 explicit authorization       4
4. AEA-008 compensation boundary        3
5. AEA-001 proposal != authority        1
```

Therefore the next useful dataset increment is not another evidence-freshness variant. It should preferably convert a real retry-identity pressure case (LangChain/MCP/A2A family) into an implementation-neutral executable vector.

## Promotion rule

Pressure-only case:

```text
real issue / field failure
        ↓
independent motivation recorded
        ↓
implementation-neutral reproduction
        ↓
stable expected semantics
        ↓
executable vector
        ↓
scored in a future requirement-set revision
```

Adding a vector after a benchmark revision is published does not silently change that revision's score. Promotion into a scored set is an explicit benchmark-version change.

## Claim ceiling

A benchmark PASS means:

> all currently scored executable cases matched.

It does **not** mean:

- all AEA requirements are executable;
- universal agent safety;
- exactly-once effects;
- external adoption;
- official MCP/IETF/OpenTelemetry conformance;
- security certification.

The report exposes missing executable requirements precisely so a high pass rate cannot hide incomplete coverage.
