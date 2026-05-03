# G Set R2 Execution Plan

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- request_count: 6
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: raw socket over plain HTTP only
- safety: approved local lab only; public target execution is blocked by default
- note: raw request content, request body content, and response body content are not stored

## Requests

| # | scenario_id | runner label | request_label | template | request_line_preview | host_header | expected_response | scaled_sleep_after_sec |
|---|---|---|---|---|---|---|---|---|
| 1 | G-R2-01 | invalid_method_token | invalid_method_token_request | invalid_method_token | FAKEMETHOD / HTTP/1.1 | 192.168.56.105 | 400/405/501 등 가능 | 1.0 |
| 2 | G-R2-02 | http10_odd_request | http10_odd_request_request | http10_odd_request | GET / HTTP/1.0 | (omitted) | 200/400/403 등 가능 | 1.0 |
| 3 | G-R2-03 | bad_protocol_version | bad_protocol_version_request | bad_protocol_version | GET / HTTP/9.9 | 192.168.56.105 | 400/505/501 등 가능 | 1.0 |
| 4 | G-R2-04 | missing_host_http11 | missing_host_http11_request | missing_host_http11 | GET / HTTP/1.1 | (omitted) | 400 등 가능 | 1.0 |
| 5 | G-R2-05 | odd_host_header | odd_host_header_request | odd_host_header | GET / HTTP/1.1 | invalid..host | 400/403/200 등 가능 | 1.0 |
| 6 | G-R2-06 | long_path_probe | long_path_probe_request | long_path_probe | GET /g-probe/<long-token:3072 chars> HTTP/1.1 | 192.168.56.105 | 200/400/414/404 등 가능 | 0.0 |

## Interpretation Guardrails

- This runner is for Apache log surface observation only and does not verify exploit, bypass, or intrusion success.
- HTTP/1.1 missing Host and odd Host cases are malformed-request context only.
- 400/408/501/505 class outcomes are protocol anomaly context only.
- Raw request content and response body content are not written to disk.
