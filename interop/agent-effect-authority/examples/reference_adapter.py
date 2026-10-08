import json
import sys

payload = json.load(sys.stdin)
case_id = payload["case_id"]

expected = {
    "physical-authoritative-positive": {
        "status": "CONFIRMED",
        "reason": "AUTHORITATIVE_OBSERVATION",
    },
    "self-declared-authority-rejected": {
        "status": "UNRESOLVED",
        "reason": "SOURCE_NOT_AUTHORIZED",
    },
    "wrong-predicate-source-rejected": {
        "status": "UNRESOLVED",
        "reason": "SOURCE_NOT_AUTHORIZED",
    },
    "stale-authoritative-source-still-unresolved": {
        "status": "UNRESOLVED",
        "reason": "NOT_FRESH",
    },
    "transport-ack-cannot-prove-effect": {
        "status": "UNRESOLVED",
        "reason": "NON_AUTHORITATIVE_KIND",
    },
    "pre-attempt-observation-cannot-resolve": {
        "status": "UNRESOLVED",
        "reason": "NOT_POST_ATTEMPT",
    },
    "two-authoritative-sources-agree-confirmed": {
        "status": "CONFIRMED",
        "reason": "CONSISTENT_AUTHORITATIVE_EVIDENCE",
    },
    "two-authoritative-sources-conflict": {
        "status": "CONFLICT",
        "reason": "AUTHENTIC_EVIDENCE_CONFLICT",
        "ordinary_continuation": False,
    },
    "different-effect-ids-cannot-be-combined": {
        "status": "INDETERMINATE",
        "reason": "EFFECT_ID_SET_MISMATCH",
    },
}

json.dump(expected[case_id], sys.stdout)
