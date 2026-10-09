#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DECISION_EVENT = "gen_ai.tool.call.decision"
OUTCOME_KEY = "gen_ai.tool.call.decision.outcome"
CALL_ID_KEY = "gen_ai.tool.call.id"
OPERATION_KEY = "gen_ai.operation.name"
EXECUTE_TOOL = "execute_tool"
VALID_OUTCOMES = {"allow", "deny", "require_approval"}


def _value(v: Any) -> Any:
    if not isinstance(v, dict):
        return v
    for key in ("stringValue", "boolValue", "intValue", "doubleValue", "bytesValue"):
        if key in v:
            return v[key]
    if "arrayValue" in v:
        vals = v["arrayValue"].get("values", [])
        return [_value(x) for x in vals]
    return v


def _attrs(items: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("key"), str):
            out[item["key"]] = _value(item.get("value"))
    return out


def _walk_otlp(
    doc: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    misplaced: list[dict[str, Any]] = []

    for resource in doc.get("resourceLogs", []) or []:
        for scope in resource.get("scopeLogs", []) or []:
            for record in scope.get("logRecords", []) or []:
                if record.get("eventName") != DECISION_EVENT:
                    continue
                attrs = _attrs(record.get("attributes"))
                decisions.append(
                    {
                        "outcome": attrs.get(OUTCOME_KEY),
                        "call_id": attrs.get(CALL_ID_KEY),
                        "tool_name": attrs.get("gen_ai.tool.name"),
                        "time": record.get("timeUnixNano"),
                    }
                )

    for resource in doc.get("resourceSpans", []) or []:
        for scope in resource.get("scopeSpans", []) or []:
            for span in scope.get("spans", []) or []:
                attrs = _attrs(span.get("attributes"))
                if DECISION_EVENT in attrs or OUTCOME_KEY in attrs:
                    misplaced.append(
                        {
                            "trace_id": span.get("traceId"),
                            "span_id": span.get("spanId"),
                            "keys": [
                                key for key in (DECISION_EVENT, OUTCOME_KEY) if key in attrs
                            ],
                        }
                    )
                if attrs.get(OPERATION_KEY) != EXECUTE_TOOL:
                    continue
                executions.append(
                    {
                        "call_id": attrs.get(CALL_ID_KEY),
                        "tool_name": attrs.get("gen_ai.tool.name"),
                        "trace_id": span.get("traceId"),
                        "span_id": span.get("spanId"),
                    }
                )
    return decisions, executions, misplaced


def verify(doc: dict[str, Any]) -> dict[str, Any]:
    decisions, executions, misplaced = _walk_otlp(doc)
    errors: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for item in misplaced:
        errors.append(
            {
                "code": "MISPLACED_DECISION_SIGNAL",
                "reason": (
                    "gen_ai.tool.call.decision is an event name and "
                    "gen_ai.tool.call.decision.outcome is an event attribute; "
                    "neither belongs on a span as a substitute for the decision event"
                ),
                "trace_id": item.get("trace_id"),
                "span_id": item.get("span_id"),
                "keys": item.get("keys", []),
            }
        )

    if not decisions and not misplaced:
        unresolved.append(
            {
                "code": "NO_DECISION_EVENT_EVIDENCE",
                "reason": "input contains no gen_ai.tool.call.decision log event",
            }
        )

    by_call_decisions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_call_execs: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for i, d in enumerate(decisions):
        if d["outcome"] not in VALID_OUTCOMES:
            errors.append({"code": "INVALID_OUTCOME", "decision_index": i, "value": d["outcome"]})
        if not d["call_id"]:
            unresolved.append(
                {
                    "code": "UNRESOLVED_CORRELATION",
                    "decision_index": i,
                    "reason": "decision event has no gen_ai.tool.call.id",
                    "tool_name": d["tool_name"],
                    "outcome": d["outcome"],
                }
            )
        else:
            by_call_decisions[str(d["call_id"])].append(d)

    for i, e in enumerate(executions):
        if e["call_id"]:
            by_call_execs[str(e["call_id"])].append(e)
        else:
            unresolved.append(
                {
                    "code": "UNRESOLVED_EXECUTION_CORRELATION",
                    "execution_index": i,
                    "reason": "execute_tool span has no gen_ai.tool.call.id",
                    "tool_name": e["tool_name"],
                    "trace_id": e["trace_id"],
                    "span_id": e["span_id"],
                }
            )

    lifecycles: list[dict[str, Any]] = []
    for call_id in sorted(set(by_call_decisions) | set(by_call_execs)):
        ds = by_call_decisions.get(call_id, [])
        es = by_call_execs.get(call_id, [])
        outcomes = [d["outcome"] for d in ds]
        status = "CORRELATED"

        if "deny" in outcomes and es:
            status = "CONTRADICTION"
            errors.append(
                {
                    "code": "DENY_WITH_OBSERVED_EXECUTION",
                    "call_id": call_id,
                    "observed_executions": len(es),
                }
            )
        elif "allow" in outcomes and len(es) > 1:
            status = "CONTRADICTION"
            errors.append(
                {
                    "code": "DUPLICATE_OBSERVED_EXECUTION",
                    "call_id": call_id,
                    "observed_executions": len(es),
                }
            )
        elif "require_approval" in outcomes and "allow" in outcomes and len(es) == 1:
            status = "POSITIVE_PATH_OBSERVED"
        elif "deny" in outcomes and not es:
            status = "NO_EXECUTION_OBSERVED"
        elif "allow" in outcomes and not es:
            status = "ALLOW_WITHOUT_OBSERVED_EXECUTION"
            unresolved.append(
                {"code": "ALLOW_WITHOUT_OBSERVED_EXECUTION", "call_id": call_id}
            )
        elif es and not ds:
            status = "EXECUTION_WITHOUT_OBSERVED_DECISION"
            unresolved.append(
                {
                    "code": "EXECUTION_WITHOUT_OBSERVED_DECISION",
                    "call_id": call_id,
                    "observed_executions": len(es),
                }
            )
        elif "require_approval" in outcomes and "allow" not in outcomes and "deny" not in outcomes:
            status = "APPROVAL_LIFECYCLE_UNRESOLVED"
            unresolved.append(
                {"code": "APPROVAL_LIFECYCLE_UNRESOLVED", "call_id": call_id}
            )

        lifecycles.append(
            {
                "call_id": call_id,
                "decision_outcomes": outcomes,
                "observed_executions": len(es),
                "status": status,
            }
        )

    return {
        "profile": "otel-tool-decision-lifecycle.v0.1",
        "decision_events": len(decisions),
        "execute_tool_spans": len(executions),
        "misplaced_decision_signals": len(misplaced),
        "lifecycles": lifecycles,
        "unresolved": unresolved,
        "errors": errors,
        "result": "FAIL" if errors else ("UNRESOLVED" if unresolved else "PASS"),
        "external_effect_confirmation": False,
        "notes": [
            "Missing execute_tool telemetry is not proof of non-execution.",
            "A PASS only validates observed lifecycle correlation; it does not prove authorization correctness or durable external effect.",
            "No decision evidence is UNRESOLVED, never PASS.",
            "Decision signals placed on spans instead of emitted as events are rejected as semantic drift."
        ],
    }


def write_github_outputs(report: dict[str, Any], path: Path) -> None:
    lines = [
        f"conformance_result={report['result']}",
        f"lifecycle_result={report['result']}",
        f"unresolved_count={len(report['unresolved'])}",
        f"error_count={len(report['errors'])}",
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("otlp_json", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    doc = json.loads(args.otlp_json.read_text(encoding="utf-8"))
    report = verify(doc)
    print(json.dumps(report, indent=2))
    if args.github_output is not None:
        write_github_outputs(report, args.github_output)
    raise SystemExit(1 if report["result"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
