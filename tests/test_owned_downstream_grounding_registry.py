import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "interop" / "owned-downstream-evidence" / "registry.v0.1.json"


def test_owned_downstream_grounding_registry_is_strict():
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert doc["schema"] == "spatialruntime.owned-downstream-grounding.v0.1"
    assert isinstance(doc.get("claim_rules"), list) and doc["claim_rules"]

    entries = doc.get("entries")
    assert isinstance(entries, list) and entries

    ids = []
    for entry in entries:
        ids.append(entry["id"])
        assert entry["relationship"].startswith("owned downstream")
        assert isinstance(entry["repository"], str) and "/" in entry["repository"]
        assert isinstance(entry["revision"], str) and len(entry["revision"]) >= 12
        assert isinstance(entry.get("evidence"), dict) and entry["evidence"]
        assert isinstance(entry.get("claim_ceiling"), list) and entry["claim_ceiling"]

        # This registry is grounding evidence only. Adoption/reproduction claims
        # belong in the external-results registry and must not leak in here.
        assert entry.get("external_consumption") in (None, False)
        assert entry.get("adoption_claim") in (None, False)
        assert entry.get("externally_reproduced") in (None, False)

    assert len(ids) == len(set(ids))
