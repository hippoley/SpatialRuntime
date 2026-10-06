from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from spatialruntime.runtime.preflight import (
    PreflightError,
    build_preflight_plan,
    load_preflight_plan,
    save_preflight_plan,
    verify_preflight_plan,
)
from spatialruntime.runtime.replay import (
    ReplayValidationError,
    bundle_hash,
    load_bundle,
    make_bundle,
    save_bundle,
    validate_bundle,
)
from spatialruntime.runtime.scenario_spec import load_scenario_spec, run_scenario_spec
from spatialruntime.scenarios import run_kitchen_living_demo


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _write_or_print_bundle(bundle: dict, output: str | None) -> int:
    report = validate_bundle(bundle)
    if output:
        path = save_bundle(bundle, output)
        payload = {"written": str(path), **report.to_dict()}
    else:
        payload = {"bundle": bundle, "replay": report.to_dict()}
    _print_json(payload)
    return 0


def _run_scenario(args: argparse.Namespace) -> int:
    if args.name != "kitchen-living":
        raise ReplayValidationError(f"unknown scenario: {args.name}")
    result = run_kitchen_living_demo()
    bundle = make_bundle(
        case_id=result["case_id"],
        traces=result["traces"],
        metadata={
            "scenario": args.name,
            "final_step": result["final_step"],
            "final_revision": result["final_revision"],
            "final_runtime_state": result["final_runtime_state"],
            "hardware": "deterministic_contract_fixture",
        },
    )
    return _write_or_print_bundle(bundle, args.output)


def _plan_spec(args: argparse.Namespace) -> int:
    spec = load_scenario_spec(args.path)
    plan = build_preflight_plan(spec)
    if args.output:
        path = save_preflight_plan(plan, args.output)
        _print_json({
            "written": str(path),
            "valid": True,
            "case_id": plan["case_id"],
            "plan_hash": plan["plan_hash"],
            "manifest_hash": plan["execution_manifest"]["manifest_hash"],
        })
    else:
        _print_json(plan)
    return 0


def _run_spec(args: argparse.Namespace) -> int:
    spec = load_scenario_spec(args.path)
    preflight_report = None
    if args.plan:
        plan = load_preflight_plan(args.plan)
        preflight_report = verify_preflight_plan(plan, spec)
    bundle = run_scenario_spec(spec)
    if preflight_report is not None:
        bundle["metadata"]["preflight_plan_hash"] = preflight_report["plan_hash"]
        bundle["metadata"]["preflight_manifest_hash"] = preflight_report["manifest_hash"]
        bundle["bundle_hash"] = bundle_hash(bundle)
    return _write_or_print_bundle(bundle, args.output)


def _replay(args: argparse.Namespace) -> int:
    bundle = load_bundle(args.path)
    report = validate_bundle(bundle)
    _print_json(report.to_dict())
    return 0


def _inspect(args: argparse.Namespace) -> int:
    bundle = load_bundle(args.path)
    report = validate_bundle(bundle)
    rows = []
    for trace in bundle["traces"]:
        safety = (trace.get("stages") or {}).get("safety") or {}
        commit = (trace.get("stages") or {}).get("commit") or {}
        hardware = (trace.get("stages") or {}).get("hardware") or {}
        rows.append({
            "step": trace["step"],
            "revision": trace["revision"],
            "status": trace["status"],
            "safety_forced_entities": safety.get("safety_forced_entities", []),
            "committed": (commit.get("summary") or {}).get("committed", 0),
            "hardware_complete": (hardware.get("device_feedback") or {}).get("complete"),
            "before_state_hash": trace["runtime_state_before_hash"],
            "after_state_hash": trace["next_runtime_state_hash"],
        })
    _print_json({"replay": report.to_dict(), "steps": rows})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spatialruntime",
        description="Evidence-preserving executable spatial runtime.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scenario = sub.add_parser("scenario", help="Run a built-in deterministic scenario.")
    scenario.add_argument("name", choices=["kitchen-living"])
    scenario.add_argument("-o", "--output", help="Write a validated episode bundle JSON file.")
    scenario.set_defaults(func=_run_scenario)

    plan = sub.add_parser("plan", help="Create a pinned preflight execution plan.")
    plan.add_argument("path")
    plan.add_argument("-o", "--output", help="Write the preflight plan JSON file.")
    plan.set_defaults(func=_plan_spec)

    run = sub.add_parser("run", help="Run a scene-source-neutral scenario JSON spec.")
    run.add_argument("path")
    run.add_argument("--plan", help="Require this approved preflight plan before execution.")
    run.add_argument("-o", "--output", help="Write a validated episode bundle JSON file.")
    run.set_defaults(func=_run_spec)

    replay = sub.add_parser("replay", help="Validate a saved episode bundle.")
    replay.add_argument("path")
    replay.set_defaults(func=_replay)

    inspect = sub.add_parser("inspect", help="Validate and summarize a saved episode bundle.")
    inspect.add_argument("path")
    inspect.set_defaults(func=_inspect)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ReplayValidationError, PreflightError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
