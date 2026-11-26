"""Compare two independently consumed ARIB reports without inventing release improvement.

Inputs must be receipts from our ARIB consumer. This checks reported evidence
differences only; it neither replays SDK nor proves contractual obligations.
"""
import argparse
import hashlib
import json
from pathlib import Path

from consumer import audit as audit_report, load_strict as load_report, EvidenceError

BACKENDS = {"sqlite", "async-sqlite", "advanced-sqlite", "sqlalchemy"}
SOURCE = "c7b9ba15c3cde310a25b9d4249fcc8e3ff0d63d9"

class ComparisonError(ValueError):
    pass

def review(receipt):
    if not isinstance(receipt, dict):
        raise ComparisonError("receipt must be object")
    if not isinstance(receipt.get("input_sha256"), str) or len(receipt["input_sha256"]) != 64:
        raise ComparisonError("report SHA-256 absent")
    if receipt.get("arib_source_commit") != SOURCE:
        raise ComparisonError("upstream benchmark source not pinned")
    if receipt.get("sdk_execution") != "real_sdk_using_upstream_benchmark":
        raise ComparisonError("not an actually replayed SDK report")
    if receipt.get("independent_storage_observer") is not False:
        raise ComparisonError("independent storage observer claim missing")
    if receipt.get("contract_violation_established") is not False:
        raise ComparisonError("unjustified contract violation claim")
    if receipt.get("scenario") != "ARIB-REPLAY-001":
        raise ComparisonError("wrong scenario")
    version = receipt.get("runtime_version")
    if not isinstance(version, str) or not version:
        raise ComparisonError("missing runtime version")
    records = receipt.get("adapters")
    if not isinstance(records, list) or len(records) != 4:
        raise ComparisonError("must include four backends")
    byname = {}
    for row in records:
        if not isinstance(row, dict):
            raise ComparisonError("malformed backend")
        name = row.get("adapter")
        if name not in BACKENDS or name in byname:
            raise ComparisonError("unknown/duplicate backend")
        n,b = row.get("observed_count"),row.get("authorized_budget")
        if type(n) is not int or type(b) is not int or n < 0 or b != 1:
            raise ComparisonError("unexpected effect budget or count")
        if row.get("trace_consistent") is not True:
            raise ComparisonError("trace has not passed consumer check")
        expected = "violated" if n > b else ("held" if n == b else None)
        if expected is None or row.get("reported_verdict") != expected:
            raise ComparisonError("inconsistent reported verdict")
        byname[name] = (n,b,expected)
    if set(byname) != BACKENDS:
        raise ComparisonError("missing backend")
    return version,byname

def bind_report(receipt, raw):
    """Rejudge fresh/raw producer bytes; don't trust receipt self-assertions."""
    if not isinstance(raw, bytes):
        raise ComparisonError("raw report is required")
    digest = hashlib.sha256(raw).hexdigest()
    if receipt.get("input_sha256") != digest:
        raise ComparisonError("receipt/report SHA-256 binding mismatch")
    try:
        independently_checked = audit_report(load_report(raw))
    except (EvidenceError, ValueError) as exc:
        raise ComparisonError("raw report independent replay failed") from exc
    if independently_checked.get("runtime_version") != receipt.get("runtime_version"):
        raise ComparisonError("runtime version contradicts original report")
    if independently_checked.get("adapters") != receipt.get("adapters"):
        raise ComparisonError("consumer verdict contradicts original report")

def compare(left,right,left_raw=None,right_raw=None):
    if left_raw is None or right_raw is None:
        raise ComparisonError("both original benchmark reports required")
    bind_report(left,left_raw)
    bind_report(right,right_raw)
    ver_l,old=review(left);ver_r,new=review(right)
    if ver_l==ver_r:
        raise ComparisonError("same SDK version")
    diff=[]
    for adapter in sorted(BACKENDS):
        a,b=old[adapter],new[adapter]
        diff.append({"adapter":adapter,
                     "baseline":{"observed":a[0],"budget":a[1],"verdict":a[2]},
                     "candidate":{"observed":b[0],"budget":b[1],"verdict":b[2]},
                     "behavior_changed":a!=b})
    return {"baseline_version":ver_l,"candidate_version":ver_r,
            "arib_source_commit":SOURCE,"scenario":"ARIB-REPLAY-001",
            "changes_detected":sum(v["behavior_changed"] for v in diff),
            "comparisons":diff,
            "claim_ceiling":"difference_between_two_real_arib_sdk_test_reports",
            "contractual_exactly_once": "NOT_EVALUATED",
            "independent_storage_observation":False,
            "third_party_adoption":"NOT_EVIDENCED"}

def read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,UnicodeError,ValueError) as e:
        raise ComparisonError("unreadable/invalid receipt") from e

if __name__ == "__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("baseline");cli.add_argument("candidate")
    cli.add_argument("--baseline-report", required=True)
    cli.add_argument("--candidate-report", required=True)
    cli.add_argument("--out",required=True)
    args=cli.parse_args()
    try:
        output=compare(read(args.baseline),read(args.candidate),
                       Path(args.baseline_report).read_bytes(),
                       Path(args.candidate_report).read_bytes())
        Path(args.out).write_text(json.dumps(output,sort_keys=True,indent=2)+"\n")
        print(json.dumps(output,sort_keys=True))
    except (ComparisonError, OSError) as exc:
        cli.exit(2,f"UNRESOLVED: {exc}\n")
