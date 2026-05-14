# 99 Prepare Apache Observability Context Feature Review

- 문서 상태: 설계 검토 초안
- 작성일: 2026-05-14
- 기준 실험:
  - `obs_php_sample_002`
  - `obs_opencart_002`
  - `obs_juiceshop_proxy_001`
- 관련 문서:
  - `docs/operations/99_apache_custom_log_format_contract.md`
  - `docs/operations/examples/apache_security_logformat_v1.conf`
  - `docs/design/99_apache_app_observability_comparison_plan.md`
  - `lab/observability/comparison_php_sample_vs_opencart.md`
  - `lab/observability/comparison_php_sample_vs_opencart_vs_juiceshop.md`
- 관련 스크립트:
  - `scripts/convert_observability_logs_to_export_json.py`
  - `scripts/summarize_observability_run.sh`
  - `scripts/update_observation_matrix_from_run.sh`
- 검토 대상 코드:
  - `src/prepare_llm_input.py`

---

## 1. 목적

이 문서는 Apache app observability 3-way 비교 결과를 바탕으로, `prepare_llm_input.py`에 추가할 수 있는 topology/context feature 후보를 검토한다.

검토 목적은 공격 탐지 범위를 무리하게 넓히는 것이 아니다. 목적은 다음이다.

```text
status_code=200, text/html, response size, handler 같은 Apache 관측값을
앱 배치 문맥과 함께 해석해 과도한 성공 단정을 줄이는 것
```

즉, 이 문서는 detection 강화 문서라기보다 **interpretation guardrail 강화 문서**다.

---

## 2. 배경

동일한 `apache_security_io_v1` LogFormat을 세 가지 Apache 웹단 앱 배치에 적용했다.

| run | topology | 핵심 관찰 |
|---|---|---|
| `obs_php_sample_002` | direct Apache/PHP sample | 파일 존재/404/500/error log 연결이 비교적 직관적 |
| `obs_opencart_002` | Apache + real PHP app + rewrite/front-controller | probe-like path도 `_route_=`/`redirect-handler`를 통해 200 fallback 가능 |
| `obs_juiceshop_proxy_001` | Apache reverse proxy + backend app | 대부분 `handler=proxy-server`, backend/SPA fallback으로 200 가능 |

세 run은 모두 Apache security log에서 S01~S15를 관찰했다. 그러나 `status_code=200`의 의미는 배치마다 크게 달랐다.

핵심 결론:

```text
status_code=200 is topology-dependent and weak as a success signal.
```

---

## 3. 주요 관찰 요약

### 3.1 PHP sample baseline

PHP sample은 direct Apache/PHP/static baseline으로 유용하다.

관찰:

- PHP endpoint는 `handler=application/x-httpd-php`로 관찰된다.
- static asset은 `handler=-`로 관찰된다.
- 없는 경로는 보통 404다.
- `/error.php`는 500 + PHP warning을 발생시켜 O2 케이스 확인에 유용하다.

해석:

```text
포맷/파서/기본 context 연결 검증에는 적합하지만,
실제 앱의 fallback/rewrite/proxy behavior를 대표하지는 않는다.
```

### 3.2 OpenCart rewrite/front-controller behavior

OpenCart는 실제 PHP 앱의 rewrite/front-controller 특성을 보여준다.

관찰:

- `handler=redirect-handler`가 다수 관찰된다.
- `query_string`에 `_route_=`가 추가된다.
- 존재하지 않는 path, sensitive-looking path, traversal-like path도 `status_code=200`으로 관찰될 수 있다.
- `/admin` 요청은 redirect-follow로 logical request 1개가 actual Apache request 2개로 확장될 수 있다.

해석:

```text
status_code=200 + handler=redirect-handler + _route_=... 조합은
공격 성공이 아니라 fallback/routed response 후보로 다룬다.
```

### 3.3 Juice Shop reverse proxy/backend behavior

Juice Shop은 Apache reverse proxy + backend app 배치를 보여준다.

관찰:

- 대부분의 요청이 `handler=proxy-server`로 관찰된다.
- probe-like path도 backend/SPA fallback으로 `status_code=200`을 반환할 수 있다.
- Apache는 backend 내부 인증/업로드/라우팅/DB 결과를 알 수 없다.
- backend container를 중지한 별도 `proxy_error_check`에서는 `503` + `proxy`/`proxy_http` error log가 관찰됐다.

해석:

```text
handler=proxy-server + status_code=200은 backend response metadata이며,
backend route success 또는 exploitation success를 뜻하지 않는다.
```

---

## 4. Feature 후보 목록

## 4.1 Common topology fields

현재 `apache_security_io_v1`에서 이미 관찰 가능한 필드:

| field | 활용 |
|---|---|
| `handler` | Apache 처리 경로 또는 topology hint |
| `status_code` | 최종 HTTP status, 성공 단정에는 부적합 |
| `original_status_code` | internal redirect 이전 status 참고 |
| `raw_request` | 원 요청 line 보존 |
| `uri` | query 제외 request path |
| `query_string` | query 및 rewrite marker 확인 |
| `response_body_bytes` | body size, 노출 증거 아님 |
| `resp_content_type` | response type, 정상/노출 증거 아님 |
| `duration_us`, `ttfb_us` | timing context |
| `error_link_id`, `request_id` | error log correlation |

이 필드들은 공격 성공 근거가 아니라 context feature로 사용한다.

---

## 4.2 OpenCart-like front-controller features

| feature | source | meaning | recommended use |
|---|---|---|---|
| `has_route_param` | `query_string` contains `_route_=` | rewrite/front-controller routing marker | context |
| `route_param_value` | `_route_` value | routed target hint | context |
| `is_front_controller_candidate` | `_route_=` or `handler=redirect-handler` | app routing/fallback 후보 | context-only |
| `is_fallback_200_candidate` | `status_code=200` + route/front-controller hint + unusual target | 200 fallback 가능성 | scoring 완화/context |
| `front_controller_reason_hints` | derived | 왜 fallback 후보인지 설명 | LLM input context |

예시:

```text
uri=/download.php
query_string=?_route_=download.php&file=..%2F..%2F..%2Fetc%2Fpasswd
status_code=200
handler=redirect-handler
```

권장 해석:

```text
traversal-like query observed, but front-controller/fallback response candidate.
Do not infer file-read success.
```

---

## 4.3 Reverse proxy/backend response features

| feature | source | meaning | recommended use |
|---|---|---|---|
| `is_reverse_proxy_candidate` | `handler=proxy-server` | Apache reverse proxy path | context-only |
| `backend_response_candidate` | `handler=proxy-server` + status | backend response metadata | context-only |
| `backend_fallback_200_candidate` | `status_code=200` + `handler=proxy-server` + unusual target | backend/SPA fallback 가능성 | scoring 완화/context |
| `reverse_proxy_reason_hints` | derived | reverse proxy 해석 보조 | LLM input context |

예시:

```text
uri=/private/secret.txt
status_code=200
handler=proxy-server
resp_content_type=text/html
```

권장 해석:

```text
sensitive-looking path was requested through Apache reverse proxy.
The backend returned 200, but Apache logs alone do not prove that the backend route exists or that a file was exposed.
```

---

## 4.4 Redirect/follow features

| feature | source | meaning | recommended use |
|---|---|---|---|
| `logical_scenario_count` | scenario catalog / run context | 의도한 logical request 수 | experiment-only |
| `actual_apache_request_count` | Apache log count | 실제 Apache request 수 | context |
| `extra_request_count` | actual - logical | redirect/follow 등으로 증가한 request 수 | context |
| `has_3xx_status` | status code | redirect 발생 가능성 | context |
| `location_header_present` | `Location` response header | redirect target 존재 | context |
| `redirect_follow_candidate` | derived | logical request가 여러 Apache request로 확장된 후보 | context-only |

주의:

- 이 feature는 실험 run에서 특히 유용하다.
- 일반 운영 로그에서는 logical scenario count가 없을 수 있으므로 `3xx + Location + close time proximity` 정도만 사용할 수 있다.
- redirect-follow는 공격 성공 근거가 아니다.

---

## 4.5 Backend unavailable / proxy error context

| feature | source | meaning | recommended use |
|---|---|---|---|
| `backend_unavailable_context` | `status_code=503` + proxy error | backend 연결 실패 | ops/context-only |
| `proxy_error_context` | error log `module_name=proxy/proxy_http` | reverse proxy backend error | context-only |
| `proxy_error_message_summary` | error log message | backend availability 설명 | LLM context |

예시:

```text
status_code=503
app_error.log module_name=proxy/proxy_http
message=failed to make connection to backend
```

권장 해석:

```text
Apache returned 503 because the backend was unavailable.
This is backend availability evidence, not evidence of compromise.
```

---

## 5. Scoring / Candidate 정책

### 5.1 점수 상승에 쓰지 않을 항목

아래 feature는 기본적으로 candidate score를 올리지 않는다.

- `is_front_controller_candidate`
- `is_fallback_200_candidate`
- `is_reverse_proxy_candidate`
- `backend_response_candidate`
- `redirect_follow_candidate`
- `backend_unavailable_context`
- `proxy_error_context`

이유:

```text
이들은 공격 강도 신호가 아니라 topology/interpretation context다.
```

### 5.2 점수 완화 또는 wording 완화에 쓸 항목

다음 조합은 공격 성공 표현을 약화하는 데 사용한다.

```text
status_code=200
AND probe-like target
AND (is_front_controller_candidate OR is_reverse_proxy_candidate)
```

효과 후보:

- `reason_hints`에 `topology:fallback_200_candidate` 추가
- LLM prompt context에 “do not infer success from this 200” 명시
- file disclosure/path traversal success-like wording 차단

### 5.3 기존 attack hint는 유지

예:

- SQLi-like query
- XSS-like query
- traversal-like query

이런 high-signal payload 관찰 자체는 candidate로 유지할 수 있다. 다만 topology context를 함께 제공해 성공 단정을 방지한다.

---

## 6. LLM input 표현 기준

### 6.1 Front-controller/fallback candidate 표현

권장:

```text
A traversal-like query was observed in Apache request metadata.
The request returned status_code=200 through a front-controller/rewrite/fallback candidate path.
Apache logs alone do not show file-read success or response body contents.
```

금지:

```text
Traversal succeeded.
The file was exposed.
The 200 response confirms exploitation.
```

### 6.2 Reverse proxy/backend response 표현

권장:

```text
A sensitive-looking path was requested through Apache reverse proxy.
The backend returned status_code=200 with handler=proxy-server.
Apache logs alone do not prove backend route success, authentication result, file exposure, or exploit success.
```

금지:

```text
The backend route existed.
The file was exposed.
The attack succeeded.
```

### 6.3 Backend unavailable context 표현

권장:

```text
Apache returned 503 while the backend was unavailable.
The related error log shows proxy/proxy_http backend connection failure.
This is backend availability evidence, not evidence of compromise.
```

금지:

```text
The backend was compromised.
The attacker caused the backend failure.
```

---

## 7. Web UI 표시 후보

UI에 표시한다면 모두 display-only badge로 둔다.

| badge | condition candidate | meaning |
|---|---|---|
| `front-controller/fallback candidate` | `handler=redirect-handler` or `_route_=` | app fallback/routing 가능성 |
| `reverse-proxy/backend-response candidate` | `handler=proxy-server` | backend response via Apache proxy |
| `redirect-follow candidate` | extra Apache request / 3xx / Location | logical request가 여러 request로 확장 가능 |
| `backend unavailable / proxy error context` | 503 + proxy/proxy_http error | backend availability issue |

금지:

- badge로 severity 변경 금지
- badge로 category 변경 금지
- badge로 verdict 변경 금지
- context-only event를 finding으로 승격 금지

---

## 8. 구현 후보

### 8.1 최소 구현 후보

`prepare_llm_input.py`의 row context 생성 단계에서 다음 helper를 추가하는 방향을 검토한다.

```text
build_apache_observability_context_hints(row) -> List[str]
```

반환 예:

```text
observability:front_controller_candidate
observability:fallback_200_candidate
observability:reverse_proxy_candidate
observability:backend_response_candidate
observability:redirect_follow_candidate
```

### 8.2 필드 추가 후보

Candidate 또는 context row에 다음 optional fields 추가 검토:

```json
{
  "topology_hints": ["reverse_proxy_candidate"],
  "fallback_response_candidate": true,
  "front_controller_candidate": false,
  "reverse_proxy_candidate": true,
  "redirect_follow_candidate": false,
  "topology_interpretation_note": "handler=proxy-server; status_code=200 is backend response metadata, not exploit success"
}
```

### 8.3 context-only summary 후보

향후 필요 시 다음 summary를 추가할 수 있다.

```text
apache_topology_context_summaries
```

단, 초기에는 row-level reason_hints만으로 충분할 수 있다.

---

## 9. 테스트 후보

### 9.1 OpenCart fallback candidate fixture

입력 row:

```text
uri=/download.php
query_string=?_route_=download.php&file=..%2F..%2Fetc%2Fpasswd
status_code=200
handler=redirect-handler
resp_content_type=text/html
```

기대:

```text
observability:front_controller_candidate
observability:fallback_200_candidate
Do not infer file-read success.
```

### 9.2 Juice Shop reverse proxy candidate fixture

입력 row:

```text
uri=/private/secret.txt
status_code=200
handler=proxy-server
resp_content_type=text/html
```

기대:

```text
observability:reverse_proxy_candidate
observability:backend_response_candidate
Do not infer backend route success or file exposure.
```

### 9.3 Proxy error context fixture

입력:

```text
security row: status_code=503, handler=proxy-server
error row: module_name=proxy_http, log_level=error, message=failed to make connection to backend
```

기대:

```text
backend_unavailable_context
proxy_error_context
context-only / ops context
not compromise evidence
```

### 9.4 Redirect-follow fixture

입력:

```text
same scenario/run marker
/admin -> 301
/admin/index.php -> 200
```

기대:

```text
redirect_follow_candidate
actual_apache_request_count > logical_scenario_count
no attack success inference
```

---

## 10. 비범위

이 문서의 범위가 아니다.

- Apache CustomLog 포맷 변경
- request body 수집
- response body 수집
- Cookie/Authorization/Set-Cookie 원문 수집
- status 200 기반 성공 판정 추가
- Web UI에서 새 관계 추론
- context-only 항목을 finding으로 승격
- severity/category/verdict 재계산

---

## 11. 권장 결론

단기적으로는 다음이 적절하다.

```text
1. topology hints를 prepare row-level context로 추가할지 검토한다.
2. scoring 상승보다는 success wording 완화/guardrail 강화에 사용한다.
3. front-controller/reverse-proxy/redirect/proxy-error는 context-only interpretation feature로 둔다.
4. 충분한 fixture를 만든 뒤 prepare에 최소 구현한다.
```

즉시 구현 우선순위는 다음 순서다.

```text
P1: row-level topology reason_hints 추가
P2: fallback_200_candidate guardrail wording 추가
P3: proxy_error_context는 error table 또는 app_error integration 경로가 정리된 뒤 추가
P4: Web UI badge는 prepare/viewer payload 필드가 안정화된 뒤 검토
```
