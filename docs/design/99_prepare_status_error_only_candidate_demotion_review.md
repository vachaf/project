# Status/Error-Only Candidate Demotion Review

- Date: 2026-05-20
- Status: design/review note
- Scope: prepare candidate policy review for rows that cross threshold mostly through status/error metadata
- Related review:
  - `docs/design/99_prepare_php_sample_candidate_policy_review.md`
  - `docs/design/99_prepare_upload_multipart_sql_comment_false_positive_review.md`
- Related diagnostic helper:
  - `scripts/explain_prepare_candidates.py`
- Related runs:
  - v1 baseline: `runs/obs_php_sample_002_pipeline_dryrun`
  - v2 guard verification: `runs/obs_php_sample_v2_sqlcomment_guard_dryrun`

---

## 1. Purpose

This document reviews whether prepare should demote candidate rows that cross `min_score` mainly through status/error metadata rather than explicit attack payload structure.

This is separate from the completed S09 upload/sql-comment-only guard.

Completed and out of scope here:

```text
upload-like POST + only sqli:sql_comment
=> weak upload/sql-comment context
=> not strong SQLi
```

This document focuses on rows like:

```text
error_status:500(+2) + error_linked(+2)
error_status:403(+2) + error_linked(+2)
login/context row + error_linked/status/no_referer
```

The target question is:

```text
Should status/error-only rows remain incident candidates, or should some be represented as context-only summaries/supporting context?
```

---

## 2. Current observed behavior

In PHP sample v1/v2 dry-runs, `candidate_rows=13` was observed under the current prepare policy.

This is not caused by `apache_security_io_v2`. v1 and v2 share the same candidate behavior under the same prepare policy.

The key scoring fact is:

```text
min_score=4
error_status(+2) + error_linked(+2) = 4
```

Therefore a row can become a candidate even without explicit SQLi/XSS/traversal/CMDI/file-disclosure payload evidence.

Representative status/error-only or near-status/error-only candidates in the PHP sample:

| scenario | request | status | likely reason | current review class |
|---|---|---:|---|---|
| S11 | `GET /error.php` | 500 | `error_status:500(+2)` + `error_linked(+2)` + client/context hints | `demotion_candidate_status_error_only` |
| S06 | `GET /private/secret.txt` | 403 | `error_status:403(+2)` + `error_linked(+2)` + sensitive/forbidden context | `demotion_candidate_status_error_only` |
| S07 | `GET /login.php` | 200 | login/context row plus error-linked app notice/long query style context | `demotion_candidate_status_error_only` in diagnostic output |

Potentially related but handled separately:

| scenario | request | reason this is separate |
|---|---|---|
| S08 `POST /login.php` 401 | auth failure context; should be reviewed under auth behavior policy |
| S09 `POST /upload.php` 400 | upload/sql-comment guard already implemented; remaining upload failure context may be separate |
| S12 scanner burst 404/200 paths | scanner/probe context demotion should be reviewed separately |
| S05 not-found 404 | may belong with scanner/probe/not-found context rather than generic status/error-only |

---

## 3. Problem statement

The current prepare policy is conservative. It treats status/error-linked rows as potentially useful candidate evidence because, in real logs, error-linked 4xx/5xx rows can indicate important security activity.

However, in controlled observability runs, many status/error rows are expected scenario outputs.

Problem:

```text
A row with no explicit attack payload can cross min_score because status/error metadata alone reaches threshold.
```

This can make dry-run candidate lists look incident-heavy even when the safer interpretation is context-only.

This is not a success-inference bug. Existing guardrails already prohibit success claims from status/bytes/content-type. The issue is candidate selection noise and wording priority.

---

## 4. Goals

- Reduce row-level candidate noise where the row is driven only by status/error metadata.
- Preserve true operational visibility for 4xx/5xx error-linked activity.
- Keep explicit payload candidates untouched.
- Keep Apache logs-only evidence boundaries intact.
- Avoid broad demotion that hides real attacks or operational security signals.
- Avoid lab-only behavior unless clearly justified.

---

## 5. Non-goals

- Do not infer exploit success, file exposure, auth success, upload success, or compromise.
- Do not remove all 4xx/5xx rows from candidate consideration.
- Do not demote rows with explicit SQLi/XSS/traversal/CMDI/file-disclosure/webshell/SSRF/SSTI/XXE signals.
- Do not change `apache_security_io_v1` or `apache_security_io_v2` semantics.
- Do not implement scanner/probe demotion in this review.
- Do not implement auth-specific demotion in this review.

---

## 6. Evidence boundary

For Apache logs only, status/error-linked rows can show:

```text
- HTTP status code
- request_id / error_link_id correlation
- Apache/PHP/proxy error context when available
- handler
- request target metadata
- timing/size/content-type metadata
```

They cannot prove:

```text
- successful exploitation
- file contents returned
- database query impact
- login/account compromise
- upload storage/execution
- server compromise
```

Therefore status/error-only candidates should be described as:

```text
observed error context
application/server error context
forbidden/not-found context
possible probing context
```

not as confirmed incidents unless combined with stronger evidence.

---

## 7. Candidate groups

### 7.1 Keep as candidates

Rows should remain candidates when any explicit attack-like signal is present.

Examples:

```text
sqli:or_true
sqli:quote_termination
xss:script_tag
traversal:dotdot_slash
traversal:etc_passwd
cmdi:metachar
file_disclosure:php_wrapper
webshell-like command query
ssrf target
ssti/xxe/log4shell structure
```

Guardrail:

```text
candidate != confirmed success
```

### 7.2 Demotion candidates

Rows are potential demotion candidates when:

```text
- no explicit attack payload signal
- score reaches threshold primarily from error_status/error_linked/no_referer/status metadata
- row is already represented in a context summary or can be represented as context
- row is isolated rather than repeated/clustered
```

Representative PHP sample candidates:

```text
S11 GET /error.php 500
S06 GET /private/secret.txt 403
S07 GET /login.php 200 with error/context linkage
```

### 7.3 Separate review buckets

Do not mix these into the first status/error-only demotion implementation:

```text
S08 login POST 401       -> auth behavior review
S09 upload POST 400      -> upload context review; SQL comment guard already done
S12 scanner burst paths  -> scanner/probe context review
S05 expected 404         -> scanner/not-found/probe context review
```

---

## 8. Policy options

### Option A. Keep current behavior

Pros:

- Lowest regression risk.
- Conservative for real logs.
- Keeps 4xx/5xx/error-linked rows visible for LLM review.

Cons:

- Observability dry-runs remain noisy.
- Error-only rows may compete with explicit payload candidates in top incident views.

### Option B. Add display-only policy classification only

Use `explain_prepare_candidates.py` and/or Web UI labels to show:

```text
status/error-only candidate
context-backed error row
auth failure context
probe context
```

Pros:

- No candidate selection risk.
- Improves reviewer interpretation.

Cons:

- Candidate count does not decrease.
- Stage1/Stage2 still process these rows as candidates.

### Option C. Narrow demotion for isolated status/error-only rows

Potential rule:

```text
IF no explicit attack payload signal
AND score reaches threshold only from status/error/no-referer/context metadata
AND row is isolated
AND row is represented in context summaries or safe context bucket
THEN do not include as row-level incident candidate
AND preserve as context/supporting event/filtered context
```

Pros:

- Reduces candidate noise.
- Keeps explicit attack payload candidates prioritized.

Cons:

- Higher regression risk.
- Requires context membership or safe replacement representation.
- Needs fixtures before implementation.

### Option D. Lower only severity/verdict/category, not candidate inclusion

Potential rule:

```text
IF status/error-only candidate
THEN keep candidate
BUT classify as suspicious/context-like rather than attack category
```

Pros:

- Safer than full demotion.
- Preserves visibility.

Cons:

- Candidate count remains high.
- May already be mostly true today for many rows.

### Option E. Apply only to observability/lab markers

Potential rule:

```text
IF obs-test/* or lab marker
AND no explicit attack payload signal
AND scenario is known status/error baseline
THEN demote
```

Pros:

- Low risk for production-like logs.
- Makes lab dry-runs cleaner.

Cons:

- Adds lab-specific behavior to prepare.
- May make regression behavior less representative.

---

## 9. Recommended direction

Do not implement demotion immediately.

Recommended sequence:

```text
1. Keep current prepare behavior for status/error-only rows.
2. Use explain_prepare_candidates.py to collect exact status/error-only candidates after the S09 guard.
3. Add a fixture/test for diagnostic classification if missing.
4. Decide whether display-only classification is sufficient.
5. If code change is needed, start with Option D or very narrow Option C.
6. Do not apply lab-marker-only behavior unless all generic options are too risky.
```

Preferred near-term action:

```text
Generate and compare candidate explanation reports for:
- runs/obs_php_sample_002_pipeline_dryrun
- runs/obs_php_sample_v2_sqlcomment_guard_dryrun
```

Then inspect only these classes:

```text
demotion_candidate_status_error_only
context_candidate_auth_failure
context_candidate_upload_failure
```

But implement demotion only for `demotion_candidate_status_error_only` after separate tests.

---

## 10. Required guard conditions for future demotion

A future status/error-only demotion rule must require all of these:

```text
no explicit SQLi/XSS/traversal/CMDI/file-disclosure/webshell/SSRF/SSTI/XXE/Log4Shell signal
no embedded attack hint from HPP or decoded target
score would be below threshold without error_status/error_linked/no_referer/status metadata
row is isolated or low-clustered
row is represented by context summary/supporting context, or safe filtered context output
not a proxy/backend outage burst needing operational attention
not a repeated 5xx spike
not a denied sensitive path pattern that should remain visible by policy
```

Additional caution for `403`:

```text
403 to a sensitive path can be useful security signal.
Do not broadly demote all 403 rows.
```

Additional caution for `500`:

```text
500 may indicate exploit attempt, app crash, backend outage, or ordinary app error.
Demote only if no payload/context suggests attack and it is isolated.
```

---

## 11. Test plan before implementation

Before any prepare-side demotion, add tests that cover:

```text
1. isolated 500 with only error_status/error_linked
   expected: classification or demotion behavior explicitly defined

2. 500 with explicit payload in query
   expected: remains candidate

3. 403 forbidden sensitive path without payload
   expected: policy decision fixed by test, likely visible context or candidate depending chosen rule

4. 403 with traversal/file-disclosure payload
   expected: remains candidate

5. repeated 5xx cluster
   expected: not silently suppressed

6. scanner/probe 404 row
   expected: not covered by this test; scanner/probe review owns it
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
isolated /error.php 500 without payload
isolated context/error-linked login form row without payload
possibly isolated forbidden/static private path row depending final policy
```

Expected non-impact:

```text
S13 SQLi-like remains SQLi candidate
S14 XSS-like remains XSS candidate
S15 traversal-like remains traversal candidate
S09 upload/sql-comment-only remains weak upload context, not strong SQLi
scanner/probe handling remains separate
```

---

## 13. Current recommendation

Do not modify prepare scoring for status/error-only rows yet.

Current recommended next step:

```text
Use explain_prepare_candidates.py outputs to decide whether display-only classification is enough.
```

If not enough, create fixture coverage first and then consider a narrow rule for isolated status/error-only rows.

Keep this separate from scanner/probe context demotion and auth/upload behavior policy.
