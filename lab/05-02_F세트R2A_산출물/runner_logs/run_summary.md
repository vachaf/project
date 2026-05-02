# F Set R2A Run Summary

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- started_at: 2026-05-02T17:14:43+09:00
- ended_at: 2026-05-02T17:16:30+09:00
- request_count: 14
- sleep_scale: 1.0
- timeout_sec: 10.0
- safety: approved local lab only; do not execute against public external targets

## Results

| request_label | method | path | status_code | duration_ms | error |
|---|---|---|---|---|---|
| slow_brute_login_1 | POST | /rest/user/login | 401 | 29.69 |  |
| slow_brute_login_2 | POST | /rest/user/login | 401 | 10.66 |  |
| slow_brute_login_3 | POST | /rest/user/login | 401 | 12.01 |  |
| slow_brute_login_4 | POST | /rest/user/login | 401 | 10.43 |  |
| slow_brute_login_5 | POST | /rest/user/login | 401 | 11.92 |  |
| slow_brute_login_6 | POST | /rest/user/login | 401 | 17.53 |  |
| browse_search_apple | GET | /rest/products/search?q=apple | 200 | 10.46 |  |
| auth_fail_1 | POST | /rest/user/login | 401 | 19.72 |  |
| browse_products | GET | /rest/products | 500 | 5.78 |  |
| auth_fail_2 | POST | /rest/user/login | 401 | 11.18 |  |
| browse_search_phone | GET | /rest/products/search?q=phone | 200 | 11.04 |  |
| auth_fail_3 | POST | /rest/user/login | 401 | 12.92 |  |
| chrome_login_200 | POST | /rest/user/login | 200 | 21.77 |  |
| ci_login_200 | POST | /rest/user/login | 200 | 55.71 |  |

## Interpretation Guardrails

- Apache-log-based analysis does not see POST body contents from this runner.
- 200 responses are baseline observations, not proof of auth success.
- 401 repetition is logged as auth-abuse possibility context only.
