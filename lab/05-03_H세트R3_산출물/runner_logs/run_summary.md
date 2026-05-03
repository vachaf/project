# H Set R3 Run Summary

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- started_at: 2026-05-03T15:39:33+09:00
- ended_at: 2026-05-03T15:39:43+09:00
- request_count: 9
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: urllib.request over http/https
- note: request body content and response body content are not stored

## Results

| scenario_id | request_label | method | path | status_code | response_headers_count | response_body_bytes_discarded | duration_ms | error |
|---|---|---|---|---|---|---|---|---|
| H-R3-01 | wp_login_probe_request | GET | /wp-login.php | 200 | 15 | 75002 | 58.78 |  |
| H-R3-02 | wp_admin_probe_request | GET | /wp-admin/ | 200 | 15 | 75002 | 22.27 |  |
| H-R3-03 | env_file_probe_request | GET | /.env | 200 | 15 | 75002 | 25.4 |  |
| H-R3-04 | phpinfo_probe_request | GET | /phpinfo.php | 200 | 15 | 75002 | 9.33 |  |
| H-R3-05 | server_status_probe_request | GET | /server-status | 403 | 5 | 279 | 2.44 |  |
| H-R3-06 | backup_zip_probe_request | GET | /backup.zip | 200 | 15 | 75002 | 11.96 |  |
| H-R3-07 | sensitive_burst_env_request | GET | /.env | 200 | 15 | 75002 | 18.26 |  |
| H-R3-07 | sensitive_burst_server_status_request | GET | /server-status | 403 | 5 | 279 | 2.25 |  |
| H-R3-07 | sensitive_burst_backup_zip_request | GET | /backup.zip | 200 | 15 | 75002 | 11.87 |  |

## Interpretation Guardrails

- Results are scanner-like path context only.
- No WordPress presence inference, no admin access inference, no sensitive file exposure inference, no phpinfo exposure inference, no server-status exposure inference, no backup exposure inference, and no compromise inference are allowed.
- Status code and response body byte count alone are not sufficient evidence of exposure success or attack success.
