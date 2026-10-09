#!/usr/bin/env python3
"""Deterministic harness self-test adapter.

This is NOT an AAP broker implementation.
"""

import json
import sys

request = json.load(sys.stdin)
case_id = request["case_id"]
scenario = request["scenario"]

if scenario["kind"] == "success":
    response = {
        "case_id": case_id,
        "agent_visible": {"status": "ok", "result": scenario["operation_result"]},
        "audit": {
            "present": True,
            "contains_credential_material": False,
            "integrity_evidence": {
                "kind": "signature",
                "verified": True,
                "key_id": "synthetic-harness-key",
                "record_digest": "sha256:" + "a" * 64,
            },
        },
        "broker_observation": {"decision": "allow", "operation_executed": True},
    }
else:
    response = {
        "case_id": case_id,
        "agent_visible": {"status": "denied", "error": "grant_denied"},
        "audit": {
            "present": True,
            "contains_credential_material": False,
            "integrity_evidence": {
                "kind": "signature",
                "verified": True,
                "key_id": "synthetic-harness-key",
                "record_digest": "sha256:" + "a" * 64,
            },
        },
        "broker_observation": {"decision": "deny", "operation_executed": False},
    }

json.dump(response, sys.stdout)
