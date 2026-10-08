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


def _walk_otlp(doc: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []

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
    return decisions, executions


def verify(doc: dict[str, Any]) -> dict[str, Any]:
    decisions, executions = _walk_otlp(doc)
    errors: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

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

    for e in executions:
        if e["call_id"]:
            by_call_execs[str(e["call_id"])].append(e)

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
        elif es and not ds:
            status = "EXECUTION_WITHOUT_OBSERVED_DECISION"

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
        "lifecycles": lifecycles,
        "unresolved": unresolved,
        "errors": errors,
        "result": "FAIL" if errors else ("UNRESOLVED" if unresolved else "PASS"),
        "external_effect_confirmation": False,
        "notes": [
            "Missing execute_tool telemetry is not proof of non-execution.",
            "A PASS only validates observed lifecycle correlation; it does not prove authorization correctness or durable external effect."
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("otlp_json", type=Path)
    args = parser.parse_args()
    doc = json.loads(args.otlp_json.read_text(encoding="utf-8"))
    report = verify(doc)
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if report["result"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
