# PHP Sample Observability Comparison: apache_security_io_v1 vs apache_security_io_v2

- 작성일: 2026-05-15
- 비교 대상:
  - v1: `lab/observability/runs/obs_php_sample_002`
  - v2: `lab/observability/runs/obs_php_sample_v2_001`
- 대상 앱: PHP sample
- topology: `apache_php`
- scenario catalog: `apache_observability_s01_s15_v1`
- 목적: 기존 v1 서버/기준선은 유지하면서, 새 v2 서버에서 LogFormat 확장 필드가 관측/변환/파이프라인에 안전하게 연결되는지 비교한다.

---

## 1. 결론

`apache_security_io_v2`는 기본 Apache+PHP 샘플 환경에서 정상 동작했다.

v2는 v1의 보안 판정력을 강화하는 포맷이 아니라, parser/viewer/LLM 입력 안정성을 높이는 보조 필드를 추가한 schema다.

이번 비교의 핵심 결론은 다음과 같다.

```text
[OK] v1 서버/기준선은 그대로 유지
[OK] v2 새 서버에서 S01~S15 관측 성공
[OK] v2 raw security log에 request_target / req_host / client_ip_source / has_cookie / has_authorization 출력 확인
[OK] converter가 v2 필드를 export JSON에 보존
[OK] v2 export JSON 기반 prepare/stage/viewer dry-run 연결 성공
[주의] v2 dry-run candidate_rows=13은 v2 필드 때문이라기보다 PHP sample direct topology와 4xx/5xx/error-linked scoring 영향으로 별도 검토 필요
```

v2 production migration은 아직 시작하지 않는다. v2는 새 테스트 서버 기반 검증 대상으로 유지한다.

---

## 2. 비교 입력

| 항목 | v1 | v2 |
|---|---|---|
| run_id | `obs_php_sample_002` | `obs_php_sample_v2_001` |
| target_app | `php_sample` | `php_sample` |
| topology | `apache_php` | `apache_php` |
| LogFormat schema | `apache_security_io_v1` | `apache_security_io_v2` |
| summary | `lab/observability/runs/obs_php_sample_002/summary.md` | `lab/observability/runs/obs_php_sample_v2_001/summary.md` |
| observation matrix | `lab/observability/runs/obs_php_sample_002/observation_matrix.autofill.md` | `lab/observability/runs/obs_php_sample_v2_001/observation_matrix.autofill.md` |
| dry-run output | earlier v1 pipeline dry-run artifact | `obs_php_sample_001_v2_pipeline_dryrun` |

---

## 3. Scenario behavior comparison

S01~S15의 HTTP behavior는 v1/v2에서 실질적으로 동일했다.

| scenario | v1 status | v2 status | comparison |
|---|---|---|---|
| S01 normal_main | 200 | 200 | 동일. PHP page view 관찰 |
| S02 static_css | 200 | 200 | 동일. static CSS 관찰 |
| S03 static_js | 200 | 200 | 동일. static JS 관찰 |
| S04 query_search | 200 | 200 | 동일. query search 관찰 |
| S05 not_found | 404 | 404 | 동일. not-found 관찰 |
| S06 forbidden_or_sensitive_path | 403 | 403 | 동일. denied path 관찰 |
| S07 login_get | 200 | 200 | 동일. login form GET 관찰 |
| S08 login_post | 401 | 401 | 동일. POST 관찰. 성공 판단 금지 |
| S09 upload_like_post | 400 | 400 | 동일. multipart/upload-like POST 관찰. 저장 성공 판단 금지 |
| S10 slow_or_large_request | 200 | 200 | 동일. timing/metadata 관찰 |
| S11 server_error | 500 | 500 | 동일. error log 연결 가능 |
| S12 scanner_burst | 200x3, 404x4 | 200x3, 404x4 | 동일. 7 logical requests, redirect/follow extra 없음 |
| S13 sqli_like | 200 | 200 | 동일. SQLi-like query 관찰. DB 성공 판단 금지 |
| S14 xss_like | 200 | 200 | 동일. XSS-like query 관찰. browser execution 판단 금지 |
| S15 traversal_like | 404 | 404 | 동일. traversal-like query 관찰. file-read success 판단 금지 |

해석:

- v2 필드 추가는 HTTP response behavior를 바꾸지 않는다.
- 기본 Apache+PHP 환경에서는 v1/v2 모두 같은 scenario evidence level을 유지한다.
- status code, response size, content type만으로 성공/노출/침해를 판단하지 않는 guardrail도 동일하게 유지한다.

---

## 4. Evidence level comparison

v1/v2의 evidence level summary는 동일하다.

| evidence level | v1 count | v2 count | notes |
|---|---:|---:|---|
| O0 | 0 | 0 | 관찰 불가 scenario 없음 |
| O1 | 12 | 12 | 대부분 Apache request/response metadata로 관찰 가능 |
| O1/O4 | 2 | 2 | S08 login_post, S09 upload_like_post. 결과 확인은 app/DB audit 필요 |
| O2 | 1 | 1 | S11 server_error. Apache/PHP warn/error context 연결 가능 |
| O3 | 0 | 0 | WAF context 없음 |
| O4 | 0 | 0 | DB/app audit 기반 결과 확인 없음 |

해석:

- v2는 evidence level을 높이지 않는다.
- `has_cookie`, `has_authorization` 같은 presence flag도 인증 성공 증거가 아니다.
- `request_target`도 convenience field일 뿐 raw request fidelity를 대체하지 않는다.

---

## 5. Field comparison

### 5.1 v1 baseline fields

v1에서 관찰된 주요 필드는 다음과 같다.

```text
log_schema
log_time
request_id
error_link_id
vhost
server_name
server_port
local_ip
src_ip
peer_ip
method
raw_request
uri
query_string
protocol
status_code
original_status_code
response_body_bytes
in_bytes
out_bytes
total_bytes
duration_us
ttfb_us
keepalive_count
connection_status
handler
req_content_type
req_content_length
resp_content_type
location
referer
origin
user_agent
host
x_forwarded_for
x_real_ip
forwarded
```

### 5.2 v2 added/renamed fields

v2에서 추가 또는 명확화된 필드는 다음과 같다.

| field | result | purpose |
|---|---|---|
| `request_target` | observed | `%U%q` 기반 normalized convenience target |
| `req_host` | observed | client-supplied Host header를 명확히 표시 |
| `client_ip_source` | observed | IP 해석 기준을 config literal로 명시. 이번 run은 `direct` |
| `has_cookie` | observed | Cookie presence flag. 원문 미수집 |
| `has_authorization` | observed | Authorization presence flag. 원문 미수집 |
| `remoteip_proxy_chain` | null / n/a | 기본 v2에서는 사용하지 않음. remoteip schema에서 별도 검토 |

### 5.3 request_target vs raw_request_target

v2 S01에서 다음 차이가 관찰됐다.

```text
raw_request:        GET /?obs_run=obs_php_sample_v2_001&scenario=S01 HTTP/1.1
request_target:     /index.php?obs_run=obs_php_sample_v2_001&scenario=S01
raw_request_target: /?obs_run=obs_php_sample_v2_001&scenario=S01
```

해석:

- `request_target`은 Apache `%U%q` 기반 normalized target이다.
- `raw_request_target`은 `raw_request`에서 추출한 original request-target이다.
- raw request-target fidelity가 필요한 경우 `raw_request` 또는 `raw_request_target`을 우선한다.
- viewer/parser convenience에는 `request_target`이 유용하다.

---

## 6. Converter / export JSON comparison

### v1

v1은 기존 converter 흐름에서 정상적으로 pipeline에 연결됐다.

### v2

초기 v2 변환에서는 raw log에 존재하던 v2 필드가 export JSON top-level row에서 누락되었다.

누락됐던 필드:

```text
request_target
req_host
client_ip_source
has_cookie
has_authorization
```

이후 `convert_observability_logs_to_export_json.py`를 수정해 v2 필드를 보존하도록 했다.

수정 후 확인된 export meta:

```text
meta.log_schema = apache_security_io_v2
meta.log_schemas = [apache_security_io_v2]
total_count = 21
```

수정 후 row-level 확인:

```text
request_target preserved
raw_request_target preserved
req_host preserved
host compatibility fallback from req_host preserved
client_ip_source preserved
has_cookie normalized to boolean
has_authorization normalized to boolean
```

Guardrail meta도 보강됐다.

```text
cookie_values_collected = false
authorization_values_collected = false
raw_body_collected = false
response_body_collected = false
```

---

## 7. Dry-run pipeline comparison

### v1 baseline

v1 PHP sample baseline은 observability run 기준으로 S01~S15 전체 관찰, request_id 기반 security/error 연결, notice-level app/PHP context와 warn/error-level context 분리를 확인했다.

### v2 dry-run

v2 export JSON으로 `obs_php_sample_001_v2_pipeline_dryrun`을 수행했다.

주요 결과:

```text
prepare return_code = 0
stage1 return_code = 0
stage2 return_code = 0
viewer_payload generated = yes
```

prepare counts:

```text
total_exported_rows = 21
selected_source_rows = 21
candidate_rows = 13
filtered_out_rows = 8
supporting_events = 3
probing_sequence_summaries = 1
static_baseline_summaries = 1
sensitive_path_probe_summaries = 1
mixed_baseline_scanner_summaries = 1
ip_behavior_aggregates = 1
```

viewer payload counts:

```text
finding_count = 12
context_count = 5
supporting_event_count = 3
```

`finding_count=12`는 stage2 reporter의 top incident limit 때문에 13개 candidate 중 상위 12건만 viewer finding으로 들어간 결과로 본다.

---

## 8. Candidate count note

v2 dry-run에서 `candidate_rows=13`이 나왔다.

현 단계에서는 이를 v2 필드 때문이라고 보지 않는다. 더 가능성이 높은 원인은 다음이다.

```text
- PHP sample direct Apache/PHP 환경에서 S12 scanner_burst의 404/200 혼합 요청이 candidate로 올라옴
- S11 500 server_error가 candidate로 올라옴
- S08/S09 POST failure 계열이 candidate로 올라올 수 있음
- 4xx/5xx + error_linked reason_hints가 candidate score에 기여함
```

즉, 분리해야 할 항목은 다음이다.

```text
v2 field preservation: pass
candidate selection/scoring delta: separate review needed
```

후속 검토 질문:

```text
- PHP sample direct baseline에서 404/403/500을 candidate로 많이 올리는 것이 적절한가?
- observability test path의 /admin, /.env, /wp-login.php 등을 context-only로 더 강하게 유지해야 하는가?
- error_linked(+2)가 direct PHP sample에서 candidate selection을 과도하게 밀어 올리는가?
- v1/v2 dry-run을 같은 최신 prepare 코드와 같은 threshold로 재실행하면 candidate count가 동일하게 나오는가?
```

---

## 9. Guardrail comparison

| guardrail | v1 | v2 | result |
|---|---|---|---|
| No success inference from status_code=200 | pass | pass | 유지 |
| No exposure inference from response size only | pass | pass | 유지 |
| No login success inference from POST only | pass | pass | 유지 |
| No upload success inference from POST only | pass | pass | 유지 |
| No compromise inference from WAF match only | n/a | n/a | WAF 없음 |
| No attacker IP assertion from X-Forwarded-For only | pass | pass | 유지 |
| No authentication inference from Cookie/Auth presence | n/a | pass | v2 신규 guardrail |

v2의 `has_cookie`와 `has_authorization`는 presence flag일 뿐이다.

```text
has_cookie=true does not imply authenticated session.
has_authorization=true does not imply successful authentication.
```

---

## 10. Decision

현재 판단은 다음과 같다.

```text
v1 baseline: keep as-is
v2 server/run: valid test baseline
v2 LogFormat output: pass
v2 converter support: pass
v2 dry-run connectivity: pass
v2 actual LLM execution: not yet needed
v2 production migration: not started
```

`apache_security_io_v2`는 기본 Apache+PHP 환경에서 실험용 baseline으로 사용할 수 있다.

다만 v2를 기존 v1 baseline에 덮어쓰기하거나 기존 observability comparison을 재수행할 필요는 없다. v2는 새 서버/새 run으로 계속 분리해서 검증한다.

---

## 11. Recommended next steps

1. v2 converter fixture/test를 추가한다.
   - `request_target`
   - `raw_request_target`
   - `req_host`
   - `host` compatibility fallback
   - `client_ip_source`
   - `has_cookie`
   - `has_authorization`
   - `meta.log_schema`
   - `meta.log_schemas`

2. v1/v2 dry-run candidate delta review를 별도 문서로 분리한다.
   - 같은 prepare 코드/threshold 기준으로 v1도 재실행할지 판단
   - candidate_rows=13이 v2 때문인지 최신 prepare scoring 때문인지 분리

3. prepare/viewer에서 v2 display-only fields를 어디까지 노출할지 검토한다.
   - `request_target`
   - `req_host`
   - `client_ip_source`
   - `has_cookie`
   - `has_authorization`

4. remoteip schema는 아직 진행하지 않는다.
   - `apache_security_io_remoteip_v2`는 별도 trusted proxy 테스트 서버에서만 검증한다.

5. actual LLM execution은 보류한다.
   - 먼저 v2 fixture/test와 candidate delta review를 끝낸 뒤 필요 시 actual spot check를 수행한다.
