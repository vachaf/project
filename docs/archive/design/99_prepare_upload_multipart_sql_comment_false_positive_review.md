# Upload Multipart SQL Comment False-Positive Review

- Date: 2026-05-15
- Status: implemented narrow guard / observation note
- Scope: narrow prepare false-positive guard for upload-like POST rows with only `sqli:sql_comment` as SQLi evidence
- Related review:
  - `docs/design/99_prepare_php_sample_candidate_policy_review.md`
- Related diagnostic helper:
  - `scripts/explain_prepare_candidates.py`
- Related fixture/test:
  - `tests/fixtures/prepare_candidate_explain_sample.json`
  - `tests/test_explain_prepare_candidates.py`
  - `tests/test_prepare_upload_multipart_sql_comment_false_positive.py`
- Related scenario:
  - PHP sample S09 upload-like POST

---

## 0. 2026-05-20 Implementation / Verification Update

Prepare 레벨에 narrow guard를 적용하고, 전용 테스트와 PHP sample v2 dry-run 재검증까지 완료했다.

적용 커밋:

```text
4dd7a975825d9c10c83ac6e6b9d9c982071be66b
```

후속 diagnostic helper 보정 커밋:

```text
e06247f2d3b2daf969579d87074d1565a280fbea
```

적용 내용:

- `src/prepare_llm_input.py`에 row-level guard 추가
- global SQLi pattern은 유지
- `POST + upload-like/multipart context + sql_comment 단독 + logged target 강한 SQLi 구조 없음` 조건에서만 `sqli:sql_comment(+2)`를 강한 SQLi 기여로 쓰지 않음
- 대신 weak context hint를 추가
- full demotion은 하지 않음
- candidate visibility는 유지

추가/보강된 hint:

```text
sqli:sql_comment_upload_context_weak_signal
sqli:sql_comment_only_upload_context_no_strong_sqli_structure
upload:multipart_or_upload_like_context
upload:no_upload_success_inference
```

PHP sample v2 재검증 run:

```text
runs/obs_php_sample_v2_sqlcomment_guard_dryrun
```

S09 확인 결과:

```json
{
  "method": "POST",
  "uri": "/upload.php",
  "status_code": 400,
  "score": 5,
  "verdict_hint": "suspicious",
  "reason_hints": [
    "xss:external_navigation",
    "error_status:400(+2)",
    "error_linked(+2)",
    "no_referer_non_browser_error(+1)",
    "sqli:sql_comment_upload_context_weak_signal",
    "sqli:sql_comment_only_upload_context_no_strong_sqli_structure",
    "upload:multipart_or_upload_like_context",
    "upload:no_upload_success_inference"
  ]
}
```

Diagnostic helper 확인 결과:

```text
S09 POST /upload.php
score=5
verdict_hint=suspicious
policy_class=context_candidate_upload_failure
reason_groups:
  status_error: error_status:400(+2), error_linked(+2), no_referer_non_browser_error(+1)
  upload_context: sqli:sql_comment_upload_context_weak_signal, sqli:sql_comment_only_upload_context_no_strong_sqli_structure, upload:multipart_or_upload_like_context, upload:no_upload_success_inference
```

강한 SQLi 유지 확인:

```text
S13 GET /search.php
score=13
verdict_hint=sqli
reason_hints include:
  sqli:or_true(+4)
  sqli:quote_termination(+4)
```

검증 결과:

```text
python3 -m py_compile src/prepare_llm_input.py src/prepare/sqli_hints.py  # pass
python3 -m pytest -q tests/test_explain_prepare_candidates.py             # 6 passed
python3 -m pytest -q tests/test_prepare_upload_multipart_sql_comment_false_positive.py  # 3 passed
python3 scripts/check_prepare_regression.py --strict                      # pass=25 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict                 # pass=19 warn=0 fail=0
```

Apache logs-only evidence boundary는 유지한다. request body, upload success, DB result, webshell success, compromise 추론은 추가하지 않았다.

---

## 1. Purpose

This document reviews and records the narrow prepare-side false-positive guard for upload-like POST rows where the only SQLi-like signal is `sqli:sql_comment`.

The motivating case is PHP sample S09:

```text
method=POST
uri=/upload.php
status_code=400
previous verdict_hint=sqli
previous reason_hints:
  sqli:sql_comment(+2)
  error_status:400(+2)
  error_linked(+2)
  no_referer_non_browser_error(+1)
```

The implemented behavior is now:

```text
verdict_hint=suspicious
score=5
policy_class=context_candidate_upload_failure in diagnostic helper
```

The goal is to avoid over-presenting upload/multipart context as SQLi while preserving candidate visibility and strong SQLi detection.

---

## 2. Current observed behavior

In current PHP sample v1/v2 dry-runs:

```text
candidate_rows=13
distinct_incident_candidates=13
```

The count is not caused by `apache_security_io_v2`; v1 and v2 behave the same under the same prepare policy.

The S09 change is not a broad candidate-count reduction. It changes the interpretation of one weak SQL comment signal:

```text
before: S09 score=7, verdict_hint=sqli
after:  S09 score=5, verdict_hint=suspicious
```

S09 remains visible as a candidate because status/error context still reaches threshold:

```text
error_status:400(+2)
error_linked(+2)
no_referer_non_browser_error(+1)
```

---

## 3. Problem statement

`SQLI_COMMENT_PATTERN` treats comment markers as SQLi-like evidence.

That is useful when paired with stronger SQLi structure, for example:

```text
' OR '1'='1 --
UNION SELECT ... --
?id=1--
?id=1/*comment*/
```

But in an upload-like POST context, `sqli:sql_comment` alone is weak.

Apache logs do not include the raw POST body. For upload-like multipart requests, a SQL comment marker observation can be ambiguous.

Possible sources include:

```text
- multipart/form-data boundary markers such as --boundary
- upload/client syntax artifacts visible in request metadata
- intentionally crafted SQLi payload in query/path/header-like metadata
```

Therefore, this class is now handled as weak upload/sql-comment context unless stronger SQLi structure is visible in logged fields.

---

## 4. Goals

- Reduce SQLi overclassification for upload-like POST rows when `sqli:sql_comment` is the only SQLi signal.
- Preserve strong SQLi candidates such as S13.
- Preserve operational visibility for upload endpoint failures.
- Keep Apache logs-only evidence boundaries intact.
- Avoid broad demotion of all upload endpoint errors.
- Avoid lab-only special casing.

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

## 7. Applied guard

The implemented guard follows Option B/D from the original review:

```text
IF method is POST
AND request is upload-like or multipart-like
AND the only SQLi hint is sqli:sql_comment
AND no stronger SQLi structure is present in logged target/query context
THEN do not add sqli:sql_comment(+2) as strong SQLi contribution
AND add weak upload/sql-comment context hints
AND keep status/error visibility
```

The guard must not fire when an upload endpoint includes explicit SQLi structure in the logged target, such as:

```text
/upload.php?name=1%27%20OR%20%271%27%3D%271--
/upload.php?file=1%20UNION%20SELECT%201,2--
```

Stronger SQLi hints that must preserve SQLi classification include:

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

---

## 8. Test coverage

### Diagnostic helper tests

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

### Prepare-level tests

```text
tests/test_prepare_upload_multipart_sql_comment_false_positive.py
```

Coverage:

```text
1. Upload-like POST with only sqli:sql_comment
   Expected:
   - verdict_hint is not sqli
   - weak upload/sql-comment context hints are present
   - no upload success inference

2. Upload-like POST with stronger SQLi in query target
   Expected:
   - remains SQLi candidate
   - stronger SQLi hints preserved

3. Normal search/query SQLi with sql_comment and stronger evidence
   Expected:
   - remains SQLi candidate
```

---

## 9. Impact on PHP sample S09

Current verified behavior:

```text
S09 POST /upload.php
status=400
score=5
verdict_hint=suspicious
policy_class=context_candidate_upload_failure
```

This is acceptable because:

- SQLi overclassification is reduced.
- Candidate visibility remains.
- Upload endpoint failure context remains visible.
- Strong SQLi candidates remain intact.
- No upload success, DB success, file storage, webshell success, or compromise is inferred.

---

## 10. Remaining open questions

- Should broader status/error-only candidates be demoted when already covered by context summaries?
- Should `PUT`/`PATCH` upload-like requests receive a similar guard later?
- Should Web UI show `upload_context` hints as display-only interpretation badges?
- Should Stage2 prompt/report wording explicitly mention upload SQL-comment weak context?

---

## 11. Current recommendation

The narrow prepare-side guard is implemented and verified.

Do not implement full upload demotion yet.

Next possible work is broader but separate:

```text
- status/error-only candidate demotion review
- scanner/probe context-only demotion review
- Web UI display-only upload context badge review
```

These should remain separate from the SQL comment-only upload guard.
