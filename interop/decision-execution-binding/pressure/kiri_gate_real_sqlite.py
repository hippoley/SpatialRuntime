"""An actual Kiri Gate SQLite pressure case for SpatialRuntime's existing verifier.

No cross-project adoption is implied. A Kiri-approved effect can be real while
a historical decision->effect identity link is not persisted. This probe MUST
return UNRESOLVED, never a fabricated PASS, from the available SQLite rows.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile

KIRI_COMMIT = "ea32ed25d59204139cac40984f3c28f570bc2cb5"
SOURCE_FILES = ("kiri_gate/gate.py", "kiri_gate/log.py", "kiri_gate/ledger.py")

def verify_binding(document):
    root = Path(__file__).resolve().parents[1] / "verify.py"
    spec = importlib.util.spec_from_file_location("spatialruntime_binding", root)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify(document)

def run():
    from kiri_gate import Answer, DecisionLog, EXTERNAL, Gate
    from kiri_gate.ledger import Ledger

    with tempfile.TemporaryDirectory(prefix="kiri-binding-") as directory:
        base = Path(directory)
        decision_path = base / "decisions.db"
        effect_path = base / "effects.db"
        performed = []

        gate = Gate(ask=lambda request: Answer(approve=True),
                    log=DecisionLog(str(decision_path)),
                    ledger=Ledger(str(effect_path)), scope="interop-test")

        @gate.tool(EXTERNAL)
        def commit_external(ticket: str):
            performed.append(ticket)
            return {"ok": True}

        result = commit_external("incident-42")
        decisions = gate.log.rows()
        with sqlite3.connect(effect_path) as db:
            db.row_factory = sqlite3.Row
            effects = [dict(row) for row in db.execute(
                "SELECT key, tool, state FROM effects ORDER BY key")]
            effect_columns = {row[1] for row in db.execute("PRAGMA table_info(effects)")}
        with sqlite3.connect(decision_path) as db:
            decision_columns = {row[1] for row in db.execute("PRAGMA table_info(decisions)")}

        if len(performed) != 1 or result != {"ok": True}:
            raise AssertionError("actual Kiri external tool was not executed exactly once")
        if len(decisions) != 1 or len(effects) != 1:
            raise AssertionError("expected one persisted decision and one persisted effect")
        if decisions[0]["approved"] != 1 or effects[0]["state"] != "done":
            raise AssertionError("not the approved+completed case under test")
        if "key" in decision_columns or "decision_id" in effect_columns:
            raise AssertionError("Kiri durable schema changed: re-evaluate mapping")

        # Only fields actually available from persistent rows are used.
        # Do not fabricate a decision reference, a tool call ID, or a scope proof.
        document = {
            "profile": "decision-execution-binding.v0.1",
            "decisions": [{
                "decision_id": "kiri-decision-" + str(decisions[0]["id"]),
                "binding_mode": "per_call",
                "outcome": "allow"
            }],
            "executions": [{
                "execution_id": effects[0]["key"],
                "tool_call_id": None,
                "decision_id": None,
                "scope_binding": "not_checked"
            }]
        }
        assessment = verify_binding(document)
        codes = {r["code"] for r in assessment["unresolved"]}
        if assessment["result"] != "UNRESOLVED":
            raise AssertionError("must not infer a historical binding from separate records")
        if not {"UNRESOLVED_DECISION_BINDING", "UNRESOLVED_TOOL_CALL_ID"}.issubset(codes):
            raise AssertionError("expected missing join/tool-call identity findings")
        return {
            "source_repo": "aryan597/kiri-gate", "source_commit": KIRI_COMMIT,
            "case_type": "actual_Kiri_SQLite_records",
            "actual_external_function_invocations": len(performed),
            "persisted_decision_rows": len(decisions),
            "persisted_effect_rows": len(effects),
            "missing_join_key_in_durable_schema": True,
            "conformance_result": assessment["result"],
            "unresolved_codes": sorted(codes),
            "effect_confirmed_by_test_local_callback": True,
            "independent_target_oracle": False,
            "external_project_adoption": False,
            "claim_ceiling": "posthoc_decision_effect_identity_binding_unresolved"
        }

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--receipt", type=Path, required=True)
    args = p.parse_args()
    receipt = run()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
