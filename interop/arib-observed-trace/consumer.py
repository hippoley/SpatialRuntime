"""Independent, bounded consumer of ARIB's reported replay effect trace.

Verifies internal consistency in a producer REPORT. It is not a second SDK
execution, a producer authentication, or evidence of contractual exactly-once.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SCENARIO = "ARIB-REPLAY-001"
BACKENDS = {"sqlite", "async-sqlite", "advanced-sqlite", "sqlalchemy"}

class EvidenceError(ValueError):
    pass

def load_strict(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceError("duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(value):
        raise EvidenceError("nonfinite JSON")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, UnicodeError) as exc:
        raise EvidenceError("invalid JSON report") from exc
    if not isinstance(data, dict):
        raise EvidenceError("report not object")
    return data

def check_replay(row):
    if row.get("id") != SCENARIO or row.get("scenario") != "s2":
        raise EvidenceError("wrong scenario")
    if row.get("adapter") not in BACKENDS:
        raise EvidenceError("unknown backend")
    e = row.get("evidence")
    if not isinstance(e, dict) or e.get("evidence_kind") != "observed_effect_trace":
        raise EvidenceError("observed trace not reported")
    n, b, trace = e.get("visible_occurrences"), e.get("authorized_effects"), e.get("effect_trace")
    if type(n) is not int or type(b) is not int or n < 0 or b < 0:
        raise EvidenceError("invalid cardinality")
    if not isinstance(trace, list) or len(trace) != n:
        raise EvidenceError("count/trace mismatch")
    indices, digests = [], set()
    for seq, effect in enumerate(trace, 1):
        if not isinstance(effect, dict) or type(effect.get("seq")) is not int or effect["seq"] != seq:
            raise EvidenceError("sequence missing/out of order")
        idx = effect.get("store_index")
        if type(idx) is not int or idx < 0:
            raise EvidenceError("invalid storage index")
        indices.append(idx)
        if effect.get("effect_key") != "session.history.item":
            raise EvidenceError("different effect identity")
        digest = effect.get("content_digest")
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{12}", digest):
            raise EvidenceError("invalid reported digest")
        digests.add(digest)
    if indices != sorted(set(indices)) or len(digests) > 1:
        raise EvidenceError("duplicate/reordered index or differing content")
    if n < b:
        raise EvidenceError("under-budget outcome unresolved")
    computed = "violated" if n > b else "held"
    if row.get("verdict") != computed:
        raise EvidenceError("verdict contradicts reported effects")
    return {"adapter": row["adapter"], "reported_verdict": computed,
            "observed_count": n, "authorized_budget": b, "trace_consistent": True}

def audit(data):
    if data.get("bench") != "agent-runtime-integrity-bench":
        raise EvidenceError("wrong benchmark")
    version = data.get("environment", {}).get("openai-agents")
    if not isinstance(version, str) or not version:
        raise EvidenceError("runtime version missing")
    findings = data.get("findings")
    if not isinstance(findings, list) or data.get("skipped_adapters"):
        raise EvidenceError("findings absent or adapters skipped")
    selected = [f for f in findings if isinstance(f, dict) and f.get("id") == SCENARIO]
    if len(selected) != 4:
        raise EvidenceError("expected four replay records")
    checked = [check_replay(f) for f in selected]
    if {row["adapter"] for row in checked} != BACKENDS:
        raise EvidenceError("duplicate/missing backend")
    return {"scenario": SCENARIO, "runtime_version": version,
            "adapters": sorted(checked, key=lambda row: row["adapter"]),
            "claim_ceiling": "producer_report_internal_consistency_only",
            "independent_sdk_reexecution": False,
            "producer_identity_authenticated": False,
            "contract_violation_established": False}

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path)
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    try:
        raw = args.report.read_bytes()
        verdict = audit(load_strict(raw))
        verdict["input_sha256"] = hashlib.sha256(raw).hexdigest()
        result = json.dumps(verdict, indent=2, sort_keys=True) + "\n"
        if args.receipt:
            args.receipt.write_text(result, encoding="utf-8")
        print(result)
    except (EvidenceError, OSError) as exc:
        p.exit(2, f"UNRESOLVED: {exc}\n")
