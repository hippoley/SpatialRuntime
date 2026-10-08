# Upstream vector proposal: discriminate Stage 3 marker legs

Target upstream: `Rul1an/assay` `privileged-mcp-action/v0`

Pinned profile/corpus context:
- profile: `privileged-mcp-action/v0`
- issue: `Rul1an/assay#1840`
- current published corpus: 14 cases
- issue body states only 5 of 27 profile rules are currently discriminated
- two explicitly undiscriminated Stage 3 rules are the `caller_visible_error.code` and `caller_visible_error.origin` legs of the denial-marker triple.

## Why these vectors

Stage 3 defines a denial marker only when all three legs hold:

1. schema = `assay.denied_call_observation.v0`
2. code = `-32042`
3. origin = `assay-proxy`

A well-formed observation that fails the marker triple is valid and inert. Therefore an implementation that accidentally checks only schema+code, or only schema+origin, can produce the wrong claim matrix while still passing the current corpus.

## Candidate vectors

### ok-006-deny-observation-wrong-origin-inert

Inputs:
- valid deny decision
- well-formed denial observation
- code = `-32042`
- origin = `other-proxy`
- binding pair matches the decision

Expected:
- bundle_integrity = `pass`
- verdict = `valid`
- policy_decision_recorded = `confirmed / producer_reported`
- caller_visible_denial = `incomplete`
- upstream_delivery = `incomplete`
- external_side_effect = `incomplete`

Discriminates implementations that treat code alone as sufficient for the marker.

### ok-007-deny-observation-wrong-code-inert

Inputs:
- valid deny decision
- well-formed denial observation
- code = `-32041`
- origin = `assay-proxy`
- binding pair matches the decision

Expected:
- same matrix as above

Discriminates implementations that treat origin alone as sufficient for the marker.

## Minimal generator patch sketch

```diff
@@
-def observation_record(*, tool=TOOL, digest=DIGEST, reason="no_declared_allowance"):
+def observation_record(*, tool=TOOL, digest=DIGEST, reason="no_declared_allowance",
+                       code=-32042, origin="assay-proxy"):
@@
-        "caller_visible_error": {"code": -32042, "origin": "assay-proxy", "reason": reason},
+        "caller_visible_error": {"code": code, "origin": origin, "reason": reason},
@@
     {
         "id": "ok-005-allow-contradicted-by-denial",
@@
     },
+    {
+        "id": "ok-006-deny-observation-wrong-origin-inert",
+        "payloads": lambda: [
+            decision_record("deny", "no_declared_allowance"),
+            observation_record(
+                reason="no_declared_allowance",
+                origin="other-proxy",
+            ),
+        ],
+        "expected": {
+            "bundle_integrity": "pass",
+            "verdict": "valid",
+            "claims": claims("confirmed", "incomplete"),
+        },
+        "description": "A well-formed observation with the correct code but non-Assay origin is valid and inert; origin is a required denial-marker leg.",
+    },
+    {
+        "id": "ok-007-deny-observation-wrong-code-inert",
+        "payloads": lambda: [
+            decision_record("deny", "no_declared_allowance"),
+            observation_record(
+                reason="no_declared_allowance",
+                code=-32041,
+            ),
+        ],
+        "expected": {
+            "bundle_integrity": "pass",
+            "verdict": "valid",
+            "claims": claims("confirmed", "incomplete"),
+        },
+        "description": "A well-formed observation from assay-proxy with the wrong code is valid and inert; code is a required denial-marker leg.",
+    },
```

## Claim ceiling

This proposal does not claim the two vectors are sufficient to raise measured corpus rule coverage until the upstream coverage measurement is rerun. They are designed specifically to discriminate two rules that the current issue body names as undiscriminated.
