# Observability Run Summary

- run_id: `obs_juiceshop_proxy_001`
- target_app: `juiceshop`
- topology: `apache_reverse_proxy_node`
- app_stack: `Apache reverse proxy + Docker Juice Shop`
- scenario_catalog_version: `apache_observability_s01_s15_v1`
- log_format_version: `apache_security_io_v1`
- 기준 목적: Apache reverse proxy 배치에서 공통 `apache_security_io_v1` 포맷과 S01~S15 관측 시나리오가 정상 동작하는지 확인

---

## 1. High-Level Result

`obs_juiceshop_proxy_001` run은 Apache reverse proxy + Juice Shop backend 환경에서 Apache security log 관측에 성공했다.

요약:

- S01~S15 전체 시나리오가 `app_security.filtered.log`에서 관찰됐다.
- `observation_matrix.md` 기준 `O0=0`, `O1=13`, `O1/O4=2`, `O2=0`, `O3=0`, `O4=0`으로 집계됐다.
- `log_schema`, `request_id`, `error_link_id`, `vhost`, `server_name`, `src_ip`, `peer_ip`, `raw_request`, `uri`, `query_string`, `status_code`, `in_bytes`, `out_bytes`, `ttfb_us`, `handler` 등 `apache_security_io_v1` 필드가 모두 관찰됐다.
- 대부분의 요청이 `status_code=200`과 `handler=proxy-server`로 관찰됐다.
- 이는 Apache가 요청을 backend Juice Shop으로 전달했고, backend/SPA fallback이 많은 요청을 200 HTML 응답으로 처리했을 가능성을 보여준다.
- 정규 S01~S15 run에서는 warn/error-level Apache proxy error context가 관찰되지 않았다.
- 별도 `proxy_error_check`에서 backend container를 중지했을 때 Apache가 `503 Service Unavailable`을 반환하고 `proxy`/`proxy_http` error log를 남기는 것을 확인했다.

---

## 2. Evidence Level Summary

| evidence level | count | notes |
|---|---:|---|
| O0 | 0 | 모든 시나리오가 Apache security log에서 관찰됨 |
| O1 | 13 | Apache request/response metadata로 관찰 가능 |
| O1/O4 | 2 | S08, S09. 요청은 관찰되지만 결과 판정은 backend app/DB audit 필요 |
| O2 | 0 | 정규 S01~S15 run에서는 warn/error-level proxy context 없음 |
| O3 | 0 | WAF/app runtime context 미수집 |
| O4 | 0 | backend app/DB audit 기반 결과 판정은 수행하지 않음 |

---

## 3. Key Observations

### 3.1 Reverse proxy handler behavior

Juice Shop run에서는 대부분의 요청에서 `handler=proxy-server`가 관찰됐다.

대표 관찰:

| scenario | request | observed status | handler | interpretation |
|---|---|---:|---|---|
| S01 | `/` | 200 | `proxy-server` | Apache가 backend Juice Shop으로 요청 전달 |
| S04 | `/search.php?q=...` | 200 | `proxy-server` | PHP 파일 처리 아님, backend/SPA fallback 가능 |
| S05 | `/does-not-exist-...` | 200 | `proxy-server` | 존재하지 않는 path도 backend가 200 HTML로 처리 가능 |
| S06 | `/private/secret.txt` | 200 | `proxy-server` | 민감 경로 probe가 파일 노출을 의미하지 않음 |
| S11 | `/error.php` | 200 | `proxy-server` | PHP sample의 500 유발 endpoint와 의미가 다름 |
| S15 | `/download.php?file=...etc/passwd` | 200 | `proxy-server` | traversal-like query 관찰일 뿐 파일 읽기 성공 아님 |

이 결과는 reverse proxy/SPA/backend 앱에서도 `status_code=200`이 공격 성공이나 파일 노출의 근거가 될 수 없음을 확인한다.

### 3.2 Backend/SPA fallback behavior

Juice Shop은 다음과 같은 probe-like 요청도 대부분 `200`으로 응답했다.

```text
/static/style.css
/static/app.js
/does-not-exist-obs_juiceshop_proxy_001
/private/secret.txt
/error.php
/download.php?file=..%2F..%2F..%2Fetc%2Fpasswd
```

이 패턴은 backend/SPA fallback response 후보로 해석해야 한다.

권장 해석:

```text
A probe-like request target was observed through Apache reverse proxy.
The backend returned status_code=200 with handler=proxy-server.
Apache logs alone do not prove that the backend route existed or that exploitation succeeded.
```

### 3.3 `/server-status` observation

S12 scanner_burst에서는 `/server-status` 요청이 `status_code=200`으로 관찰됐다.

주의:

- 이 run의 S12 요청은 서버/실험 환경 내부에서 발생한 요청일 수 있다.
- `/server-status` 200은 response body나 외부 노출을 증명하지 않는다.
- 외부 노출 여부는 별도 non-local client check로 확인해야 한다.

### 3.4 Proxy backend unavailable check

정규 S01~S15 run과 별도로 backend 장애 관측을 수행했다.

절차:

```bash
sudo docker stop juice-shop
curl -i -H 'User-Agent: proxy-error-check/1.0' http://juiceshop.local/
sudo tail -n 20 /var/log/apache2/juiceshop_error.log
sudo docker start juice-shop
```

관찰 결과:

```text
HTTP/1.1 503 Service Unavailable
```

관련 error log:

```text
[module_name:proxy] [log_level:error] AH00957: http: attempt to connect to 127.0.0.1:3000 failed
[module_name:proxy_http] [log_level:error] AH01114: HTTP: failed to make connection to backend: 127.0.0.1
```

해석:

- Apache error log는 reverse proxy backend availability 문제를 명확히 보여줄 수 있다.
- backend down 상황은 S01~S15 정규 run과 분리해서 proxy availability context로 기록해야 한다.
- 이 503/proxy error는 backend 연결 실패의 증거이지 공격 성공/침해 증거가 아니다.

---

## 4. Comparison Notes Against Previous Runs

| 항목 | PHP sample | OpenCart | Juice Shop proxy |
|---|---|---|---|
| 배치 | Apache direct PHP/static | Apache + real PHP app + rewrite/front-controller | Apache reverse proxy + backend app |
| 주요 handler | `application/x-httpd-php`, `-` | `application/x-httpd-php`, `redirect-handler`, `httpd/unix-directory` | `proxy-server`, 일부 `server-status` |
| 없는 경로 | 보통 404 | fallback/rewrite로 200 가능 | backend/SPA fallback으로 200 가능 |
| `/error.php` | 500 + PHP warning | 200 fallback | 200 backend/proxy response |
| S08/S09 | O1/O4 | O1/O4 | O1/O4 |
| 정규 run warn/error context | 일부 있음 | 없음 | 없음 |
| 별도 backend 장애 관측 | 해당 없음 | 해당 없음 | 503 + `proxy`/`proxy_http` error |

핵심 차이:

```text
Juice Shop에서는 Apache가 application handler가 아니라 reverse proxy 관찰자다.
따라서 Apache logs alone으로 backend route existence, authentication result, upload result, DB effect를 판단하지 않는다.
```

---

## 5. Guardrail Checks

| guardrail | result | notes |
|---|---|---|
| No success inference from status_code=200 | pass | Juice Shop backend/SPA fallback으로 200이 많으므로 중요 |
| No exposure inference from response size only | pass | S06/S15는 200이어도 파일 노출로 판단하지 않음 |
| No login success inference from POST only | pass | S08은 O1/O4. backend app/DB audit 필요 |
| No upload success inference from POST only | pass | S09는 O1/O4. 저장 성공 판단 금지 |
| No compromise inference from WAF match only | n/a | WAF context 미수집 |
| No attacker IP assertion from x_forwarded_for only | pass | x_forwarded_for는 관찰 header로만 취급 |
| No backend compromise inference from proxy error | pass | 503/proxy error는 backend availability context일 뿐 침해 증거가 아님 |

---

## 6. Pipeline Implications

### 6.1 Prepare/feature extraction

Reverse proxy 앱에서는 다음 feature를 분리해서 보관하는 것이 좋다.

- `handler=proxy-server`
- `status_code`
- `response_body_bytes`
- `duration_us`
- `ttfb_us`
- `proxy/backend error context` 여부
- backend unavailable 여부는 정규 request finding이 아니라 availability/context evidence로 분리

### 6.2 LLM input

LLM 입력에는 다음 식으로 표현하는 것이 적절하다.

```text
A traversal-like query was observed in an Apache reverse proxy request.
The backend returned status_code=200 with handler=proxy-server.
Apache logs alone do not show backend route success, file-read success, or response body contents.
```

backend down/proxy error는 다음처럼 표현한다.

```text
Apache returned 503 while the backend was unavailable.
The related error log shows proxy/proxy_http backend connection failure.
This is backend availability evidence, not evidence of compromise.
```

피해야 할 표현:

```text
Traversal succeeded.
The file was exposed.
The login succeeded.
The upload succeeded.
The backend was compromised.
The 200 response proves exploitation.
```

### 6.3 Web UI / report

Juice Shop/reverse proxy run에서는 UI에 다음 보조 badge 후보를 붙일 수 있다.

```text
reverse-proxy/backend-response candidate
```

표시 조건 후보:

```text
handler=proxy-server
AND status_code=200
AND request target is unusual/probe-like
```

proxy error context가 있을 때는 별도 context badge 후보:

```text
backend unavailable / proxy error context
```

이 badge들은 finding severity를 올리는 근거가 아니라 해석 보조 context다.

---

## 7. Recommended Next Changes

1. PHP sample / OpenCart / Juice Shop 3-way comparison document를 작성한다.
2. reverse-proxy/backend-response candidate feature를 prepare 후보로 추가 검토한다.
3. proxy backend unavailable context를 정규 attack success evidence와 분리하는 기준을 문서화한다.
4. 필요하면 `proxy_error_check`를 별도 scenario catalog extension으로 분리한다.
5. raw body/backend app logs 없이 login/upload/file-read success를 판단하지 않는 guardrail을 유지한다.

---

## 8. Final Assessment

`obs_juiceshop_proxy_001`는 Apache reverse proxy 환경에서 `apache_security_io_v1` 공통 포맷을 적용한 관측 실험으로 유효하다.

이 run은 다음 결론을 제공한다.

```text
Apache security log can consistently observe reverse-proxied Juice Shop request metadata,
but handler=proxy-server and frequent status_code=200 show that Apache is observing backend responses, not backend internal outcomes.
Backend app or DB audit evidence is required for authentication, upload, route success, and exploitation outcomes.
Apache error log is useful for backend availability failures, as shown by the separate 503 proxy_error_check.
```
