# Observation Matrix Autofill Draft

- run_id: `obs_opencart_v2_001`
- run_dir: `lab/observability/runs/obs_opencart_v2_001`
- generated_at_utc: `2026-05-21T07:20:09Z`
- source_security_log: `lab/observability/runs/obs_opencart_v2_001/raw/app_security.filtered.log`
- source_error_log: `lab/observability/runs/obs_opencart_v2_001/raw/app_error.by_request_id.log`

> Review this draft before copying sections into `observation_matrix.md`.

## 1. Scenario Result Matrix

| scenario | count | expected logical | extra requests | redirect/follow | request summary | actual status | observed in security | observed in warn/error | error levels | evidence level | notes |
|---|---:|---:|---:|---|---|---|---|---|---|---|---|
| S01 normal_main | 1 | 1 | 0 | no | GET; /index.php | 200 | yes | no |  | O1 | observed in Apache request metadata |
| S02 static_css | 1 | 1 | 0 | no | GET; /static/style.css | 404 | yes | no |  | O1 | observed in Apache request metadata |
| S03 static_js | 1 | 1 | 0 | no | GET; /static/app.js | 404 | yes | no |  | O1 | observed in Apache request metadata |
| S04 query_search | 1 | 1 | 0 | no | GET; /search.php | 200 | yes | no |  | O1 | observed in Apache request metadata |
| S05 not_found | 1 | 1 | 0 | no | GET; /does-not-exist-obs_opencart_v2_001 | 200 | yes | no |  | O1 | observed in Apache request metadata |
| S06 forbidden_or_sensitive_path | 1 | 1 | 0 | no | GET; /private/secret.txt | 200 | yes | no |  | O1 | observed in Apache request metadata |
| S07 login_get | 1 | 1 | 0 | no | GET; /login.php | 200 | yes | no |  | O1 | observed in Apache request metadata |
| S08 login_post | 1 | 1 | 0 | no | POST; /login.php | 200 | yes | no |  | O1/O4 | POST observed; success/failure requires app or DB audit |
| S09 upload_like_post | 1 | 1 | 0 | no | POST; /upload.php | 200 | yes | no |  | O1/O4 | multipart/upload-like POST observed; stored result requires app or DB audit |
| S10 slow_or_large_request | 1 | 1 | 0 | no | GET; /search.php | 200 | yes | no |  | O1 | observed in Apache request metadata |
| S11 server_error | 1 | 1 | 0 | no | GET; /error.php | 200 | yes | no |  | O1 | server-error scenario request observed, but no 500 status in Apache response |
| S12 scanner_burst | 8 | 7 | 1 | yes | GETx8; /.env, /admin, /admin/index.php, /does-not-exist, /index.php, /search.php, /server-status, /wp-login.php | 200x7, 301 | yes | no |  | O1 | burst pattern observed via repeated User-Agent marker; redirect/follow candidate: actual Apache requests=8 exceeds logical expected=7; 3xx status observed; Location header observed |
| S13 sqli_like | 1 | 1 | 0 | no | GET; /search.php | 200 | yes | no |  | O1 | SQLi-like query observed; no success inference |
| S14 xss_like | 1 | 1 | 0 | no | GET; /search.php | 200 | yes | no |  | O1 | XSS-like query observed; no browser execution inference |
| S15 traversal_like | 1 | 1 | 0 | no | GET; /download.php | 200 | yes | no |  | O1 | traversal-like query observed; no file-read success inference |

## 2. Evidence Level Summary

| evidence level | count | notes |
|---|---:|---|
| O0 | 0 |  |
| O1 | 13 |  |
| O1/O4 | 2 |  |
| O2 | 0 |  |
| O3 | 0 |  |
| O4 | 0 |  |

## 3. Redirect/Follow Summary

| scenario | actual request count | expected logical count | extra requests | status | note |
|---|---:|---:|---:|---|---|
| S12 scanner_burst | 8 | 7 | 1 | candidate | actual Apache requests=8 exceeds logical expected=7; 3xx status observed; Location header observed |

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

- event 1
  - request_id: `ag6yEMf2BCo-etZOWg7W3gAAAAU`
  - method: `GET`
  - uri: `/index.php`
  - query_string: `?obs_run=obs_opencart_v2_001&scenario=S01`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S02 static_css

- event 1
  - request_id: `ag6yEeiARrlb8sH9qFYJgwAAAAM`
  - method: `GET`
  - uri: `/static/style.css`
  - query_string: `?obs_run=obs_opencart_v2_001&scenario=S02`
  - status_code: `404`
  - location: `-`
  - handler: `-`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S03 static_js

- event 1
  - request_id: `ag6yETIybSFMuw_XtVgZCAAAAAQ`
  - method: `GET`
  - uri: `/static/app.js`
  - query_string: `?obs_run=obs_opencart_v2_001&scenario=S03`
  - status_code: `404`
  - location: `-`
  - handler: `-`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S04 query_search

- event 1
  - request_id: `ag6yEboHxTlje10BrVVJ-wAAAAI`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?_route_=search.php&q=normal-search&obs_run=obs_opencart_v2_001&scenario=S04`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S05 not_found

- event 1
  - request_id: `ag6yEowuwBRfRHbG0EB58QAAAAE`
  - method: `GET`
  - uri: `/does-not-exist-obs_opencart_v2_001`
  - query_string: `?_route_=does-not-exist-obs_opencart_v2_001&scenario=S05&obs_run=obs_opencart_v2_001`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S06 forbidden_or_sensitive_path

- event 1
  - request_id: `ag6yEgFkHUMqfLSYvrj3pQAAAAA`
  - method: `GET`
  - uri: `/private/secret.txt`
  - query_string: `?_route_=private/secret.txt&scenario=S06&obs_run=obs_opencart_v2_001`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S07 login_get

- event 1
  - request_id: `ag6yEsf2BCo-etZOWg7W3wAAAAU`
  - method: `GET`
  - uri: `/login.php`
  - query_string: `?_route_=login.php&obs_run=obs_opencart_v2_001&scenario=S07`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S08 login_post

- event 1
  - request_id: `ag6yEuiARrlb8sH9qFYJhAAAAAM`
  - method: `POST`
  - uri: `/login.php`
  - query_string: `?_route_=login.php`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `application/x-www-form-urlencoded`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S09 upload_like_post

- event 1
  - request_id: `ag6yEzIybSFMuw_XtVgZCQAAAAQ`
  - method: `POST`
  - uri: `/upload.php`
  - query_string: `?_route_=upload.php`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `multipart/form-data; boundary=------------------------872a391984eedd40`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S10 slow_or_large_request

- event 1
  - request_id: `ag6yE7oHxTlje10BrVVJ_AAAAAI`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?_route_=search.php&q=slow-check&sleep_ms=300&obs_run=obs_opencart_v2_001&scenario=S10`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S11 server_error

- event 1
  - request_id: `ag6yE4wuwBRfRHbG0EB58gAAAAE`
  - method: `GET`
  - uri: `/error.php`
  - query_string: `?_route_=error.php&obs_run=obs_opencart_v2_001&scenario=S11`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S12 scanner_burst

- event 1
  - request_id: `ag6yFAFkHUMqfLSYvrj3pgAAAAA`
  - method: `GET`
  - uri: `/index.php`
  - query_string: `?obs_run=obs_opencart_v2_001&scenario=S12&burst_index=1`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 2
  - request_id: `ag6yFMf2BCo-etZOWg7W4AAAAAU`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?_route_=search.php&obs_run=obs_opencart_v2_001&scenario=S12&burst_index=2`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 3
  - request_id: `ag6yFOiARrlb8sH9qFYJhQAAAAM`
  - method: `GET`
  - uri: `/admin`
  - query_string: `?obs_run=obs_opencart_v2_001&scenario=S12&burst_index=3`
  - status_code: `301`
  - location: `http://opencart-v2.local/admin/?obs_run=obs_opencart_v2_001&scenario=S12&burst_index=3`
  - handler: `httpd/unix-directory`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 4
  - request_id: `ag6yFOiARrlb8sH9qFYJhgAAAAM`
  - method: `GET`
  - uri: `/admin/index.php`
  - query_string: `?obs_run=obs_opencart_v2_001&scenario=S12&burst_index=3`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 5
  - request_id: `ag6yFDIybSFMuw_XtVgZCgAAAAQ`
  - method: `GET`
  - uri: `/wp-login.php`
  - query_string: `?_route_=wp-login.php&obs_run=obs_opencart_v2_001&scenario=S12&burst_index=4`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 6
  - request_id: `ag6yFLoHxTlje10BrVVJ_QAAAAI`
  - method: `GET`
  - uri: `/.env`
  - query_string: `?_route_=.env&obs_run=obs_opencart_v2_001&scenario=S12&burst_index=5`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 7
  - request_id: `ag6yFIwuwBRfRHbG0EB58wAAAAE`
  - method: `GET`
  - uri: `/server-status`
  - query_string: `?_route_=server-status&obs_run=obs_opencart_v2_001&scenario=S12&burst_index=6`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 8
  - request_id: `ag6yFAFkHUMqfLSYvrj3pwAAAAA`
  - method: `GET`
  - uri: `/does-not-exist`
  - query_string: `?_route_=does-not-exist&obs_run=obs_opencart_v2_001&scenario=S12&burst_index=7`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S13 sqli_like

- event 1
  - request_id: `ag6yFMf2BCo-etZOWg7W4QAAAAU`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?_route_=search.php&q=1%27%20OR%20%271%27%3D%271&obs_run=obs_opencart_v2_001&scenario=S13`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S14 xss_like

- event 1
  - request_id: `ag6yFOiARrlb8sH9qFYJhwAAAAM`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?_route_=search.php&q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E&obs_run=obs_opencart_v2_001&scenario=S14`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S15 traversal_like

- event 1
  - request_id: `ag6yFTIybSFMuw_XtVgZCwAAAAQ`
  - method: `GET`
  - uri: `/download.php`
  - query_string: `?_route_=download.php&file=..%2F..%2F..%2Fetc%2Fpasswd&obs_run=obs_opencart_v2_001&scenario=S15`
  - status_code: `200`
  - location: `-`
  - handler: `redirect-handler`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

## 7. Prohibited Inferences Check

| guardrail | status | notes |
|---|---|---|
| No success inference from status_code=200 | pass | Needs manual review in final report |
| No exposure inference from response size only | pass | Needs manual review in final report |
| No login success inference from POST only | pass | S08 remains O1/O4 |
| No upload success inference from POST only | pass | S09 remains O1/O4 |
| No compromise inference from WAF match only | n/a | No WAF context in this run |
| No attacker IP assertion from x_forwarded_for only | pass | x_forwarded_for is logged as observed header only |

