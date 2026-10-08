#!/usr/bin/env python3
"""Negative adapter used only to prove the harness rejects context leakage."""
import json
import sys

request = json.load(sys.stdin)
scenario = request["scenario"]

response = {
    "case_id": request["case_id"],
    "agent_visible": {
        "status": "ok" if scenario["kind"] == "success" else "denied",
        "error": "grant_denied" if scenario["kind"] != "success" else None,
        "result": scenario.get("operation_result"),
        "debug_backend": scenario.get("canary_backend"),
        "debug_credential": scenario.get("canary_credential"),
    },
    "audit": {
        "present": True,
        "signed": True,
        "contains_credential_material": False,
    },
    "broker_observation": {
        "decision": "allow" if scenario["kind"] == "success" else "deny",
        "operation_executed": scenario["kind"] == "success",
    },
}
json.dump(response, sys.stdout)
