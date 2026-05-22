# Prepare Candidate Explanation

- input: `/home/user/project/runs/obs_php_sample_v2_error_heavy_external_001/llm_input.json`
- source: `analysis_candidates`
- candidate_count: `12`

## Policy counts

| policy_class | count |
|---|---:|
| `context_candidate_auth_failure` | 1 |
| `context_candidate_probe` | 4 |
| `context_candidate_upload_failure` | 1 |
| `demotion_candidate_status_error_only` | 3 |
| `keep_candidate_payload` | 3 |

## Candidate table

| # | scenario | method | uri | status | score | verdict_hint | policy_class | top reasons |
|---:|---|---|---|---:|---:|---|---|---|
| 4 | - | POST | /login.php | 401 | 8 | suspicious | `context_candidate_auth_failure` | error_status:401(+2), error_linked(+2), no_referer_non_browser_error(+1), long_query(+1), login_endpoint(+1) |
| 5 | - | GET | /wp-login.php | 404 | 6 | suspicious | `context_candidate_probe` | error_status:404(+2), error_linked(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 10 | - | GET | /.env | 404 | 4 | suspicious | `context_candidate_probe` | error_status:404(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 9 | - | GET | /admin | 404 | 4 | suspicious | `context_candidate_probe` | error_status:404(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 12 | - | GET | /does-not-exist-error-heavy-obs_php_sample_v2_error_heavy_external_001 | 404 | 4 | suspicious | `context_candidate_probe` | error_status:404(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 6 | - | POST | /upload.php | 400 | 6 | suspicious | `context_candidate_upload_failure` | error_status:400(+2), error_linked(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 8 | - | GET | /error.php | 500 | 6 | suspicious | `demotion_candidate_status_error_only` | error_status:500(+2), error_linked(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 7 | - | GET | /private/secret.txt | 403 | 6 | suspicious | `demotion_candidate_status_error_only` | error_status:403(+2), error_linked(+2), no_referer_non_browser_error(+1), long_query(+1) |
| 11 | - | GET | /login.php | 200 | 4 | suspicious | `demotion_candidate_status_error_only` | error_linked(+2), long_query(+1), login_endpoint(+1) |
| 1 | - | GET | /download.php | 404 | 16 | path_traversal | `keep_candidate_payload` | traversal:etc_passwd(+5), traversal:dotdot_slash(+4), error_status:404(+2), error_linked(+2), very_long_query(+1) |
| 2 | - | GET | /search.php | 200 | 15 | sqli | `keep_candidate_payload` | sqli:quote_termination(+4), sqli:or_true(+4), sqli:sql_comment(+2), query_endpoint_with_attack_tokens(+2), error_linked(+2) |
| 3 | - | GET | /search.php | 200 | 14 | xss | `keep_candidate_payload` | xss:script_tag(+5), xss:alert_call(+3), query_endpoint_with_attack_tokens(+2), error_linked(+2), very_long_query(+1) |

## Details

### 4. - POST /login.php

- request_id: `ag_7KjLvmTJOLn-ntwQC2wAAAAI`
- status_code: `401`
- score/min_score/margin: `8/4/4`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_auth_failure`
- policy_note: login/auth POST metadata does not prove auth success; consider auth behavior context unless repeated/combined with payload
- reason_groups:
  - `status_error`: error_status:401(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `auth`: login_endpoint(+1), auth_payload_content_type(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 5. - GET /wp-login.php

- request_id: `ag_7Kx4y9UCmVFw1MIusIwAAAAU`
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

### 10. - GET /.env

- request_id: `ag_7KjtegpqAyf9kIwS_cAAAAAA`
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

### 9. - GET /admin

- request_id: `ag_7K2A9Ti1_J7E7zPz-awAAAAc`
- status_code: `404`
- score/min_score/margin: `4/4/0`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_probe`
- policy_note: probe/sensitive-path signal may be better represented by probing/sensitive-path/mixed-baseline summaries
- reason_groups:
  - `status_error`: error_status:404(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 12. - GET /does-not-exist-error-heavy-obs_php_sample_v2_error_heavy_external_001

- request_id: `ag_7KkT26sUguIVwP5mXQwAAAAM`
- status_code: `404`
- score/min_score/margin: `4/4/0`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_probe`
- policy_note: probe/sensitive-path signal may be better represented by probing/sensitive-path/mixed-baseline summaries
- reason_groups:
  - `status_error`: error_status:404(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 6. - POST /upload.php

- request_id: `ag_7KjUOnCHnAu2e68sqBwAAAAQ`
- status_code: `400`
- score/min_score/margin: `6/4/2`
- verdict_hint: `suspicious`
- policy_class: `context_candidate_upload_failure`
- policy_note: upload-like POST has only weak SQL comment signal; multipart boundary/comment-marker false positive is possible, so review as upload failure context unless stronger SQLi evidence exists
- reason_groups:
  - `status_error`: error_status:400(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `upload_context`: sqli:sql_comment_upload_context_weak_signal, sqli:sql_comment_only_upload_context_no_strong_sqli_structure, upload:multipart_or_upload_like_context, upload:no_upload_success_inference
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 8. - GET /error.php

- request_id: `ag_7KWA9Ti1_J7E7zPz-agAAAAc`
- status_code: `500`
- score/min_score/margin: `6/4/2`
- verdict_hint: `suspicious`
- policy_class: `demotion_candidate_status_error_only`
- policy_note: candidate appears driven mainly by status/error metadata; review before demoting because real logs may need this signal
- reason_groups:
  - `status_error`: error_status:500(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 7. - GET /private/secret.txt

- request_id: `ag_7KSdk_p7r7jh-WKq7mAAAAAY`
- status_code: `403`
- score/min_score/margin: `6/4/2`
- verdict_hint: `suspicious`
- policy_class: `demotion_candidate_status_error_only`
- policy_note: candidate appears driven mainly by status/error metadata; review before demoting because real logs may need this signal
- reason_groups:
  - `status_error`: error_status:403(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation

### 11. - GET /login.php

- request_id: `ag_7KqOJAVs7URJOF23TbwAAAAE`
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

### 1. - GET /download.php

- request_id: `ag_7Kydk_p7r7jh-WKq7mQAAAAY`
- status_code: `404`
- score/min_score/margin: `16/4/12`
- verdict_hint: `path_traversal`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: traversal:dotdot_slash(+4), traversal:etc_passwd(+5)
  - `status_error`: error_status:404(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `length_complexity`: long_query(+1), very_long_query(+1)
  - `other`: xss:external_navigation

### 2. - GET /search.php

- request_id: `ag_7K0T26sUguIVwP5mXRAAAAAM`
- status_code: `200`
- score/min_score/margin: `15/4/11`
- verdict_hint: `sqli`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: sqli:or_true(+4), sqli:sql_comment(+2), sqli:quote_termination(+4), sqli:quote_termination, sqli:comment_sequence
  - `status_error`: error_linked(+2)
  - `length_complexity`: long_query(+1)
  - `other`: xss:external_navigation, query_endpoint_with_attack_tokens(+2)

### 3. - GET /search.php

- request_id: `ag_7LDLvmTJOLn-ntwQC3AAAAAI`
- status_code: `200`
- score/min_score/margin: `14/4/10`
- verdict_hint: `xss`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: xss:script_tag(+5), xss:alert_call(+3), xss:script_tag, xss:external_navigation
  - `status_error`: error_linked(+2)
  - `length_complexity`: long_query(+1), very_long_query(+1)
  - `other`: encoding:url_encoded_payload, query_endpoint_with_attack_tokens(+2)
