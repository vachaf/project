# Observability Run Summary

- run_id: `obs_opencart_002`
- target_app: `opencart`
- topology: `apache_php`
- app_stack: `Apache + PHP + MySQL + OpenCart`
- scenario_catalog_version: `apache_observability_s01_s15_v1`
- log_format_version: `apache_security_io_v1`
- 기준 목적: Apache를 웹단으로 사용하는 실제 PHP 앱에서 `apache_security_io_v1` 포맷과 S01~S15 관측 시나리오가 정상 동작하는지 확인

---

## 1. High-Level Result

`obs_opencart_002` run은 OpenCart 환경에서 Apache security log 관측에 성공했다.

요약:

- S01~S15 전체 시나리오가 `app_security.filtered.log`에서 관찰됐다.
- `observation_matrix.md` 기준 `O0=0`, `O1=13`, `O1/O4=2`, `O2=0`, `O3=0`, `O4=0`으로 집계됐다.
- `log_schema`, `request_id`, `error_link_id`, `vhost`, `server_name`, `src_ip`, `peer_ip`, `raw_request`, `uri`, `query_string`, `status_code`, `in_bytes`, `out_bytes`, `ttfb_us`, `handler` 등 `apache_security_io_v1` 필드가 모두 관찰됐다.
- PHP sample baseline과 달리 OpenCart는 `.htaccess`/front-controller rewrite의 영향으로 존재하지 않는 경로나 예상되지 않은 PHP-like 경로도 `status_code=200`으로 반환하는 경우가 많았다.
- warn/error-level Apache/PHP error context는 관찰되지 않았다.
- S08 login POST와 S09 upload-like POST는 request metadata로는 관찰되지만, 실제 로그인 성공/실패 또는 파일 저장 성공 여부는 앱 로그나 DB/audit evidence 없이는 판단하지 않는다.

---

## 2. Evidence Level Summary

| evidence level | count | notes |
|---|---:|---|
| O0 | 0 | 모든 시나리오가 Apache security log에서 관찰됨 |
| O1 | 13 | Apache request/response metadata로 관찰 가능 |
| O1/O4 | 2 | S08, S09. 요청은 관찰되지만 결과 판정은 app/DB audit 필요 |
| O2 | 0 | warn/error-level Apache/PHP error context가 필요한 케이스 없음 |
| O3 | 0 | WAF/app context 미수집 |
| O4 | 0 | DB/app audit 기반 결과 판정은 수행하지 않음 |

---

## 3. Key Observations

### 3.1 OpenCart front-controller/rewrite behavior

OpenCart 환경에서는 여러 요청이 실제 파일 존재 여부와 무관하게 front-controller 또는 rewrite 경로로 처리됐다.

대표 관찰:

| scenario | request | observed status | handler | interpretation |
|---|---|---:|---|---|
| S05 | `/does-not-exist-obs_opencart_002` | 200 | `redirect-handler` | 존재하지 않는 경로도 앱 라우팅/fallback으로 처리됨 |
| S06 | `/private/secret.txt` | 200 | `redirect-handler` | 민감 경로 probe가 실제 파일 노출을 의미하지 않음 |
| S11 | `/error.php` | 200 | `redirect-handler` | PHP sample과 달리 500 유발 endpoint가 아님 |
| S15 | `/download.php?file=...etc/passwd` | 200 | `redirect-handler` | traversal-like query 관찰일 뿐 파일 읽기 성공 아님 |

이 결과는 OpenCart 같은 실제 PHP 앱에서 `status_code=200`을 공격 성공이나 파일 노출의 근거로 사용하면 안 된다는 점을 확인한다.

### 3.2 Query string rewrite marker

OpenCart에서는 여러 요청에서 `query_string`에 `_route_=`가 추가되어 관찰됐다.

예:

```text
?_route_=search.php&q=normal-search&obs_run=obs_opencart_002&scenario=S04
?_route_=download.php&file=..%2F..%2F..%2Fetc%2Fpasswd&obs_run=obs_opencart_002&scenario=S15
```

이 값은 OpenCart/Apache rewrite 처리의 관찰 결과이며, 원 요청 target과 앱 내부 라우팅 해석을 구분해서 다뤄야 한다.

### 3.3 Handler differences

OpenCart run에서는 다음 handler가 관찰됐다.

| handler | meaning |
|---|---|
| `application/x-httpd-php` | PHP 파일 직접 처리 |
| `redirect-handler` | rewrite/front-controller 처리 경로 |
| `httpd/unix-directory` | directory redirect, 예: `/admin` → `/admin/` 또는 `/admin/index.php` 계열 |

이 차이는 PHP sample baseline보다 실제 앱에서 handler 기반 분류가 더 중요하다는 것을 보여준다.

### 3.4 Scanner burst behavior

S12 scanner_burst에서는 7개 logical burst path가 실행됐지만, 로그에서는 8개 request가 관찰됐다.

원인:

- `/admin` 요청이 `301` 후 `/admin/index.php`로 follow되어 추가 요청이 발생했다.
- runner의 curl 설정이 redirect follow를 사용하기 때문에, logical scenario 1개가 Apache request 여러 건으로 확장될 수 있다.

따라서 matrix의 `count`는 scenario logical count가 아니라 실제 Apache request count로 해석해야 한다.

---

## 4. Comparison Against PHP Sample Baseline

| 항목 | PHP sample baseline | OpenCart run |
|---|---|---|
| 없는 경로 | 보통 404 | rewrite/fallback으로 200 가능 |
| static `/static/style.css`, `/static/app.js` | 200 | 404 |
| `/error.php` | 500 + PHP warning | 200, no warn/error context |
| 민감 경로 probe | 403/404 가능 | 200 fallback 가능 |
| `handler` | PHP endpoint는 `application/x-httpd-php`, static은 `-` | `application/x-httpd-php`, `redirect-handler`, `httpd/unix-directory` 혼재 |
| S12 request count | 7 | 8, redirect follow 영향 |
| warn/error context | 일부 있음 | 없음 |

핵심 차이는 OpenCart가 실제 앱 rewrite/front-controller를 통해 많은 비정상-looking path를 정상 HTML 응답으로 처리한다는 점이다.

---

## 5. Guardrail Checks

| guardrail | result | notes |
|---|---|---|
| No success inference from status_code=200 | pass | OpenCart에서 200 fallback이 많으므로 특히 중요 |
| No exposure inference from response size only | pass | S06/S15는 200이어도 파일 노출로 판단하지 않음 |
| No login success inference from POST only | pass | S08은 O1/O4. app/DB audit 필요 |
| No upload success inference from POST only | pass | S09는 O1/O4. 저장 성공 판단 금지 |
| No compromise inference from WAF match only | n/a | WAF context 미수집 |
| No attacker IP assertion from x_forwarded_for only | pass | x_forwarded_for는 관찰 header로만 취급 |

---

## 6. Pipeline Implications

### 6.1 Prepare/feature extraction

OpenCart 같은 실제 PHP 앱에서는 다음 feature를 분리해서 보관하는 것이 좋다.

- `raw_request`
- `uri`
- `query_string`
- `_route_` 존재 여부
- `handler`
- `status_code`
- `original_status_code`
- redirect-follow로 인한 동일 scenario 내 다중 request

특히 `_route_`가 있는 요청은 원 path와 rewrite/fallback 처리 결과를 구분해야 한다.

### 6.2 LLM input

LLM 입력에는 다음 식으로 표현하는 것이 적절하다.

```text
- traversal-like query was observed in Apache request metadata.
- The request returned status_code=200 through OpenCart rewrite/front-controller behavior.
- Apache logs alone do not show file-read success or response body contents.
```

피해야 할 표현:

```text
- traversal succeeded
- /etc/passwd was exposed
- login succeeded
- upload succeeded
- sensitive file was leaked
```

### 6.3 Web UI / report

OpenCart run에서는 `status_code=200`이 많은 path probe에도 나타나므로 UI에서 다음 보조 설명이 필요하다.

```text
200 response on OpenCart-like front-controller apps may indicate fallback/routed HTML response, not attack success.
```

---

## 7. Recommended Next Changes

1. PHP sample과 OpenCart의 matrix를 비교하는 별도 요약 문서를 작성한다.
2. `summarize_observability_run.sh`에 redirect-follow로 인해 scenario count가 logical request count보다 증가할 수 있음을 notes에 반영한다.
3. OpenCart-like rewrite/front-controller behavior를 prepare 단계의 context feature 후보로 추가한다.
4. `status_code=200` + `handler=redirect-handler` + `_route_=` 조합을 fallback/routed response 후보로 다루되, 공격 성공으로 승격하지 않는다.
5. 다음 비교 대상으로 Juice Shop reverse proxy run을 수행한다.

---

## 8. Final Assessment

`obs_opencart_002`는 OpenCart 환경에서 `apache_security_io_v1` 공통 포맷을 적용한 관측 실험으로 유효하다.

이 run은 다음 결론을 제공한다.

```text
Apache security log can consistently observe OpenCart request metadata,
but OpenCart rewrite/front-controller behavior makes status_code=200 a weak success signal.
Application or DB audit evidence is required for internal outcomes such as login success, upload success, and file-read success.
```
