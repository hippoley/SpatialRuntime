from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from spatialruntime.runtime.replay import (
    ReplayValidationError,
    load_bundle,
    make_bundle,
    save_bundle,
    validate_bundle,
)
from spatialruntime.scenarios import run_kitchen_living_demo


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


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
    report = validate_bundle(bundle)
    if args.output:
        path = save_bundle(bundle, args.output)
        payload = {"written": str(path), **report.to_dict()}
    else:
        payload = {"bundle": bundle, "replay": report.to_dict()}
    _print_json(payload)
    return 0


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
    except ReplayValidationError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
