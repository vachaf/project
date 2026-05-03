# G Set R1 Execution Plan

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- request_count: 6
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- safety: approved local lab only; public target execution is blocked by default
- note: request body content and response body content are not stored

## Requests

| # | scenario_id | runner label | request_label | method | path | expected_response | request_body_bytes | scaled_sleep_after_sec |
|---|---|---|---|---|---|---|---|---|
| 1 | G-R1-01 | options_root | options_root_request | OPTIONS | / | any | 0 | 1.0 |
| 2 | G-R1-02 | trace_root | trace_root_request | TRACE | / | any | 0 | 1.0 |
| 3 | G-R1-03 | put_probe | put_probe_request | PUT | /upload/g_probe.txt | any | 7 | 1.0 |
| 4 | G-R1-04 | delete_probe | delete_probe_request | DELETE | /api/resource/g_probe | any | 0 | 1.0 |
| 5 | G-R1-05 | head_root | head_root_request | HEAD | / | any | 0 | 1.0 |
| 6 | G-R1-06 | get_root | get_root_request | GET | / | any | 0 | 0.0 |

## Interpretation Guardrails

- This runner records HTTP request metadata only and does not verify method allowance or exploit success.
- TRACE response bodies are not stored or printed.
- PUT request bodies are execution-only dummy bytes and only body length is recorded.
- DELETE targets a test path only and does not verify resource deletion.
- HEAD and GET are baseline references and should not be promoted by method alone.
