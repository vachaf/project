# 99 Apache Custom Log Format Contract

- 문서 상태: 운영/설계 계약 초안
- 작성일: 2026-05-14
- 기준 문서:
  - Apache HTTP Server 2.4 `mod_log_config`
  - `docs/design/99_apache_log_collection_expansion_plan.md`
  - `docs/design/99_apache_log_collection_expansion_scope_correction.md`
  - `docs/design/99_apache_app_observability_comparison_plan.md`
- 기준 범위:
  - 웹단에 Apache HTTP Server를 사용하는 애플리케이션 전반
  - 정적 파일 직접 서빙, PHP-FPM/CGI, reverse proxy, WAF 연계 배치 모두 포함
  - reverse proxy는 지원 배치 중 하나이며 필수 전제가 아님
- 비고:
  - 이 문서는 DB 구조를 전제로 하지 않는다.
  - 이 문서는 Apache 요청 1건을 어떤 증거 단위로 남길지 정의하는 log contract다.

---

## 1. 목적

이 문서는 Apache `CustomLog` / `LogFormat`으로 생성할 보안 분석용 요청 로그의 공통 계약을 정의한다.

목표는 앱별로 다른 로그 포맷을 만드는 것이 아니라, Apache를 웹단으로 사용하는 모든 앱에 가능한 한 같은 canonical format을 적용하는 것이다.

이 계약은 이후 다음 구현의 기준이 된다.

1. Apache VirtualHost 설정
2. 로그 수집기 parser
3. MariaDB 또는 파일 기반 적재 구조
4. export/prepare 단계 입력 스키마
5. LLM 분석 입력
6. Web UI related context 표시

---

## 2. 핵심 원칙

### 2.1 앱별 포맷 분기 금지

앱마다 `CustomLog` 필드 구성을 다르게 만들지 않는다.

권장 구조:

```text
공통 Apache request evidence:
  apache_security_core_v1

선택 확장:
  apache_security_io_v1
  optional proxy/remoteip fields
  app_runtime_logs
  modsecurity_audit_logs
```

앱별로 달라질 수 있는 것은 다음이다.

| 항목 | 앱별 차이 허용 | 설명 |
|---|---:|---|
| 로그 파일명 | yes | 앱/vhost별 파일 분리 가능 |
| `ServerName` / `vhost` | yes | Apache 배치에 따라 다름 |
| `DocumentRoot` / `ProxyPass` | yes | 앱 배치에 따라 다름 |
| `mod_remoteip` 적용 여부 | yes | 앞단 프록시 여부에 따라 다름 |
| 앱 런타임 로그 | yes | PHP/Node/Java 등 앱별로 다름 |
| WAF audit log | yes | WAF 적용 여부에 따라 다름 |
| `app_security.log` 필드 구성 | no | 비교 가능성을 위해 공통 유지 |

### 2.2 Apache request evidence와 app evidence 분리

`app_security.log`는 Apache가 관찰한 HTTP request/response metadata를 기록한다.

다음 정보는 `app_security.log`에 섞지 않는다.

- 앱 내부 로그인 성공/실패
- 상품/게시글/계정 생성 성공
- 파일 저장 성공
- DB 변경 결과
- WAF rule match 상세 원문
- request body 원문
- response body 원문

이 값들은 별도 로그 계층으로 둔다.

```text
app_runtime_logs
modsecurity_audit_logs
system_auth_logs
firewall_logs
```

### 2.3 key=value 포맷 유지

기본 포맷은 JSON이 아니라 key=value 형식으로 둔다.

이유:

- Apache `LogFormat`은 JSON serializer가 아니다.
- quote/backslash/특수문자 escaping은 Apache가 처리하지만, JSON 전체의 구조적 escaping을 보장하는 것은 아니다.
- key=value + quoted string 방식이 parser와 운영 디버깅에 더 안정적이다.

권장 표기:

```text
number_field=123
string_field="value"
empty_field=""
missing_field="-"
```

### 2.4 문자열 필드는 quote로 감싼다

공백, slash, quote, user-agent, referer, query string이 섞일 수 있는 필드는 항상 quote로 감싼다.

예:

```text
raw_request="GET /search.php?q=a%20b HTTP/1.1"
user_agent="Mozilla/5.0 ..."
referer="-"
```

### 2.5 log schema를 첫 필드로 둔다

모든 security log line의 첫 필드는 `log_schema`로 둔다.

예:

```text
log_schema=apache_security_core_v1 ...
log_schema=apache_security_io_v1 ...
```

이 값은 parser, export, prepare 단계에서 포맷 버전 식별자로 사용한다.

---

## 3. 포맷 버전 정책

### 3.1 권장 버전

| 포맷 | 목적 | 필수 모듈 |
|---|---|---|
| `apache_security_core_v1` | 모든 Apache 웹단 앱의 최소 공통 request evidence | `mod_log_config`, 권장: `mod_unique_id` |
| `apache_security_io_v1` | core + I/O/TTFB 확장 | `mod_log_config`, `mod_logio`, 권장: `mod_unique_id` |
| `apache_security_lite_v1` | 고트래픽/제한 환경용 future option | TBD |

초기 운영/실험에서는 가능하면 `apache_security_io_v1`을 사용한다. 단, `mod_logio`를 켤 수 없는 환경에서는 `apache_security_core_v1`을 사용한다.

### 3.2 포맷 변경 규칙

기존 필드의 의미를 바꾸지 않는다.

허용:

- optional field 추가
- 새 schema version 추가
- 새 별도 로그 계층 추가

금지:

- 같은 `log_schema` 이름으로 필드 의미 변경
- `status_code`의 token 변경
- `src_ip` / `peer_ip` 의미 혼합
- 앱별로 같은 필드명에 다른 의미 부여

---

## 4. `apache_security_core_v1`

### 4.1 목적

Apache가 웹단에서 관찰한 요청 1건의 최소 공통 증거를 남긴다.

적용 대상:

- 정적 파일 직접 서빙
- PHP 앱
- PHP-FPM/CGI
- reverse proxy 앱
- WAF 연계 앱
- 복합 VirtualHost

### 4.2 Apache 설정 예시

```apache
LogFormat "log_schema=apache_security_core_v1 \
log_time=%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t \
request_id=%{UNIQUE_ID}e error_link_id=%L \
vhost=\"%v\" server_name=\"%V\" server_port=%p local_ip=%A \
src_ip=%a peer_ip=%{c}a \
method=%m raw_request=\"%r\" uri=\"%U\" query_string=\"%q\" protocol=%H \
status_code=%>s original_status_code=%s response_body_bytes=%B \
duration_us=%D keepalive_count=%k connection_status=%X handler=\"%R\" \
req_content_type=\"%{Content-Type}i\" req_content_length=\"%{Content-Length}i\" \
resp_content_type=\"%{Content-Type}o\" location=\"%{Location}o\" \
referer=\"%{Referer}i\" origin=\"%{Origin}i\" user_agent=\"%{User-Agent}i\" \
host=\"%{Host}i\" \
x_forwarded_for=\"%{X-Forwarded-For}i\" x_real_ip=\"%{X-Real-IP}i\" forwarded=\"%{Forwarded}i\"" apache_security_core_v1

CustomLog ${APACHE_LOG_DIR}/app_security.log apache_security_core_v1
```

### 4.3 필드 카탈로그

| field | token | type | evidence meaning | trust | sensitivity |
|---|---|---|---|---|---|
| `log_schema` | literal | string | 포맷 버전 | high | low |
| `log_time` | `%{...}t` | timestamp | 요청 수신 시각 | high | low |
| `request_id` | `%{UNIQUE_ID}e` | string | 요청 상관분석 ID | medium | low |
| `error_link_id` | `%L` | string | error log 연결 ID | medium | low |
| `vhost` | `%v` | string | canonical server name | high | low |
| `server_name` | `%V` | string | UseCanonicalName 기준 server name | high | low |
| `server_port` | `%p` | integer | 요청 처리 서버 포트 | high | low |
| `local_ip` | `%A` | ip | local IP address | high | low |
| `src_ip` | `%a` | ip | Apache가 판단한 client IP | config-dependent | medium |
| `peer_ip` | `%{c}a` | ip | underlying TCP peer IP | high | medium |
| `method` | `%m` | string | HTTP method | high | low |
| `raw_request` | `%r` | string | first request line | high | medium |
| `uri` | `%U` | string | query 제외 request path | high | medium |
| `query_string` | `%q` | string | query string | high | medium~high |
| `protocol` | `%H` | string | HTTP protocol | high | low |
| `status_code` | `%>s` | integer | final response status | high | low |
| `original_status_code` | `%s` | integer | original response status | high | low |
| `response_body_bytes` | `%B` | integer | response body size, headers 제외 | high | low |
| `duration_us` | `%D` | integer | request duration microseconds | high | low |
| `keepalive_count` | `%k` | integer | connection 내 keepalive request count | high | low |
| `connection_status` | `%X` | string | response 완료 후 connection status | high | low |
| `handler` | `%R` | string | response handler | medium | low |
| `req_content_type` | `%{Content-Type}i` | string | request Content-Type header | client-controlled | low |
| `req_content_length` | `%{Content-Length}i` | integer/string | request Content-Length header | client-controlled | low |
| `resp_content_type` | `%{Content-Type}o` | string | response Content-Type header | server-generated | low |
| `location` | `%{Location}o` | string | redirect target | server-generated | medium |
| `referer` | `%{Referer}i` | string | request Referer header | client-controlled | medium |
| `origin` | `%{Origin}i` | string | request Origin header | client-controlled | medium |
| `user_agent` | `%{User-Agent}i` | string | request User-Agent header | client-controlled | medium |
| `host` | `%{Host}i` | string | request Host header | client-controlled | medium |
| `x_forwarded_for` | `%{X-Forwarded-For}i` | string | forwarding header 관찰값 | untrusted unless remoteip policy | medium |
| `x_real_ip` | `%{X-Real-IP}i` | string | forwarding header 관찰값 | untrusted unless proxy policy | medium |
| `forwarded` | `%{Forwarded}i` | string | forwarding header 관찰값 | untrusted unless proxy policy | medium |

---

## 5. `apache_security_io_v1`

### 5.1 목적

`apache_security_core_v1`에 network I/O와 TTFB 관찰값을 추가한다.

추가 필드:

| field | token | meaning |
|---|---|---|
| `in_bytes` | `%I` | request + headers 포함 수신 바이트 |
| `out_bytes` | `%O` | response + headers 포함 송신 바이트 |
| `total_bytes` | `%S` | `%I + %O` |
| `ttfb_us` | `%^FB` | first byte까지의 시간 |

필수/권장 모듈:

```bash
sudo a2enmod logio
```

TTFB 사용 시:

```apache
LogIOTrackTTFB ON
```

### 5.2 Apache 설정 예시

```apache
LogIOTrackTTFB ON

LogFormat "log_schema=apache_security_io_v1 \
log_time=%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t \
request_id=%{UNIQUE_ID}e error_link_id=%L \
vhost=\"%v\" server_name=\"%V\" server_port=%p local_ip=%A \
src_ip=%a peer_ip=%{c}a \
method=%m raw_request=\"%r\" uri=\"%U\" query_string=\"%q\" protocol=%H \
status_code=%>s original_status_code=%s response_body_bytes=%B \
in_bytes=%I out_bytes=%O total_bytes=%S \
duration_us=%D ttfb_us=%^FB keepalive_count=%k connection_status=%X handler=\"%R\" \
req_content_type=\"%{Content-Type}i\" req_content_length=\"%{Content-Length}i\" \
resp_content_type=\"%{Content-Type}o\" location=\"%{Location}o\" \
referer=\"%{Referer}i\" origin=\"%{Origin}i\" user_agent=\"%{User-Agent}i\" \
host=\"%{Host}i\" \
x_forwarded_for=\"%{X-Forwarded-For}i\" x_real_ip=\"%{X-Real-IP}i\" forwarded=\"%{Forwarded}i\"" apache_security_io_v1

CustomLog ${APACHE_LOG_DIR}/app_security.log apache_security_io_v1
```

### 5.3 사용 기준

실험/분석 서버에서는 가능하면 `apache_security_io_v1`을 표준으로 사용한다.

다만 다음 환경에서는 `apache_security_core_v1`로 낮춘다.

- `mod_logio`를 활성화할 수 없는 환경
- TTFB 측정이 필요 없는 고트래픽 서버
- 성능/로그량 제한이 강한 환경

---

## 6. Optional proxy/remoteip fields

### 6.1 원칙

proxy 관련 필드는 모든 앱에 같은 이름으로 포함해도 되지만, 해석은 환경 의존적이다.

| field | 의미 | 기본 해석 |
|---|---|---|
| `x_forwarded_for` | client가 보낸 또는 proxy가 추가한 header | 원본 header 관찰값, 신뢰값 아님 |
| `x_real_ip` | proxy 계열 header | 원본 header 관찰값, 신뢰값 아님 |
| `forwarded` | standard forwarding header | 원본 header 관찰값, 신뢰값 아님 |
| `remoteip_proxy_chain` | `mod_remoteip` note | `mod_remoteip` 적용 환경에서만 의미 있음 |

### 6.2 `mod_remoteip` 적용 시 추가 후보

```apache
remoteip_proxy_chain=\"%{remoteip-proxy-ip-list}n\"
```

포맷에 추가할 경우 새 schema version을 만든다.

예:

```text
apache_security_io_remoteip_v1
```

같은 `apache_security_io_v1` 이름으로 필드 의미나 필드 구성을 바꾸지 않는다.

### 6.3 금지 해석

- `x_forwarded_for`만으로 공격자 IP를 확정하지 않는다.
- `x_real_ip`만으로 실제 client IP를 확정하지 않는다.
- `src_ip`는 `mod_remoteip` 적용 여부에 따라 의미가 달라질 수 있음을 항상 기록한다.
- `peer_ip`는 실제 TCP peer를 나타내므로, proxy/LB 환경에서는 proxy IP일 수 있다.

---

## 7. 제외 필드

기본 `app_security.log`에는 다음을 포함하지 않는다.

| 항목 | 제외 사유 |
|---|---|
| `%{Cookie}i` | session ID, personal data, tracking value 노출 위험 |
| `%{Authorization}i` | credential/token 노출 위험 |
| `%{Set-Cookie}o` | session token 노출 위험 |
| request body | 민감정보/개인정보/credential 노출 위험 |
| response body | 개인정보/비즈니스 데이터/secret 노출 위험 |
| `%f` filename | 서버 내부 filesystem path 노출 가능 |
| 모든 request header 전체 | 노이즈와 민감정보 위험 |
| 모든 response header 전체 | secret/header leakage 위험 |

필요하면 원문 대신 presence flag를 별도 환경변수로 만든다.

예:

```apache
SetEnvIfNoCase Cookie ".+" has_cookie=1
SetEnvIfNoCase Authorization ".+" has_authorization=1
```

이 경우에도 새 schema version 또는 optional field policy를 문서화한 뒤 적용한다.

---

## 8. status code와 internal redirect 기준

### 8.1 primary status

분석의 primary status는 항상 `status_code=%>s`다.

이유:

- 내부 redirect가 있는 경우 `%s`는 original request status일 수 있다.
- `%>s`는 final status를 기록한다.

### 8.2 original status

`original_status_code=%s`는 보조 필드다.

활용 예:

- internal redirect 관찰
- auth/rewrite 흐름 확인
- framework fallback behavior 확인

금지:

- `original_status_code`만으로 최종 client response를 판단하지 않는다.

---

## 9. raw request와 normalized URI 기준

### 9.1 raw request

`raw_request=%r`는 first request line이다.

활용:

- encoded payload 확인
- unusual path 확인
- duplicate slash / malformed target 관찰
- raw method/path/protocol 보존

### 9.2 URI / query string

`uri=%U`는 query 제외 path다.

`query_string=%q`는 query string이 있으면 `?`를 포함하고, 없으면 빈 문자열이다.

활용:

- route 집계
- query parameter 기반 의심 요청 분류
- scenario marker 필터링

### 9.3 금지 해석

- query string에 SQLi-like payload가 있다고 해서 SQL injection 성공을 말하지 않는다.
- path에 traversal-like payload가 있다고 해서 파일 읽기 성공을 말하지 않는다.
- raw request만으로 application route resolution 결과를 단정하지 않는다.

---

## 10. response size / network bytes 기준

### 10.1 response body bytes

`response_body_bytes=%B`는 HTTP response body size이며 headers를 제외한다.

주의:

- 실제 network bytes와 다를 수 있다.
- SSL, aborted connection, header size, transfer behavior와 구분해야 한다.

### 10.2 network bytes

`out_bytes=%O`는 `mod_logio` 기준 network sent bytes다.

`in_bytes=%I`는 request + headers 포함 수신 바이트다.

`total_bytes=%S`는 `%I + %O`다.

### 10.3 금지 해석

- `response_body_bytes`만으로 파일 노출을 판단하지 않는다.
- `out_bytes`만으로 데이터 유출을 판단하지 않는다.
- 큰 응답 크기만으로 공격 성공을 말하지 않는다.

---

## 11. handler 기준

`handler=%R`는 response를 생성한 handler다.

활용:

- static file 처리와 PHP/proxy 처리 구분
- Apache module 처리 확인
- reverse proxy handler 확인

주의:

- caching module 등 일부 처리 경로에서는 handler 정보가 비어 있거나 기대와 다를 수 있다.
- handler는 내부 처리 힌트이지 앱 결과 증거가 아니다.

---

## 12. Conditional logging 정책

초기 v1에서는 conditional logging을 사용하지 않는다.

즉:

```text
모든 요청을 같은 포맷으로 남긴다.
```

이유:

- 비교 실험에서 baseline 요청이 사라지는 것을 방지한다.
- static asset과 dynamic request의 차이를 동일 포맷으로 비교할 수 있다.
- 필터링은 수집 이후 export/prepare 단계에서 수행하는 것이 안전하다.

향후 예외:

- 고트래픽 정적 파일 전용 서버
- 별도 asset log 분리 필요
- 개인정보/규정상 특정 요청 제외 필요

이 경우에도 새 policy 문서와 schema version을 추가한다.

---

## 13. Error log 연계

`app_security.log`의 `error_link_id=%L`과 `request_id=%{UNIQUE_ID}e`는 `app_error.log`와 연결하기 위한 필드다.

권장 `ErrorLogFormat`:

```apache
ErrorLogFormat "[%{uc}t] [error_link_id:%L] [request_id:%{UNIQUE_ID}e] [module_name:%-m] [log_level:%-l] [src_ip:%a peer_ip:%{c}a] message=%M"
ErrorLog ${APACHE_LOG_DIR}/app_error.log
```

연결 우선순위:

1. `request_id`
2. `error_link_id`
3. 시간 근접 + src_ip + raw_request 근접 매칭

주의:

- error log는 서버 처리 오류의 근거이지 공격 성공 근거가 아니다.
- error message 원문은 LLM 입력 전에 요약/마스킹을 검토한다.

---

## 14. Apache module requirements

### 14.1 minimum

```bash
sudo a2enmod unique_id
```

`UNIQUE_ID`가 없는 환경에서는 `request_id`가 비거나 `-`일 수 있다. 이 경우에도 log row를 버리지 않는다.

### 14.2 recommended for IO version

```bash
sudo a2enmod logio
```

### 14.3 optional

```bash
sudo a2enmod remoteip
sudo a2enmod headers
```

- `remoteip`: 앞단 proxy/LB 신뢰 정책이 명확할 때만 적용한다.
- `headers`: backend app으로 `X-Request-ID`를 전달할 때 사용한다.

---

## 15. VirtualHost 적용 예시

### 15.1 PHP/static app

```apache
<VirtualHost *:80>
    ServerName apache-log-test.local
    DocumentRoot /var/www/apache-log-test/public

    ErrorLogFormat "[%{uc}t] [error_link_id:%L] [request_id:%{UNIQUE_ID}e] [module_name:%-m] [log_level:%-l] [src_ip:%a peer_ip:%{c}a] message=%M"
    ErrorLog ${APACHE_LOG_DIR}/apache-log-test_error.log

    CustomLog ${APACHE_LOG_DIR}/apache-log-test_security.log apache_security_io_v1
</VirtualHost>
```

### 15.2 reverse proxy app

```apache
<VirtualHost *:80>
    ServerName juiceshop.local

    ProxyRequests Off
    ProxyPass        / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/

    RequestHeader set X-Request-ID "%{UNIQUE_ID}e"

    ErrorLogFormat "[%{uc}t] [error_link_id:%L] [request_id:%{UNIQUE_ID}e] [module_name:%-m] [log_level:%-l] [src_ip:%a peer_ip:%{c}a] message=%M"
    ErrorLog ${APACHE_LOG_DIR}/juiceshop_error.log

    CustomLog ${APACHE_LOG_DIR}/juiceshop_security.log apache_security_io_v1
</VirtualHost>
```

포맷은 동일하고, 파일명과 배치 설정만 다르다.

---

## 16. 검증 명령

### 16.1 module 확인

```bash
apache2ctl -M | grep -E 'log_config|unique_id|logio|remoteip|headers'
```

### 16.2 설정 검증

```bash
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### 16.3 sample request

```bash
curl -i -H 'User-Agent: log-contract-test/1.0' \
  'http://apache-log-test.local/search.php?q=test&scenario=contract_check'
```

### 16.4 log 확인

```bash
sudo tail -n 5 /var/log/apache2/*security.log
sudo tail -n 5 /var/log/apache2/*error.log
```

체크 포인트:

- `log_schema`가 첫 필드인가
- `request_id`가 존재하는가
- `status_code`가 `%>s` 기준으로 기록되는가
- `raw_request`, `uri`, `query_string`이 모두 기록되는가
- `src_ip`, `peer_ip`가 모두 기록되는가
- `x_forwarded_for`가 비어 있더라도 필드가 유지되는가
- `Cookie`, `Authorization`, `Set-Cookie` 원문이 기록되지 않는가

---

## 17. Sample log line

예시:

```text
log_schema=apache_security_io_v1 log_time=2026-05-14T12:34:56.123+0900 request_id=ZkExampleAAAAAA error_link_id=- vhost="apache-log-test.local" server_name="apache-log-test.local" server_port=80 local_ip=192.168.56.105 src_ip=192.168.56.1 peer_ip=192.168.56.1 method=GET raw_request="GET /search.php?q=test&scenario=contract_check HTTP/1.1" uri="/search.php" query_string="?q=test&scenario=contract_check" protocol=HTTP/1.1 status_code=200 original_status_code=200 response_body_bytes=1234 in_bytes=512 out_bytes=1560 total_bytes=2072 duration_us=2345 ttfb_us=1200 keepalive_count=0 connection_status=- handler="application/x-httpd-php" req_content_type="-" req_content_length="-" resp_content_type="text/html; charset=UTF-8" location="-" referer="-" origin="-" user_agent="log-contract-test/1.0" host="apache-log-test.local" x_forwarded_for="-" x_real_ip="-" forwarded="-"
```

---

## 18. LLM 분석 guardrails

이 log contract로 수집된 값만으로 다음을 단정하지 않는다.

| 금지 판단 | 이유 |
|---|---|
| 로그인 성공 | Apache request metadata만으로 앱 내부 인증 결과를 알 수 없음 |
| 계정 탈취 성공 | 앱/DB audit 없이는 불가 |
| 파일 업로드 성공 | endpoint request와 저장 성공은 다름 |
| 파일 내용 노출 | status/size/content-type만으로 내용 확인 불가 |
| SQL injection 성공 | query string은 payload 관찰일 뿐 DB 결과가 아님 |
| XSS 성공 | browser execution 결과가 없음 |
| SSRF 성공 | backend outbound request 증거가 없음 |
| 서버 침해 성공 | Apache request metadata만으로 불가 |
| WAF 탐지 = 침해 성공 | WAF rule match는 탐지/차단 증거이지 성공 증거가 아님 |

권장 표현:

| 관찰 | 표현 |
|---|---|
| SQLi-like query | `SQLi-like query parameter was observed` |
| XSS-like query | `XSS-like payload was observed in query string` |
| traversal-like path | `path traversal-like request target was observed` |
| upload-like POST | `upload-like POST request was observed` |
| repeated login-like POST | `repeated login-like POST requests were observed` |

---

## 19. 다음 작업

1. 이 문서를 기준으로 Apache sample conf를 정리한다.
2. `scripts/run_observability_scenarios.sh` 결과와 sample log line을 비교한다.
3. parser fixture를 `apache_security_core_v1` / `apache_security_io_v1` 기준으로 추가한다.
4. DB/DDL은 이 contract가 안정화된 뒤 결정한다.
5. prepare 단계에서 `log_schema` 기반 parsing branch를 설계한다.
