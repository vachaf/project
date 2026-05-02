# F Set R2B Run Summary

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- started_at: 2026-05-02T19:08:13+09:00
- ended_at: 2026-05-02T19:08:29+09:00
- request_count: 11
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- safety: approved local lab only; do not execute against public external targets by default

## Results

| request_label | method | path | status_code | response_body_bytes | duration_ms | error |
|---|---|---|---|---|---|---|
| existing_account_failure_1_admin | POST | /rest/user/login | 401 | 26 | 38.11 |  |
| existing_account_failure_2_user1 | POST | /rest/user/login | 401 | 26 | 11.66 |  |
| existing_account_failure_3_jim | POST | /rest/user/login | 401 | 26 | 10.71 |  |
| nonexistent_account_failure_1 | POST | /rest/user/login | 401 | 26 | 13.71 |  |
| nonexistent_account_failure_2 | POST | /rest/user/login | 401 | 26 | 10.61 |  |
| nonexistent_account_failure_3 | POST | /rest/user/login | 401 | 26 | 9.4 |  |
| lockout_probe_failure_1 | POST | /rest/user/login | 401 | 26 | 11.41 |  |
| lockout_probe_failure_2 | POST | /rest/user/login | 401 | 26 | 12.81 |  |
| lockout_probe_failure_3 | POST | /rest/user/login | 401 | 26 | 19.51 |  |
| lockout_probe_failure_4 | POST | /rest/user/login | 401 | 26 | 11.19 |  |
| lockout_probe_failure_5 | POST | /rest/user/login | 401 | 26 | 7.88 |  |

## Interpretation Guardrails

- Results are limited to response surface comparison and response delta observation.
- No account existence inference, no lockout confirmation, and no auth success inference.
- Apache-log-based analysis does not see POST body contents from this runner.
