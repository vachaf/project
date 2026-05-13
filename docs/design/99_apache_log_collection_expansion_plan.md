# 99 Apache 로그 수집 확장 계획서

- 문서 상태: 설계 초안
- 작성일: 2026-05-14
- 기준 범위:
  - Ubuntu Apache reverse proxy 환경
  - `app_security.log` 중심 수집 구조
  - `src/apache_log_shipper.py` 기반 MariaDB 적재 구조
  - Apache 로그 기반 LLM 침입 로그 분석 파이프라인
- 비고:
  - 이 문서는 설계/계획 문서이며, 코드/DDL/Apache 설정 변경을 직접 수행하지 않는다.
  - 확장 후에도 Web UI와 분석 파이프라인은 입력 로그를 읽기 전용으로 다뤄야 한다.

---

## 1. 목적

현재 프로젝트는 Apache VirtualHost에서 별도 `LogFormat`으로 생성한 `app_security.log`를 중심으로 요청 메타데이터를 수집하고, 이를 MariaDB와 LLM 분석 파이프라인으로 연결한다.

이 문서의 목적은 현재 구조를 유지하면서 다음 로그 계층을 단계적으로 확장하기 위한 기준을 정의하는 것이다.

1. `app_security.log` 필드 보강
2. `app_error.log` 상관분석 강화
3. `src_ip` / `peer_ip` / `X-Forwarded-For` 신뢰 경계 정리
4. 애플리케이션 로그와 request ID 연계
5. ModSecurity audit log 선택 도입
6. OS/서비스 로그를 보조 증거로 연결

핵심 방향은 `app_security.log`를 대체하는 것이 아니라, 이를 canonical request evidence로 유지하고 주변 증거를 별도 계층으로 붙이는 것이다.

---

## 2. 현재 기준 구조

### 2.1 Apache VirtualHost 로그 설정 요약

현재 Apache 설정은 크게 3개 로그를 생성한다.

| 로그 파일 | 역할 |
|---|---|
| `${APACHE_LOG_DIR}/app_access.log` | 일반 access log 호환/대조용 |
| `${APACHE_LOG_DIR}/app_security.log` | 보안 분석용 key=value 요청 메타데이터 |
| `${APACHE_LOG_DIR}/app_error.log` | Apache error log, request/error link 포함 |

현재 `app_security.log`는 다음 주요 필드를 포함한다.

| 필드 축 | 예시 필드 |
|---|---|
| 요청 식별 | `request_id`, `error_link_id` |
| vhost/IP | `vhost`, `src_ip`, `peer_ip`, `x_forwarded_for` |
| 요청 | `method`, `raw_request`, `uri`, `query_string`, `protocol` |
| 응답 | `status_code`, `response_body_bytes`, `resp_content_type` |
| I/O | `in_bytes`, `out_bytes`, `total_bytes` |
| 성능 | `duration_us`, `ttfb_us`, `keepalive_count`, `connection_status` |
| 헤더 | `req_content_type`, `req_content_length`, `referer`, `user_agent`, `host` |

### 2.2 현재 shipper/DB 기준

현재 수집기는 다음 기본 로그 경로를 기준으로 동작한다.

```text
APACHE_ACCESS_LOG=/var/log/apache2/app_access.log
APACHE_SECURITY_LOG=/var/log/apache2/app_security.log
APACHE_ERROR_LOG=/var/log/apache2/app_error.log
```

현재 DB 테이블 축은 다음과 같다.

| 테이블 | 역할 |
|---|---|
| `apache_access_logs` | access log 적재 |
| `apache_security_logs` | security log 적재, 현재 핵심 분석 입력 |
| `apache_error_logs` | error log 적재 |

---

## 3. 설계 원칙

### 3.1 로그 계층 분리

확장 로그는 가능한 한 하나의 테이블에 섞지 않는다.

권장 구조:

```text
apache_security_logs       # canonical request evidence
apache_error_logs          # Apache 처리 오류/경고
apache_access_logs         # 호환/대조용
modsecurity_audit_logs     # 선택: WAF 룰 매칭 증거
app_runtime_logs           # 선택: 앱 내부 이벤트
system_auth_logs           # 선택: SSH/sudo 인증 이벤트
firewall_logs              # 선택: UFW/iptables 계층 이벤트
fail2ban_logs              # 선택: 차단 이력
```

### 3.2 신뢰 경계 유지

Apache access/security log만으로 다음을 단정하지 않는다.

- POST body 내용
- response body 내용
- DB 쿼리 결과
- 브라우저 실행 결과
- 로그인 성공/계정 탈취 성공
- 파일 업로드/삭제 성공
- 서버 침해 성공
- CORS/protocol bypass 성공
- 정적 파일 실제 노출 여부
- `.env`, `phpinfo`, `server-status`, backup 파일의 실제 내용 노출

분석 문구는 항상 관측 가능한 로그 증거에 한정한다.

예시:

| 부적절한 표현 | 권장 표현 |
|---|---|
| SQL injection succeeded | SQLi-like query parameter was observed |
| account takeover succeeded | repeated login-like requests were observed |
| file was exposed | sensitive-path probe received status code X |
| upload succeeded | upload-like endpoint request was observed |

### 3.3 원문 보존과 LLM 입력 분리

DB에는 필요한 경우 `raw_log`를 보존할 수 있으나, LLM 입력에는 민감 필드를 그대로 넘기지 않는다.

특히 다음 값은 요약/마스킹/해시 처리 대상으로 둔다.

- Cookie
- Authorization
- Set-Cookie
- request body
- response body
- session ID
- JWT
- CSRF token
- 개인정보가 포함될 수 있는 앱 로그 필드

---

## 4. 확장 대상별 계획

## 4.1 Phase A — `app_security.log` 유지 및 필드 정리

### 목표

`app_security.log`를 계속 주 분석 로그로 사용하되, 필드 의미와 파서/DB 매핑을 명확히 한다.

### 주요 작업

1. 현재 `security_db_aligned` 포맷을 canonical 포맷으로 문서화한다.
2. `query_string=""`, `query_string="-"`, 누락값 처리 기준을 고정한다.
3. `status_code`, `response_body_bytes`, `out_bytes`의 의미 차이를 문서화한다.
4. `x_forwarded_for`는 원본 헤더이며 신뢰값이 아님을 명시한다.
5. `src_ip`와 `peer_ip`의 해석을 `mod_remoteip` 적용 여부에 따라 구분한다.
6. `request_id`와 `error_link_id`가 비어 있는 경우에도 row를 버리지 않는 기준을 유지한다.

### 권장 신규 문서/테스트

- `docs/operations/xx_apache_security_log_format.md`
- parser fixture:
  - 정상 key=value line
  - quoted value 포함 line
  - empty query string
  - `-` 값
  - 누락된 optional key
  - malformed line fallback

### 완료 기준

- 기존 `app_security.log` 샘플이 모두 파싱된다.
- 누락/빈 값 처리 정책이 테스트로 고정된다.
- LLM 입력 생성 단계에서 각 필드의 신뢰 수준이 문서화된다.

---

## 4.2 Phase B — `app_error.log` 상관분석 강화

### 목표

Apache error log를 단순 적재하는 수준에서 벗어나, `app_security.log` 이벤트와 연결된 보조 컨텍스트로 사용한다.

### 연결 키

우선순위:

1. `request_id`
2. `error_link_id`
3. 시간 근접 + `src_ip` + `raw_request` 근접 매칭

### 분석 활용 예

| security event | related error context |
|---|---|
| `status_code=500` | backend/app/module error message |
| `status_code=502/503/504` | `mod_proxy` connection failure/timeout |
| `status_code=403` | authz/rewrite/filesystem permission 관련 메시지 |
| redirect loop | internal redirect limit message |

### 주의사항

`app_error.log`는 서버 처리 오류의 근거이지 공격 성공 근거가 아니다. 예를 들어 `Permission denied`는 접근 실패/권한 오류를 보여줄 수 있지만, 파일 내용 노출을 증명하지 않는다.

### LLM 입력 예시

```json
{
  "event_type": "apache_request",
  "request": {
    "request_id": "...",
    "src_ip": "192.0.2.10",
    "method": "GET",
    "uri": "/admin",
    "status_code": 403
  },
  "related_errors": [
    {
      "log_level": "error",
      "module_name": "authz_core",
      "message_summary": "authorization denied by server configuration"
    }
  ]
}
```

### 완료 기준

- security row 1건에 0개 이상의 related error rows를 붙일 수 있다.
- 연결 실패 시에도 원본 security event는 유지된다.
- LLM 입력은 error raw message 전체 대신 요약/정규화된 필드를 우선 사용한다.

---

## 4.3 Phase C — IP 신뢰성 및 `mod_remoteip` 정리

### 목표

앞단 프록시 또는 로드밸런서가 있는 환경에서 `src_ip`, `peer_ip`, `X-Forwarded-For`를 안전하게 해석한다.

### 현재 필드 의미

| 필드 | 의미 | 신뢰 수준 |
|---|---|---|
| `src_ip` | Apache가 판단한 client IP | 설정 의존 |
| `peer_ip` | 실제 TCP 연결 peer IP | 높음 |
| `x_forwarded_for` | 요청 헤더 원문 | 낮음, 위조 가능 |

### 권장 Apache 설정 예

```apache
RemoteIPHeader X-Forwarded-For
RemoteIPTrustedProxy 192.168.56.1
```

신뢰 가능한 프록시 대역이 확정되지 않은 상태에서는 `RemoteIPTrustedProxy`를 임의로 넓게 열지 않는다.

### 권장 추가 필드

```apache
remoteip_proxy_chain="%{remoteip-proxy-ip-list}n"
```

### DB 추가 후보 컬럼

```sql
ALTER TABLE apache_security_logs
  ADD COLUMN remoteip_proxy_chain TEXT NULL;
```

### 완료 기준

- `src_ip`가 mod_remoteip 적용 후 값인지 문서화된다.
- `peer_ip`와 `x_forwarded_for`를 분석상 혼동하지 않는다.
- LLM 입력에서 `x_forwarded_for`를 공격자 IP 확정 근거로 사용하지 않는다.

---

## 4.4 Phase D — Apache request ID를 애플리케이션 로그로 전달

### 목표

Apache reverse proxy 뒤의 애플리케이션 로그와 Apache 로그를 같은 request ID로 연결한다.

현재 Apache는 다음 형태의 reverse proxy 구조를 가진다.

```apache
ProxyPass        / http://127.0.0.1:3000/
ProxyPassReverse / http://127.0.0.1:3000/
```

Apache 로그만으로는 앱 내부 결과를 알 수 없다. 따라서 앱 로그에 request ID를 전달해야 한다.

### Apache 설정 후보

```apache
RequestHeader set X-Request-ID "%{UNIQUE_ID}e"
```

필요 모듈:

```bash
sudo a2enmod headers
sudo systemctl reload apache2
```

### 앱 로그 권장 구조

```json
{
  "time": "2026-05-14T12:00:00.123+0900",
  "request_id": "...",
  "route": "/login",
  "app_event": "login_failed",
  "result": "failed",
  "reason": "invalid_password"
}
```

### 앱 로그 설계 원칙

- 비밀번호, 토큰, 세션 쿠키를 남기지 않는다.
- 사용자 식별자는 가능하면 hash 또는 내부 surrogate key를 사용한다.
- LLM 입력에는 앱 로그 원문보다 정규화된 event summary를 사용한다.
- 앱 로그가 있을 때만 로그인 성공/실패 같은 내부 결과를 제한적으로 말한다.

### DB 신규 테이블 후보

```sql
CREATE TABLE IF NOT EXISTS app_runtime_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) NOT NULL,
    request_id VARCHAR(128) DEFAULT NULL,
    app_name VARCHAR(128) DEFAULT NULL,
    route VARCHAR(255) DEFAULT NULL,
    event_type VARCHAR(128) DEFAULT NULL,
    result VARCHAR(64) DEFAULT NULL,
    severity VARCHAR(64) DEFAULT NULL,
    message_summary TEXT,
    raw_log LONGTEXT,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_app_runtime_log_time (log_time),
    KEY idx_app_runtime_request_id (request_id),
    KEY idx_app_runtime_event_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### 완료 기준

- Apache `request_id`가 앱 로그에도 기록된다.
- request_id 기준으로 Apache request와 앱 event를 조인할 수 있다.
- 앱 로그가 없는 환경에서도 기존 Apache-only 분석은 그대로 동작한다.

---

## 4.5 Phase E — ModSecurity audit log 선택 도입

### 목표

WAF 룰 매칭 증거를 Apache request evidence와 별도 계층으로 연결한다.

### 수집 후보

```text
/var/log/apache2/modsec_audit.log
/var/log/modsecurity/audit.log
```

### DB 신규 테이블 후보

```sql
CREATE TABLE IF NOT EXISTS modsecurity_audit_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) DEFAULT NULL,
    transaction_id VARCHAR(128) DEFAULT NULL,
    request_id VARCHAR(128) DEFAULT NULL,
    src_ip VARCHAR(45) DEFAULT NULL,
    method VARCHAR(16) DEFAULT NULL,
    uri TEXT,
    status_code SMALLINT UNSIGNED DEFAULT NULL,
    action VARCHAR(64) DEFAULT NULL,
    anomaly_score DECIMAL(10,2) DEFAULT NULL,
    rule_ids TEXT,
    rule_messages_json LONGTEXT,
    categories_json LONGTEXT,
    raw_log LONGTEXT,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_modsec_log_time (log_time),
    KEY idx_modsec_transaction_id (transaction_id),
    KEY idx_modsec_request_id (request_id),
    KEY idx_modsec_src_ip (src_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### LLM 입력 권장 형태

```json
{
  "waf": {
    "matched": true,
    "blocked": true,
    "rule_ids": ["942100", "930120"],
    "categories": ["sqli", "lfi"],
    "anomaly_score": 8
  }
}
```

### 주의사항

ModSecurity audit log에는 request body, header, cookie, token, response 일부가 포함될 수 있다. 따라서 다음 원칙을 적용한다.

- 원문은 장기 보존하지 않거나 별도 보안 보관 정책을 둔다.
- LLM 입력에는 rule ID, category, action, score 중심 요약만 전달한다.
- request body 원문을 LLM에 그대로 전달하지 않는다.

### 완료 기준

- ModSecurity가 없는 환경에서도 기존 pipeline은 실패하지 않는다.
- ModSecurity 로그가 있으면 optional context로만 붙는다.
- WAF 탐지 결과와 Apache status code를 혼동하지 않는다.

---

## 4.6 Phase F — OS/서비스 로그 보조 증거 확장

### 목표

Apache 요청 분석과 직접 연결되지는 않지만, 운영/보안 정황 확인에 도움이 되는 로그를 별도 증거 계층으로 수집한다.

### 후보 로그

| 로그 | 목적 |
|---|---|
| `journalctl -u apache2` | Apache reload/restart/failure 확인 |
| `/var/log/auth.log` | SSH/sudo 인증 이벤트 |
| `/var/log/ufw.log` | 방화벽 허용/차단 이벤트 |
| `/var/log/fail2ban.log` | IP 차단 이력 |
| PHP-FPM log | PHP backend 오류 |
| Node app log | 앱 내부 오류/비즈니스 이벤트 |

### 원칙

- OS 로그는 request-level evidence가 아니라 environment/context evidence로 분류한다.
- IP와 시간대가 가까워도 동일 공격 행위로 단정하지 않는다.
- LLM 입력에는 `nearby_context` 또는 `environment_context`로 분리한다.

### 완료 기준

- Apache request finding과 OS/service context가 UI/리포트에서 구분된다.
- OS/service context는 finding verdict를 직접 변경하지 않는다.
- read-only invariant를 유지한다.

---

## 5. 권장 Apache 설정 확장안

아래는 즉시 적용안이 아니라 후보안이다. 적용 시 DB 컬럼, parser, fixture, regression test를 함께 수정해야 한다.

```apache
LogFormat "log_time=%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t \
request_id=%{UNIQUE_ID}e error_link_id=%L \
vhost=%v server_name=\"%V\" server_port=%p local_ip=%A \
src_ip=%a peer_ip=%{c}a remoteip_proxy_chain=\"%{remoteip-proxy-ip-list}n\" \
method=%m raw_request=\"%r\" uri=\"%U\" query_string=\"%q\" protocol=%H \
status_code=%>s response_body_bytes=%B \
in_bytes=%I out_bytes=%O total_bytes=%S \
duration_us=%D ttfb_us=%^FB keepalive_count=%k connection_status=%X \
handler=\"%R\" remote_user=\"%u\" \
req_content_type=\"%{Content-Type}i\" req_content_length=\"%{Content-Length}i\" \
resp_content_type=\"%{Content-Type}o\" \
referer=\"%{Referer}i\" user_agent=\"%{User-Agent}i\" \
host=\"%{Host}i\" x_forwarded_for=\"%{X-Forwarded-For}i\"" security_db_aligned_v2

CustomLog ${APACHE_LOG_DIR}/app_security.log security_db_aligned_v2
```

### 추가 후보 필드 의미

| 필드 | 목적 |
|---|---|
| `server_name` | name-based vhost 디버깅 |
| `server_port` | HTTP/HTTPS/프록시 포트 구분 |
| `local_ip` | 다중 NIC 환경 식별 |
| `remoteip_proxy_chain` | mod_remoteip 처리 후 proxy chain 확인 |
| `handler` | 응답을 처리한 Apache handler |
| `remote_user` | HTTP auth 사용 시 인증 사용자 |

### 제외 권장 필드

다음은 기본 수집에서 제외한다.

| 필드 | 제외 사유 |
|---|---|
| `Cookie` 원문 | 세션/토큰 노출 위험 |
| `Authorization` 원문 | credential/token 노출 위험 |
| request body | 민감정보/개인정보 노출 위험 |
| response body | 개인정보/비즈니스 데이터 노출 위험 |
| `Set-Cookie` 원문 | 세션 토큰 노출 위험 |

필요 시 원문 대신 presence flag만 남긴다.

```text
has_cookie=true
has_authorization=true
has_session_cookie=true
```

---

## 6. DB/Parser 변경 기준

### 6.1 변경 원칙

`LogFormat` 필드를 추가할 때는 다음 순서로 변경한다.

1. Apache 설정 후보 문서화
2. 샘플 로그 fixture 추가
3. parser 필드 추가
4. DDL migration 추가
5. shipper insert SQL 수정
6. export CLI 출력 확인
7. prepare 단계 입력 스키마 확인
8. regression test 수행

### 6.2 backward compatibility

새 필드는 optional로 취급한다.

- 기존 로그 line에 새 key가 없어도 parser는 실패하지 않는다.
- DB 신규 컬럼은 nullable로 시작한다.
- export/prepare 단계는 필드 누락을 정상 케이스로 처리한다.
- LLM 입력에는 `null`, `missing`, `not_collected`를 구분할 수 있으면 구분한다.

### 6.3 파서 주의사항

현재 key=value 포맷은 quoted value를 포함한다. 따라서 단순 whitespace split을 사용하지 않는다.

유지해야 할 케이스:

```text
raw_request="GET /search?q=a b HTTP/1.1"
user_agent="Mozilla/5.0 (...)"
referer="-"
query_string="?q=test"
```

---

## 7. LLM 분석 입력 확장 기준

### 7.1 입력 계층

LLM 입력은 다음 계층으로 분리한다.

```json
{
  "request_evidence": {},
  "apache_error_context": [],
  "waf_context": [],
  "app_context": [],
  "system_context": []
}
```

### 7.2 verdict 영향 기준

| 계층 | verdict 영향 |
|---|---|
| `request_evidence` | 기본 후보 판단 근거 |
| `apache_error_context` | 처리 오류/서버 반응 보조 근거 |
| `waf_context` | 탐지/차단 여부 보조 근거 |
| `app_context` | 내부 결과 판단 가능 범위를 제한적으로 확장 |
| `system_context` | 환경/운영 정황 보조, 직접 verdict 변경 금지 |

### 7.3 금지 규칙

- `status_code=200`만으로 공격 성공 판단 금지
- `response_body_bytes` 크기만으로 파일 노출 판단 금지
- `resp_content_type=text/html`만으로 정상 페이지/에러 페이지 판단 금지
- `x_forwarded_for`만으로 공격자 IP 확정 금지
- ModSecurity rule match만으로 실제 침해 성공 판단 금지
- error log의 stack/error message만으로 데이터 유출 판단 금지

---

## 8. Web UI/Report 연계 기준

확장 로그를 Web UI에 노출할 때는 finding과 context를 분리한다.

### 8.1 권장 표시 구조

```text
Finding
  - primary request evidence: app_security.log
  - related apache errors: app_error.log
  - related WAF matches: modsecurity_audit_logs
  - related app events: app_runtime_logs
  - nearby system context: auth/firewall/fail2ban
```

### 8.2 read-only invariant

Web UI는 다음을 수행하지 않는다.

- 로그 원본 수정
- report 재작성
- severity/category/verdict 재계산
- context-only event를 finding으로 승격
- 새로운 공격 성공 판단 생성

확장 로그는 이미 생성된 finding을 설명하는 related context 또는 evidence context로만 사용한다.

---

## 9. 검증 계획

### 9.1 Apache 설정 검증

```bash
sudo apache2ctl configtest
sudo apache2ctl -M | grep -E 'unique_id|logio|headers|remoteip'
sudo systemctl reload apache2
```

### 9.2 로그 생성 검증

```bash
curl -H 'User-Agent: expansion-test' 'http://localhost/test?q=1'
sudo tail -n 5 /var/log/apache2/app_security.log
sudo tail -n 5 /var/log/apache2/app_error.log
```

### 9.3 shipper 검증

```bash
python3 src/apache_log_shipper.py --once --reset-state
```

### 9.4 DB 검증 SQL

```sql
SELECT COUNT(*) FROM apache_security_logs;
SELECT COUNT(*) FROM apache_error_logs;
SELECT log_time, request_id, src_ip, method, uri, status_code
FROM apache_security_logs
ORDER BY id DESC
LIMIT 10;
```

### 9.5 pipeline 검증

```bash
python3 src/export_db_logs_cli.py --today --table security --pretty --out /tmp/security_today.json
python3 src/run_analysis_pipeline.py --export-input /tmp/security_today.json --dry-run
```

### 9.6 regression 기준

- 기존 `app_security.log` 샘플 파싱 유지
- 기존 `app_access.log` / `app_error.log` 적재 유지
- missing optional field 허용
- malformed optional context 때문에 pipeline 실패 금지
- LLM 입력에서 금지 추론 문구가 재발하지 않는지 fixture 확인

---

## 10. 단계별 작업 순서

### 10.1 단기 작업

1. 현재 `app_security.log` 포맷 문서화
2. `app_error.log` 관련 context 연결 설계
3. `src_ip` / `peer_ip` / `x_forwarded_for` 해석 규칙 문서화
4. `mod_unique_id`, `mod_logio` 활성화 점검 절차 정리
5. parser fixture 추가

### 10.2 중기 작업

1. `mod_remoteip` 적용 여부 결정
2. `remoteip_proxy_chain` 필드 추가
3. `app_error.log` related context 생성
4. DB nullable 컬럼 migration
5. export/prepare 단계의 optional field 처리

### 10.3 장기 작업

1. `X-Request-ID` 앱 전달
2. app runtime log 수집기 추가
3. ModSecurity audit log optional collector 추가
4. OS/service context collector 추가
5. Web UI related context 표시 개선

---

## 11. 우선순위 매트릭스

| 항목 | 분석 효과 | 구현 난이도 | 민감정보 위험 | 우선순위 |
|---|---:|---:|---:|---:|
| `app_security.log` 필드 의미 문서화 | 높음 | 낮음 | 낮음 | 1 |
| `app_error.log` 상관분석 | 높음 | 중간 | 낮음 | 2 |
| `mod_remoteip` 정리 | 높음 | 중간 | 낮음 | 3 |
| request ID 앱 전달 | 높음 | 중간 | 중간 | 4 |
| ModSecurity audit log | 중간~높음 | 중간 | 높음 | 5 |
| OS/service logs | 중간 | 중간 | 중간 | 6 |
| request/response body 수집 | 제한적 | 높음 | 매우 높음 | 보류 |

---

## 12. 명시적 비범위

이 계획서의 범위가 아니다.

- 운영 서버에 설정 즉시 반영
- Apache/DB/shipper 코드 수정
- request body/response body 원문 수집 기본화
- WAF 탐지를 공격 성공으로 승격
- 앱 내부 결과가 없는 상태에서 로그인/탈취/업로드 성공 판단
- Web UI에서 새로운 verdict 생성
- context-only item을 finding으로 자동 승격

---

## 13. 권장 다음 작업

1. 이 문서를 기준으로 `app_security.log` 포맷 명세 문서를 별도로 작성한다.
2. `app_error.log` 상관분석 설계를 prepare 단계 또는 context builder 단계 중 어디에 둘지 결정한다.
3. `src/apache_log_shipper.py` parser fixture를 먼저 추가한다.
4. DB migration은 optional nullable 컬럼부터 작게 진행한다.
5. 모든 변경은 기존 flat/run_dir report 및 Web UI read-only invariant와 분리해서 검증한다.
