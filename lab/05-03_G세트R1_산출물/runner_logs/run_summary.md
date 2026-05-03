# G Set R1 Run Summary

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- started_at: 2026-05-03T10:00:11+09:00
- ended_at: 2026-05-03T10:00:16+09:00
- request_count: 6
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- safety: approved local lab only; public target execution is blocked by default
- note: request body content and response body content are not stored

## Results

| request_label | method | path | status_code | response_body_bytes | duration_ms | error |
|---|---|---|---|---|---|---|
| options_root_request | OPTIONS | / | 204 | 0 | 21.39 |  |
| trace_root_request | TRACE | / | 405 | 302 | 6.11 |  |
| put_probe_request | PUT | /upload/g_probe.txt | 200 | 75002 | 19.91 |  |
| delete_probe_request | DELETE | /api/resource/g_probe | 500 | 3045 | 3.94 |  |
| head_root_request | HEAD | / | 200 | 0 | 8.57 |  |
| get_root_request | GET | / | 200 | 75002 | 13.7 |  |

## Interpretation Guardrails

- OPTIONS/TRACE/PUT/DELETE observations are possibility-level method probing context only.
- No method allowance inference, no file write success inference, no resource deletion success inference, no XST success inference, and no CORS success inference.
- TRACE response bodies and request body contents are not stored.
