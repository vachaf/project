# F Set R2A Execution Plan

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- request_count: 14
- sleep_scale: 1.0
- timeout_sec: 10.0
- safety: approved local lab only; do not execute against public external targets
- note: POST body values are execution-only inputs and are not visible to the Apache-log-based analysis pipeline

## Requests

| # | scenario_id | runner label | request_label | method | path | expected_response | scaled_sleep_after_sec |
|---|---|---|---|---|---|---|---|
| 1 | F-R2A-01 | slow_brute_401_x6 | slow_brute_login_1 | POST | /rest/user/login | 401 | 10.0 |
| 2 | F-R2A-01 | slow_brute_401_x6 | slow_brute_login_2 | POST | /rest/user/login | 401 | 10.0 |
| 3 | F-R2A-01 | slow_brute_401_x6 | slow_brute_login_3 | POST | /rest/user/login | 401 | 10.0 |
| 4 | F-R2A-01 | slow_brute_401_x6 | slow_brute_login_4 | POST | /rest/user/login | 401 | 10.0 |
| 5 | F-R2A-01 | slow_brute_401_x6 | slow_brute_login_5 | POST | /rest/user/login | 401 | 10.0 |
| 6 | F-R2A-01 | slow_brute_401_x6 | slow_brute_login_6 | POST | /rest/user/login | 401 | 0.0 |
| 7 | F-R2A-02 | interleaved_browse_auth_failures | browse_search_apple | GET | /rest/products/search?q=apple | 200 | 8.0 |
| 8 | F-R2A-02 | interleaved_browse_auth_failures | auth_fail_1 | POST | /rest/user/login | 401 | 12.0 |
| 9 | F-R2A-02 | interleaved_browse_auth_failures | browse_products | GET | /rest/products | 200 | 8.0 |
| 10 | F-R2A-02 | interleaved_browse_auth_failures | auth_fail_2 | POST | /rest/user/login | 401 | 10.0 |
| 11 | F-R2A-02 | interleaved_browse_auth_failures | browse_search_phone | GET | /rest/products/search?q=phone | 200 | 8.0 |
| 12 | F-R2A-02 | interleaved_browse_auth_failures | auth_fail_3 | POST | /rest/user/login | 401 | 0.0 |
| 13 | F-R2A-03 | chrome_single_200_baseline | chrome_login_200 | POST | /rest/user/login | 200 | 0.0 |
| 14 | F-R2A-04 | ci_single_200_baseline | ci_login_200 | POST | /rest/user/login | 200 | 0.0 |

## Interpretation Guardrails

- The runner does not verify auth success, attack success, or account takeover.
- Expected interpretation strings are capped at possibility level.
- Non-browser user-agent alone is not treated as attack evidence.
