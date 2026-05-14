# PHP Sample vs OpenCart Apache Observability Comparison

- 문서 상태: 비교 요약
- 작성일: 2026-05-14
- 비교 대상:
  - `obs_php_sample_002`
  - `obs_opencart_002`
- 공통 조건:
  - Apache 웹단
  - `apache_security_io_v1` LogFormat
  - `apache_observability_s01_s15_v1` scenario catalog
  - User-Agent canonical marker: `obs-test/Sxx run=<run_id>`
- 비범위:
  - 취약점 진단 결과 작성
  - 공격 성공 여부 판정
  - 앱/DB 내부 상태 변경 판정

---

## 1. Executive Summary

두 run 모두 `apache_security_io_v1` 포맷으로 Apache request/response metadata를 안정적으로 관찰했다.

핵심 차이는 애플리케이션 배치와 라우팅 방식이다.

```text
PHP sample:
  단순 PHP/정적 파일 기준 baseline.
  파일 존재 여부와 의도한 endpoint 동작이 Apache 로그에 비교적 직관적으로 드러난다.

OpenCart:
  실제 PHP 앱 + rewrite/front-controller 기반 동작.
  존재하지 않는 경로나 probe-like path도 앱 라우팅/fallback을 통해 status_code=200으로 관찰될 수 있다.
```

가장 중요한 결론:

```text
Apache 로그에서 status_code=200이 관찰되어도 실제 공격 성공, 파일 노출, 로그인 성공, 업로드 성공으로 해석하면 안 된다.
실제 앱에서는 rewrite/front-controller/fallback 응답 때문에 200이 약한 신호가 된다.
```

---

## 2. Compared Runs

| 항목 | PHP sample | OpenCart |
|---|---|---|
| run_id | `obs_php_sample_002` | `obs_opencart_002` |
| target_app | `php_sample` | `opencart` |
| topology | `apache_php` | `apache_php` |
| app stack | Apache + PHP sample | Apache + PHP + MySQL + OpenCart |
| log format | `apache_security_io_v1` | `apache_security_io_v1` |
| scenario catalog | `apache_observability_s01_s15_v1` | `apache_observability_s01_s15_v1` |
| WAF context | not collected | not collected |
| app/DB audit | not collected | not collected |

---

## 3. Evidence Level Comparison

| evidence level | PHP sample | OpenCart | interpretation |
|---|---:|---:|---|
| O0 | 0 | 0 | 모든 시나리오가 Apache security log에서 관찰됨 |
| O1 | 12 | 13 | Apache request/response metadata로 관찰 가능 |
| O1/O4 | 2 | 2 | S08/S09. 요청은 관찰되지만 결과 판정은 app/DB audit 필요 |
| O2 | 1 | 0 | PHP sample의 S11은 warn/error-level context가 연결됨 |
| O3 | 0 | 0 | WAF/app context 미수집 |
| O4 | 0 | 0 | DB/app audit 기반 결과 판정은 수행하지 않음 |

---

## 4. Scenario-Level Differences

### 4.1 Normal/static requests

| scenario | PHP sample | OpenCart | implication |
|---|---|---|---|
| S01 normal_main | `/index.php`, 200, PHP handler | `/index.php`, 200, PHP handler | 둘 다 정상 baseline 관찰 가능 |
| S02 static_css | `/static/style.css`, 200 | `/static/style.css`, 404 | OpenCart에는 해당 synthetic static path가 없음 |
| S03 static_js | `/static/app.js`, 200 | `/static/app.js`, 404 | static path는 앱별 fixture 의존성이 큼 |

해석:

- 공통 시나리오 path가 모든 앱에서 존재한다고 가정하면 안 된다.
- static baseline은 앱별 실제 asset path를 추가로 수집해야 더 정밀해진다.

---

### 4.2 Query/search requests

| scenario | PHP sample | OpenCart | implication |
|---|---|---|---|
| S04 query_search | `/search.php?q=...`, 200, PHP handler | `/search.php?..._route_=search.php...`, 200, `redirect-handler` | OpenCart rewrite가 query string에 `_route_`를 추가 |
| S10 slow_or_large_request | `/search.php?...sleep_ms=300...`, 200 | `/search.php?..._route_=search.php...`, 200 | 같은 request path라도 앱 라우팅 의미가 다름 |
| S13 sqli_like | SQLi-like query 관찰, 200 | SQLi-like query 관찰, 200 + `_route_` | 둘 다 O1. 성공 판단 금지 |
| S14 xss_like | XSS-like query 관찰, 200 | XSS-like query 관찰, 200 + `_route_` | 둘 다 O1. 브라우저 실행 판단 금지 |

해석:

- OpenCart에서는 `_route_=`가 rewrite/front-controller 처리 힌트다.
- LLM 입력에서 raw target과 routed/fallback behavior를 분리해서 설명해야 한다.

---

### 4.3 Not-found, sensitive-path, traversal-like requests

| scenario | PHP sample | OpenCart | implication |
|---|---|---|---|
| S05 not_found | 404 | 200 + `redirect-handler` | OpenCart fallback으로 200 가능 |
| S06 forbidden_or_sensitive_path | 403 + authz error context | 200 + `redirect-handler` | 200이어도 파일 노출이 아님 |
| S15 traversal_like | 404 or PHP app handling + warn/error context | 200 + `redirect-handler` | traversal-like query 관찰일 뿐 파일 읽기 성공 아님 |

해석:

- OpenCart-like 앱에서는 `status_code=200`이 probe 성공 신호가 아니라 fallback/routed HTML 응답일 수 있다.
- `status_code`, `response_body_bytes`, `resp_content_type`만으로 파일 노출을 판단하지 않는다.

---

### 4.4 Login/upload-like requests

| scenario | PHP sample | OpenCart | implication |
|---|---|---|---|
| S08 login_post | POST `/login.php`, 401, O1/O4 | POST `/login.php`, 200, O1/O4 | request는 관찰 가능. 성공/실패는 app/DB audit 필요 |
| S09 upload_like_post | POST `/upload.php`, 400, O1/O4 | POST `/upload.php`, 200, O1/O4 | upload-like request는 관찰 가능. 저장 성공 판단 금지 |

해석:

- S08/S09는 두 앱 모두 Apache request metadata로는 관찰 가능하다.
- 결과 판정은 앱 로그 또는 DB/audit evidence가 있어야 한다.
- HTTP status 차이는 앱 응답 방식 차이일 수 있으므로 내부 결과로 해석하지 않는다.

---

### 4.5 Server-error scenario

| scenario | PHP sample | OpenCart | implication |
|---|---|---|---|
| S11 server_error | `/error.php`, 500, notice+warn, O2 | `/error.php`, 200, no warn/error, O1 | 동일 path라도 앱마다 의미가 다름 |

해석:

- PHP sample의 `/error.php`는 의도적으로 500/warn을 만들기 위한 endpoint다.
- OpenCart의 `/error.php`는 실제 500 유발 endpoint가 아니라 rewrite/fallback으로 처리된다.
- 따라서 scenario label만으로 expected status를 고정하면 안 되고, 실제 앱별 라우팅 결과를 함께 봐야 한다.

---

### 4.6 Scanner burst

| item | PHP sample | OpenCart |
|---|---|---|
| logical burst paths | 7 | 7 |
| observed Apache requests | 7 | 8 |
| reason for extra count | none | `/admin` redirect follow로 `/admin/index.php` 추가 |
| status mix | 200/404 중심, `/server-status` local 200 | 200 다수 + 301 |

해석:

- runner의 redirect follow 때문에 logical scenario 1개가 Apache request 여러 건으로 확장될 수 있다.
- matrix의 `count`는 logical request count가 아니라 actual Apache request count다.
- OpenCart의 `/admin`은 directory/app routing behavior를 드러낸다.

---

## 5. Handler Comparison

| handler | PHP sample | OpenCart | interpretation |
|---|---|---|---|
| `application/x-httpd-php` | PHP endpoint에서 주로 관찰 | `/index.php`, `/admin/index.php` 등에서 관찰 | PHP 직접 처리 |
| `-` | static asset, 404 등에서 관찰 | 일부 404/static missing에서 관찰 | 별도 handler 없음 또는 정적/부재 처리 |
| `redirect-handler` | 거의 없음 | 다수 경로에서 관찰 | rewrite/front-controller/fallback 처리 힌트 |
| `httpd/unix-directory` | 관찰되지 않음 | `/admin` 301에서 관찰 | directory redirect |
| `server-status` | localhost S12에서 관찰 | OpenCart run에서는 routed/fallback으로 관찰 가능 | 환경/라우팅에 따라 의미 다름 |

Pipeline implication:

```text
handler는 앱 배치/라우팅을 설명하는 중요한 context feature다.
handler=redirect-handler + _route_=... + status_code=200 조합은 fallback/routed response 후보로 다룬다.
```

---

## 6. Error Context Comparison

| 항목 | PHP sample | OpenCart |
|---|---|---|
| notice-level app/PHP context | 있음 | 없음 또는 관찰되지 않음 |
| warn/error-level context | S06, S11, S12 일부, S15 등에서 관찰 | 없음 |
| request_id 기반 error correlation | 동작 확인 | 동작 가능하나 이번 run에는 연결 대상 거의 없음 |
| S11 | 500 + PHP warning | 200 + no warn/error |

해석:

- error log 연결은 PHP sample에서 검증됐다.
- OpenCart run에서는 warning/error가 거의 없어 O2 케이스가 나타나지 않았다.
- error context가 없다는 것은 공격/오류가 없다는 확정 증거가 아니라, Apache/PHP error log에 관련 warn/error가 없었다는 의미다.

---

## 7. Guardrail Comparison

| guardrail | PHP sample | OpenCart | conclusion |
|---|---|---|---|
| `status_code=200`만으로 성공 판단 금지 | 필요 | 매우 중요 | OpenCart fallback 200 때문에 더 중요 |
| response size만으로 노출 판단 금지 | 필요 | 매우 중요 | 200 + HTML fallback 가능 |
| login POST만으로 성공 판단 금지 | 필요 | 필요 | 둘 다 O1/O4 |
| upload POST만으로 저장 성공 판단 금지 | 필요 | 필요 | 둘 다 O1/O4 |
| query payload만으로 SQLi/XSS/traversal 성공 판단 금지 | 필요 | 필요 | 둘 다 O1 |
| x_forwarded_for만으로 attacker IP 확정 금지 | 필요 | 필요 | 이번 run에서는 값 없음 |

---

## 8. Pipeline Design Implications

### 8.1 Prepare 단계 feature 후보

다음 필드는 둘 다 공통으로 유지한다.

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

OpenCart-like 앱에서 추가로 파생하면 좋은 feature:

- `has_route_param`: query string에 `_route_=` 존재 여부
- `route_param_value`: `_route_` 값
- `is_front_controller_candidate`: `handler=redirect-handler` 또는 `_route_=` 기반
- `is_fallback_200_candidate`: `status_code=200` + path probe/sensitive-like target + front-controller hint
- `scenario_request_count`: runner/experiment context에서 logical scenario 대비 actual request count
- `redirect_follow_candidate`: same scenario marker에서 301 이후 추가 request 관찰

### 8.2 LLM input 표현 방식

OpenCart-like 요청은 다음처럼 표현한다.

```text
A traversal-like query was observed in Apache request metadata.
The request returned status_code=200 through an OpenCart rewrite/front-controller path.
Apache logs alone do not prove file-read success or response body disclosure.
```

피해야 할 표현:

```text
Traversal succeeded.
/etc/passwd was exposed.
The upload succeeded.
The login succeeded.
The 200 response proves exploitation.
```

### 8.3 Web UI 표시 후보

OpenCart-like front-controller behavior가 감지되면 UI에 보조 badge를 붙일 수 있다.

```text
front-controller/fallback candidate
```

표시 조건 후보:

```text
status_code=200
AND (handler=redirect-handler OR query_string contains _route_=)
AND request target is unusual/probe-like
```

단, 이 badge는 finding severity를 올리는 근거가 아니라 해석 보조 context다.

---

## 9. Lessons Learned

1. `apache_security_io_v1`은 단순 PHP sample과 실제 OpenCart 모두에서 적용 가능하다.
2. 동일 LogFormat을 유지해야 앱별 차이가 더 명확하게 보인다.
3. 실제 PHP 앱에서는 rewrite/front-controller 때문에 200 응답이 매우 약한 성공 신호다.
4. `handler`와 `query_string`의 `_route_=`는 앱 라우팅/fallback 해석에 유용하다.
5. S08/S09 같은 POST scenario는 User-Agent marker가 canonical 식별자로 필요하다.
6. error log context는 notice/warn/error를 분리해야 한다.
7. runner의 redirect follow는 actual Apache request count를 증가시킬 수 있다.

---

## 10. Recommended Next Steps

1. `summarize_observability_run.sh`에 redirect-follow/double-request notes를 자동 반영한다.
2. prepare 단계 후보 문서에 OpenCart-like front-controller/fallback features를 추가한다.
3. Juice Shop reverse proxy 환경에서도 같은 `apache_security_io_v1` 포맷으로 S01~S15 run을 수행한다.
4. 이후 세 run을 비교한다.

```text
php_sample      -> direct Apache/PHP baseline
opencart        -> real PHP app + rewrite/front-controller behavior
juiceshop_proxy -> Apache reverse proxy + backend app behavior
```
