# PHP Sample vs OpenCart vs Juice Shop Apache Observability Comparison

- 문서 상태: 3-way 비교 요약
- 작성일: 2026-05-14
- 비교 대상:
  - `obs_php_sample_002`
  - `obs_opencart_002`
  - `obs_juiceshop_proxy_001`
- 공통 조건:
  - Apache 웹단
  - `apache_security_io_v1` LogFormat
  - `apache_observability_s01_s15_v1` scenario catalog
  - User-Agent canonical marker: `obs-test/Sxx run=<run_id>`
- 비범위:
  - 취약점 진단 결과 작성
  - 공격 성공 여부 판정
  - 앱/DB/backend 내부 상태 변경 판정

---

## 1. Executive Summary

세 run 모두 `apache_security_io_v1` 포맷으로 Apache request/response metadata를 안정적으로 관찰했다.

핵심 결론은 다음이다.

```text
동일한 Apache LogFormat을 유지하면 앱 배치별 차이가 명확하게 드러난다.
하지만 status_code=200은 앱 배치에 따라 의미가 크게 달라지므로 성공 신호로 사용하면 안 된다.
```

배치별 의미는 다음과 같다.

```text
PHP sample:
  Apache direct PHP/static baseline.
  파일 존재/404/500/error log 연결이 비교적 직관적이다.

OpenCart:
  Apache + real PHP app + rewrite/front-controller.
  존재하지 않는 경로나 probe-like path도 앱 라우팅/fallback으로 200이 될 수 있다.

Juice Shop:
  Apache reverse proxy + backend app.
  Apache는 backend 응답을 관찰할 뿐 backend 내부 결과를 알 수 없다.
  handler=proxy-server가 reverse proxy 관측의 핵심 힌트다.
```

---

## 2. Compared Runs

| 항목 | PHP sample | OpenCart | Juice Shop |
|---|---|---|---|
| run_id | `obs_php_sample_002` | `obs_opencart_002` | `obs_juiceshop_proxy_001` |
| target_app | `php_sample` | `opencart` | `juiceshop` |
| topology | `apache_php` | `apache_php` | `apache_reverse_proxy_node` |
| app stack | Apache + PHP sample | Apache + PHP + MySQL + OpenCart | Apache reverse proxy + Docker Juice Shop |
| log format | `apache_security_io_v1` | `apache_security_io_v1` | `apache_security_io_v1` |
| scenario catalog | `apache_observability_s01_s15_v1` | `apache_observability_s01_s15_v1` | `apache_observability_s01_s15_v1` |
| WAF context | not collected | not collected | not collected |
| app/DB/backend audit | not collected | not collected | not collected |

---

## 3. Evidence Level Comparison

| evidence level | PHP sample | OpenCart | Juice Shop | interpretation |
|---|---:|---:|---:|---|
| O0 | 0 | 0 | 0 | 모든 시나리오가 Apache security log에서 관찰됨 |
| O1 | 12 | 13 | 13 | Apache request/response metadata로 관찰 가능 |
| O1/O4 | 2 | 2 | 2 | S08/S09. 요청은 관찰되지만 결과 판정은 app/DB/backend audit 필요 |
| O2 | 1 | 0 | 0 | PHP sample S11에서만 warn/error-level context가 정규 run에 연결됨 |
| O3 | 0 | 0 | 0 | WAF/app runtime context 미수집 |
| O4 | 0 | 0 | 0 | 내부 결과 판정은 수행하지 않음 |

별도 관찰:

- Juice Shop backend를 중지한 `proxy_error_check`에서는 Apache가 `503`을 반환하고 `proxy`/`proxy_http` error log를 남겼다.
- 이 관찰은 정규 S01~S15 run과 분리된 backend availability context다.

---

## 4. Topology-Specific Behavior

### 4.1 Direct Apache/PHP baseline: PHP sample

특성:

- PHP endpoint는 `handler=application/x-httpd-php`로 관찰된다.
- static asset은 `handler=-`로 관찰된다.
- 없는 경로는 보통 404로 관찰된다.
- 의도된 `/error.php`는 500 + PHP warning으로 관찰되어 O2 케이스 확인에 유용하다.

해석 가치:

```text
단순하고 예측 가능한 baseline이다.
Apache 로그 포맷/field/parser 동작 검증에 적합하다.
```

---

### 4.2 Real PHP app + rewrite/front-controller: OpenCart

특성:

- `handler=redirect-handler`가 다수 관찰된다.
- `query_string`에 `_route_=`가 추가된다.
- 존재하지 않는 경로나 probe-like path도 `status_code=200`으로 관찰될 수 있다.
- `/admin` 요청은 redirect-follow 때문에 logical 1개 요청이 actual Apache request 2개로 확장될 수 있다.

해석 가치:

```text
실제 PHP 앱에서는 status_code=200이 매우 약한 성공 신호다.
front-controller/fallback context를 별도 feature로 제공해야 한다.
```

---

### 4.3 Apache reverse proxy + backend app: Juice Shop

특성:

- 대부분의 요청이 `handler=proxy-server`로 관찰된다.
- probe-like path도 backend/SPA fallback으로 `status_code=200`이 될 수 있다.
- Apache는 backend 내부 인증/업로드/라우팅/DB 결과를 알 수 없다.
- backend unavailable 상황에서는 Apache error log에 `proxy`/`proxy_http` error가 기록되고 client에는 503이 반환된다.

해석 가치:

```text
reverse proxy 환경에서는 Apache 로그가 backend response metadata까지만 보여준다.
backend internal outcome은 app/runtime/DB audit 없이는 판단하지 않는다.
```

---

## 5. Scenario-Level Comparison

### 5.1 Static and normal requests

| scenario | PHP sample | OpenCart | Juice Shop | implication |
|---|---|---|---|---|
| S01 normal_main | 200, PHP handler | 200, PHP handler | 200, proxy-server | 모두 기본 요청 관찰 가능 |
| S02 static_css | 200 | 404 | 200 | synthetic static path 존재 여부는 앱별로 다름 |
| S03 static_js | 200 | 404 | 200 | static baseline은 앱별 실제 asset path 보강 필요 |

---

### 5.2 Search/query and payload-like requests

| scenario | PHP sample | OpenCart | Juice Shop | implication |
|---|---|---|---|---|
| S04 query_search | 200, PHP handler | 200, `_route_`, redirect-handler | 200, proxy-server | 같은 URI라도 앱 배치에 따라 의미가 다름 |
| S13 sqli_like | O1 | O1 + `_route_` | O1 + proxy-server | SQLi-like query 관찰일 뿐 성공 아님 |
| S14 xss_like | O1 | O1 + `_route_` | O1 + proxy-server | 브라우저 실행/성공 판단 금지 |
| S15 traversal_like | 404 or PHP handling | 200 fallback | 200 backend fallback | 파일 읽기 성공 판단 금지 |

---

### 5.3 Login/upload-like requests

| scenario | PHP sample | OpenCart | Juice Shop | implication |
|---|---|---|---|---|
| S08 login_post | O1/O4 | O1/O4 | O1/O4 | POST 요청 관찰 가능. 성공/실패는 app/DB/backend audit 필요 |
| S09 upload_like_post | O1/O4 | O1/O4 | O1/O4 | upload-like 요청 관찰 가능. 저장 성공 판단 금지 |

공통 결론:

```text
Apache logs show that POST happened, not what the application concluded.
```

---

### 5.4 Server error / backend error

| case | PHP sample | OpenCart | Juice Shop |
|---|---|---|---|
| S11 `/error.php` | 500 + PHP warning, O2 | 200 fallback, O1 | 200 backend response, O1 |
| separate backend down check | n/a | n/a | 503 + proxy/proxy_http error |

해석:

- 동일한 scenario label이라도 앱별 endpoint 의미가 다르다.
- S11은 PHP sample에서는 error generator지만 OpenCart/Juice Shop에서는 그렇지 않다.
- reverse proxy 장애 관찰은 별도 availability context로 관리해야 한다.

---

### 5.5 Scanner burst

| 항목 | PHP sample | OpenCart | Juice Shop |
|---|---:|---:|---:|
| logical burst paths | 7 | 7 | 7 |
| actual Apache requests | 7 | 8 | 7 |
| extra request reason | none | `/admin` redirect-follow | none |
| dominant status | mixed 200/404 | mostly 200 + 301 | 200x7 |

결론:

```text
Matrix count는 logical scenario count가 아니라 actual Apache request count다.
redirect-follow/double-request candidate를 별도 context로 표시해야 한다.
```

---

## 6. Handler-Based Interpretation

| handler | observed in | interpretation |
|---|---|---|
| `application/x-httpd-php` | PHP sample, OpenCart | PHP 직접 처리 |
| `-` | PHP sample, OpenCart | static/missing/no standard handler 등 |
| `redirect-handler` | OpenCart | rewrite/front-controller/fallback 후보 |
| `httpd/unix-directory` | OpenCart | directory redirect 후보 |
| `proxy-server` | Juice Shop | Apache reverse proxy backend response |
| `server-status` | PHP sample/Juice Shop local scanner path | mod_status handler. 외부 노출 여부는 별도 확인 필요 |

Pipeline implication:

```text
handler는 공격 성공 근거가 아니라 topology/routing interpretation feature다.
```

---

## 7. Feature Candidates for Prepare / LLM Input

### 7.1 Common features

- `log_schema`
- `request_id`
- `error_link_id`
- `raw_request`
- `uri`
- `query_string`
- `status_code`
- `original_status_code`
- `response_body_bytes`
- `in_bytes`
- `out_bytes`
- `ttfb_us`
- `handler`
- `req_content_type`
- `resp_content_type`
- `user_agent`

### 7.2 OpenCart-like features

- `has_route_param`
- `route_param_value`
- `is_front_controller_candidate`
- `is_fallback_200_candidate`
- condition candidate:

```text
status_code=200
AND (handler=redirect-handler OR query_string contains _route_=)
AND request target is unusual/probe-like
```

### 7.3 Reverse proxy features

- `is_reverse_proxy_candidate`
- `handler=proxy-server`
- `backend_response_candidate`
- `backend_unavailable_context`
- condition candidate:

```text
handler=proxy-server
AND status_code=200
AND request target is unusual/probe-like
```

For proxy errors:

```text
status_code=503
AND app_error.log contains module_name=proxy/proxy_http
```

### 7.4 Redirect/follow features

- `logical_scenario_count`
- `actual_apache_request_count`
- `extra_request_count`
- `redirect_follow_candidate`
- `has_3xx_status`
- `location_header_present`

---

## 8. LLM Wording Rules

Recommended wording:

```text
A traversal-like query was observed in Apache request metadata.
The response was status_code=200, but the app topology suggests fallback/routed/backend response behavior.
Apache logs alone do not prove file-read success or response body disclosure.
```

For reverse proxy backend errors:

```text
Apache returned 503 while the backend was unavailable.
The related error log shows proxy/proxy_http backend connection failure.
This is backend availability evidence, not evidence of compromise.
```

Avoid:

```text
Traversal succeeded.
/etc/passwd was exposed.
Login succeeded.
Upload succeeded.
Backend was compromised.
The 200 response proves exploitation.
```

---

## 9. Web UI / Report Implications

Candidate display-only badges:

| badge | condition candidate | meaning |
|---|---|---|
| `front-controller/fallback candidate` | `status_code=200` + `handler=redirect-handler` or `_route_=` | OpenCart-like routed/fallback response |
| `reverse-proxy/backend-response candidate` | `status_code=200` + `handler=proxy-server` | backend response through Apache proxy |
| `redirect-follow candidate` | actual request count > expected logical count or 3xx/Location observed | scenario produced multiple Apache requests |
| `backend unavailable / proxy error context` | 503 + proxy/proxy_http error | backend availability issue |

These badges must not create new findings or change severity/category/verdict.

---

## 10. Final Conclusion

The 3-way comparison confirms that the common `apache_security_io_v1` format is suitable across three Apache-fronted app topologies:

```text
1. direct Apache/PHP sample
2. real PHP app with rewrite/front-controller behavior
3. Apache reverse proxy to backend app
```

The strongest finding is not a new attack signature, but an interpretation rule:

```text
status_code=200 is topology-dependent and weak as a success signal.
Handler, query rewrite markers, redirect-follow behavior, and proxy error context must be provided as interpretation context, while success claims require app/backend/DB audit evidence.
```

---

## 11. Next Steps

1. Add prepare feature candidate review for:
   - front-controller/fallback candidate
   - reverse-proxy/backend-response candidate
   - redirect-follow candidate
   - backend unavailable/proxy error context
2. Keep `apache_security_io_v1` frozen for additional app topology runs.
3. Do not add body/cookie/auth logging to Apache CustomLog.
4. Keep Web UI display-only; do not infer new relationships or verdicts from badges.
