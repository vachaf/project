# Scanner/Probe Context Candidate Demotion Review

- Date: 2026-05-20
- Status: design/review note
- Scope: prepare candidate policy review for scanner/probe-like rows that are already represented by context summaries
- Related reviews:
  - `docs/design/99_prepare_php_sample_candidate_policy_review.md`
  - `docs/design/99_prepare_status_error_only_candidate_demotion_review.md`
  - `docs/design/99_prepare_upload_multipart_sql_comment_false_positive_review.md`
- Related diagnostic helper:
  - `scripts/explain_prepare_candidates.py`
- Related runs:
  - v1 baseline: `runs/obs_php_sample_002_pipeline_dryrun`
  - v2 guard verification: `runs/obs_php_sample_v2_sqlcomment_guard_dryrun`
- Related context summary families:
  - `probing_sequence_summaries`
  - `sensitive_path_probe_summaries`
  - `mixed_baseline_scanner_summaries`
  - `ip_behavior_aggregates`
  - `static_baseline_summaries`

---

## 1. Purpose

This document reviews whether prepare should demote scanner/probe-like row-level candidates when the same activity is already represented by context summaries.

This is separate from these completed or separate reviews:

```text
completed:
  S09 upload-like POST + only sqli:sql_comment => weak upload/sql-comment context

separate:
  status/error-only candidate demotion review
  auth behavior review
  upload behavior review
```

This review focuses on rows like:

```text
GET /admin                  404
GET /.env                   404
GET /wp-login.php           404
GET /does-not-exist         404
GET /server-status          200/403 depending client/topology
```

The target question is:

```text
Should individual scanner/probe rows remain row-level incident candidates, or should some be represented primarily by probing/sensitive-path/mixed-baseline context summaries?
```

---

## 2. Current observed behavior

In PHP sample v1/v2 dry-runs, `candidate_rows=13` was observed under the current prepare policy.

This is not caused by `apache_security_io_v2`. v1 and v2 share the same candidate behavior under the same prepare policy.

The scanner/probe contribution is visible in S12 scanner burst and related expected not-found rows.

Representative rows:

| scenario | request | status | likely context | current review class |
|---|---|---:|---|---|
| S12 | `GET /admin` | 404 | admin path probe | `context_candidate_probe` |
| S12 | `GET /.env` | 404 | sensitive file probe | `context_candidate_probe` |
| S12 | `GET /wp-login.php` | 404 | WordPress login probe | `context_candidate_probe` |
| S12 | `GET /does-not-exist` | 404 | not-found probe/noise | `context_candidate_probe` |
| S12 | `GET /server-status` | 200 or 403 by topology/client | server-status handler/exposure context | context-only unless external exposure is separately verified |
| S05 | `GET /does-not-exist-*` | 404 | expected not-found/probe context | `context_candidate_probe` |

Relevant prepare summary outputs can already represent this activity:

```text
probing_sequence_summaries
sensitive_path_probe_summaries
mixed_baseline_scanner_summaries
ip_behavior_aggregates
static_baseline_summaries
```

Therefore the row-level candidate question is about duplication and prioritization, not whether the activity should be ignored.

---

## 3. Problem statement

The current prepare policy is intentionally conservative. Probe-like paths can be useful as row-level candidate evidence because real scanners often touch sensitive or technology-specific paths.

However, in controlled observability runs, S12 intentionally sends a burst of probe-like paths. The activity is better understood as a context group:

```text
scanner/probe context
sensitive path probe context
mixed baseline scanner context
IP behavior aggregate context
```

Problem:

```text
Several individual scanner/probe rows can cross candidate threshold even though the grouped context summary may be the safer primary representation.
```

This can make dry-run candidate lists look more incident-heavy than necessary and can duplicate information already present in context summaries.

This is not a success-inference bug. The guardrail remains:

```text
probe path observed != resource exists
server-status 200 from localhost != external exposure
404/403/200 != successful exploitation
```

The issue is candidate selection and reporting priority.

---

## 4. Goals

- Reduce row-level candidate noise for scanner/probe rows when context summaries already represent the activity.
- Preserve visibility of sensitive-path probing.
- Preserve explicit payload candidates.
- Preserve repeated or high-confidence scanner patterns as context evidence.
- Keep Apache logs-only evidence boundaries intact.
- Avoid broad suppression of real scanner activity.
- Avoid lab-only special casing if generic context-summary-backed logic is possible.

---

## 5. Non-goals

- Do not infer file/resource existence from `404`, `403`, `200`, response size, or content type.
- Do not infer `/server-status` external exposure from localhost-only access.
- Do not remove all sensitive-path observations.
- Do not demote rows with explicit payload structure such as traversal, SQLi, XSS, CMDI, file disclosure, SSRF, XXE, SSTI, Log4Shell, or webshell-like access.
- Do not change `apache_security_io_v1` or `apache_security_io_v2` semantics.
- Do not implement status/error-only demotion here.
- Do not change Web UI relationship logic or promote context-only items to findings.

---

## 6. Evidence boundary

For Apache logs only, scanner/probe rows can show:

```text
- requested path/target
- query string
- HTTP status
- handler
- request_id/error_link_id correlation
- timing/size/content-type metadata
- source IP / peer IP / forwarded headers as observed fields
- user-agent as observed client-supplied metadata
```

They cannot prove:

```text
- file exists on disk
- file contents were exposed
- server-status is externally exposed
- WordPress/OpenCart/Juice Shop/admin functionality exists
- authentication bypass
- server compromise
- scanner identity or intent with certainty
```

Therefore scanner/probe context should be described as:

```text
observed probe pattern
sensitive-path access attempt
technology fingerprinting/probing context
not-found/probe noise
context-only scanner burst
```

not as confirmed exposure or compromise.

---

## 7. Candidate groups

### 7.1 Keep as row-level candidates

Rows should remain candidates when explicit attack-like payload structure is present, even if they also look like probes.

Examples:

```text
/download.php?file=../../../etc/passwd
/search.php?q=' OR '1'='1
/search.php?q=<script>alert(1)</script>
/admin?cmd=id
/.env?x=<payload>
```

Guardrail:

```text
candidate != confirmed success
```

### 7.2 Context-summary-backed demotion candidates

Rows are demotion candidates when they are mainly scanner/probe paths without explicit exploit payload structure and are already represented in context summaries.

Representative examples:

```text
/admin                 404
/.env                  404
/wp-login.php          404
/does-not-exist        404
/server-status         localhost 200 or external 403, depending topology
```

These should remain visible through one or more context mechanisms:

```text
sensitive_path_probe_summaries
probing_sequence_summaries
mixed_baseline_scanner_summaries
ip_behavior_aggregates
supporting_events if generated by existing logic
```

### 7.3 Separate review buckets

Do not mix these into the scanner/probe demotion implementation:

```text
S11 /error.php 500       -> status/error-only review
S06 /private/secret.txt 403 -> may be status/error or sensitive-path policy; handle carefully
S08 /login.php POST 401  -> auth behavior review
S09 /upload.php POST 400 -> upload behavior review; SQL comment guard already done
S13/S14/S15              -> explicit payload candidates; keep
```

---

## 8. Policy options

### Option A. Keep current behavior

Pros:

- Lowest regression risk.
- Keeps individual scanner/probe rows visible.
- Conservative for real logs where single sensitive path hits can be important.

Cons:

- Observability dry-runs remain noisy.
- Individual probe rows may duplicate context summaries.
- LLM top incident views may over-prioritize benign lab probes.

### Option B. Display-only classification only

Use `explain_prepare_candidates.py` and/or Web UI labels to show:

```text
context_candidate_probe
sensitive-path probe context
scanner/probe context
server-status observation context
```

Pros:

- No candidate selection risk.
- Improves reviewer interpretation.
- Compatible with current guardrails.

Cons:

- Candidate count does not decrease.
- Stage1/Stage2 still process individual probe rows.

### Option C. Context-summary-backed demotion

Potential rule:

```text
IF row has no explicit attack payload signal
AND row is scanner/probe/sensitive-path-like
AND row is already represented by a context summary
AND row is not a high-risk singleton that policy wants to keep as candidate
THEN do not include as row-level incident candidate
AND preserve it in context summaries/supporting context
```

Pros:

- Reduces candidate noise.
- Keeps grouped scanner/probe context.
- Better separates incident candidates from baseline/probing context.

Cons:

- Requires reliable membership/linkage between row candidates and context summaries.
- Risk of hiding important single sensitive-path probes if too broad.
- Requires fixtures before implementation.

### Option D. Limit row-level candidates from a scanner burst

Potential rule:

```text
IF many probe rows belong to the same probing sequence
THEN keep at most N representative row candidates
AND represent the rest through context summaries
```

Pros:

- Keeps sample evidence while reducing duplication.
- Useful for large scanner bursts.

Cons:

- Needs stable grouping and representative selection.
- May alter top incident ordering.

### Option E. Lab/observability-only demotion

Potential rule:

```text
IF obs-test/* marker and known S12 scanner_burst
THEN demote individual probe rows to context-only
```

Pros:

- Very low risk to production-like logs.
- Cleans lab dry-runs quickly.

Cons:

- Adds lab-specific behavior to prepare.
- Less useful as a general policy.
- Could make lab regression less representative of real scanner traffic.

---

## 9. Recommended direction

Do not implement scanner/probe demotion immediately.

Recommended sequence:

```text
1. Keep current prepare behavior for scanner/probe rows.
2. Use explain_prepare_candidates.py to identify context_candidate_probe rows after the S09 guard.
3. Confirm which rows are already represented in probing/sensitive-path/mixed-baseline summaries.
4. Add fixture coverage before any demotion.
5. Prefer display-only classification or context-summary-backed demotion over lab-only demotion.
```

Preferred near-term action:

```text
Generate candidate explanation reports and compare with context summaries for:
- runs/obs_php_sample_002_pipeline_dryrun
- runs/obs_php_sample_v2_sqlcomment_guard_dryrun
```

Inspect only these classes:

```text
context_candidate_probe
context_only_server_status
```

---

## 10. Required guard conditions for future demotion

A future scanner/probe demotion rule must require all of these:

```text
no explicit SQLi/XSS/traversal/CMDI/file-disclosure/webshell/SSRF/SSTI/XXE/Log4Shell signal
no HPP embedded attack hint
row is scanner/probe/sensitive-path-like by existing reason_hints or stable path category
row is represented by an existing context summary or preserved supporting context
not a configured high-priority singleton path that should remain row-level candidate
not an externally verified sensitive exposure
not a repeated high-risk sequence without a separate summary representation
```

Special handling for `/.env`:

```text
/.env probes are important sensitive-path signals.
Demotion is acceptable only if sensitive_path_probe_summaries preserve them clearly.
Do not infer file exposure from the request alone.
```

Special handling for `/server-status`:

```text
localhost 200 is server-status handler observation, not external exposure.
external 403 is denial context, not exposure.
external 200 would require separate verification and should likely remain visible.
```

Special handling for `/wp-login.php`:

```text
WordPress path probe does not prove WordPress exists.
It is technology fingerprinting/probing context unless backed by stronger evidence.
```

Special handling for `/admin`:

```text
/admin 404/redirect/fallback does not prove admin panel exists or was accessed.
Topology context may change interpretation.
```

---

## 11. Test plan before implementation

Before any prepare-side scanner/probe demotion, add tests that cover:

```text
1. scanner burst with /admin, /.env, /wp-login.php, /does-not-exist
   expected: context summaries preserve the burst

2. individual /.env probe without explicit payload
   expected: policy decision fixed by test; likely context-backed visibility

3. /.env with explicit file-disclosure/traversal payload
   expected: remains candidate

4. /server-status localhost 200
   expected: server-status observation context, not external exposure

5. /server-status external 403
   expected: denial context, not exposure

6. /server-status external 200 if fixture exists later
   expected: separate high-visibility context/candidate, still not compromise

7. scanner burst plus one explicit payload row
   expected: explicit payload row remains candidate, other probes may be context-backed
```

Regression checks after any code change:

```bash
python3 -m py_compile src/prepare_llm_input.py
python3 -m pytest -q tests/test_explain_prepare_candidates.py
python3 -m pytest -q tests/test_prepare_upload_multipart_sql_comment_false_positive.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

---

## 12. Impact expectation if implemented later

If a narrow demotion rule is later implemented, expected impact should be limited to rows like:

```text
/admin 404 without payload
/.env 404 without payload, if preserved by sensitive_path_probe_summaries
/wp-login.php 404 without payload
/does-not-exist 404 without payload
server-status localhost observation, if preserved as context
```

Expected non-impact:

```text
S13 SQLi-like remains SQLi candidate
S14 XSS-like remains XSS candidate
S15 traversal-like remains traversal candidate
S09 upload/sql-comment-only remains weak upload context, not strong SQLi
status/error-only review remains separate
```

Candidate count may decrease only if demotion is actually implemented. This document does not implement it.

---

## 13. Web UI/reporting considerations

If demotion is not implemented, Web UI/reporting can still reduce confusion by showing display-only labels such as:

```text
context-backed probe
sensitive path probe
technology fingerprinting probe
server-status observed locally
no file exposure proof
no app existence proof
```

These labels must not alter:

```text
severity
verdict
category
finding/context relationship
supporting_events generation
```

If demotion is implemented later, the UI should continue to show the grouped context summaries clearly so probe evidence is not lost.

---

## 14. Current recommendation

Do not modify prepare scoring for scanner/probe rows yet.

Current recommended next step:

```text
Use explain_prepare_candidates.py outputs plus context summary counts to decide whether display-only classification is enough.
```

If candidate noise remains a concern, create fixture coverage first and then consider context-summary-backed demotion.

Keep this separate from:

```text
status/error-only demotion
auth behavior policy
upload behavior policy
explicit payload candidate handling
```
