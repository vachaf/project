# Upload Multipart SQL Comment False-Positive Review

- Date: 2026-05-15
- Status: design/review note
- Scope: narrow prepare false-positive review for upload-like POST rows with only `sqli:sql_comment` as SQLi evidence
- Related review:
  - `docs/design/99_prepare_php_sample_candidate_policy_review.md`
- Related diagnostic helper:
  - `scripts/explain_prepare_candidates.py`
- Related fixture/test:
  - `tests/fixtures/prepare_candidate_explain_sample.json`
  - `tests/test_explain_prepare_candidates.py`
- Related scenario:
  - PHP sample S09 upload-like POST

---

## 0. 2026-05-20 Implementation Update

Prepare 레벨에 narrow guard를 적용하고, 전용 테스트를 추가했다.

- Added test:
  - `tests/test_prepare_upload_multipart_sql_comment_false_positive.py`
  - case A: upload-like POST + only `sqli:sql_comment`
  - case B: upload-like POST + strong SQLi in logged target
  - case C: normal search SQLi with sql_comment + strong evidence
- Applied guard:
  - `src/prepare_llm_input.py`
  - SQLi pattern 자체는 유지
  - `POST + upload-like/multipart context + sql_comment 단독 + logged target 강한 SQLi 구조 없음`일 때만 `sqli:sql_comment(+2)`를 약신호 컨텍스트로 처리
- S09 기대 동작:
  - `verdict_hint=sqli` 과분류를 피하고 `suspicious/context` 쪽으로 유지
  - candidate visibility는 유지 가능
- Strong SQLi 유지:
  - upload endpoint라도 `or_true`, `quote_termination` 등 강한 SQLi 구조가 있으면 기존처럼 SQLi candidate 유지
  - S13 SQLi-like / S14 XSS-like / S15 traversal-like 회귀 없음

Apache logs-only evidence boundary도 유지한다. request body, upload success, DB result, webshell success, compromise 추론은 추가하지 않았다.

---

## 1. Purpose

This document reviews whether prepare should add a narrow false-positive guard for upload-like POST rows where the only SQLi-like signal is `sqli:sql_comment`.

The motivating case is PHP sample S09:

```text
method=POST
uri=/upload.php
status_code=400
verdict_hint=sqli
reason_hints:
  sqli:sql_comment(+2)
  error_status:400(+2)
  error_linked(+2)
  no_referer_non_browser_error(+1)
```

The diagnostic helper now classifies this as:

```text
context_candidate_upload_failure
```

rather than:

```text
keep_candidate_payload
```

This review asks whether the same idea should be applied inside prepare scoring/selection, not just in the diagnostic helper.

---

## 2. Current observed behavior

In current PHP sample v1/v2 dry-runs:

```text
candidate_rows=13
distinct_incident_candidates=13
```

The count is not caused by `apache_security_io_v2`; v1 and v2 behave the same under the same prepare policy.

The important S09 detail is that upload-like POST currently gets an SQLi-like payload contribution from `sqli:sql_comment(+2)`.

However, Apache logs do not include the raw POST body. Therefore, for upload-like multipart requests, a SQL comment marker observation can be ambiguous.

Possible sources of the marker include:

```text
- multipart/form-data boundary markers such as --boundary
- upload/client syntax artifacts visible in request metadata
- intentionally crafted SQLi payload in query/path/header-like metadata
```

Apache access/security logs alone cannot distinguish all of these unless the stronger SQLi structure is visible in the logged fields.

---

## 3. Problem statement

`SQLI_COMMENT_PATTERN` treats comment markers as SQLi-like evidence.

That is usually useful when paired with stronger SQLi structure, for example:

```text
' OR '1'='1 --
UNION SELECT ... --
?id=1--
?id=1/*comment*/
```

But in an upload-like POST context, `sqli:sql_comment` alone is weak.

Problem:

```text
upload-like POST + only sqli:sql_comment
```

can be over-presented as:

```text
SQLi payload candidate
```

when the safer interpretation is:

```text
upload failure / multipart context candidate
```

This is not a success-inference issue. The existing guardrails still prevent DB success claims. The issue is candidate category and wording quality.

---

## 4. Goals

- Reduce SQLi overclassification for upload-like POST rows when `sqli:sql_comment` is the only SQLi signal.
- Preserve strong SQLi candidates such as S13.
- Preserve operational visibility for upload endpoint failures.
- Keep Apache logs-only evidence boundaries intact.
- Avoid broad demotion of all upload endpoint errors.
- Avoid lab-only special casing where possible.

---

## 5. Non-goals

- Do not infer that upload succeeded or failed beyond observed HTTP/app metadata.
- Do not infer file storage, file execution, webshell success, or compromise.
- Do not parse or reconstruct raw POST bodies.
- Do not remove all upload endpoint candidates.
- Do not suppress SQLi candidates with stronger SQLi structure.
- Do not change v1/v2 LogFormat semantics.

---

## 6. Evidence boundary

For Apache access/security logs only:

```text
Observed:
- method
- URI/query target
- status code
- content type/length metadata
- request_id/error_link_id
- handler
- response metadata

Not observed:
- raw POST body
- uploaded file contents
- stored file path
- DB query execution
- backend validation result unless separately logged
- browser or server-side code execution
```

Therefore:

```text
sqli:sql_comment alone on an upload-like POST should not be treated as strong SQLi payload evidence.
```

---

## 7. Candidate policy options

### Option A. Do nothing in prepare

Keep prepare scoring unchanged and rely on `explain_prepare_candidates.py` for review.

Pros:

- Zero risk to existing scoring behavior.
- Keeps conservative detection.
- Diagnostic helper already makes S09 interpretation clearer.

Cons:

- Stage1/Stage2 still receives S09 with `verdict_hint=sqli`.
- LLM/report wording may still overemphasize SQLi unless prompt/reporting compensates.

### Option B. Remove only the SQLi score contribution in upload/sql-comment-only context

Potential rule:

```text
IF method is POST
AND request is upload-like or multipart-like
AND the only SQLi hint is sqli:sql_comment
AND no stronger SQLi structure is present
THEN do not add the sqli:sql_comment score contribution
AND add a context hint such as sqli:sql_comment_upload_context_weak_signal
```

Expected S09 effect:

```text
before: score=7, verdict_hint=sqli
after:  score likely 5, verdict_hint may become suspicious/context depending on remaining hints
```

Pros:

- Narrowly addresses the false-positive class.
- Preserves status/error observability.
- Does not demote stronger SQLi payloads.

Cons:

- S09 may still remain a candidate due to `error_status + error_linked + no_referer`.
- Implementation must be careful not to suppress query-string SQL comment attacks to upload endpoints.

### Option C. Demote upload/sql-comment-only rows to context-only

Potential rule:

```text
IF upload-like POST
AND only SQLi signal is sqli:sql_comment
AND remaining score is status/error/no-referer only
THEN remove from incident candidates and represent as upload failure context/supporting event
```

Pros:

- Reduces candidate noise more strongly.
- Aligns with diagnostic classification.

Cons:

- Higher risk. Upload endpoint failures can be meaningful in real logs.
- Requires context summary linkage before demotion.
- Should not be implemented without fixture/regression coverage.

### Option D. Keep candidate but change verdict/category

Potential rule:

```text
IF upload-like POST + only sqli:sql_comment
THEN keep as candidate if score still crosses threshold
BUT verdict_hint becomes suspicious instead of sqli
AND add reason hint for weak upload SQL-comment context
```

Pros:

- Avoids SQLi overclassification while preserving review visibility.
- Lower risk than full demotion.

Cons:

- Candidate count remains unchanged.
- Requires careful ordering with existing verdict selection.

---

## 8. Recommended direction

Recommended sequence:

```text
1. Keep diagnostic helper classification in place. Completed.
2. Add fixture/test for diagnostic behavior. Completed.
3. Before changing prepare, add or identify prepare-level fixture coverage for:
   - upload-like POST with only sqli:sql_comment
   - upload-like POST with stronger SQLi evidence
   - normal SQLi query with sql_comment + stronger evidence
4. Prefer Option D or Option B before Option C.
5. Do not implement broad upload demotion yet.
```

Preferred implementation path if code change is pursued:

```text
First candidate: Option D
- keep candidate visibility if remaining score crosses threshold
- avoid `verdict_hint=sqli` when the only SQLi signal is weak upload-context sql_comment
- add explicit reason hint that SQL comment is weak in upload/multipart context

Second candidate: Option B
- remove or zero out the `sqli:sql_comment(+2)` scoring contribution only in this narrow context

Defer: Option C
- full demotion to context-only should wait until broader context-summary demotion policy is designed
```

---

## 9. Required guard conditions for prepare-side handling

A prepare-side guard must require all of the following:

```text
method is POST
AND endpoint/context is upload-like or multipart-like
AND SQLi hint set contains sqli:sql_comment
AND SQLi hint set contains no stronger SQLi hint
AND query_string/raw_request_target do not show stronger SQLi structure
```

Stronger SQLi hints include at least:

```text
sqli:or_true
sqli:and_true
sqli:quote_termination
sqli:union_select
sqli:select_from
sqli:information_schema
sqli:sleep_func
sqli:benchmark_func
sqli:waitfor_delay
sqli:drop_table
sqli:insert_into
sqli:update_set
sqli:delete_from
```

The guard must not fire when an upload endpoint includes explicit SQLi structure in the logged target, such as:

```text
/upload.php?name=1%27%20OR%20%271%27%3D%271--
/upload.php?file=1%20UNION%20SELECT%201,2--
```

---

## 10. Suggested reason hints

If prepare is changed, use explicit weak-signal hints rather than silently dropping context.

Candidate hints:

```text
sqli:sql_comment_upload_context_weak_signal
sqli:sql_comment_only_upload_context_no_strong_sqli_structure
upload:multipart_or_upload_like_context
upload:no_upload_success_inference
```

Avoid wording that implies success or backend validation result.

---

## 11. Test plan

### Diagnostic helper tests

Already added:

```text
tests/fixtures/prepare_candidate_explain_sample.json
tests/test_explain_prepare_candidates.py
```

Coverage:

```text
- upload-like POST + sqli:sql_comment-only -> context_candidate_upload_failure
- strong SQLi payload -> keep_candidate_payload
- status/error-only row -> demotion_candidate_status_error_only
- sensitive probe -> context_candidate_probe
```

### Prepare-level tests before code change

Before modifying prepare scoring/verdict logic, add or extend tests to cover:

```text
1. Upload-like POST with only sqli:sql_comment
   Expected:
   - no strong SQLi verdict/category, or SQLi score contribution is suppressed
   - upload weak-context hint is present
   - no upload success inference

2. Upload-like POST with stronger SQLi in query target
   Expected:
   - remains SQLi candidate
   - stronger SQLi hints preserved

3. Normal search/query SQLi with sql_comment and stronger evidence
   Expected:
   - remains SQLi candidate

4. Normal request with status/error only
   Expected:
   - unchanged until broader status/error demotion is implemented
```

### Regression checks

Run after any prepare-side code change:

```bash
python3 -m py_compile src/prepare_llm_input.py src/prepare/sqli_hints.py
python3 -m pytest -q tests/test_explain_prepare_candidates.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

---

## 12. Impact on PHP sample S09

Current diagnostic classification:

```text
S09 POST /upload.php
status=400
score=7
verdict_hint=sqli
policy_class=context_candidate_upload_failure
```

Preferred prepare-side behavior, if changed:

```text
S09 should not be presented as strong SQLi based only on sqli:sql_comment.
```

Acceptable outcomes:

```text
A. Still candidate, but verdict_hint/category no longer SQLi.
B. Still candidate, with weak upload/sql-comment context hint.
C. Eventually context-only/supporting event, but only after broader demotion policy exists.
```

Current preferred first change:

```text
A or B, not C.
```

---

## 13. Open questions

- Should `sqli:sql_comment` ever be a standalone SQLi signal without stronger SQLi structure?
- Should the guard live inside `src/prepare/sqli_hints.py` or inside row-level scoring in `prepare_llm_input.py`?
- Should verdict selection distinguish `weak_sqli_context` from `sqli`?
- Should upload context be detected by URI only, `req_content_type`, or both?
- Should this rule apply only to POST, or also PUT/PATCH upload-like requests later?

---

## 14. Current recommendation

Do not implement full demotion yet.

Implementing a narrow prepare-side guard is reasonable only after prepare-level tests are added.

Preferred next implementation candidate:

```text
upload-like POST + only sqli:sql_comment
=> not strong SQLi verdict
=> add weak upload/sql-comment context hint
=> preserve status/error visibility
```

This preserves the Apache logs-only boundary and reduces SQLi overclassification without hiding upload endpoint failures.
