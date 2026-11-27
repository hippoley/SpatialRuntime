"""Conservative remote-adoption gate: a registry declaration is not adoption.

A qualifying case requires a successful GitHub Actions run in an *unrelated*
repository, and its workflow definition pinned to an immutable SpatialRuntime
revision. GitHub API data is consulted ONLY for candidates. Network failures
are unresolved and cannot close the gate.
"""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from urllib.parse import quote, urlparse

REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
WORKFLOW = re.compile(r"^\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$")
USE = re.compile(r"(?m)^\s*-?\s*uses:\s*['\"]?hippoley/SpatialRuntime/interop/conformance@([0-9a-f]{40})['\"]?\s*(?:#.*)?$")
MAX_BYTES = 1000000

# A string that looks like a YAML Action inside a shell block is NOT a
# workflow step. Mask block scalar contents before searching for any step.
BLOCK_SCALAR = re.compile(r"^(\s*)(?:[A-Za-z_][A-Za-z0-9_-]*):\s*[|>][+-]?\s*(?:#.*)?$")


def _source_has_named_action(source: str, step_name: str, revision: str) -> bool:
    """Fail closed outside simple unambiguous name/uses workflow-step syntax.

    This intentionally is not a general YAML parser. Unsupported or ambiguous
    workflow syntax must not close the external-adoption gate.
    """
    original_lines = source.splitlines()
    lines = []
    scalar_indent = None
    for line in original_lines:
        indent = len(line) - len(line.lstrip(" "))
        if scalar_indent is not None:
            if not line.strip() or indent > scalar_indent:
                lines.append("")
                continue
            scalar_indent = None
        scalar = BLOCK_SCALAR.fullmatch(line)
        if scalar:
            scalar_indent = len(scalar.group(1))
        lines.append(line)

    candidates = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r"(\s*)-\s*name:\s*['\"]?(.+?)['\"]?\s*", line)
        if not match or match.group(2).strip("'\" ") != step_name:
            continue
        indent = len(match.group(1))
        direct = []
        for following in lines[index + 1:]:
            if not following.strip():
                continue
            level = len(following) - len(following.lstrip(" "))
            if level <= indent:
                break
            if level == indent + 2:
                direct.append(following)
        uses = [line for line in direct if re.match(r"^\s*uses:", line)]
        runs = [line for line in direct if re.match(r"^\s*run:", line)]
        candidates.append(len(uses) == 1 and not runs and revision in set(USE.findall(uses[0])))
    return len(candidates) == 1 and candidates[0]


class Unverified(Exception):
    pass

def _fetch_json(url: str):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "SpatialRuntime-public-adoption-auditor",
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise Unverified("external API response too large")
            return json.loads(data)
    except (OSError, ValueError, urllib.error.HTTPError) as error:
        raise Unverified("public GitHub evidence unavailable") from error

def _repo(value):
    if not isinstance(value, str) or not REPOSITORY.fullmatch(value):
        return False
    return value.split("/", 1)[0].casefold() != "hippoley"

def check(consumer: object) -> tuple[bool, str]:
    if not isinstance(consumer, dict) or consumer.get("project_owned_evidence") is not True:
        return False, "project-owned evidence not asserted"
    repo = consumer.get("repository")
    run_id = consumer.get("workflow_run_id")
    path = consumer.get("workflow_path")
    job_id = consumer.get("workflow_job_id")
    step_name = consumer.get("action_step_name")
    sha = consumer.get("workflow_commit")
    ref = consumer.get("spatialruntime_commit")
    if not _repo(repo) or type(run_id) is not int or run_id <= 0:
        return False, "unrelated repository / run identifier missing"
    if type(job_id) is not int or job_id <= 0:
        return False, "external action job id missing"
    if not isinstance(step_name, str) or not step_name.strip() or len(step_name) > 180:
        return False, "external action step identity missing"
    if not isinstance(path, str) or not WORKFLOW.fullmatch(path):
        return False, "workflow path invalid"
    if not isinstance(sha, str) or not REVISION.fullmatch(sha):
        return False, "external workflow revision not pinned"
    if not isinstance(ref, str) or not REVISION.fullmatch(ref):
        return False, "SpatialRuntime action revision not pinned"
    if consumer.get("workflow_run_url") != f"https://github.com/{repo}/actions/runs/{run_id}":
        return False, "workflow run link does not belong to unrelated repository"

    try:
        run = _fetch_json(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}")
        if not isinstance(run, dict) or run.get("conclusion") != "success":
            return False, "external workflow has no confirmed successful run"
        if run.get("head_sha") != sha or run.get("event") not in ("push", "pull_request", "workflow_dispatch", "release", "schedule"):
            return False, "run commit or triggering event mismatch"
        repo_record = run.get("repository")
        if not isinstance(repo_record, dict) or str(repo_record.get("full_name", "")).casefold() != repo.casefold():
            return False, "run belongs to another repository"
        if run.get("path", "").lstrip(". /") != path.lstrip(". /"):
            return False, "run workflow file mismatch"

        api_path = quote(path, safe="/")
        blob = _fetch_json(f"https://api.github.com/repos/{repo}/contents/{api_path}?ref={sha}")
        if not isinstance(blob, dict) or blob.get("encoding") != "base64" or blob.get("type") != "file":
            return False, "workflow source not available at run revision"
        raw = base64.b64decode(blob.get("content", ""), validate=False)
        if len(raw) > MAX_BYTES:
            return False, "workflow source too large"
        matches = set(USE.findall(raw.decode("utf-8")))
        if ref not in matches:
            return False, "external workflow does not pin declared SpatialRuntime Action revision"
        jobs = _fetch_json(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
        if not isinstance(jobs, dict) or not isinstance(jobs.get("jobs"), list):
            return False, "external job execution metadata missing"
        if type(jobs.get("total_count")) is not int or jobs["total_count"] > len(jobs["jobs"]):
            return False, "incomplete external job list"
        target = [j for j in jobs["jobs"] if isinstance(j, dict) and j.get("id") == job_id]
        if len(target) != 1:
            return False, "claimed job missing"
        job = target[0]
        if job.get("conclusion") != "success" or job.get("status") != "completed" or job.get("head_sha") != sha:
            return False, "claimed job was not completed successfully at the checked commit"
        steps = job.get("steps")
        if not isinstance(steps, list):
            return False, "action step execution metadata missing"
        selected = [step for step in steps if isinstance(step, dict) and step.get("name") == step_name]
        if len(selected) != 1 or selected[0].get("conclusion") != "success" or selected[0].get("status") != "completed":
            return False, "named action step was skipped, failed or ambiguous"
        if not _source_has_named_action(raw.decode("utf-8"), step_name, ref):
            return False, "successful named step is not a direct pinned Action invocation in workflow source"
    except (Unverified, TypeError, ValueError, UnicodeError) as error:
        return False, f"external evidence could not be independently verified: {error}"
    return True, "externally verified GitHub Actions consumer"

def check_registry_entry(entry: object) -> tuple[bool,str]:
    if not isinstance(entry, dict):
        return False,"malformed entry"
    if entry.get("evidence_maturity") != "externally-consumed" or entry.get("external_consumption") is not True or entry.get("adoption_claim") is not True:
        return False,"entry does not assert externally-consumed adoption"
    return check(entry.get("consumer"))
