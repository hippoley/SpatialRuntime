# CF-06 independent-consumer falsification packet (2026-10-14)

**Status:** research and consumer experiment DESIGN ONLY; no independent run, endorsement, adoption, or maintainer acknowledgment is implied.

**Decision:** use the already released neutral GitHub Action at `interop/conformance@conformance-v0.1.0`. Do not start a new agent framework, device gateway, generic observability SDK, or competing protocol. The only question here is whether a repository **unrelated to hippoley** obtains enough practical value from the existing contract to run it in its own CI.

## Falsifiable claim

> On a third-party's existing tool/agent/device-action event history, a pinned conformance profile can discriminate authorization/decision, dispatch/ACK, and authoritative outcome, including unresolved cases, without requiring that project to adopt SpatialRuntime's runtime.

A profile's `PASS` is **not** proof that a physical action happened unless it is supported by authoritative external outcome evidence. A self-authored mapping, green local test, or another hippoley repository does not count as independent adoption.

## Why not rebuild what already exists?

| Adjacent open source | Owns / claims | Boundary worth testing |
| --- | --- | --- |
| [ros-claw/rosclaw](https://github.com/ros-claw/rosclaw) | physical action governance, versioned receipts and simulation / hardware boundaries | Does a separate outcome-evidence checker find a real discrepancy in its existing receipt path? Never claim hardware evidence on its behalf |
| [sint-ai/sint-protocol](https://github.com/sint-ai/sint-protocol) | agent/MCP/industrial security governance and receipt chains | Does a neutral checker expose decision-to-effect evidence ambiguity without duplicating its policy engine? |
| [agentkitai/agentlens](https://github.com/agentkitai/agentlens) | tracing, replay, audit trail and guardrails | Is there a gap between observed tool success and proved external effect that trace replay does not already address? |
| [openma-ai/OpenMatter](https://github.com/openma-ai/OpenMatter) | work events, explicit authority and durable effects | Does a version-pinned independent verifier add value beyond its own effect recovery contract? |

These are **candidate comparison targets, not partnerships or users**. Their current capabilities and contribution policies must be freshly checked before contacting maintainers. Especially where a repository requires human review, never submit AI-authored claims or PRs autonomously.

## Testable acceptance matrix

| Fixture | Required verifier result | Rationale |
| --- | --- | --- |
| Authorization recorded; no dispatch or external observation | UNRESOLVED or equivalent non-PASS | approval is not execution |
| Tool returns success/ACK but no authoritative readback | UNRESOLVED or equivalent non-PASS | ACK is not effect |
| Matching authorized decision, execution identity, time window, and authoritative outcome | PASS only within the selected profile's actual semantics | complete causal linkage |
| Execution linked to wrong decision, object, or expired authorization | FAIL | contradictory authority |
| Missing or conflicting lineage / replay identity | UNRESOLVED or FAIL according to the published profile | incomplete facts cannot become PASS |
| Retried dispatch with ambiguous external outcome | UNRESOLVED until reconciled | prevent double-effect claims |

**Do not assume** every listed vector is already supported by a particular v0.1.0 mode. First map each fixture to the published machine-readable catalog and the mode's documented semantics. A missing check is a coverage gap, **not** evidence of a failing third-party system. Version new checks instead of silently changing released modes.

## Minimum unrelated-consumer experiment

1. Obtain an explicit need or maintainer-approved task from a repository not controlled by hippoley; identify one actual ambiguous effect in its own logs/fixtures.
2. Record upstream URL, issue/PR or written permission, upstream commit SHA, licensing/privacy constraints, and exact reason existing project tests do not settle the question.
3. Reproduce that original case with the upstream's own documented command and retain the unmodified result and failure artifacts.
4. Add the **smallest** opt-in consumer-owned CI job pinning `hippoley/SpatialRuntime/interop/conformance@conformance-v0.1.0` or an immutable SHA. Require `conformance_result == PASS` only for cases the profile can genuinely adjudicate; preserve UNRESOLVED honestly.
5. Include at least one mutated negative and one deliberately unresolved fixture. Archive source SHA, profile/tag resolution, command, runner, exit code, report, artifact ID, and SHA-256 digest.
6. Have an unrelated maintainer run/accept the integration or independently reproduce the result. Record exact evidence in `interop/external-results/registry.v0.1.json` according to its validation contract.
7. Only then evaluate whether issue #14 can close. A PR opened by hippoley, a fork, a green internal workflow, or a courteous maintainer reply are **not** sufficient alone.

## Kill / pivot criteria

After **two substantive, well-matched external attempts**, if there is no consumer run, review, real counterexample, citation, or maintainer-requested work: do not expand the profile catalog; prioritize the established AirTrajectory interactive/physical backlog and seek concrete external failure reports. If established projects already verify the same effect property at lower integration cost, prefer upstream contribution or an adapter over a competing package.

## Evidence ledger for this packet

- **Observed in this repository:** neutral Action, pinned release, documented semantics and existing CF-06 issue #14.
- **Observed in public upstream READMEs:** adjacent projects state overlapping scope; no independent benchmarking was executed in this batch.
- **Not done:** integration, test run, PR to third parties, hardware exercise, third-party validation, adoption claim.
- **Closure scope:** the strategy and falsification design is now explicit; CF-06 and all product/hardware gates remain OPEN/PARTIAL as before.
