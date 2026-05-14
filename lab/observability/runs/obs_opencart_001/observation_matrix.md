# Observation Matrix Autofill Draft

- run_id: `obs_opencart_001`
- run_dir: `lab/observability/runs/obs_opencart_001`
- generated_at_utc: `2026-05-14T07:51:23Z`
- source_security_log: `lab/observability/runs/obs_opencart_001/raw/app_security.filtered.log`
- source_error_log: `lab/observability/runs/obs_opencart_001/raw/app_error.by_request_id.log`

> Review this draft before copying sections into `observation_matrix.md`.

## 1. Scenario Result Matrix

| scenario | count | request summary | actual status | observed in security | observed in warn/error | error levels | evidence level | notes |
|---|---:|---|---|---|---|---|---|---|
| S01 normal_main | 0 | - | 200 | no | no |  | O0 | not observed |
| S02 static_css | 0 | - | 404 | no | no |  | O0 | not observed |
| S03 static_js | 0 | - | 404 | no | no |  | O0 | not observed |
| S04 query_search | 0 | - | 200 | no | no |  | O0 | not observed |
| S05 not_found | 0 | - | 200 | no | no |  | O0 | not observed |
| S06 forbidden_or_sensitive_path | 0 | - | 200 | no | no |  | O0 | not observed |
| S07 login_get | 0 | - | 200 | no | no |  | O0 | not observed |
| S08 login_post | 0 | - | 200 | no | no |  | O0 | not observed |
| S09 upload_like_post | 0 | - | 200 | no | no |  | O0 | not observed |
| S10 slow_or_large_request | 0 | - | 200 | no | no |  | O0 | not observed |
| S11 server_error | 0 | - | 200 | no | no |  | O0 | not observed |
| S12 scanner_burst | 0 | - | 200x6, 403 | no | no |  | O0 | not observed |
| S13 sqli_like | 0 | - | 200 | no | no |  | O0 | not observed |
| S14 xss_like | 0 | - | 200 | no | no |  | O0 | not observed |
| S15 traversal_like | 0 | - | 200 | no | no |  | O0 | not observed |

## 2. Evidence Level Summary

| evidence level | count | notes |
|---|---:|---|
| O0 | 15 |  |
| O1 | 0 |  |
| O1/O4 | 0 |  |
| O2 | 0 |  |
| O3 | 0 |  |
| O4 | 0 |  |

## 3. Related Error-Level Summary

| scenario | notice count | warn/error count | modules | interpretation |
|---|---:|---:|---|---|
| S01 normal_main | 0 | 0 |  | none |
| S02 static_css | 0 | 0 |  | none |
| S03 static_js | 0 | 0 |  | none |
| S04 query_search | 0 | 0 |  | none |
| S05 not_found | 0 | 0 |  | none |
| S06 forbidden_or_sensitive_path | 0 | 0 |  | none |
| S07 login_get | 0 | 0 |  | none |
| S08 login_post | 0 | 0 |  | none |
| S09 upload_like_post | 0 | 0 |  | none |
| S10 slow_or_large_request | 0 | 0 |  | none |
| S11 server_error | 0 | 0 |  | none |
| S12 scanner_burst | 0 | 0 |  | none |
| S13 sqli_like | 0 | 0 |  | none |
| S14 xss_like | 0 | 0 |  | none |
| S15 traversal_like | 0 | 0 |  | none |

## 4. Field Observation Checklist

| field | observed | notes |
|---|---:|---|
| `log_schema` | no |  |
| `log_time` | no |  |
| `request_id` | no |  |
| `error_link_id` | no |  |
| `vhost` | no |  |
| `server_name` | no |  |
| `server_port` | no |  |
| `local_ip` | no |  |
| `src_ip` | no |  |
| `peer_ip` | no |  |
| `method` | no |  |
| `raw_request` | no |  |
| `uri` | no |  |
| `query_string` | no |  |
| `protocol` | no |  |
| `status_code` | no |  |
| `original_status_code` | no |  |
| `response_body_bytes` | no |  |
| `in_bytes` | no |  |
| `out_bytes` | no |  |
| `total_bytes` | no |  |
| `duration_us` | no |  |
| `ttfb_us` | no |  |
| `keepalive_count` | no |  |
| `connection_status` | no |  |
| `handler` | no |  |
| `req_content_type` | no |  |
| `req_content_length` | no |  |
| `resp_content_type` | no |  |
| `location` | no |  |
| `referer` | no |  |
| `origin` | no |  |
| `user_agent` | no |  |
| `host` | no |  |
| `x_forwarded_for` | no |  |
| `x_real_ip` | no |  |
| `forwarded` | no |  |

## 5. Per-Scenario Details

### S01 normal_main

- observed: no

### S02 static_css

- observed: no

### S03 static_js

- observed: no

### S04 query_search

- observed: no

### S05 not_found

- observed: no

### S06 forbidden_or_sensitive_path

- observed: no

### S07 login_get

- observed: no

### S08 login_post

- observed: no

### S09 upload_like_post

- observed: no

### S10 slow_or_large_request

- observed: no

### S11 server_error

- observed: no

### S12 scanner_burst

- observed: no

### S13 sqli_like

- observed: no

### S14 xss_like

- observed: no

### S15 traversal_like

- observed: no

## 6. Prohibited Inferences Check

| guardrail | status | notes |
|---|---|---|
| No success inference from status_code=200 | pass | Needs manual review in final report |
| No exposure inference from response size only | pass | Needs manual review in final report |
| No login success inference from POST only | pass | S08 remains O1/O4 |
| No upload success inference from POST only | pass | S09 remains O1/O4 |
| No compromise inference from WAF match only | n/a | No WAF context in this run |
| No attacker IP assertion from x_forwarded_for only | pass | x_forwarded_for is logged as observed header only |

