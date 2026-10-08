import json
from pathlib import Path
import sys


NON_AUTHORITATIVE_KINDS = {
    "model_estimate",
    "transport_ack",
    "cached_state",
    "unprovenanced",
}
TRUSTED_LEVELS = {"attested", "verified"}


def _normalized(value):
    return str(value or "").strip()


def _find_registry_entry(claim, policy):
    if not isinstance(policy, dict):
        return None

    entries = policy.get("verified_evidence", [])
    if not isinstance(entries, list):
        return None

    match_fields = (
        "logical_effect_id",
        "attempt_id",
        "evidence_id",
        "evidence_digest",
        "effect_domain",
        "source_id",
        "observation_kind",
        "verdict",
    )
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if all(
            _normalized(entry.get(field)).lower()
            == _normalized(claim.get(field)).lower()
            for field in match_fields
        ):
            return entry
    return None


def evaluate_observation(claim, authority_policy):
    required = {
        "logical_effect_id",
        "attempt_id",
        "evidence_id",
        "evidence_digest",
        "effect_domain",
        "source_id",
        "observation_kind",
        "verdict",
    }
    missing = sorted(
        field for field in required if not _normalized(claim.get(field))
    )
    if missing:
        return {
            "status": "UNRESOLVED",
            "reason": "MISSING_FIELDS",
            "missing": missing,
        }

    kind = _normalized(claim["observation_kind"]).lower()
    if kind in NON_AUTHORITATIVE_KINDS:
        return {
            "status": "UNRESOLVED",
            "reason": "NON_AUTHORITATIVE_KIND",
        }

    entry = _find_registry_entry(claim, authority_policy)
    if entry is None:
        return {
            "status": "UNRESOLVED",
            "reason": "EVIDENCE_NOT_VERIFIED",
        }

    verifier_id = _normalized(entry.get("verifier_id"))
    if not verifier_id:
        return {
            "status": "UNRESOLVED",
            "reason": "VERIFIER_MISSING",
        }

    trust = _normalized(entry.get("trust")).lower()
    if trust not in TRUSTED_LEVELS:
        return {
            "status": "UNRESOLVED",
            "reason": "INSUFFICIENT_TRUST",
        }

    invalidation = _normalized(entry.get("invalidation")).lower()
    if invalidation != "valid":
        return {
            "status": "UNRESOLVED",
            "reason": "EVIDENCE_INVALIDATED",
        }

    if entry.get("observed_after_attempt") is not True:
        return {
            "status": "UNRESOLVED",
            "reason": "NOT_POST_ATTEMPT",
        }

    if entry.get("fresh") is not True:
        return {
            "status": "UNRESOLVED",
            "reason": "NOT_FRESH",
        }

    verdict = _normalized(entry.get("verdict")).upper()
    if verdict not in {"CONFIRMED", "CONTRADICTED", "UNRESOLVED"}:
        raise ValueError("unsupported verdict")

    return {
        "status": verdict,
        "reason": "TRUSTED_EVIDENCE",
        "evidence_id": _normalized(entry.get("evidence_id")),
        "verifier_id": verifier_id,
        "trust": trust,
    }


def main(claim_path, policy_path):
    claim = json.loads(Path(claim_path).read_text(encoding="utf-8"))
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    print(json.dumps(evaluate_observation(claim, policy), sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
