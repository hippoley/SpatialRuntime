import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "interop" / "agent-effect-authority"
VERIFY = BASE / "verify_semantic_mapping.py"
NARADA = BASE / "mappings" / "narada.v0.1.json"
LANGGRAPH = BASE / "mappings" / "langgraph.v0.1.json"


def run(path: Path):
    return subprocess.run(
        [sys.executable, str(VERIFY), str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_narada_mapping_envelope_passes():
    result = run(NARADA)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["mapping_envelope"] == "PASS"
    assert report["source"]["repository"] == "narada-core/narada"
    assert report["source_project_adoption"] is False
    assert report["semantic_truth_verified"] is False
    assert report["targets"] >= 10


def test_mapping_rejects_adoption_claim(tmp_path: Path):
    doc = json.loads(NARADA.read_text(encoding="utf-8"))
    doc["declaration"]["source_project_adoption"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    result = run(path)
    assert result.returncode != 0
    assert "source_project_adoption must be false" in result.stderr


def test_mapping_rejects_duplicate_target(tmp_path: Path):
    doc = json.loads(NARADA.read_text(encoding="utf-8"))
    doc["mappings"].append(dict(doc["mappings"][0]))
    path = tmp_path / "dup.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    result = run(path)
    assert result.returncode != 0
    assert "duplicate target" in result.stderr


def test_langgraph_mapping_envelope_passes():
    result = run(LANGGRAPH)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["mapping_envelope"] == "PASS"
    assert report["source"]["repository"] == "langchain-ai/langgraph"
    assert report["source_project_adoption"] is False
    assert report["relations"]["source_weaker"] >= 1
    assert report["relations"]["orthogonal"] >= 1
