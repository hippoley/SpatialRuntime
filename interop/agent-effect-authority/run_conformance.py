import argparse
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "interop" / "agent-effect-authority"

def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

single = _load("verify_effect_observation", "verify_effect_observation.py")
multi = _load("verify_effect_evidence_set", "verify_effect_evidence_set.py")

def _matches_expected(observed, expected):
    return isinstance(observed, dict) and isinstance(expected, dict) and bool(expected) and all(
        observed.get(key) == value for key, value in expected.items()
    )

def _call_adapter(command, suite_id, policy, case):
    envelope = {
        "protocol": "effect-evidence-adapter.v0.1",
        "suite": suite_id,
        "authority_policy": policy,
        "case_id": case["id"],
    }
    if "observation" in case:
        envelope["observation"] = case["observation"]
    if "observations" in case:
        envelope["observations"] = case["observations"]

    try:
        proc = subprocess.run(
            shlex.split(command),
            input=json.dumps(envelope),
            text=True,
            capture_output=True,
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "ADAPTER_ERROR",
            "reason": "TIMEOUT",
        }
    except (OSError, ValueError) as exc:
        return {
            "status": "ADAPTER_ERROR",
            "reason": "INVOCATION_ERROR",
            "error_type": type(exc).__name__,
        }
    if proc.returncode != 0:
        return {
            "status": "ADAPTER_ERROR",
            "reason": "NONZERO_EXIT",
            "returncode": proc.returncode,
            "stderr": proc.stderr.strip(),
        }

    try:
        verdict = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "status": "ADAPTER_ERROR",
            "reason": "INVALID_JSON",
            "stdout": proc.stdout.strip(),
        }
    if not isinstance(verdict, dict) or not isinstance(verdict.get("status"), str):
        return {
            "status": "ADAPTER_ERROR",
            "reason": "INVALID_VERDICT_SHAPE",
        }
    return verdict

def _builtin_observe(suite_id, policy, case):
    if suite_id == "iev-adversarial-v0.1":
        return single.evaluate_observation(case["observation"], policy)
    if suite_id == "authentic-evidence-conflict-v0.1":
        return multi.evaluate_evidence_set(case["observations"], policy)
    raise ValueError(f"unsupported suite: {suite_id}")

def _run_suite(results, suite_id, vector_file, adapter_command=None):
    payload = json.loads((BASE / vector_file).read_text(encoding="utf-8"))
    policy = payload["authority_policy"]
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{vector_file}: benchmark must contain nonempty cases")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"].strip():
            raise ValueError(f"{vector_file}: invalid case identity")
        if case["id"] in seen:
            raise ValueError(f"{vector_file}: duplicate case id: {case['id']}")
        seen.add(case["id"])
        expected = case.get("expected")
        if not isinstance(expected, dict) or not expected or not isinstance(expected.get("status"), str):
            raise ValueError(f"{vector_file}/{case['id']}: invalid expected verdict")

    for case in cases:
        observed = (
            _call_adapter(adapter_command, suite_id, policy, case)
            if adapter_command
            else _builtin_observe(suite_id, policy, case)
        )
        results.append({
            "suite": suite_id,
            "case_id": case["id"],
            "expected": case["expected"],
            "observed": observed,
            "pass": _matches_expected(observed, case["expected"]),
        })

def run(adapter_command=None):
    results = []
    _run_suite(results, "iev-adversarial-v0.1", "iev-adversarial-vectors.v0.1.json", adapter_command)
    _run_suite(results, "authentic-evidence-conflict-v0.1", "authentic-evidence-conflict-v0.1.json", adapter_command)

    passed = sum(1 for row in results if row["pass"])
    return {
        "conformance_bundle": "effect-evidence-v0.1",
        "adapter_protocol": "effect-evidence-adapter.v0.1",
        "adapter_mode": bool(adapter_command),
        "passed": passed,
        "failed": len(results) - passed,
        "total": len(results),
        "results": results,
    }

def _write_github_outputs(summary, path, report_path=None):
    result = "PASS" if summary["failed"] == 0 else "FAIL"
    lines = [
        f"conformance_result={result}",
        f"passed_count={summary['passed']}",
        f"failed_count={summary['failed']}",
        f"total_count={summary['total']}",
    ]
    if report_path:
        lines.append(f"report_path={report_path}")
    Path(path).open("a", encoding="utf-8").write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--adapter-command",
        help=(
            "External verifier command. The harness writes one JSON envelope to "
            "stdin per vector and expects one JSON verdict on stdout."
        ),
    )
    parser.add_argument(
        "--github-output",
        help="Optional GitHub Actions output file for structured conformance summary.",
    )
    parser.add_argument(
        "--report",
        help="Optional path for a durable machine-readable JSON run report.",
    )
    args = parser.parse_args()

    summary = run(adapter_command=args.adapter_command)
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    print(rendered)
    report_path = None
    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(rendered + "\n", encoding="utf-8")
        report_path = str(report)
    if args.github_output:
        _write_github_outputs(summary, args.github_output, report_path)
    raise SystemExit(0 if summary["failed"] == 0 else 1)

if __name__ == "__main__":
    main()
