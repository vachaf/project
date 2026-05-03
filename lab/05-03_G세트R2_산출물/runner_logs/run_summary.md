# G Set R2 Run Summary

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- started_at: 2026-05-03T11:14:35+09:00
- ended_at: 2026-05-03T11:14:41+09:00
- request_count: 6
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: raw socket over plain HTTP only
- note: raw request content, request body content, and response body content are not stored

## Results

| scenario_id | request_label | connected | status_line | parsed_status_code | response_header_bytes | response_body_bytes_discarded | duration_ms | error |
|---|---|---|---|---|---|---|---|---|
| G-R2-01 | invalid_method_token_request | True | HTTP/1.1 400 Bad Request | 400 | 144 | 5 | 25.06 |  |
| G-R2-02 | http10_odd_request_request | True | HTTP/1.1 200 OK | 200 | 473 | 75002 | 62.79 |  |
| G-R2-03 | bad_protocol_version_request | True | HTTP/1.1 200 OK | 200 | 473 | 75002 | 21.11 |  |
| G-R2-04 | missing_host_http11_request | True | HTTP/1.1 400 Bad Request | 400 | 182 | 301 | 6.53 |  |
| G-R2-05 | odd_host_header_request | True | HTTP/1.1 400 Bad Request | 400 | 182 | 301 | 6.05 |  |
| G-R2-06 | long_path_probe_request | True | HTTP/1.1 200 OK | 200 | 473 | 75002 | 34.04 |  |

## Interpretation Guardrails

- Observations are limited to request parsing, status code, protocol, method, and error linkage at Apache log surface level.
- No malformed request success inference, no intrusion success inference, and no bypass success inference are allowed.
