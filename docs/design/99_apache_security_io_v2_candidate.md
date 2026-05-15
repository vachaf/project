# 99 Apache Security IO v2 Candidate

- 문서 상태: 설계 후보 / 구현 전 검토 문서
- 작성일: 2026-05-15
- 기준 범위:
  - Apache HTTP Server를 웹단으로 사용하는 애플리케이션의 request evidence log
  - static/PHP/PHP-FPM/CGI/reverse proxy/WAF-fronted 배치 공통
  - 기존 `apache_security_core_v1` / `apache_security_io_v1` 계약은 변경하지 않음
- 관련 문서:
  - `docs/operations/99_apache_custom_log_format_contract.md`
  - `docs/operations/examples/apache_security_logformat_v1.conf`
  - `docs/design/99_apache_app_observability_comparison_plan.md`
  - `docs/design/99_prepare_apache_observability_context_feature_review.md`
  - `docs/진행상황.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`

---

## 1. 목적

이 문서는 `apache_security_io_v2` 후보를 정의한다.

v2의 목적은 더 강한 공격 성공 판정을 만들기 위한 것이 아니다. v1에서 이미 수집 중인 Apache request/response evidence를 파서, prepare, Stage2 reporter, viewer_payload, Web UI가 더 안정적으로 소비할 수 있도록 보완하는 것이다.

핵심 방향은 다음과 같다.

```text
apache_security_io_v2 =
  apache_security_io_v1
  + parser/viewer/LLM 입력 안정성을 높이는 normalized field
  + IP/header trust boundary를 명확히 하는 field
  + 원문 민감정보 대신 privacy-preserving presence flag
  - 앱 내부 성공/실패/DB 결과/브라우저 실행/침해 성공 판단
```

현재 단계에서 v2는 구현 대상이 아니라 fixture/parser 설계 후보로 둔다. 기존 observability 비교 run과 실제 LLM 기준선은 계속 v1을 기준으로 유지한다.

---

## 2. v1 고정 원칙

`apache_security_core_v1`과 `apache_security_io_v1`은 기존 계약으로 고정한다.

금지:

- 같은 `log_schema=apache_security_io_v1` 이름으로 필드 의미를 바꾸지 않는다.
- v1의 필드 순서, 필드명, token 의미를 임의 변경하지 않는다.
- `status_code=%>s`, `original_status_code=%s`, `src_ip=%a`, `peer_ip=%{c}a` 의미를 바꾸지 않는다.
- 앱별로 같은 필드명에 다른 의미를 부여하지 않는다.
- v1 sample log와 기존 parser/export/prepare 회귀를 깨지 않는다.
- v2가 존재한다는 이유만으로 PHP/OpenCart/JuiceShop observability baseline을 재실행하지 않는다.

허용:

- v1 문서에 guardrail, parser note, privacy note를 보강한다.
- 새 필드가 필요하면 `apache_security_io_v2` 또는 별도 optional schema로 추가한다.
- v2 파서는 v1 파서와 병행 지원한다.

---

## 3. v2 설계 원칙

### 3.1 Evidence contract, not verdict schema

v2도 Apache가 관찰한 request/response metadata를 남기는 evidence contract다.

다음과 같은 분석 결과 필드는 넣지 않는다.

```text
attack_detected
is_sqli
is_xss
is_bruteforce
severity
confidence
verdict
confirmed
compromised
exfiltrated
```

이 값들은 Apache LogFormat의 역할이 아니라 prepare/Stage1/Stage2/report/lint 계층의 derived result다.

### 3.2 Apache logs-only evidence boundary 유지

v2 필드만으로 다음을 단정하지 않는다.

| 금지 판단 | 이유 |
|---|---|
| 로그인 성공/실패 | Apache는 app 내부 인증 결과를 모름 |
| 계정 탈취 성공 | app/session/DB/audit evidence 필요 |
| 파일 업로드 저장 성공 | POST request와 저장 성공은 다름 |
| 파일 내용 노출 | status/size/content-type만으로 내용 확인 불가 |
| SQL injection 성공 | query payload는 DB 결과 증거가 아님 |
| XSS 성공 | 브라우저 실행 결과가 없음 |
| SSRF 성공 | backend outbound request 증거가 없음 |
| 서버 침해 성공 | Apache request metadata만으로 불가 |
| 데이터 유출 | response bytes/out bytes만으로 유출 확인 불가 |

### 3.3 Privacy-preserving expansion

v2는 원문 민감정보를 추가 수집하지 않는다.

계속 제외:

- Cookie 원문
- Authorization 원문
- Set-Cookie 원문
- request body 원문
- response body 원문
- 모든 request header 전체
- 모든 response header 전체
- DB query/result
- app runtime secret

대신 필요한 경우 presence flag만 후보로 둔다.

```text
has_cookie
has_authorization
```

---

## 4. v1 대비 v2 후보 변경 요약

| 구분 | field | v1 상태 | v2 후보 | 우선순위 | 비고 |
|---|---|---|---|---:|---|
| 추가 | `request_target` | 없음 | `%U%q` | P0 | path + query normalized convenience target |
| 변경/명확화 | `host` -> `req_host` | `host=%{Host}i` | `req_host=%{Host}i` | P0 | request Host header임을 명확화 |
| 추가 | `client_ip_source` | 없음 | literal | P0 | `direct`, `remoteip_trusted_proxy`, `unknown` |
| 추가 | `has_cookie` | 없음 | `%{has_cookie}e` | P1 | Cookie 값 원문 제외, boolean-like normalization 필요 |
| 추가 | `has_authorization` | 없음 | `%{has_authorization}e` | P1 | Authorization 값 원문 제외, boolean-like normalization 필요 |
| 분리 권장 | `remoteip_proxy_chain` | optional 후보 | `apache_security_io_remoteip_v2` | P1 | 기본 v2에서 제외 권장 |
| 보류 | TLS fields | 없음 | optional schema | P2 | HTTPS/TLS 분석 확장 시 별도 검토 |
| 보류 | backend request/response id | 없음 | optional schema | P2 | backend 협조 필요 |
| 제외 | request/response body | 없음 | 추가 금지 | - | 민감정보/로그량 위험 |
| 제외 | verdict/severity | 없음 | 추가 금지 | - | derived result 계층 |

권장 분리:

```text
apache_security_io_v2:
  apache_security_io_v1
  + request_target
  + req_host
  + client_ip_source
  + has_cookie
  + has_authorization

apache_security_io_remoteip_v2:
  apache_security_io_v2
  + remoteip_proxy_chain
```

---

## 5. 후보 필드 상세

### 5.1 `request_target`

```apache
request_target="%U%q"
```

의미:

- query string을 포함한 normalized convenience request target
- `raw_request`에서 method/protocol을 다시 파싱하지 않고 request target을 사용할 수 있게 한다.

예:

```text
uri="/search"
query_string="?q=1%27+OR+1%3D1"
request_target="/search?q=1%27+OR+1%3D1"
```

활용:

- prepare candidate summary
- Stage2 top_incidents metadata enrichment
- viewer_payload finding display
- Web UI display-only request target 표시
- route grouping과 raw request 표시의 분리

한계:

```text
request_target is a normalized convenience target built from %U%q.
It must not replace raw_request when raw request-target fidelity matters.
For unusual slash/encoding/protocol cases, raw_request remains the source of truth.
```

주의:

- `%U`/`%q` 조합은 `raw_request=%r`의 request-target 원문과 완전히 동일하다고 가정하지 않는다.
- duplicate slash, unusual encoding, malformed request line, protocol anomaly 검토에서는 `raw_request`를 우선 증거로 둔다.

금지 해석:

- `request_target`에 SQLi/XSS/traversal-like payload가 있어도 성공 판정으로 사용하지 않는다.

### 5.2 `req_host`

```apache
req_host="%{Host}i"
```

의미:

- HTTP request `Host` header 원문 관찰값
- v1의 `host`보다 client-controlled header라는 의미가 명확하다.

비교:

| field | 의미 |
|---|---|
| `vhost` | Apache canonical server/vhost context |
| `server_name` | UseCanonicalName 기준 server name |
| `req_host` | client가 보낸 Host header |

주의:

- `req_host`는 client-controlled header다.
- host header injection-like 관찰에는 사용할 수 있지만, 신뢰된 서버 정체성으로 쓰지 않는다.

### 5.3 `client_ip_source`

예:

```apache
client_ip_source="direct"
```

또는:

```apache
client_ip_source="remoteip_trusted_proxy"
```

의미:

- `src_ip`가 어떤 정책으로 해석되어야 하는지 나타내는 literal field
- 자동 산출값이 아니라 Apache config 작성자가 배치 정책에 맞춰 명시한다.

권장 값:

| 값 | 의미 |
|---|---|
| `direct` | Apache가 직접 client TCP peer를 받는 배치 |
| `remoteip_trusted_proxy` | `mod_remoteip` + trusted proxy policy가 적용된 배치 |
| `unknown` | 정책 미확정 또는 migration 중 |

해석 기준:

- `client_ip_source=direct`: `src_ip`와 `peer_ip`가 대체로 같은 의미일 수 있다.
- `client_ip_source=remoteip_trusted_proxy`: `src_ip`는 remoteip 적용 후 effective client IP일 수 있고, `peer_ip`는 실제 TCP peer/proxy일 수 있다.
- `x_forwarded_for`, `x_real_ip`, `forwarded`는 여전히 raw request header이며 기본적으로 untrusted다.

### 5.4 `has_cookie`, `has_authorization`

설정 후보:

```apache
SetEnvIfNoCase Cookie ".+" has_cookie=1
SetEnvIfNoCase Authorization ".+" has_authorization=1
```

LogFormat 후보:

```apache
has_cookie="%{has_cookie}e" has_authorization="%{has_authorization}e"
```

의미:

- Cookie/Authorization 원문을 기록하지 않고 존재 여부만 관찰한다.

Normalization:

| raw value | normalized |
|---|---|
| `"1"` | `true` |
| `"-"` | `false` |
| `""` | `false` |
| missing | `false` |
| other | `true` 또는 parser warning 후보 |

활용:

- authenticated-looking request context
- API token-like request context
- session-bearing request context

금지 해석:

- `has_cookie=true`는 authenticated session을 의미하지 않는다.
- `has_authorization=true`는 successful authentication을 의미하지 않는다.
- 계정 탈취/세션 유효성/권한 상승 판단에 사용하지 않는다.

### 5.5 `remoteip_proxy_chain` 분리 후보

기본 `apache_security_io_v2`에는 넣지 않는 쪽을 권장한다.

분리 후보:

```apache
remoteip_proxy_chain="%{remoteip-proxy-ip-list}n"
```

분리 이유:

```text
- remoteip 미적용 서버에서는 의미 없는 필드가 됨
- mod_remoteip 적용 여부와 신뢰 프록시 정책이 강하게 얽힘
- direct Apache / PHP / reverse proxy baseline과 비교할 때 불필요한 해석 분기가 생김
```

권장 schema:

```text
apache_security_io_remoteip_v2 =
  apache_security_io_v2
  + remoteip_proxy_chain
```

주의:

- remoteip policy가 명시되지 않은 상태에서는 신뢰하지 않는다.
- 이 필드는 client identity 확정 근거가 아니라 topology/trust context다.

---

## 6. `apache_security_io_v2` LogFormat 후보

> 이 블록은 설계 후보이며, production 적용 전 parser fixture와 compatibility test를 먼저 작성한다.

```apache
# Optional presence flags. Do not log Cookie or Authorization values.
SetEnvIfNoCase Cookie ".+" has_cookie=1
SetEnvIfNoCase Authorization ".+" has_authorization=1

<IfModule logio_module>
    LogIOTrackTTFB ON

    LogFormat "log_schema=apache_security_io_v2 \
log_time=%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t \
request_id=%{UNIQUE_ID}e error_link_id=%L \
vhost=\"%v\" server_name=\"%V\" server_port=%p local_ip=%A \
client_ip_source=\"direct\" \
src_ip=%a peer_ip=%{c}a \
method=%m raw_request=\"%r\" request_target=\"%U%q\" uri=\"%U\" query_string=\"%q\" protocol=%H \
status_code=%>s original_status_code=%s response_body_bytes=%B \
in_bytes=%I out_bytes=%O total_bytes=%S \
duration_us=%D ttfb_us=%^FB keepalive_count=%k connection_status=%X handler=\"%R\" \
req_content_type=\"%{Content-Type}i\" req_content_length=\"%{Content-Length}i\" \
resp_content_type=\"%{Content-Type}o\" location=\"%{Location}o\" \
referer=\"%{Referer}i\" origin=\"%{Origin}i\" user_agent=\"%{User-Agent}i\" \
req_host=\"%{Host}i\" \
x_forwarded_for=\"%{X-Forwarded-For}i\" x_real_ip=\"%{X-Real-IP}i\" forwarded=\"%{Forwarded}i\" \
has_cookie=\"%{has_cookie}e\" has_authorization=\"%{has_authorization}e\"" apache_security_io_v2
</IfModule>
```

remoteip trusted proxy 배치에서는 literal을 다음처럼 바꾼다.

```apache
client_ip_source="remoteip_trusted_proxy"
```

remoteip proxy chain까지 기록하려면 기본 v2가 아니라 `apache_security_io_remoteip_v2` 후보를 사용한다.

---

## 7. Optional schema 후보

### 7.1 `apache_security_io_remoteip_v2`

remoteip 관련 출력 안정성이나 운영 정책 차이가 크므로 기본 v2와 분리하는 것을 권장한다.

후보 추가 필드:

```text
remoteip_proxy_chain
```

전제:

- `client_ip_source="remoteip_trusted_proxy"`
- `mod_remoteip` 활성화
- `RemoteIPTrustedProxy` 또는 동등한 trusted proxy policy 명시

LogFormat 추가 후보:

```apache
remoteip_proxy_chain="%{remoteip-proxy-ip-list}n"
```

분리 기준:

- `mod_remoteip` 적용 환경에서만 의미 있는 필드가 많을 때
- proxy/LB 신뢰 정책을 별도 계약으로 문서화해야 할 때
- direct Apache 배치와 remoteip 배치의 parser/validation rule을 분리해야 할 때

### 7.2 `apache_security_tls_v2`

HTTPS/TLS 분석이 필요할 때 별도 schema로 검토한다.

후보 필드:

```apache
tls_protocol="%{SSL_PROTOCOL}x"
tls_cipher="%{SSL_CIPHER}x"
```

보류 이유:

- 현재 Apache logs-only intrusion analysis의 핵심 필드는 아님
- SSL 모듈/termination 위치에 따라 값 의미가 크게 달라짐
- 앞단 LB/CDN에서 TLS가 종료되면 Apache에는 원본 TLS context가 없을 수 있음

### 7.3 backend/app correlation extension

backend app이 `X-Request-ID`를 응답 헤더로 되돌려주거나 app runtime log와 명확히 연결되는 경우 별도 확장으로 검토한다.

보류 이유:

- app별 협조가 필요하다.
- app evidence와 Apache evidence를 섞으면 contract 경계가 흐려질 수 있다.
- 현재 v2의 목적은 Apache request evidence 안정화다.

---

## 8. Parser 요구사항

v2 파서는 단순 whitespace split을 사용하지 않는다.

필수 처리:

- `key=value`
- quoted string
- quoted value 내부 공백
- escaped quote
- escaped backslash
- empty string
- `-` missing marker
- query string의 encoded quote/space
- User-Agent의 공백/세미콜론
- Referer/Location의 특수문자

필수 보존 필드:

```text
log_schema
log_time
request_id
error_link_id
client_ip_source
src_ip
peer_ip
method
raw_request
request_target
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
handler
req_host
x_forwarded_for
x_real_ip
forwarded
has_cookie
has_authorization
```

Boolean-like normalization:

```text
has_cookie:
  "1" -> true
  "-", "", missing -> false

has_authorization:
  "1" -> true
  "-", "", missing -> false
```

v1/v2 호환 원칙:

- v1 row에서 v2 전용 필드가 없어도 row를 버리지 않는다.
- v2 row에서 optional field가 `-` 또는 빈 값이어도 row를 버리지 않는다.
- `request_target`이 없으면 `uri + query_string` 또는 `raw_request` fallback을 사용한다.
- raw request-target fidelity가 필요한 분석에서는 `request_target`보다 `raw_request`를 우선한다.
- `log_schema` 기반 branch를 우선 사용한다.
- unknown schema는 fail-closed가 아니라 review/warn 대상으로 분류한다.

---

## 9. 테스트/fixture 후보

### 9.1 fixture 파일 후보

```text
tests/fixtures/apache_security_io_v2_sample.log
```

포함해야 할 케이스:

1. 정상 GET request
2. query string이 없는 요청
3. query string에 URL-encoded quote/space가 있는 요청
4. raw_request에 공백이 포함되는 정상 요청
5. User-Agent에 공백/괄호/세미콜론이 있는 요청
6. Referer가 `-`인 요청
7. Location header가 있는 redirect 요청
8. X-Forwarded-For가 여러 IP를 포함하는 요청
9. `client_ip_source=direct`
10. `client_ip_source=remoteip_trusted_proxy`
11. `has_cookie="1"`, `has_authorization="1"`
12. `has_cookie="-"`, `has_authorization="-"`
13. traversal-like request target
14. SQLi-like query target
15. XSS-like encoded query target
16. duplicate slash / unusual encoding 케이스에서 `raw_request` 보존 확인

remoteip 확장 fixture는 기본 v2 fixture와 분리한다.

```text
tests/fixtures/apache_security_io_remoteip_v2_sample.log
```

remoteip fixture 후보:

1. `client_ip_source=remoteip_trusted_proxy`
2. `remoteip_proxy_chain`이 `-`인 요청
3. `remoteip_proxy_chain`에 proxy list가 있는 요청
4. `src_ip`와 `peer_ip`가 다른 요청

### 9.2 test 파일 후보

```text
tests/test_apache_security_log_parser_v2.py
```

검증 항목:

- v1 parser regression 유지
- v2 parser 추가
- `request_target` 보존
- `request_target`이 normalized convenience field임을 전제로 fallback 유지
- `req_host` 보존
- `client_ip_source` 보존
- `has_cookie` / `has_authorization` boolean-like normalization
- quoted value with spaces 보존
- `raw_request` 파손 없음
- `query_string`과 `request_target`의 `?` 처리 일관성
- unknown optional field에 대한 fallback-safe 처리

---

## 10. Pipeline 반영 후보

### 10.1 export/prepare

- `log_schema=apache_security_io_v2` branch 추가 후보
- `request_target`이 있으면 일반 표시/요약에는 우선 사용 가능
- raw fidelity가 필요한 분석에서는 `raw_request`를 우선 사용
- v1 row는 기존 `uri + query_string` 또는 raw_request parsing fallback 유지
- `client_ip_source`는 score/severity 변경 없이 context metadata로만 보존
- `has_cookie` / `has_authorization`은 boolean-like derived context로 normalize하되 auth success/failure 판단에 사용하지 않음

### 10.2 Stage1/Stage2

- v2 필드는 wording 완화와 evidence clarity를 위한 metadata로만 사용
- `request_target`은 payload 관찰 표현에 사용 가능
- `client_ip_source`는 IP 해석 신뢰도 문맥으로만 사용
- `remoteip_proxy_chain`은 remoteip optional schema에서만 topology/trust context로 사용
- v2 필드로 공격 성공/침해/유출 표현을 강화하지 않음

### 10.3 viewer_payload / Web UI

표시 후보:

- Request Target: `request_target`
- Host Header: `req_host`
- Client IP Source: `client_ip_source`
- Cookie/Auth Presence: `has_cookie`, `has_authorization` display-only badge
- Proxy Chain: `remoteip_proxy_chain` display-only, 단 remoteip schema에서만

금지:

- display-only field를 severity/category/verdict 변경 근거로 사용
- context-only를 finding/incident로 승격
- Web UI에서 새 관계 추론 또는 판정 생성

---

## 11. Migration 정책

1. v1을 운영/회귀 기준으로 유지한다.
2. v2는 먼저 문서/fixture/parser 후보로만 검토한다.
3. 현재 observability comparison run을 v2로 migrate하지 않는다.
4. v2가 있다는 이유만으로 PHP/OpenCart/JuiceShop baseline을 재실행하지 않는다.
5. v2 parser fixture와 compatibility test가 통과하기 전에는 sample Apache conf를 적용하지 않는다.
6. v2 Apache sample conf는 parser fixture와 parser branch 이후 별도 example 파일로 추가한다.
7. v1/v2 parser 병행 지원 후 dry-run fixture를 만든다.
8. 실제 Apache observability run은 필요 시 별도 run_id로 수행한다.
9. v2 적용 여부와 무관하게 기존 `obs_juiceshop_proxy_001_actual` 기준선은 유지한다.
10. v2 field가 없는 기존 report/viewer_payload는 fallback-safe하게 유지한다.

권장 도입 순서:

```text
1. v2 fixture sample line 작성
2. parser test 작성
3. parser branch 추가
4. convert_observability_logs_to_export_json.py v2 지원 검토
5. sample conf 작성
6. 필요 시 실제 Apache run
```

---

## 12. Non-goals

이 문서의 범위가 아니다.

- FastAPI/DB 기반 신규 탐지 시스템 구현
- Web UI execution console화
- pipeline 실행/DB 제어/report rewrite
- sampling/retention 운영 정책 확정
- WAF audit log schema 통합
- app runtime log schema 통합
- OpenTelemetry trace/span schema 설계
- 공격 성공/침해/유출 verdict 생성
- 자동 차단/IP block 정책
- v1 기준 observability run 재작성

---

## 13. Open questions

1. `client_ip_source` literal 값 목록을 `direct`, `remoteip_trusted_proxy`, `unknown` 세 개로 충분히 둘 것인가?
2. `has_cookie` / `has_authorization` presence flag를 v2 기본에 포함할 것인가, privacy option으로 분리할 것인가?
3. `has_cookie` / `has_authorization`의 unexpected raw value를 true로 볼지 parser warning으로만 둘 것인가?
4. `apache_security_io_remoteip_v2`를 별도 schema로 확정할 것인가?
5. TLS field는 `apache_security_tls_v2`로 분리할 필요가 있는가?
6. Web UI display-only badge는 v2 이후에 검토할지, 기존 v1 topology hint 기반으로 먼저 진행할지?

---

## 14. 현재 권장 결론

현재 기준의 권장안은 다음이다.

```text
v1:
  고정. 현재 기준선 유지.
  현재 observability comparison run과 actual LLM/Web UI PASS 기준은 v1로 유지.

v2 candidate:
  request_target 추가
  host를 req_host로 명확화
  client_ip_source 추가
  has_cookie/has_authorization presence flag 검토
  has_cookie/has_authorization normalization 규칙 추가
  remoteip_proxy_chain은 기본 v2가 아니라 apache_security_io_remoteip_v2로 분리 권장
  verdict/severity/body/cookie/auth 원문은 계속 제외

도입 순서:
  문서 -> parser fixture -> parser test -> parser branch -> converter v2 지원 검토 -> 필요 시 Apache sample conf -> 필요 시 실제 observability run
```

v2의 목적은 더 많은 결론을 내는 것이 아니라, 같은 Apache evidence를 더 안전하고 덜 모호하게 소비하는 것이다. v2는 지금 당장 운영 기준으로 전환하지 않고, parser fixture와 compatibility test가 통과한 뒤에만 후속 구현 대상으로 다룬다.
