# Prepare Candidate Explanation

- input: `/home/user/project/runs/obs_juiceshop_proxy_v2_error_check_001_current_dryrun/llm_input.json`
- source: `analysis_candidates`
- candidate_count: `2`

## Policy counts

| policy_class | count |
|---|---:|
| `demotion_candidate_status_error_only` | 1 |
| `keep_candidate_payload` | 1 |

## Candidate table

| # | scenario | method | uri | status | score | verdict_hint | policy_class | top reasons |
|---:|---|---|---|---:|---:|---|---|---|
| 2 | - | GET | / | 503 | 5 | suspicious | `demotion_candidate_status_error_only` | error_status:503(+2), error_linked(+2), no_referer_non_browser_error(+1) |
| 1 | - | GET | /search | 503 | 19 | sqli | `keep_candidate_payload` | sqli:quote_termination(+4), sqli:or_true(+4), sqli:sql_comment(+2), query_endpoint_with_attack_tokens(+2), error_status:503(+2) |

## Details

### 2. - GET /

- request_id: `ag6d2oYS5IXnvAooCUylMgAAANQ`
- status_code: `503`
- score/min_score/margin: `5/4/1`
- verdict_hint: `suspicious`
- policy_class: `demotion_candidate_status_error_only`
- policy_note: candidate appears driven mainly by status/error metadata; review before demoting because real logs may need this signal
- reason_groups:
  - `status_error`: error_status:503(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `observability`: observability:reverse_proxy_candidate, observability:backend_response_candidate
  - `other`: xss:external_navigation

### 1. - GET /search

- request_id: `ag6d34YS5IXnvAooCUylMwAAANY`
- status_code: `503`
- score/min_score/margin: `19/4/15`
- verdict_hint: `sqli`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: sqli:or_true(+4), sqli:sql_comment(+2), sqli:quote_termination(+4), sqli:quote_termination, sqli:boolean_true_condition, sqli:comment_sequence
  - `status_error`: error_status:503(+2), error_linked(+2), no_referer_non_browser_error(+1)
  - `observability`: observability:reverse_proxy_candidate, observability:backend_response_candidate
  - `length_complexity`: special_char_ratio_high(+1), special_char_ratio_very_high(+1)
  - `other`: xss:external_navigation, query_endpoint_with_attack_tokens(+2)
