#!/usr/bin/env python3
"""Negative adapter: correct deny/allow behavior but audit is not signed."""
import json
import sys

req = json.load(sys.stdin)
scenario = req["scenario"]
success = scenario["kind"] == "success"

json.dump(
    {
        "case_id": req["case_id"],
        "agent_visible": (
            {"status": "ok", "result": scenario.get("operation_result")}
            if success
            else {"status": "denied", "error": "grant_denied"}
        ),
        "audit": {
            "present": True,
            "contains_credential_material": False,
            "integrity_evidence": {
                "kind": "none",
                "verified": False,
                "key_id": None,
                "record_digest": None,
            },
        },
        "broker_observation": {
            "decision": "allow" if success else "deny",
            "operation_executed": success,
        },
    },
    sys.stdout,
)
