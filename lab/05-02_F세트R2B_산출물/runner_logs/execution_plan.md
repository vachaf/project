# F Set R2B Execution Plan

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- request_count: 11
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- safety: approved local lab only; do not execute against public external targets by default
- note: POST body values are execution-only inputs and are not visible to the Apache-log-based analysis pipeline

## Requests

| # | scenario_id | runner label | request_label | method | path | expected_response | scaled_sleep_after_sec |
|---|---|---|---|---|---|---|---|
| 1 | F-R2B-01 | existing_account_failures_x3 | existing_account_failure_1_admin | POST | /rest/user/login | 401 | 1.0 |
| 2 | F-R2B-01 | existing_account_failures_x3 | existing_account_failure_2_user1 | POST | /rest/user/login | 401 | 1.0 |
| 3 | F-R2B-01 | existing_account_failures_x3 | existing_account_failure_3_jim | POST | /rest/user/login | 401 | 0.0 |
| 4 | F-R2B-02 | nonexistent_account_failures_x3 | nonexistent_account_failure_1 | POST | /rest/user/login | 401 | 1.0 |
| 5 | F-R2B-02 | nonexistent_account_failures_x3 | nonexistent_account_failure_2 | POST | /rest/user/login | 401 | 1.0 |
| 6 | F-R2B-02 | nonexistent_account_failures_x3 | nonexistent_account_failure_3 | POST | /rest/user/login | 401 | 0.0 |
| 7 | F-R2B-03 | lockout_probe_like_401_x5 | lockout_probe_failure_1 | POST | /rest/user/login | 401 | 3.0 |
| 8 | F-R2B-03 | lockout_probe_like_401_x5 | lockout_probe_failure_2 | POST | /rest/user/login | 401 | 3.0 |
| 9 | F-R2B-03 | lockout_probe_like_401_x5 | lockout_probe_failure_3 | POST | /rest/user/login | 401 | 3.0 |
| 10 | F-R2B-03 | lockout_probe_like_401_x5 | lockout_probe_failure_4 | POST | /rest/user/login | 401 | 3.0 |
| 11 | F-R2B-03 | lockout_probe_like_401_x5 | lockout_probe_failure_5 | POST | /rest/user/login | 401 | 0.0 |

## Interpretation Guardrails

- This runner is for response surface comparison and response delta observation only.
- No account existence inference, no lockout confirmation, no auth success inference, and no attack outcome confirmation from runner input values.
- Apache-log-based analysis does not see POST body contents from this runner.
