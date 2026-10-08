import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "interop" / "agent-effect-authority" / "run_conformance.py"

SPEC = importlib.util.spec_from_file_location("run_effect_evidence_conformance", RUNNER)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_external_adapter_can_run_full_bundle(tmp_path):
    adapter = tmp_path / "adapter.py"
    adapter.write_text("import json\nimport sys\n\npayload = json.load(sys.stdin)\ncase_id = payload[\"case_id\"]\n\nexpected = {\n    \"physical-authoritative-positive\": {\n        \"status\": \"CONFIRMED\",\n        \"reason\": \"AUTHORITATIVE_OBSERVATION\",\n    },\n    \"self-declared-authority-rejected\": {\n        \"status\": \"UNRESOLVED\",\n        \"reason\": \"SOURCE_NOT_AUTHORIZED\",\n    },\n    \"wrong-predicate-source-rejected\": {\n        \"status\": \"UNRESOLVED\",\n        \"reason\": \"SOURCE_NOT_AUTHORIZED\",\n    },\n    \"stale-authoritative-source-still-unresolved\": {\n        \"status\": \"UNRESOLVED\",\n        \"reason\": \"NOT_FRESH\",\n    },\n    \"transport-ack-cannot-prove-effect\": {\n        \"status\": \"UNRESOLVED\",\n        \"reason\": \"NON_AUTHORITATIVE_KIND\",\n    },\n    \"pre-attempt-observation-cannot-resolve\": {\n        \"status\": \"UNRESOLVED\",\n        \"reason\": \"NOT_POST_ATTEMPT\",\n    },\n    \"two-authoritative-sources-agree-confirmed\": {\n        \"status\": \"CONFIRMED\",\n        \"reason\": \"CONSISTENT_AUTHORITATIVE_EVIDENCE\",\n    },\n    \"two-authoritative-sources-conflict\": {\n        \"status\": \"CONFLICT\",\n        \"reason\": \"AUTHENTIC_EVIDENCE_CONFLICT\",\n        \"ordinary_continuation\": False,\n    },\n    \"different-effect-ids-cannot-be-combined\": {\n        \"status\": \"INDETERMINATE\",\n        \"reason\": \"EFFECT_ID_SET_MISMATCH\",\n    },\n}\n\njson.dump(expected[case_id], sys.stdout)\n", encoding="utf-8")

    summary = module.run(
        adapter_command=f"{sys.executable} {adapter}"
    )

    assert summary["adapter_mode"] is True
    assert summary["failed"] == 0
    assert summary["passed"] == summary["total"]
    assert summary["total"] >= 9


def test_expected_fields_allow_adapter_extra_metadata(tmp_path):
    adapter = tmp_path / "adapter.py"
    adapter.write_text(
        "import json,sys\n"
        "payload=json.load(sys.stdin)\n"
        "cid=payload['case_id']\n"
        "mapping={\n"
        "'physical-authoritative-positive':('CONFIRMED','AUTHORITATIVE_OBSERVATION'),\n"
        "'self-declared-authority-rejected':('UNRESOLVED','SOURCE_NOT_AUTHORIZED'),\n"
        "'wrong-predicate-source-rejected':('UNRESOLVED','SOURCE_NOT_AUTHORIZED'),\n"
        "'stale-authoritative-source-still-unresolved':('UNRESOLVED','NOT_FRESH'),\n"
        "'transport-ack-cannot-prove-effect':('UNRESOLVED','NON_AUTHORITATIVE_KIND'),\n"
        "'pre-attempt-observation-cannot-resolve':('UNRESOLVED','NOT_POST_ATTEMPT'),\n"
        "'two-authoritative-sources-agree-confirmed':('CONFIRMED','CONSISTENT_AUTHORITATIVE_EVIDENCE'),\n"
        "'two-authoritative-sources-conflict':('CONFLICT','AUTHENTIC_EVIDENCE_CONFLICT'),\n"
        "'different-effect-ids-cannot-be-combined':('INDETERMINATE','EFFECT_ID_SET_MISMATCH')}\n"
        "status,reason=mapping[cid]\n"
        "out={'status':status,'reason':reason,'adapter':'third-party'}\n"
        "if cid=='two-authoritative-sources-conflict': out['ordinary_continuation']=False\n"
        "json.dump(out,sys.stdout)\n",
        encoding="utf-8",
    )

    summary = module.run(
        adapter_command=f"{sys.executable} {adapter}"
    )
    assert summary["failed"] == 0
