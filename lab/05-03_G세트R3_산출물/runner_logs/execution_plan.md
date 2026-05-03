# G Set R3 Execution Plan

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- request_count: 7
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: urllib.request over http/https
- safety: approved local lab only; public target execution is blocked by default
- note: request body content and response body content are not stored

## Requests

| # | scenario_id | runner label | request_label | method | path | extra_header_names | expected_response | scaled_sleep_after_sec |
|---|---|---|---|---|---|---|---|---|
| 1 | G-R3-01 | normal_head_health_check | head_health_request | HEAD | /health | (none) | any | 1.0 |
| 2 | G-R3-02 | browser_like_options_preflight | options_preflight_request | OPTIONS | / | Access-Control-Request-Headers,Access-Control-Request-Method,Origin | any | 1.0 |
| 3 | G-R3-03 | normal_get_browse | get_browse_request | GET | / | (none) | any | 1.0 |
| 4 | G-R3-04 | internal_monitoring_get | monitoring_ua_request | GET | / | (none) | any | 1.0 |
| 5 | G-R3-05 | repeated_head_monitoring_x3 | repeated_head_monitoring_01 | HEAD | / | (none) | any | 2.0 |
| 6 | G-R3-05 | repeated_head_monitoring_x3 | repeated_head_monitoring_02 | HEAD | / | (none) | any | 2.0 |
| 7 | G-R3-05 | repeated_head_monitoring_x3 | repeated_head_monitoring_03 | HEAD | / | (none) | any | 0.0 |

## Interpretation Guardrails

- This runner is baseline/reference harness only and does not verify attack success.
- HEAD, OPTIONS, and GET observations must not be promoted by method alone.
- Monitoring-like User-Agent values are context only and are not attack evidence by themselves.
- Preflight-like OPTIONS headers are execution inputs only; CORS weakness must not be inferred.
- Request body content and response body content are not written to disk.
