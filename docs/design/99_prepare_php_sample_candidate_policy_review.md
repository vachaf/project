# PHP Sample Candidate Policy Review

- Date: 2026-05-15
- Status: implemented narrow upload/sql-comment guard; broader demotion still review-only
- Scope: prepare candidate selection policy for Apache+PHP observability sample runs
- Related runs:
  - v1: `lab/observability/runs/obs_php_sample_002`
  - v2: `lab/observability/runs/obs_php_sample_v2_001`
  - guard verification: `runs/obs_php_sample_v2_sqlcomment_guard_dryrun`
- Related comparison:
  - `lab/observability/comparison_php_sample_v1_vs_v2.md`
- Related summary:
  - `lab/observability/runs/obs_php_sample_v2_001/summary.md`
- Related diagnostic helper:
  - `scripts/explain_prepare_candidates.py`
- Related narrow guard review:
  - `docs/design/99_prepare_upload_multipart_sql_comment_false_positive_review.md`

---

## 0. 2026-05-20 Policy Update

`S09 upload-like POST + only sqli:sql_comment` false-positive class에 대해 prepare 레벨 narrow guard를 반영하고, PHP sample v2 dry-run으로 재확인했다.

Implementation:

```text
src/prepare_llm_input.py
```

Test / diagnostic coverage:

```text
tests/test_prepare_upload_multipart_sql_comment_false_positive.py
tests/test_explain_prepare_candidates.py
tests/fixtures/prepare_candidate_explain_sample.json
scripts/explain_prepare_candidates.py
```

적용 결과:

```text
S09 POST /upload.php
before: score=7, verdict_hint=sqli
 after: score=5, verdict_hint=suspicious
policy_class=context_candidate_upload_failure
```

추가된 weak-context hints:

```text
sqli:sql_comment_upload_context_weak_signal
sqli:sql_comment_only_upload_context_no_strong_sqli_structure
upload:multipart_or_upload_like_context
upload:no_upload_success_inference
```

강한 SQLi 구조는 유지된다.

```text
S13 GET /search.php
score=13
verdict_hint=sqli
reason_hints include sqli:or_true(+4), sqli:quote_termination(+4)
```

검증 결과:

```text
python3 -m py_compile src/prepare_llm_input.py src/prepare/sqli_hints.py  # pass
python3 -m pytest -q tests/test_explain_prepare_candidates.py             # 6 passed
python3 -m pytest -q tests/test_prepare_upload_multipart_sql_comment_false_positive.py  # 3 passed
python3 scripts/check_prepare_regression.py --strict                      # pass=25 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict                 # pass=19 warn=0 fail=0
```

이 변경은 full demotion이 아니다. Candidate visibility는 유지하고, upload-like POST의 SQL comment-only 약신호를 strong SQLi로 과분류하지 않도록 한정한다. Apache logs-only boundary도 그대로 유지하며, upload success/DB success/compromise 추론은 추가하지 않는다.

---

## 1. Purpose

This document reviews why the PHP sample observability runs produce `candidate_rows=13` under the current prepare policy.

The immediate question was whether `apache_security_io_v2` caused more candidates than v1. It did not.

A current v1 dry-run and the v2 dry-run both show:

```text
candidate_rows=13
distinct_incident_candidates=13
```

Therefore the candidate count is a result of the current prepare scoring/filtering policy for the PHP sample S01~S15 traffic, not an effect of the v2 LogFormat fields.

After the narrow S09 guard, the count can still remain high because this work does not demote status/error/probe candidates globally. It only prevents upload/sql-comment-only rows from being over-presented as strong SQLi.

---

## 2. Current Decision

```text
v2 field effect: no evidence
prepare policy effect: yes
candidate explanation helper: added
S09 upload/sql_comment-only prepare guard: implemented
S09 diagnostic classification: context_candidate_upload_failure
full upload demotion: not implemented
broader status/error/probe demotion: still review-only
```

The v2 validation remains successful:

```text
apache_security_io_v2 LogFormat output: pass
converter v2 field preservation: pass
pipeline dry-run connectivity: pass
```

This document now separates two items:

```text
implemented:
  upload-like POST + only sqli:sql_comment => weak upload/sql-comment context

still open:
  whether all 13 PHP sample candidates should remain incident candidates or some should become context-only summaries
```

---

## 3. Relevant prepare scoring behavior

`evaluate_row()` performs row-level scoring. If the final score reaches `min_score` it emits a candidate.

In the current dry-run, `min_score=4`.

Relevant scoring patterns include:

```text
status_code in {400,401,403,404,500,502,503}  -> +2
error_link_id exists                           -> +2
no referer + non-browser UA + status>=400      -> +1
login endpoint                                 -> +1
auth payload content-type + login endpoint     -> +1
query endpoint + attack tokens                 -> +2
long query                                     -> +1
SQLi/XSS/traversal/CMDI patterns               -> pattern-specific points
```

A row with only the following can already reach candidate threshold:

```text
error_status(+2) + error_linked(+2) = 4
```

This is useful in real logs because a linked 4xx/5xx error may be important. However, in controlled observability traffic it also pulls expected test failures into incident candidates.

The S09 guard only affects one narrow SQLi contribution path:

```text
POST + upload-like/multipart context + only sqli:sql_comment + no stronger SQLi in logged target
```

It does not remove `error_status`, `error_linked`, or `no_referer_non_browser_error` visibility.

---

## 4. Diagnostic helper result

A diagnostic helper was added to explain why candidates crossed the threshold.

```text
scripts/explain_prepare_candidates.py
```

The helper does not modify prepare output, candidate scoring, demotion, severity, verdict, or category. It only groups candidate reasons into review buckets.

After the prepare guard, the helper was adjusted so weak upload/sql-comment hints are grouped under `upload_context`, not `attack_payload`.

### 4.1 v1/v2 policy count comparison

Before the prepare guard, v1/v2 both showed `candidate_rows=13`. That confirmed that the candidate count is not a v2 field effect.

After the S09 guard, the expected policy shape is still centered on the same classes, but S09 is explicitly context-oriented:

```text
keep_candidate_payload = 3
context_candidate_upload_failure = 1
context_candidate_auth_failure = 1
context_candidate_probe = 5
demotion_candidate_status_error_only = 3
```

### 4.2 Updated candidate table interpretation

| scenario | method | uri | status | score | diagnostic policy_class | interpretation |
|---|---|---|---:|---:|---|---|
| S15 | GET | `/download.php` | 404 | 15 | `keep_candidate_payload` | traversal-like request-pattern candidate; no file-read success inference |
| S14 | GET | `/search.php` | 200 | 13 | `keep_candidate_payload` | XSS-like request-pattern candidate; no browser execution inference |
| S13 | GET | `/search.php` | 200 | 13 | `keep_candidate_payload` | SQLi-like request-pattern candidate; no DB/auth/data impact inference |
| S09 | POST | `/upload.php` | 400 | 5 | `context_candidate_upload_failure` | upload-like POST with weak SQL comment context only; no upload success inference |
| S08 | POST | `/login.php` | 401 | 7 | `context_candidate_auth_failure` | auth failure context; no login success inference |
| S12 | GET | `/wp-login.php` | 404 | 6 | `context_candidate_probe` | probe/sensitive-path context |
| S11 | GET | `/error.php` | 500 | 6 | `demotion_candidate_status_error_only` | isolated app/server error context unless tied to payload/repetition |
| S06 | GET | `/private/secret.txt` | 403 | 6 | `demotion_candidate_status_error_only` | forbidden/sensitive path context; no exposure inference |
| S12 | GET | `/does-not-exist` | 404 | 4 | `context_candidate_probe` | scanner/probe context |
| S12 | GET | `/.env` | 404 | 4 | `context_candidate_probe` | sensitive-path probe context; no file exposure inference |
| S12 | GET | `/admin` | 404 | 4 | `context_candidate_probe` | admin-path probe context; no app presence inference |
| S07 | GET | `/login.php` | 200 | 4 | `demotion_candidate_status_error_only` | login form/context row, not auth success |
| S05 | GET | `/does-not-exist-*` | 404 | 4 | `context_candidate_probe` | expected not-found/probe context |

### 4.3 Important S09 finding

Before the guard, S09 looked like a payload candidate because it contained:

```text
sqli:sql_comment(+2)
error_status:400(+2)
error_linked(+2)
no_referer_non_browser_error(+1)
```

However, in the PHP sample, S09 is an upload-like POST failure. Apache security logs do not contain the raw POST body, and multipart/form-data boundaries or upload-like request syntax can include comment-marker-like text such as `--`.

The implemented behavior is now:

```text
sqli:sql_comment(+2) is not used as a strong SQLi contribution in this narrow upload-like context.
```

The row remains a candidate due to status/error context, but its `verdict_hint` is `suspicious` rather than `sqli`.

---

## 5. Candidate classification for PHP sample S01~S15

### 5.1 Candidates that should remain candidates

These rows contain explicit attack-like payload structure and should remain incident candidates.

| scenario | reason to keep candidate | guardrail |
|---|---|---|
| S13 SQLi-like | SQLi payload structure such as quote termination / OR true pattern | Do not infer DB query success, auth bypass, or data exposure |
| S14 XSS-like | XSS payload structure such as script/alert pattern | Do not infer browser execution or theft |
| S15 traversal-like | traversal payload structure such as dot-dot slash and `/etc/passwd` target | Do not infer file read or file content exposure |

Notes:

- These should remain candidates even when response is 200/404/text/html.
- Success must remain inconclusive from Apache logs alone.
- These are request-pattern candidates, not confirmed compromises.

### 5.2 Candidates that may be better represented as context-only

These rows can cross `min_score=4` mostly through status/error metadata rather than explicit exploit payload structure.

| scenario / request type | likely current reason | preferred representation |
|---|---|---|
| S11 `/error.php` 500 | `error_status:500(+2)` + `error_linked(+2)` | error/application context unless repeated or associated with explicit attack payload |
| S08 `/login.php` POST 401 | login endpoint + auth payload content type + 401/error context | auth behavior context; no login success inference |
| S09 `/upload.php` POST 400 | 400/error context plus weak upload/sql-comment context | upload failure context; no upload success inference; not strong SQLi unless stronger SQLi structure exists |
| S12 `/admin`, `/.env`, `/wp-login.php`, `/server-status`, `/does-not-exist` | probe paths + 4xx/200 + possible error_linked | probing/sensitive-path/mixed-baseline context summaries |
| S06 `/private/secret.txt` 403 | sensitive/forbidden path + 403/error context | may remain candidate or sensitive-path context depending on policy, but no exposure inference |
| S07 `/login.php` GET 200 | login endpoint + error-linked app notice/context + long query | login form/context row; no authentication success inference |
| S05 not-found 404 | not-found + non-browser/no-referer + long query | not-found/probe context unless repeated/associated with payload |

The key concern is not that these are irrelevant. They are useful context. The remaining question is whether they should appear as top incident candidates when stronger payload candidates already exist.

---

## 6. Why this happens in the PHP sample

The PHP sample scenario catalog intentionally exercises several non-success cases:

```text
S05 404 not found
S06 403 forbidden private path
S08 401 login POST
S09 400 upload-like POST
S11 500 server error
S12 burst with /admin, /wp-login.php, /.env, /server-status, /does-not-exist
S15 traversal-like request returning 404
```

These are valuable for observability because they verify that Apache logs capture response status, handler, error correlation, and request metadata.

But the same signals are also candidate-scoring signals:

```text
4xx/5xx status
error_link_id
non-browser test UA
no referer
sensitive/probe path
```

So the PHP sample naturally produces many candidates under a conservative row-level scoring policy.

---

## 7. Policy options

### Option A. Keep current scoring unchanged except implemented narrow guard

Pros:

- Preserves conservative detection in real operational logs.
- Avoids accidentally suppressing useful 4xx/5xx error-linked signals.
- S09 SQLi overclassification is already reduced by the narrow guard.

Cons:

- Observability runs still show many candidates that are better understood as context-only.
- Stage1/Stage2 dry-run previews can remain noisier than desired.

### Option B. Add demotion rules for isolated status/error-only rows

Potential rule shape:

```text
IF row has no explicit attack payload signal
AND candidate score is mostly from error_status/error_linked/no_referer_non_browser_error
AND row is already represented in a context-only summary
THEN keep it as filtered/context-only rather than incident candidate
```

Pros:

- Reduces incident candidate noise for observability/test runs.
- Keeps probing/sensitive-path/mixed-baseline summaries as the primary representation for scanner burst noise.

Cons:

- Risk of hiding real operational error-linked activity if rule is too broad.
- Requires fixtures and regression tests before implementation.

### Option C. Apply demotion only to lab/observability traffic markers

Potential rule shape:

```text
IF user_agent contains obs-test/* or lab marker
AND no explicit attack payload signal
AND row belongs to known scenario context
THEN demote to context-only
```

Pros:

- Safer for production-like logs.
- Makes observability runs easier to inspect.

Cons:

- Adds lab-specific policy to prepare, which may be undesirable.
- Could create a separate behavior between lab and real logs.

### Option D. Do not change prepare further; improve reporting/display context only

Pros:

- No additional candidate selection risk.
- Stage2/Web UI can label these as context/error/probing candidates.

Cons:

- Candidate count remains high.
- Stage1 still processes rows that may be context-only.

---

## 8. Recommended direction

Do not implement broad demotion yet.

Recommended sequence from this point:

```text
1. Keep the narrow upload/sql-comment guard. Completed.
2. Keep diagnostic helper classification. Completed.
3. Observe PHP sample v1/v2 candidate distribution after guard.
4. Review status/error-only and scanner/probe context candidates separately.
5. Add fixtures before any broader demotion rule.
```

For status/error-only demotion, require all of these:

```text
- no SQLi/XSS/traversal/CMDI/file-disclosure/webshell/SSRF/Log4Shell/SSTI/XXE explicit payload signal
- no HPP embedded attack signal
- score reaches threshold primarily from status/error/no-referer metadata
- row is represented in an existing context-only summary
- not repeated in a way that indicates an operational security incident
```

---

## 9. Candidate reason review checklist

For each candidate, inspect:

```text
request_id
scenario marker / user_agent
method
uri
query_string
status_code
error_link_id
score
verdict_hint
reason_hints
context summary membership
```

Useful local commands:

```bash
python3 scripts/explain_prepare_candidates.py \
  --run-dir runs/obs_php_sample_002_pipeline_dryrun \
  --format markdown \
  --out /tmp/obs_php_sample_002_candidate_explain.md

python3 scripts/explain_prepare_candidates.py \
  --run-dir runs/obs_php_sample_v2_sqlcomment_guard_dryrun \
  --format markdown \
  --out /tmp/obs_php_sample_v2_sqlcomment_guard_explain.md

jq '.meta.source_counts' runs/obs_php_sample_002_pipeline_dryrun/stage1_results.json
```

For direct llm input inspection:

```bash
jq '.analysis_candidates[] | {
  request_id,
  uri,
  status_code,
  score,
  verdict_hint,
  reason_hints
}' runs/obs_php_sample_002_pipeline_dryrun/llm_input.json
```

For v2 guard dry-run:

```bash
jq '.analysis_candidates[] | {
  request_id,
  uri,
  status_code,
  score,
  verdict_hint,
  log_schema,
  handler,
  raw_request_target,
  reason_hints
}' runs/obs_php_sample_v2_sqlcomment_guard_dryrun/llm_input.json
```

Adjust paths if the run copied artifacts under a different run_dir structure.

---

## 10. Expected classification table

| candidate group | keep candidate? | reason |
|---|---|---|
| SQLi-like query | yes | explicit payload structure |
| XSS-like query | yes | explicit payload structure |
| traversal-like query | yes | explicit payload structure, but success inconclusive |
| upload-like POST with SQL comment-only signal | candidate may remain; not strong SQLi | upload/multipart failure context unless stronger SQLi structure exists |
| isolated 500 error page | maybe no | likely app/error context unless tied to attack payload or repetition |
| isolated login POST 401 | maybe no | auth behavior context; no success inference |
| isolated upload POST 400 | maybe no | upload failure context; no stored upload inference |
| scanner burst single 404 probes | maybe no | better represented by probing/sensitive-path/mixed-baseline summaries |
| forbidden sensitive path 403 | maybe | can be a candidate in some real logs, but in sample it may be context-only |
| `/server-status` 200 from localhost | no by itself | context-only; external exposure requires separate verification |

---

## 11. Guardrails

Any future change must preserve these:

```text
- Do not infer success from status_code=200.
- Do not infer file exposure from response_body_bytes or resp_content_type.
- Do not infer login success from POST metadata, Cookie, or Authorization presence.
- Do not infer upload success from multipart POST metadata.
- Do not infer browser execution from XSS payload in Apache logs.
- Do not infer DB results from SQLi-like query in Apache logs.
- Do not infer attacker identity from X-Forwarded-For alone.
- Do not promote context-only summaries to findings without explicit candidate evidence.
```

---

## 12. Proposed follow-up work

### P1. Diagnostic documentation

Status: completed.

`explain_prepare_candidates.py` explains why each candidate crossed threshold and classifies candidates into review buckets. It also treats weak upload/sql-comment hints as `upload_context`, not `attack_payload`.

### P2. Narrow SQL comment-only upload guard

Status: completed.

`src/prepare_llm_input.py` now treats upload-like POST + only `sqli:sql_comment` as weak upload/sql-comment context rather than strong SQLi.

### P3. Broader status/error demotion rule proposal

Still open.

Only after additional fixture review, consider a narrow demotion rule for status/error-only rows already represented in context-only summaries.

### P4. Scanner/probe context demotion proposal

Still open.

Review whether individual scanner burst probe rows should remain candidates or be represented by probing/sensitive-path/mixed-baseline summaries.

### P5. Web UI/reporting polish

If candidates remain high, show clearer display-only labels in dry-run/report preview:

```text
status/error-only candidate
context-backed probe
auth failure context
upload failure context
weak upload/sql-comment context
```

These labels must remain display-only and must not alter severity/verdict/category.

---

## 13. Current recommendation

Keep the implemented S09 narrow guard.

Do not implement broader demotion yet.

Treat the current `candidate_rows=13` as a useful signal that the PHP sample contains many intentionally noisy/error scenarios. The next candidate-policy work should be scoped separately:

```text
1. status/error-only candidate demotion review
2. scanner/probe context-only demotion review
3. Web UI display-only upload/context badges if useful
```
