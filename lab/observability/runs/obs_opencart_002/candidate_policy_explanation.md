# Prepare Candidate Explanation

- input: `/opt/web_log_analysis/runs/obs_opencart_002_current_dryrun/llm_input.json`
- source: `analysis_candidates`
- candidate_count: `3`

## Policy counts

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |

## Candidate table

| # | scenario | method | uri | status | score | verdict_hint | policy_class | top reasons |
|---:|---|---|---|---:|---:|---|---|---|
| 1 | S14 | GET | /search.php | 200 | 12 | xss | `keep_candidate_payload` | xss:script_tag(+5), xss:alert_call(+3), query_endpoint_with_attack_tokens(+2), very_long_query(+1), long_query(+1) |
| 2 | S15 | GET | /download.php | 200 | 11 | path_traversal | `keep_candidate_payload` | traversal:etc_passwd(+5), traversal:dotdot_slash(+4), very_long_query(+1), long_query(+1) |
| 3 | S13 | GET | /search.php | 200 | 11 | sqli | `keep_candidate_payload` | sqli:quote_termination(+4), sqli:or_true(+4), query_endpoint_with_attack_tokens(+2), long_query(+1) |

## Details

### 1. S14 GET /search.php

- request_id: `agWCT2FfzJj2c4Cdx5KuQQAAAAk`
- status_code: `200`
- score/min_score/margin: `12/4/8`
- verdict_hint: `xss`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: xss:script_tag(+5), xss:alert_call(+3), xss:script_tag, xss:external_navigation
  - `observability`: observability:front_controller_candidate, observability:route_param_present, observability:route_param=search.php
  - `length_complexity`: long_query(+1), very_long_query(+1)
  - `other`: encoding:url_encoded_payload, query_endpoint_with_attack_tokens(+2)

### 2. S15 GET /download.php

- request_id: `agWCT85SKrDnj3kWeoAzgwAAAAo`
- status_code: `200`
- score/min_score/margin: `11/4/7`
- verdict_hint: `path_traversal`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: traversal:dotdot_slash(+4), traversal:etc_passwd(+5), traversal:html_fallback_like_response
  - `observability`: observability:front_controller_candidate, observability:route_param_present, observability:route_param=download.php, observability:fallback_200_candidate
  - `length_complexity`: long_query(+1), very_long_query(+1)
  - `other`: xss:external_navigation

### 3. S13 GET /search.php

- request_id: `agWCT36yJKgAB6rWicbxrwAAAAg`
- status_code: `200`
- score/min_score/margin: `11/4/7`
- verdict_hint: `sqli`
- policy_class: `keep_candidate_payload`
- policy_note: explicit attack-like payload structure is present; keep as request-pattern candidate, not success proof
- reason_groups:
  - `attack_payload`: sqli:or_true(+4), sqli:quote_termination(+4)
  - `observability`: observability:front_controller_candidate, observability:route_param_present, observability:route_param=search.php
  - `length_complexity`: long_query(+1)
  - `other`: encoding:url_encoded_payload, xss:external_navigation, query_endpoint_with_attack_tokens(+2)
