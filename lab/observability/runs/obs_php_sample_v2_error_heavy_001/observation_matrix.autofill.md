# Observation Matrix Autofill Draft

- run_id: `obs_php_sample_v2_error_heavy_001`
- run_dir: `lab/observability/runs/obs_php_sample_v2_error_heavy_001`
- generated_at_utc: `2026-05-20T14:30:10Z`
- source_security_log: `lab/observability/runs/obs_php_sample_v2_error_heavy_001/raw/app_security.filtered.log`
- source_error_log: `lab/observability/runs/obs_php_sample_v2_error_heavy_001/raw/app_error.by_request_id.log`

> Review this draft before copying sections into `observation_matrix.md`.

## 1. Scenario Result Matrix

| scenario | count | expected logical | extra requests | redirect/follow | request summary | actual status | observed in security | observed in warn/error | error levels | evidence level | notes |
|---|---:|---:|---:|---|---|---|---|---|---|---|---|
| S01 normal_main | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S02 static_css | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S03 static_js | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S04 query_search | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S05 not_found | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S06 forbidden_or_sensitive_path | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S07 login_get | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S08 login_post | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S09 upload_like_post | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S10 slow_or_large_request | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S11 server_error | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S12 scanner_burst | 0 | 7 | 0 | no | - |  | no | no |  | O0 | not observed |
| S13 sqli_like | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S14 xss_like | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |
| S15 traversal_like | 0 | 1 | 0 | no | - |  | no | no |  | O0 | not observed |

## 2. Evidence Level Summary

| evidence level | count | notes |
|---|---:|---|
| O0 | 15 |  |
| O1 | 0 |  |
| O1/O4 | 0 |  |
| O2 | 0 |  |
| O3 | 0 |  |
| O4 | 0 |  |

## 3. Redirect/Follow Summary

| scenario | actual request count | expected logical count | extra requests | status | note |
|---|---:|---:|---:|---|---|

## 4. Related Error-Level Summary

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

## 5. Field Observation Checklist

| field | observed | notes |
|---|---:|---|
| `log_schema` | yes |  |
| `log_time` | yes |  |
| `request_id` | yes |  |
| `error_link_id` | yes |  |
| `vhost` | yes |  |
| `server_name` | yes |  |
| `server_port` | yes |  |
| `local_ip` | yes |  |
| `src_ip` | yes |  |
| `peer_ip` | yes |  |
| `method` | yes |  |
| `raw_request` | yes |  |
| `uri` | yes |  |
| `query_string` | yes |  |
| `protocol` | yes |  |
| `status_code` | yes |  |
| `original_status_code` | yes |  |
| `response_body_bytes` | yes |  |
| `in_bytes` | yes |  |
| `out_bytes` | yes |  |
| `total_bytes` | yes |  |
| `duration_us` | yes |  |
| `ttfb_us` | yes |  |
| `keepalive_count` | yes |  |
| `connection_status` | yes |  |
| `handler` | yes |  |
| `req_content_type` | yes |  |
| `req_content_length` | yes |  |
| `resp_content_type` | yes |  |
| `location` | yes |  |
| `referer` | yes |  |
| `origin` | yes |  |
| `user_agent` | yes |  |
| `host` | no |  |
| `x_forwarded_for` | yes |  |
| `x_real_ip` | yes |  |
| `forwarded` | yes |  |

## 6. Per-Scenario Details

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

## 7. Prohibited Inferences Check

| guardrail | status | notes |
|---|---|---|
| No success inference from status_code=200 | pass | Needs manual review in final report |
| No exposure inference from response size only | pass | Needs manual review in final report |
| No login success inference from POST only | pass | S08 remains O1/O4 |
| No upload success inference from POST only | pass | S09 remains O1/O4 |
| No compromise inference from WAF match only | n/a | No WAF context in this run |
| No attacker IP assertion from x_forwarded_for only | pass | x_forwarded_for is logged as observed header only |

