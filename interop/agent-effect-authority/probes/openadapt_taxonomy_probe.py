import json

from openadapt_flow.runtime.effects.adapter import (
    AdapterResult,
    reconciliation_required,
    transaction_outcome_for,
)
from openadapt_flow.transaction import TransactionOutcome


def main() -> None:
    rows = []

    expected = {
        AdapterResult.CONFIRMED: {
            "neutral": "confirmed",
            "reconciliation_required": False,
            "transaction_outcome": None,
        },
        AdapterResult.REFUTED: {
            "neutral": "contradicted-or-absent",
            "reconciliation_required": False,
            "transaction_outcome": "HALTED_BEFORE_EFFECT",
        },
        AdapterResult.UNAVAILABLE: {
            "neutral": "unresolved",
            "reconciliation_required": True,
            "transaction_outcome": "RECONCILIATION_REQUIRED",
        },
        AdapterResult.STALE: {
            "neutral": "unresolved",
            "reconciliation_required": True,
            "transaction_outcome": "RECONCILIATION_REQUIRED",
        },
        AdapterResult.CONFLICTING: {
            "neutral": "conflict",
            "reconciliation_required": True,
            "transaction_outcome": "RECONCILIATION_REQUIRED",
        },
        AdapterResult.INDETERMINATE: {
            "neutral": "unresolved",
            "reconciliation_required": True,
            "transaction_outcome": "RECONCILIATION_REQUIRED",
        },
    }

    for native, exp in expected.items():
        actual_reconcile = reconciliation_required(native)
        outcome = transaction_outcome_for(native)
        actual_outcome = outcome.value if isinstance(outcome, TransactionOutcome) else None

        assert actual_reconcile is exp["reconciliation_required"], native
        assert actual_outcome == exp["transaction_outcome"], native

        rows.append(
            {
                "native": native.value,
                "neutral": exp["neutral"],
                "reconciliation_required": actual_reconcile,
                "transaction_outcome": actual_outcome,
                "pass": True,
            }
        )

    assert all(
        row["reconciliation_required"]
        for row in rows
        if row["native"] in {"unavailable", "stale", "conflicting", "indeterminate"}
    )

    report = {
        "implementation": "OpenAdaptAI/openadapt-flow",
        "probe": "effect-evidence-taxonomy-v0.1",
        "audit_kind": "executed",
        "rows": rows,
        "passed": len(rows),
        "failed": 0,
        "total": len(rows),
        "nonclaims": [
            "This probe executes a pinned public OpenAdapt commit.",
            "It validates only the effect-verifier taxonomy boundary exercised here.",
            "It does not imply OpenAdapt adoption of SpatialRuntime.",
        ],
    }

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
