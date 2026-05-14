# Apache 앱 관측 가능성 매트릭스 템플릿

- 문서 상태: 실험 결과 기록 템플릿
- 작성일: 2026-05-14
- 관련 시나리오 카탈로그: `lab/observability/scenario_catalog.md`

---

## 1. Run Metadata

| 항목 | 값 |
|---|---|
| run_id |  |
| target_app |  |
| topology |  |
| app_stack |  |
| os_version |  |
| apache_version |  |
| php_or_app_runtime_version |  |
| apache_modules |  |
| log_format_version |  |
| waf_enabled |  |
| app_log_available |  |
| db_or_audit_log_available |  |
| start_time_kst |  |
| end_time_kst |  |
| scenario_catalog_version | `apache_observability_s01_s15_v1` |
| operator_notes |  |

### topology 값 예시

```text
static_apache
apache_php
apache_php_fpm
apache_cgi
apache_reverse_proxy_node
apache_reverse_proxy_java
apache_with_modsecurity
mixed_vhost
```

---

## 2. Log Sources

| 로그 | 경로 | 수집 여부 | 비고 |
|---|---|---:|---|
| app_security.log |  |  | canonical request evidence |
| app_access.log |  |  | compatibility/reference |
| app_error.log |  |  | Apache error context |
| apache_log_shipper.log |  |  | collector status |
| app_runtime.log |  |  | optional app context |
| php_fpm.log |  |  | optional PHP runtime context |
| modsec_audit.log |  |  | optional WAF context |
| auth.log |  |  | optional system context |
| ufw.log |  |  | optional firewall context |
| fail2ban.log |  |  | optional blocking context |

---

## 3. Observability Level Legend

| 등급 | 의미 |
|---|---|
| O0 | 관찰 불가 |
| O1 | Apache request metadata로 관찰 가능 |
| O2 | Apache error log까지 붙이면 보강 가능 |
| O3 | WAF/app log까지 붙이면 내부 처리 일부 확인 가능 |
| O4 | DB/app audit까지 있어야 결과 확인 가능 |

---

## 4. Scenario Result Matrix

| scenario | request summary | expected status | actual status | observed in security | observed in error | observed in app | observed in WAF | evidence level | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| S01 normal_main |  |  |  |  |  |  |  |  |  |
| S02 static_css |  |  |  |  |  |  |  |  |  |
| S03 static_js |  |  |  |  |  |  |  |  |  |
| S04 query_search |  |  |  |  |  |  |  |  |  |
| S05 not_found |  |  |  |  |  |  |  |  |  |
| S06 forbidden_or_sensitive_path |  |  |  |  |  |  |  |  |  |
| S07 login_get |  |  |  |  |  |  |  |  |  |
| S08 login_post |  |  |  |  |  |  |  |  |  |
| S09 upload_like_post |  |  |  |  |  |  |  |  |  |
| S10 slow_or_large_request |  |  |  |  |  |  |  |  |  |
| S11 server_error |  |  |  |  |  |  |  |  |  |
| S12 scanner_burst |  |  |  |  |  |  |  |  |  |
| S13 sqli_like |  |  |  |  |  |  |  |  |  |
| S14 xss_like |  |  |  |  |  |  |  |  |  |
| S15 traversal_like |  |  |  |  |  |  |  |  |  |

---

## 5. Field Observation Checklist

### 5.1 app_security.log

| 필드 | 관찰 여부 | 비고 |
|---|---:|---|
| log_time |  |  |
| request_id |  |  |
| error_link_id |  |  |
| vhost |  |  |
| src_ip |  |  |
| peer_ip |  |  |
| method |  |  |
| raw_request |  |  |
| uri |  |  |
| query_string |  |  |
| protocol |  |  |
| status_code |  |  |
| response_body_bytes |  |  |
| in_bytes |  |  |
| out_bytes |  |  |
| total_bytes |  |  |
| duration_us |  |  |
| ttfb_us |  |  |
| keepalive_count |  |  |
| connection_status |  |  |
| req_content_type |  |  |
| req_content_length |  |  |
| resp_content_type |  |  |
| referer |  |  |
| user_agent |  |  |
| host |  |  |
| x_forwarded_for |  |  |

### 5.2 app_error.log

| 필드 | 관찰 여부 | 비고 |
|---|---:|---|
| log_time |  |  |
| error_link_id |  |  |
| request_id |  |  |
| module_name |  |  |
| log_level |  |  |
| src_ip |  |  |
| peer_ip |  |  |
| message |  |  |

### 5.3 Optional Context Logs

| context | 관찰 여부 | 연결 키 | 비고 |
|---|---:|---|---|
| app runtime event |  | request_id/time/IP |  |
| PHP-FPM error |  | time/path/process |  |
| WAF rule match |  | transaction_id/time/IP/request |  |
| system auth event |  | time/IP/user |  |
| firewall event |  | time/IP/port |  |
| fail2ban event |  | time/IP/jail |  |

---

## 6. Scenario Detail Notes

### S01 normal_main

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S02 static_css

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S03 static_js

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S04 query_search

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S05 not_found

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S06 forbidden_or_sensitive_path

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S07 login_get

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S08 login_post

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S09 upload_like_post

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S10 slow_or_large_request

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S11 server_error

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S12 scanner_burst

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S13 sqli_like

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S14 xss_like

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

### S15 traversal_like

```text
request:
security rows:
error rows:
app rows:
waf rows:
evidence level:
notes:
```

---

## 7. Difference Summary

### 7.1 What Apache-only evidence showed

```text
-
-
-
```

### 7.2 What app_error.log added

```text
-
-
-
```

### 7.3 What app/WAF logs added

```text
-
-
-
```

### 7.4 What remained unknowable without DB/app audit

```text
-
-
-
```

---

## 8. Prohibited Inferences Check

| 금지 추론 | 위반 여부 | 비고 |
|---|---:|---|
| status_code=200만으로 공격 성공 판단 |  |  |
| response_body_bytes만으로 파일 노출 판단 |  |  |
| resp_content_type만으로 정상/오류 페이지 확정 |  |  |
| login-like POST만으로 로그인 성공 판단 |  |  |
| upload-like POST만으로 파일 저장 성공 판단 |  |  |
| WAF rule match만으로 침해 성공 판단 |  |  |
| error log만으로 데이터 유출 판단 |  |  |
| x_forwarded_for만으로 공격자 IP 확정 |  |  |

---

## 9. Pipeline Implications

### 9.1 prepare 단계 반영 후보

```text
-
-
-
```

### 9.2 LLM input context 반영 후보

```text
-
-
-
```

### 9.3 Web UI 표시 반영 후보

```text
-
-
-
```

### 9.4 보류 항목

```text
-
-
-
```
