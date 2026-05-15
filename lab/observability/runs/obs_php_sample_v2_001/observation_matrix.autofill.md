# Observation Matrix Autofill Draft

- run_id: `obs_php_sample_v2_001`
- run_dir: `lab/observability/runs/obs_php_sample_v2_001`
- generated_at_utc: `2026-05-15T05:45:20Z`
- source_security_log: `lab/observability/runs/obs_php_sample_v2_001/raw/app_security.filtered.log`
- source_error_log: `lab/observability/runs/obs_php_sample_v2_001/raw/app_error.by_request_id.log`

> Review this draft before copying sections into `observation_matrix.md`.

## 1. Scenario Result Matrix

| scenario | count | expected logical | extra requests | redirect/follow | request summary | actual status | observed in security | observed in warn/error | error levels | evidence level | notes |
|---|---:|---:|---:|---|---|---|---|---|---|---|---|
| S01 normal_main | 1 | 1 | 0 | no | GET; /index.php | 200 | yes | no | notice | O1 | observed in Apache request metadata; notice-level app/PHP context only |
| S02 static_css | 1 | 1 | 0 | no | GET; /static/style.css | 200 | yes | no |  | O1 | observed in Apache request metadata |
| S03 static_js | 1 | 1 | 0 | no | GET; /static/app.js | 200 | yes | no |  | O1 | observed in Apache request metadata |
| S04 query_search | 1 | 1 | 0 | no | GET; /search.php | 200 | yes | no | notice | O1 | observed in Apache request metadata; notice-level app/PHP context only |
| S05 not_found | 1 | 1 | 0 | no | GET; /does-not-exist-obs_php_sample_v2_001 | 404 | yes | no |  | O1 | observed in Apache request metadata |
| S06 forbidden_or_sensitive_path | 1 | 1 | 0 | no | GET; /private/secret.txt | 403 | yes | yes | error | O1 | observed in Apache request metadata |
| S07 login_get | 1 | 1 | 0 | no | GET; /login.php | 200 | yes | no | notice | O1 | observed in Apache request metadata; notice-level app/PHP context only |
| S08 login_post | 1 | 1 | 0 | no | POST; /login.php | 401 | yes | no | notice | O1/O4 | POST observed; success/failure requires app or DB audit |
| S09 upload_like_post | 1 | 1 | 0 | no | POST; /upload.php | 400 | yes | no | notice | O1/O4 | multipart/upload-like POST observed; stored result requires app or DB audit |
| S10 slow_or_large_request | 1 | 1 | 0 | no | GET; /search.php | 200 | yes | no | notice | O1 | observed in Apache request metadata; notice-level app/PHP context only |
| S11 server_error | 1 | 1 | 0 | no | GET; /error.php | 500 | yes | yes | notice, warn | O2 | 500 observed; warn/error-level Apache/PHP context linked |
| S12 scanner_burst | 7 | 7 | 0 | no | GETx7; /.env, /admin, /does-not-exist, /index.php, /search.php, /server-status, /wp-login.php | 200x3, 404x4 | yes | yes | error, noticex2 | O1 | burst pattern observed via repeated User-Agent marker |
| S13 sqli_like | 1 | 1 | 0 | no | GET; /search.php | 200 | yes | no | notice | O1 | SQLi-like query observed; no success inference |
| S14 xss_like | 1 | 1 | 0 | no | GET; /search.php | 200 | yes | no | notice | O1 | XSS-like query observed; no browser execution inference |
| S15 traversal_like | 1 | 1 | 0 | no | GET; /download.php | 404 | yes | yes | error | O1 | traversal-like query observed; no file-read success inference |

## 2. Evidence Level Summary

| evidence level | count | notes |
|---|---:|---|
| O0 | 0 |  |
| O1 | 12 |  |
| O1/O4 | 2 |  |
| O2 | 1 |  |
| O3 | 0 |  |
| O4 | 0 |  |

## 3. Redirect/Follow Summary

| scenario | actual request count | expected logical count | extra requests | status | note |
|---|---:|---:|---:|---|---|

## 4. Related Error-Level Summary

| scenario | notice count | warn/error count | modules | interpretation |
|---|---:|---:|---|---|
| S01 normal_main | 1 | 0 | php | notice-only context |
| S02 static_css | 0 | 0 |  | none |
| S03 static_js | 0 | 0 |  | none |
| S04 query_search | 1 | 0 | php | notice-only context |
| S05 not_found | 0 | 0 |  | none |
| S06 forbidden_or_sensitive_path | 0 | 1 | authz_core | warn/error context |
| S07 login_get | 1 | 0 | php | notice-only context |
| S08 login_post | 1 | 0 | php | notice-only context |
| S09 upload_like_post | 1 | 0 | php | notice-only context |
| S10 slow_or_large_request | 1 | 0 | php | notice-only context |
| S11 server_error | 1 | 1 | phpx2 | warn/error context |
| S12 scanner_burst | 2 | 1 | phpx3 | warn/error context |
| S13 sqli_like | 1 | 0 | php | notice-only context |
| S14 xss_like | 1 | 0 | php | notice-only context |
| S15 traversal_like | 0 | 1 | php | warn/error context |

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
  - request_id: `agaqw1Nu_D8aUI1OAXSj9QAAAAM`
  - method: `GET`
  - uri: `/index.php`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S01`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`

### S02 static_css

- event 1
  - request_id: `agaqw8WbuYzatlchTEQbCwAAAAQ`
  - method: `GET`
  - uri: `/static/style.css`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S02`
  - status_code: `200`
  - location: `-`
  - handler: `-`
  - req_content_type: `-`
  - resp_content_type: `text/css`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S03 static_js

- event 1
  - request_id: `agaqwzvSRlfxuyGyKWrAYQAAAAI`
  - method: `GET`
  - uri: `/static/app.js`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S03`
  - status_code: `200`
  - location: `-`
  - handler: `-`
  - req_content_type: `-`
  - resp_content_type: `text/javascript`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S04 query_search

- event 1
  - request_id: `agaqw1GmAsuRathlDi5iEgAAAAA`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?q=normal-search&obs_run=obs_php_sample_v2_001&scenario=S04`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`

### S05 not_found

- event 1
  - request_id: `agaqw_Oku66hobxq_YCD1QAAAAE`
  - method: `GET`
  - uri: `/does-not-exist-obs_php_sample_v2_001`
  - query_string: `?scenario=S05&obs_run=obs_php_sample_v2_001`
  - status_code: `404`
  - location: `-`
  - handler: `-`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S06 forbidden_or_sensitive_path

- event 1
  - request_id: `agaqxDDz_9fwa3AnTTwzrAAAAAU`
  - method: `GET`
  - uri: `/private/secret.txt`
  - query_string: `?scenario=S06&obs_run=obs_php_sample_v2_001`
  - status_code: `403`
  - location: `-`
  - handler: `-`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `0`
  - related_warn_or_error_count: `1`
  - related_error_levels: `error`

### S07 login_get

- event 1
  - request_id: `agaqxJbD6O29QFRRuF6RBQAAAAY`
  - method: `GET`
  - uri: `/login.php`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S07`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`

### S08 login_post

- event 1
  - request_id: `agaqxFNu_D8aUI1OAXSj9gAAAAM`
  - method: `POST`
  - uri: `/login.php`
  - query_string: ``
  - status_code: `401`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `application/x-www-form-urlencoded`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`

### S09 upload_like_post

- event 1
  - request_id: `agaqxMWbuYzatlchTEQbDAAAAAQ`
  - method: `POST`
  - uri: `/upload.php`
  - query_string: ``
  - status_code: `400`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `multipart/form-data; boundary=------------------------60a0e8943189d0d6`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`

### S10 slow_or_large_request

- event 1
  - request_id: `agaqxTvSRlfxuyGyKWrAYgAAAAI`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?q=slow-check&sleep_ms=300&obs_run=obs_php_sample_v2_001&scenario=S10`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`

### S11 server_error

- event 1
  - request_id: `agaqxVGmAsuRathlDi5iEwAAAAA`
  - method: `GET`
  - uri: `/error.php`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S11`
  - status_code: `500`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `2`
  - related_notice_count: `1`
  - related_warn_or_error_count: `1`
  - related_error_levels: `notice, warn`

### S12 scanner_burst

- event 1
  - request_id: `agaqxfOku66hobxq_YCD1gAAAAE`
  - method: `GET`
  - uri: `/index.php`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S12&burst_index=1`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`
- event 2
  - request_id: `agaqxTDz_9fwa3AnTTwzrQAAAAU`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S12&burst_index=2`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`
- event 3
  - request_id: `agaqxZbD6O29QFRRuF6RBgAAAAY`
  - method: `GET`
  - uri: `/admin`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S12&burst_index=3`
  - status_code: `404`
  - location: `-`
  - handler: `-`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 4
  - request_id: `agaqxVNu_D8aUI1OAXSj9wAAAAM`
  - method: `GET`
  - uri: `/wp-login.php`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S12&burst_index=4`
  - status_code: `404`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `0`
  - related_warn_or_error_count: `1`
  - related_error_levels: `error`
- event 5
  - request_id: `agaqxcWbuYzatlchTEQbDQAAAAQ`
  - method: `GET`
  - uri: `/.env`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S12&burst_index=5`
  - status_code: `404`
  - location: `-`
  - handler: `-`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 6
  - request_id: `agaqxTvSRlfxuyGyKWrAYwAAAAI`
  - method: `GET`
  - uri: `/server-status`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S12&burst_index=6`
  - status_code: `200`
  - location: `-`
  - handler: `server-status`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``
- event 7
  - request_id: `agaqxVGmAsuRathlDi5iFAAAAAA`
  - method: `GET`
  - uri: `/does-not-exist`
  - query_string: `?obs_run=obs_php_sample_v2_001&scenario=S12&burst_index=7`
  - status_code: `404`
  - location: `-`
  - handler: `-`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `0`
  - related_notice_count: `0`
  - related_warn_or_error_count: `0`
  - related_error_levels: ``

### S13 sqli_like

- event 1
  - request_id: `agaqxfOku66hobxq_YCD1wAAAAE`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?q=1%27%20OR%20%271%27%3D%271&obs_run=obs_php_sample_v2_001&scenario=S13`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`

### S14 xss_like

- event 1
  - request_id: `agaqxTDz_9fwa3AnTTwzrgAAAAU`
  - method: `GET`
  - uri: `/search.php`
  - query_string: `?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E&obs_run=obs_php_sample_v2_001&scenario=S14`
  - status_code: `200`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `1`
  - related_warn_or_error_count: `0`
  - related_error_levels: `notice`

### S15 traversal_like

- event 1
  - request_id: `agaqxpbD6O29QFRRuF6RBwAAAAY`
  - method: `GET`
  - uri: `/download.php`
  - query_string: `?file=..%2F..%2F..%2Fetc%2Fpasswd&obs_run=obs_php_sample_v2_001&scenario=S15`
  - status_code: `404`
  - location: `-`
  - handler: `application/x-httpd-php`
  - req_content_type: `-`
  - resp_content_type: `text/html`
  - related_error_count: `1`
  - related_notice_count: `0`
  - related_warn_or_error_count: `1`
  - related_error_levels: `error`

## 7. Prohibited Inferences Check

| guardrail | status | notes |
|---|---|---|
| No success inference from status_code=200 | pass | Needs manual review in final report |
| No exposure inference from response size only | pass | Needs manual review in final report |
| No login success inference from POST only | pass | S08 remains O1/O4 |
| No upload success inference from POST only | pass | S09 remains O1/O4 |
| No compromise inference from WAF match only | n/a | No WAF context in this run |
| No attacker IP assertion from x_forwarded_for only | pass | x_forwarded_for is logged as observed header only |

