# H Set R3 Execution Plan

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- request_count: 9
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: urllib.request over http/https
- safety: approved local lab only; public target execution is blocked by default
- note: request body content and response body content are not stored

## Requests

| # | scenario_id | runner label | request_label | method | path | expected_response | scaled_sleep_after_sec |
|---|---|---|---|---|---|---|---|
| 1 | H-R3-01 | wp_login_probe | wp_login_probe_request | GET | /wp-login.php | any | 1.0 |
| 2 | H-R3-02 | wp_admin_probe | wp_admin_probe_request | GET | /wp-admin/ | any | 1.0 |
| 3 | H-R3-03 | env_file_probe | env_file_probe_request | GET | /.env | any | 1.0 |
| 4 | H-R3-04 | phpinfo_probe | phpinfo_probe_request | GET | /phpinfo.php | any | 1.0 |
| 5 | H-R3-05 | server_status_probe | server_status_probe_request | GET | /server-status | any | 1.0 |
| 6 | H-R3-06 | backup_zip_probe | backup_zip_probe_request | GET | /backup.zip | any | 1.0 |
| 7 | H-R3-07 | sensitive_path_burst | sensitive_burst_env_request | GET | /.env | any | 2.0 |
| 8 | H-R3-07 | sensitive_path_burst | sensitive_burst_server_status_request | GET | /server-status | any | 2.0 |
| 9 | H-R3-07 | sensitive_path_burst | sensitive_burst_backup_zip_request | GET | /backup.zip | any | 0.0 |

## Interpretation Guardrails

- This runner is scanner-like path context harness only and does not verify WordPress presence, admin access, file exposure, phpinfo exposure, server-status exposure, backup exposure, or attack success.
- Status code and response body byte count alone are not sufficient to infer file disclosure, access success, blocking success, application presence, or server compromise.
- Even if `/.env`, `/phpinfo.php`, `/server-status`, or `/backup.zip` return `200`, exposure success must not be inferred.
- Request body content and response body content are not written to disk.
