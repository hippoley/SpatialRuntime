import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "interop" / "agent-effect-authority" / "case-matrix-v0.1.json"
MANIFEST = ROOT / "interop" / "agent-effect-authority" / "manifest.json"


def test_case_matrix_covers_every_aea_requirement():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    expected = {row["id"] for row in manifest["requirements"]}
    observed = set()

    for domain in matrix["domains"]:
        assert domain["reference"].startswith("https://")
        assert domain["pressure_cases"]
        for case in domain["pressure_cases"]:
            assert case["case"]
            assert case["invariant"]
            observed.update(case["requirements"])

    assert observed == expected


def test_case_matrix_spans_multiple_domains():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    ids = {domain["id"] for domain in matrix["domains"]}
    assert {
        "physical-control",
        "durable-agent-observability",
        "release-governance",
    } <= ids
