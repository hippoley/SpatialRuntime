#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

VALID_MODES = {"per_call", "standing"}
VALID_OUTCOMES = {"allow", "deny", "conditional"}
VALID_SCOPE_RESULTS = {"match", "mismatch", "not_checked"}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def verify(doc: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    if doc.get("profile") != "decision-execution-binding.v0.1":
        errors.append({"code": "PROFILE_MISMATCH"})

    decisions = doc.get("decisions")
    executions = doc.get("executions")
    if not isinstance(decisions, list):
        errors.append({"code": "DECISIONS_NOT_LIST"})
        decisions = []
    if not isinstance(executions, list):
        errors.append({"code": "EXECUTIONS_NOT_LIST"})
        executions = []

    decision_by_id: dict[str, dict[str, Any]] = {}
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            errors.append({"code": "INVALID_DECISION", "index": index})
            continue
        decision_id = decision.get("decision_id")
        if not _nonempty(decision_id):
            errors.append({"code": "MISSING_DECISION_ID", "index": index})
            continue
        decision_id = str(decision_id)
        if decision_id in decision_by_id:
            errors.append({"code": "DUPLICATE_DECISION_ID", "decision_id": decision_id})
            continue

        mode = decision.get("binding_mode")
        outcome = decision.get("outcome")
        if mode not in VALID_MODES:
            errors.append({"code": "INVALID_BINDING_MODE", "decision_id": decision_id, "value": mode})
        if outcome not in VALID_OUTCOMES:
            errors.append({"code": "INVALID_DECISION_OUTCOME", "decision_id": decision_id, "value": outcome})
        decision_by_id[decision_id] = decision

    execution_ids: set[str] = set()
    tool_call_ids: set[str] = set()
    binding_counts: Counter[str] = Counter()
    normalized_executions: list[dict[str, Any]] = []

    for index, execution in enumerate(executions):
        if not isinstance(execution, dict):
            errors.append({"code": "INVALID_EXECUTION", "index": index})
            continue

        execution_id = execution.get("execution_id")
        tool_call_id = execution.get("tool_call_id")
        decision_id = execution.get("decision_id")
        scope_binding = execution.get("scope_binding")

        if not _nonempty(execution_id):
            errors.append({"code": "MISSING_EXECUTION_ID", "index": index})
            continue
        execution_id = str(execution_id)
        if execution_id in execution_ids:
            errors.append({"code": "DUPLICATE_EXECUTION_ID", "execution_id": execution_id})
        execution_ids.add(execution_id)

        if not _nonempty(tool_call_id):
            unresolved.append({
                "code": "UNRESOLVED_TOOL_CALL_ID",
                "execution_id": execution_id,
                "reason": "execution cannot be bound to a stable tool-call identity"
            })
        else:
            tool_call_id = str(tool_call_id)
            if tool_call_id in tool_call_ids:
                errors.append({"code": "DUPLICATE_TOOL_CALL_ID", "tool_call_id": tool_call_id})
            tool_call_ids.add(tool_call_id)

        if not _nonempty(decision_id):
            unresolved.append({
                "code": "UNRESOLVED_DECISION_BINDING",
                "execution_id": execution_id,
                "reason": "execution has no authoritative decision reference"
            })
            normalized_executions.append({
                "execution_id": execution_id,
                "tool_call_id": tool_call_id,
                "decision_id": None,
                "scope_binding": scope_binding,
            })
            continue

        decision_id = str(decision_id)
        decision = decision_by_id.get(decision_id)
        if decision is None:
            unresolved.append({
                "code": "UNKNOWN_DECISION_REFERENCE",
                "execution_id": execution_id,
                "decision_id": decision_id,
            })
        else:
            binding_counts[decision_id] += 1
            if decision.get("outcome") == "deny":
                errors.append({
                    "code": "DENIED_DECISION_HAS_EXECUTION",
                    "decision_id": decision_id,
                    "execution_id": execution_id,
                })

        if scope_binding not in VALID_SCOPE_RESULTS:
            errors.append({
                "code": "INVALID_SCOPE_BINDING",
                "execution_id": execution_id,
                "value": scope_binding,
            })
        elif scope_binding == "mismatch":
            errors.append({
                "code": "SCOPE_BINDING_MISMATCH",
                "execution_id": execution_id,
                "decision_id": decision_id,
            })
        elif scope_binding == "not_checked":
            unresolved.append({
                "code": "SCOPE_BINDING_NOT_CHECKED",
                "execution_id": execution_id,
                "decision_id": decision_id,
            })

        normalized_executions.append({
            "execution_id": execution_id,
            "tool_call_id": tool_call_id,
            "decision_id": decision_id,
            "scope_binding": scope_binding,
        })

    for decision_id, count in binding_counts.items():
        decision = decision_by_id.get(decision_id, {})
        if decision.get("binding_mode") == "per_call" and count > 1:
            errors.append({
                "code": "PER_CALL_DECISION_REUSED",
                "decision_id": decision_id,
                "bound_executions": count,
            })

    decision_summaries = [
        {
            "decision_id": did,
            "binding_mode": decision.get("binding_mode"),
            "outcome": decision.get("outcome"),
            "bound_executions": binding_counts.get(did, 0),
        }
        for did, decision in decision_by_id.items()
    ]

    result = "FAIL" if errors else ("UNRESOLVED" if unresolved else "PASS")
    return {
        "profile": "decision-execution-binding.v0.1",
        "result": result,
        "decisions": decision_summaries,
        "executions": normalized_executions,
        "unresolved": unresolved,
        "errors": errors,
        "external_effect_confirmation": False,
        "notes": [
            "Decision identity and tool-call identity are distinct namespaces.",
            "A standing decision may cover multiple executions; a per-call decision may not.",
            "PASS proves only the supplied binding/scope evidence, not that the real-world effect occurred.",
        ],
    }


def write_github_outputs(report: dict[str, Any], path: Path) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"conformance_result={report['result']}\n")
        handle.write(f"unresolved_count={len(report['unresolved'])}\n")
        handle.write(f"error_count={len(report['errors'])}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("claim", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    doc = json.loads(args.claim.read_text(encoding="utf-8"))
    report = verify(doc)
    print(json.dumps(report, indent=2))
    if args.github_output is not None:
        write_github_outputs(report, args.github_output)
    raise SystemExit(1 if report["result"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
