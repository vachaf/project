# G Set R3 Run Summary

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- started_at: 2026-05-03T12:16:00+09:00
- ended_at: 2026-05-03T12:16:08+09:00
- request_count: 7
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: urllib.request over http/https
- note: request body content and response body content are not stored

## Results

| scenario_id | request_label | method | path | status_code | response_headers_count | response_body_bytes_discarded | duration_ms | error |
|---|---|---|---|---|---|---|---|---|
| G-R3-01 | head_health_request | HEAD | /health | 200 | 15 | 0 | 39.81 |  |
| G-R3-02 | options_preflight_request | OPTIONS | / | 204 | 7 | 0 | 6.0 |  |
| G-R3-03 | get_browse_request | GET | / | 200 | 15 | 75002 | 16.43 |  |
| G-R3-04 | monitoring_ua_request | GET | / | 200 | 15 | 75002 | 9.49 |  |
| G-R3-05 | repeated_head_monitoring_01 | HEAD | / | 200 | 15 | 0 | 3.84 |  |
| G-R3-05 | repeated_head_monitoring_02 | HEAD | / | 200 | 15 | 0 | 7.02 |  |
| G-R3-05 | repeated_head_monitoring_03 | HEAD | / | 200 | 15 | 0 | 8.72 |  |

## Interpretation Guardrails

- Results are baseline/reference context only.
- No CORS success inference, no method allowance inference, no server-configuration weakness inference, and no attack-success inference are allowed.
- User-Agent strings and repeated HEAD alone are not sufficient to label an attack.
