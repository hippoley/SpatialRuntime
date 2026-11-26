"""Fetch the ARIB published report by immutable commit and Git blob."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from consumer import audit, load_strict

UPSTREAM = "https://github.com/tonydzi/agent-runtime-integrity-bench.git"
COMMIT = "c7b9ba15c3cde310a25b9d4249fcc8e3ff0d63d9"
PATH = "results/2026-10-09-openai-agents-0.23.1.json"
BLOB = "2ff221747058c97139f837238e07d39a74133a15"

def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          text=True, capture_output=True, timeout=150).stdout.strip()

def verify():
    with tempfile.TemporaryDirectory(prefix="arib-pinned-") as root:
        cwd = Path(root)
        git(cwd, "init", "--quiet")
        git(cwd, "remote", "add", "origin", UPSTREAM)
        git(cwd, "fetch", "--quiet", "--depth", "1", "origin", COMMIT)
        if git(cwd, "rev-parse", "FETCH_HEAD") != COMMIT:
            raise ValueError("upstream commit changed")
        if git(cwd, "rev-parse", "FETCH_HEAD:" + PATH) != BLOB:
            raise ValueError("upstream report Git blob mismatch")
        raw = subprocess.run(["git", "show", "FETCH_HEAD:" + PATH], cwd=cwd,
                             check=True, capture_output=True, timeout=120).stdout
    return audit(load_strict(raw))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=Path("arib-report-audit.json"))
    args = parser.parse_args()
    result = verify()
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
