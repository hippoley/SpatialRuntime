#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

VALID_MODES = {"per_call", "standing"}
VALID_OUTCOMES = {"allow", "deny", "conditional"}
VALID_SCOPE_RESULTS = {"match", "mismatch", "not_checked"}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _time(value: Any) -> datetime | None:
    if not _nonempty(value):
        return None
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def verify(doc: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    if doc.get("profile") != "decision-execution-binding.v0.2":
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
    decision_times: dict[str, tuple[datetime | None, datetime | None]] = {}

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

        decided_at_raw = decision.get("decided_at")
        valid_until_raw = decision.get("valid_until")
        decided_at = _time(decided_at_raw)
        valid_until = _time(valid_until_raw)

        if decided_at_raw is not None and decided_at is None:
            errors.append({"code": "INVALID_DECIDED_AT", "decision_id": decision_id})
        if valid_until_raw is not None and valid_until is None:
            errors.append({"code": "INVALID_VALID_UNTIL", "decision_id": decision_id})
        if decided_at is not None and valid_until is not None and valid_until <= decided_at:
            errors.append({"code": "INVALID_DECISION_WINDOW", "decision_id": decision_id})

        decision_by_id[decision_id] = decision
        decision_times[decision_id] = (decided_at, valid_until)

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
        started_at_raw = execution.get("started_at")
        started_at = _time(started_at_raw)

        if not _nonempty(execution_id):
            errors.append({"code": "MISSING_EXECUTION_ID", "index": index})
            continue
        execution_id = str(execution_id)
        if execution_id in execution_ids:
            errors.append({"code": "DUPLICATE_EXECUTION_ID", "execution_id": execution_id})
        execution_ids.add(execution_id)

        if started_at_raw is not None and started_at is None:
            errors.append({"code": "INVALID_EXECUTION_STARTED_AT", "execution_id": execution_id})

        if not _nonempty(tool_call_id):
            unresolved.append({
                "code": "UNRESOLVED_TOOL_CALL_ID",
                "execution_id": execution_id,
                "reason": "execution cannot be bound to a stable execution-attempt identity",
            })
        else:
            tool_call_id = str(tool_call_id)
            if tool_call_id in tool_call_ids:
                errors.append({"code": "DUPLICATE_TOOL_CALL_ID", "tool_call_id": tool_call_id})
            tool_call_ids.add(tool_call_id)

        decision: dict[str, Any] | None = None
        if not _nonempty(decision_id):
            unresolved.append({
                "code": "UNRESOLVED_DECISION_BINDING",
                "execution_id": execution_id,
                "reason": "execution has no authoritative decision reference",
            })
            decision_id = None
        else:
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

                decided_at, valid_until = decision_times.get(decision_id, (None, None))
                if decided_at is not None:
                    if started_at is None:
                        unresolved.append({
                            "code": "EXECUTION_START_TIME_NOT_EVIDENCED",
                            "decision_id": decision_id,
                            "execution_id": execution_id,
                        })
                    elif started_at < decided_at:
                        errors.append({
                            "code": "EXECUTION_PRECEDES_DECISION",
                            "decision_id": decision_id,
                            "execution_id": execution_id,
                        })
                if valid_until is not None:
                    if started_at is None:
                        unresolved.append({
                            "code": "DECISION_EXPIRY_NOT_CHECKABLE",
                            "decision_id": decision_id,
                            "execution_id": execution_id,
                        })
                    elif started_at >= valid_until:
                        errors.append({
                            "code": "DECISION_EXPIRED_BEFORE_EXECUTION",
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
            "started_at": started_at_raw,
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
            "decided_at": decision.get("decided_at"),
            "valid_until": decision.get("valid_until"),
            "bound_executions": binding_counts.get(did, 0),
        }
        for did, decision in decision_by_id.items()
    ]

    result = "FAIL" if errors else ("UNRESOLVED" if unresolved else "PASS")
    return {
        "profile": "decision-execution-binding.v0.2",
        "result": result,
        "decisions": decision_summaries,
        "executions": normalized_executions,
        "unresolved": unresolved,
        "errors": errors,
        "external_effect_confirmation": False,
        "notes": [
            "Decision identity and execution-attempt identity are distinct namespaces.",
            "A per-call decision may bind at most one execution attempt.",
            "When a decision carries a validity window, execution start must be evidenced inside that window.",
            "PASS proves supplied decision/execution binding evidence, not authoritative real-world effect completion.",
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
