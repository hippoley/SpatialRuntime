#!/usr/bin/env python3
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path

import rfc8785

REPORT_NON_CLAIMS = [
    "allow does not prove upstream delivery",
    "deny does not establish maliciousness",
    "caller-visible denial does not prove external side-effect absence",
    "bundle integrity does not upgrade source class",
]

DECISION_NON_CLAIMS = {
    "policy decision only; does not assert or verify the upstream side effect (stays asserted, E9 ladder)",
    "an allow is the decision to forward; it does not assert the call reached or was performed by the upstream (a transport failure surfaces as proxy_failed, not here)",
    "credential referenced by alias only, never the token or declared scopes",
    "deny is fail-closed caution and allow is a policy decision — neither is a maliciousness verdict",
    "not the observation artifact (assay.mcp_manifest_observed.v0) and not the mechanism artifact (assay.enforcement_health.v0)",
}

OBSERVATION_NON_CLAIMS = {
    "caller-visible proxy denial observation only; policy decision lives in assay.enforcement_decision.v0",
    "does not assert or verify the upstream side effect",
    "does not assert maliciousness, safety, approval, or whole-action trust",
    "must not be read as a replacement for the bound enforcement decision record",
}

DECISION_SCHEMA = "assay.enforcement_decision.v0"
OBSERVATION_SCHEMA = "assay.denied_call_observation.v0"
ESTABLISH_SCHEMA = "assay.manifest_establish.v0"
KNOWN_SCHEMAS = {DECISION_SCHEMA, OBSERVATION_SCHEMA, ESTABLISH_SCHEMA}
PROFILE_PREFIXES = (
    "assay.enforcement_decision.",
    "assay.denied_call_observation.",
    "assay.manifest_establish.",
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

DECISIONS = {"allow", "deny"}
REASONS = {
    "unclassified_tool_call",
    "classification_incomplete",
    "no_declared_allowance",
    "credential_scope_unknown",
    "credential_scope_insufficient",
    "manifest_baseline_missing",
    "manifest_observation_ambiguous",
    "manifest_current_observation_incomplete",
    "manifest_drifted_since_approval",
    "allow",
}
DRIFT_STATES = {
    "satisfied",
    "baseline_missing",
    "current_observation_incomplete",
    "observation_ambiguous",
    "drifted",
    "not_evaluated",
}
ESTABLISH_PATHS = {
    "no_establish_needed",
    "established_then_allowed",
    "established_then_denied",
    "immediate_deny",
}


def jcs(value):
    return rfc8785.dumps(value)


def sha256_prefixed(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def report_integrity_fail(message):
    return {
        "schema": "assay.privileged_mcp_action.verify.report.v0",
        "profile": "privileged-mcp-action/v0",
        "bundle_integrity": "fail",
        "findings": [{"stage": "bundle_integrity", "message": message}],
        "non_claims": REPORT_NON_CLAIMS,
    }


def report_invalid(findings):
    return {
        "schema": "assay.privileged_mcp_action.verify.report.v0",
        "profile": "privileged-mcp-action/v0",
        "bundle_integrity": "pass",
        "verdict": "invalid",
        "findings": findings or [{"stage": "profile", "message": "profile invalid"}],
        "non_claims": REPORT_NON_CLAIMS,
    }


def cell(status):
    out = {"status": status}
    if status in {"confirmed", "refuted"}:
        out["source_class"] = "producer_reported"
    return out


def report_valid(decision, marker, establish, findings):
    denial = "confirmed" if marker and decision["decision"] == "deny" else "incomplete"
    if marker and decision["decision"] == "allow":
        denial = "refuted"
        findings.append({
            "stage": "claim_recompute",
            "message": "allow decision contradicted by bound caller-visible denial",
        })

    if establish is not None:
        path = establish["establish_path"]
        contradiction = (
            (decision["decision"] == "allow" and path in {"immediate_deny", "established_then_denied"})
            or (decision["decision"] == "deny" and path == "established_then_allowed")
        )
        if contradiction:
            findings.append({
                "stage": "claim_recompute",
                "message": "manifest-establish journey contradicts recorded decision; claim matrix unchanged",
            })

    return {
        "schema": "assay.privileged_mcp_action.verify.report.v0",
        "profile": "privileged-mcp-action/v0",
        "bundle_integrity": "pass",
        "verdict": "valid",
        "claims": {
            "policy_decision_recorded": cell("confirmed"),
            "caller_visible_denial": cell(denial),
            "upstream_delivery": cell("incomplete"),
            "external_side_effect": cell("incomplete"),
        },
        "findings": findings,
        "non_claims": REPORT_NON_CLAIMS,
    }


def _is_profile_namespace(value):
    return isinstance(value, str) and value.startswith(PROFILE_PREFIXES)


def _contains_required(actual, required):
    return isinstance(actual, list) and required.issubset(set(actual))


def verify_bundle(path):
    try:
        with tarfile.open(path, mode="r:gz") as tf:
            members = tf.getmembers()
            names = [m.name for m in members]
            if names != ["manifest.json", "events.ndjson"]:
                return report_integrity_fail("bundle must contain manifest.json first and events.ndjson second")
            for m in members:
                p = Path(m.name)
                if m.isdir() or p.is_absolute() or ".." in p.parts:
                    return report_integrity_fail("unsafe or non-file tar entry")
            manifest_bytes = tf.extractfile(members[0]).read()
            events_bytes = tf.extractfile(members[1]).read()
    except Exception as exc:
        return report_integrity_fail(f"archive read failed: {exc}")

    try:
        manifest = json.loads(manifest_bytes)
    except Exception as exc:
        return report_integrity_fail(f"manifest JSON invalid: {exc}")

    if manifest.get("schema_version") != 1:
        return report_integrity_fail("manifest schema_version must be 1")
    if manifest.get("algorithms") != {
        "canon": "jcs-rfc8785",
        "hash": "sha256",
        "root": 'sha256(concat(content_hash + "\\n"))',
    }:
        return report_integrity_fail("manifest algorithms mismatch")

    file_entry = manifest.get("files", {}).get("events.ndjson")
    if not isinstance(file_entry, dict):
        return report_integrity_fail("events.ndjson manifest entry missing")
    if file_entry.get("path") != "events.ndjson":
        return report_integrity_fail("events.ndjson path mismatch")
    if file_entry.get("bytes") != len(events_bytes):
        return report_integrity_fail("events.ndjson byte length mismatch")
    if file_entry.get("sha256") != sha256_prefixed(events_bytes):
        return report_integrity_fail("events.ndjson sha256 mismatch")

    lines = events_bytes.splitlines()
    if manifest.get("event_count") != len(lines):
        return report_integrity_fail("event_count mismatch")

    events = []
    content_hashes = []
    run_id = manifest.get("run_id")

    for idx, line in enumerate(lines):
        try:
            event = json.loads(line)
        except Exception as exc:
            return report_integrity_fail(f"event {idx} JSON invalid: {exc}")
        required = {
            "specversion",
            "type",
            "source",
            "id",
            "time",
            "datacontenttype",
            "assayrunid",
            "assayseq",
            "assaycontenthash",
            "data",
        }
        if not required.issubset(event):
            return report_integrity_fail(f"event {idx} missing required members")
        if event["specversion"] != "1.0" or event["datacontenttype"] != "application/json":
            return report_integrity_fail(f"event {idx} CloudEvent constants invalid")
        if event["assayseq"] != idx:
            return report_integrity_fail(f"event {idx} sequence is not contiguous")
        if event["assayrunid"] != run_id:
            return report_integrity_fail(f"event {idx} run id mismatch")
        if event["id"] != f"{run_id}:{idx}":
            return report_integrity_fail(f"event {idx} id mismatch")

        subset = {
            "specversion": event["specversion"],
            "type": event["type"],
            "datacontenttype": event["datacontenttype"],
            "data": event["data"],
        }
        if "subject" in event:
            subset["subject"] = event["subject"]
        expected_hash = sha256_prefixed(jcs(subset))
        if event["assaycontenthash"] != expected_hash:
            return report_integrity_fail(f"event {idx} content hash mismatch")

        content_hashes.append(expected_hash)
        events.append(event)

    recomputed_root = sha256_prefixed(
        b"".join(h.encode("utf-8") + b"\n" for h in content_hashes)
    )
    if manifest.get("run_root") != recomputed_root:
        return report_integrity_fail("run_root mismatch")
    if manifest.get("bundle_id") != recomputed_root:
        return report_integrity_fail("bundle_id mismatch")

    findings = []
    selected = []
    for idx, event in enumerate(events):
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        schema = data.get("schema")
        event_type = event.get("type")
        in_scope_schema = _is_profile_namespace(schema)
        in_scope_type = _is_profile_namespace(event_type)
        if in_scope_schema or in_scope_type:
            if schema != event_type:
                findings.append({"stage": "statement_well_formedness", "message": f"event {idx} type/schema mismatch"})
                continue
            if schema not in KNOWN_SCHEMAS:
                findings.append({"stage": "statement_well_formedness", "message": f"event {idx} unknown profile schema"})
                continue
            selected.append((idx, schema, data))

    decisions = [d for _, s, d in selected if s == DECISION_SCHEMA]
    observations = [d for _, s, d in selected if s == OBSERVATION_SCHEMA]
    establishes = [d for _, s, d in selected if s == ESTABLISH_SCHEMA]

    if len(decisions) != 1:
        findings.append({"stage": "statement_well_formedness", "message": "exactly one decision record required"})
    if len(observations) > 1:
        findings.append({"stage": "statement_well_formedness", "message": "at most one denial observation allowed"})
    if len(establishes) > 1:
        findings.append({"stage": "statement_well_formedness", "message": "at most one establish record allowed"})

    if findings:
        return report_invalid(findings)

    decision = decisions[0]
    if decision.get("decision") not in DECISIONS:
        findings.append({"stage": "statement_well_formedness", "message": "decision vocabulary invalid"})
    if decision.get("reason") not in REASONS:
        findings.append({"stage": "statement_well_formedness", "message": "reason vocabulary invalid"})
    if decision.get("drift_state") not in DRIFT_STATES:
        findings.append({"stage": "statement_well_formedness", "message": "drift_state vocabulary invalid"})
    tool = decision.get("tool")
    if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not tool["name"]:
        findings.append({"stage": "statement_well_formedness", "message": "tool.name must be non-empty"})
    action = decision.get("action")
    digest = action.get("target_digest") if isinstance(action, dict) else None
    if not isinstance(digest, str) or not SHA256_RE.match(digest):
        findings.append({"stage": "statement_well_formedness", "message": "action.target_digest invalid"})
    if not isinstance(decision.get("fail_closed"), bool) or decision.get("fail_closed") != (decision.get("decision") == "deny"):
        findings.append({"stage": "statement_well_formedness", "message": "fail_closed derivation invalid"})
    if not _contains_required(decision.get("non_claims"), DECISION_NON_CLAIMS):
        findings.append({"stage": "statement_well_formedness", "message": "decision non_claims incomplete"})

    observation = observations[0] if observations else None
    marker = False
    if observation is not None:
        call = observation.get("call")
        err = observation.get("caller_visible_error")
        obs_digest = observation.get("caller_visible_response_digest")
        if not isinstance(call, dict) or not isinstance(call.get("tool_name"), str) or not call["tool_name"]:
            findings.append({"stage": "statement_well_formedness", "message": "observation call.tool_name invalid"})
        if not isinstance(err, dict) or any(err.get(k) is None for k in ("code", "origin", "reason")):
            findings.append({"stage": "statement_well_formedness", "message": "observation caller_visible_error incomplete"})
        if not isinstance(obs_digest, str) or not SHA256_RE.match(obs_digest):
            findings.append({"stage": "statement_well_formedness", "message": "caller_visible_response_digest invalid"})
        if not _contains_required(observation.get("non_claims"), OBSERVATION_NON_CLAIMS):
            findings.append({"stage": "statement_well_formedness", "message": "observation non_claims incomplete"})
        if not findings:
            marker = (
                err.get("code") == -32042
                and err.get("origin") == "assay-proxy"
            )

    establish = establishes[0] if establishes else None
    if establish is not None:
        if establish.get("establish_path") not in ESTABLISH_PATHS:
            findings.append({"stage": "statement_well_formedness", "message": "establish_path invalid"})
        run_outcome = establish.get("run_outcome")
        attempted = establish.get("establish_attempted")
        if not isinstance(run_outcome, str) or not isinstance(attempted, bool):
            findings.append({"stage": "statement_well_formedness", "message": "establish record types invalid"})
        elif attempted != (run_outcome != "not_performed"):
            findings.append({"stage": "statement_well_formedness", "message": "establish_attempted derivation invalid"})

    if findings:
        return report_invalid(findings)

    if marker:
        call = observation["call"]
        if (
            call.get("tool_name") != decision["tool"]["name"]
            or call.get("target_digest") != decision["action"]["target_digest"]
        ):
            return report_invalid([{
                "stage": "binding_validity",
                "message": "caller-visible denial marker is not bound to the decision",
            }])

    return report_valid(decision, marker, establish, findings)


def main():
    if len(sys.argv) != 2:
        print(json.dumps(report_integrity_fail("usage: verifier.py <bundle-path>")))
        return 2
    result = verify_bundle(sys.argv[1])
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
