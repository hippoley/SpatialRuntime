#!/usr/bin/env python3
"""Minimal adapter shape for SpatialRuntime effect-evidence conformance.

Replace the example verdict logic below with your own verifier.
The adapter contract is one JSON object on stdin -> one JSON object on stdout.
"""

import json
import sys

envelope = json.load(sys.stdin)

# The conformance harness provides:
# - protocol
# - suite
# - authority_policy
# - case_id
# - observation OR observations
#
# Call your own implementation here and emit its verdict.
#
# Example:
# verdict = my_verifier(envelope)
#
# This stub intentionally returns an unresolved verdict so copying the file
# cannot accidentally claim conformance before the implementation is wired.
verdict = {
    "status": "UNRESOLVED",
    "reason": "ADAPTER_NOT_IMPLEMENTED",
}

json.dump(verdict, sys.stdout)
