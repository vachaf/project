# Prepare Candidate Explanation

- input: `/opt/web_log_analysis/runs/obs_php_sample_v2_001_current_dryrun/llm_input.json`
- source: `analysis_candidates`
- candidate_count: `13`

## Policy counts

| policy_class | count |
|---|---:|
| `context_candidate_auth_failure` | 1 |
| `context_candidate_probe` | 5 |
| `context_candidate_upload_failure` | 1 |
| `demotion_candidate_status_error_only` | 3 |
| `keep_candidate_payload` | 3 |

## Candidate table

| # | scenario | method | uri | status | score | verdict_hint | policy_class | top reasons |
|---:|---|---|---|---:|---:|---|---|---|
| 4 | S08 | POST | /login.php | 401 | 7 | suspicious | `context_candidate_auth_failure` | error_status:401(+2), error_linked(+2), no_referer_non_browser_error(+1), login_endpoint(+1), auth_payload_content_type(+1) |
| 5 | S12 | GET | /wp-login.php | 404 | 6 | suspicious | `context_candidate_probe` | error_status:404(+2), error_linked(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 10 | S12 | GET | /.env | 404 | 4 | suspicious | `context_candidate_probe` | error_status:404(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 11 | S12 | GET | /admin | 404 | 4 | suspicious | `context_candidate_probe` | error_status:404(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 9 | S12 | GET | /does-not-exist | 404 | 4 | suspicious | `context_candidate_probe` | error_status:404(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 13 | S05 | GET | /does-not-exist-obs_php_sample_v2_001 | 404 | 4 | suspicious | `context_candidate_probe` | error_status:404(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 8 | S09 | POST | /upload.php | 400 | 5 | suspicious | `context_candidate_upload_failure` | error_status:400(+2), error_linked(+2), no_referer_non_browser_error(+1) |
| 6 | S11 | GET | /error.php | 500 | 6 | suspicious | `demotion_candidate_status_error_only` | error_status:500(+2), error_linked(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 7 | S06 | GET | /private/secret.txt | 403 | 6 | suspicious | `demotion_candidate_status_error_only` | error_status:403(+2), error_linked(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 12 | S07 | GET | /login.php | 200 | 4 | suspicious | `demotion_candidate_status_error_only` | error_linked(+2), long_query(+1), login_endpoint(+1) |
| 1 | S15 | GET | /download.php | 404 | 15 | path_traversal | `keep_candidate_payload` | traversal:etc_passwd(+5), traversal:dotdot_slash(+4), error_status:404(+2), error_linked(+2), no_referer_non_browser_error(+1) |
| 2 | S14 | GET | /search.php | 200 | 13 | xss | `keep_candidate_payload` | xss:script_tag(+5), xss:alert_call(+3), query_endpoint_with_attack_tokens(+2), error_linked(+2), long_query(+1) |
| 3 | S13 | GET | /search.php | 200 | 13 | sqli | `keep_candidate_payload` | sqli:quote_termination(+4), sqli:or_true(+4), query_endpoint_with_attack_tokens(+2), error_linked(+2), long_query(+1) |

## Details

### 4. S08 POST /login.php

- request_id: `agaqxFNu_D8aUI1OAXSj9gAAAAM`
- status_code: `401`
- score/min_score/margin: `7/4/3`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_auth_failure`
- policy_note: login/auth POST metadata does not prove auth success; consider auth behavior context unless repeated/combined with payload
- reason_groups:
  - `status_error`: error_status:401(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `auth`: login_endpoint(+1), auth_payload_content_type(+1)
  - `other`: xss:external_navigation

### 5. S12 GET /wp-login.php

- request_id: `agaqxVNu_D8aUI1OAXSj9wAAAAM`
- status_code: `404`
- score/min_score/margin: `6/4/2`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_probe`
- policy_note: probe/sensitive-path signal may be better represented by probing/sensitive-path/mixed-baseline summaries
- reason_groups:
  - `status_error`: error_status:404(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `probe_context`: sensitive_path:wp_login, sensitive_path:admin_path, sensitive_path:no_app_presence_inference
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 10. S12 GET /.env

- request_id: `agaqxcWbuYzatlchTEQbDQAAAAQ`
- status_code: `404`
- score/min_score/margin: `4/4/0`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_probe`
- policy_note: probe/sensitive-path signal may be better represented by probing/sensitive-path/mixed-baseline summaries
- reason_groups:
  - `status_error`: error_status:404(+2), no_referer_non_browser_error(+1)
  - `probe_context`: sensitive_path:env_file, sensitive_path:config_like_path, sensitive_path:no_file_exposure_inference
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 11. S12 GET /admin

- request_id: `agaqxZbD6O29QFRRuF6RBgAAAAY`
- status_code: `404`
- score/min_score/margin: `4/4/0`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_probe`
- policy_note: probe/sensitive-path signal may be better represented by probing/sensitive-path/mixed-baseline summaries
- reason_groups:
  - `status_error`: error_status:404(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 9. S12 GET /does-not-exist

- request_id: `agaqxVGmAsuRathlDi5iFAAAAAA`
- status_code: `404`
- score/min_score/margin: `4/4/0`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_probe`
- policy_note: probe/sensitive-path signal may be better represented by probing/sensitive-path/mixed-baseline summaries
- reason_groups:
  - `status_error`: error_status:404(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 13. S05 GET /does-not-exist-obs_php_sample_v2_001

- request_id: `agaqw_Oku66hobxq_YCD1QAAAAE`
- status_code: `404`
- score/min_score/margin: `4/4/0`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_probe`
- policy_note: probe/sensitive-path signal may be better represented by probing/sensitive-path/mixed-baseline summaries
- reason_groups:
  - `status_error`: error_status:404(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 8. S09 POST /upload.php

- request_id: `agaqxMWbuYzatlchTEQbDAAAAAQ`
- status_code: `400`
- score/min_score/margin: `5/4/1`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_upload_failure`
- policy_note: upload-like POST has only weak SQL comment signal; multipart boundary/comment-marker false positive is possible, so review as upload failure context unless stronger SQLi evidence exists
- reason_groups:
  - `status_error`: error_status:400(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `upload_context`: sqli:sql_comment_upload_context_weak_signal, sqli:sql_comment_only_upload_context_no_strong_sqli_structure, upload:multipart_or_upload_like_context, upload:no_upload_success_inference
  - `other`: xss:external_navigation

### 6. S11 GET /error.php

- request_id: `agaqxVGmAsuRathlDi5iEwAAAAA`
- status_code: `500`
- score/min_score/margin: `6/4/2`
- verdict_hint: `suspicious`
- policy_class: `demotion_candidate_status_error_only`
- policy_note: candidate appears driven mainly by status/error metadata; review before demoting because real logs may need this signal
- reason_groups:
  - `status_error`: error_status:500(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 7. S06 GET /private/secret.txt

- request_id: `agaqxDDz_9fwa3AnTTwzrAAAAAU`
- status_code: `403`
- score/min_score/margin: `6/4/2`
- verdict_hint: `suspicious`
- policy_class: `demotion_candidate_status_error_only`
- policy_note: candidate appears driven mainly by status/error metadata; review before demoting because real logs may need this signal
- reason_groups:
  - `status_error`: error_status:403(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 12. S07 GET /login.php

- request_id: `agaqxJbD6O29QFRRuF6RBQAAAAY`
- status_code: `200`
- score/min_score/margin: `4/4/0`
- verdict_hint: `suspicious`
- policy_class: `demotion_candidate_status_error_only`
- policy_note: candidate appears driven mainly by status/error metadata; review before demoting because real logs may need this signal
- reason_groups:
  - `status_error`: error_linked(+2)
  - `auth`: login_endpoint(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 1. S15 GET /download.php

- request_id: `agaqxpbD6O29QFRRuF6RBwAAAAY`
- status_code: `404`
- score/min_score/margin: `15/4/11`
- verdict_hint: `path_traversal`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: traversal:dotdot_slash(+4), traversal:etc_passwd(+5)
  - `status_error`: error_status:404(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 2. S14 GET /search.php

- request_id: `agaqxTDz_9fwa3AnTTwzrgAAAAU`
- status_code: `200`
- score/min_score/margin: `13/4/9`
- verdict_hint: `xss`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: xss:script_tag(+5), xss:alert_call(+3), xss:script_tag, xss:external_navigation
  - `status_error`: error_linked(+2)
  - `length_complexity`: long_query(+1)
  - `other`: encoding:url_encoded_payload, query_endpoint_with_attack_tokens(+2)

### 3. S13 GET /search.php

- request_id: `agaqxfOku66hobxq_YCD1wAAAAE`
- status_code: `200`
- score/min_score/margin: `13/4/9`
- verdict_hint: `sqli`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: sqli:or_true(+4), sqli:quote_termination(+4)
  - `status_error`: error_linked(+2)
  - `length_complexity`: long_query(+1)
  - `other`: encoding:url_encoded_payload, xss:external_navigation, query_endpoint_with_attack_tokens(+2)
