# DB 구조 및 Apache 사이트 설정 확정본 설명서

- 문서 상태: 확정본
- 버전: v1.0
- 작성일: 2026-03-26
- 적용 대상: Apache를 리버스 프록시로 사용하는 웹 애플리케이션 로그 수집 환경
- 기준 애플리케이션: Juice Shop 실험 환경을 기준으로 작성하되, 특정 애플리케이션에 종속되지 않도록 일반화함

---

## 1. 문서 목적

이 문서는 팀 내에서 서로 다르게 작성된 로그 수집 문서들을 비교한 뒤, **최종적으로 통일할 DB 구조와 Apache 사이트 설정 기준**을 확정하기 위한 설명 문서다.

이 문서에서 확정하는 대상은 다음 두 가지다.

1. **MariaDB 내 웹 로그 저장 구조**
2. **Apache VirtualHost 기준 로그 생성 포맷**

즉, 본 문서는 “어떤 로그를 어떤 형식으로 남기고, 그 로그를 어떤 DB 구조에 저장할 것인가”를 확정하는 기준 문서다.

---

## 2. 문서 범위

### 2.1 이 문서에서 확정하는 것

- Apache 로그 3종 분리 구조
  - access log
  - security log
  - error log
- DB 이름 및 테이블 구조
- 로그 키 이름과 DB 컬럼명 기준
- 요청 상관분석용 식별자 정책
- Apache 사이트 설정의 표준 형태

### 2.2 이 문서에서 확정하지 않는 것

아래 항목은 별도 구현 문서 또는 운영 문서에서 다룬다.

- Python shipper 구현 상세
- DB 적재 코드 상세
- 실시간 분류기 구현 방식
- 탐지 규칙 상세 정규식
- 대시보드/시각화 구현

즉, 이 문서는 **구조와 포맷의 기준서**이며, 수집기 구현 세부는 별도다.

---

## 3. 최종 결론

최종 방향은 다음과 같이 확정한다.

- **로그 수집의 중심 지점은 Apache로 통일한다.**
- **기본 access 로그는 유지한다.**
- **탐지·분류용 security 로그를 별도로 생성한다.**
- **error 로그는 보조 분석용으로 별도 저장한다.**
- **DB는 단일 테이블이 아니라 3개 테이블 구조로 통일한다.**
- **애플리케이션 이름과 무관하게 DB 이름은 `web_logs`로 통일한다.**

즉, 최종 구조는 다음과 같다.

```text
클라이언트 / 공격도구 / 실험 스크립트
                ↓
             Apache
                ↓
   ┌──────┼──────┐
   ↓            ↓            ↓
access log   security log   error log
   ↓            ↓            ↓
   └────── 수집기 ───┘
                ↓
             MariaDB
                ↓
  apache_access_logs
  apache_security_logs
  apache_error_logs
```

---

## 4. 왜 이 구조로 통일하는가

기존 단일 access 로그 적재 구조는 구현이 단순하고 시연이 쉽다는 장점이 있다. 하지만 후속 분석을 생각하면 다음 정보가 부족하다.

- 요청 식별자
- 에러 로그 연결 키
- 처리 시간
- I/O 바이트
- 후속 탐지 라벨 필드

반면 확장형 구조는 다음 장점이 있다.

- `request_id` 기반 상관분석 가능
- `error_link_id` 기반 error 연계 가능
- `duration_us`, `ttfb_us`, `in_bytes`, `out_bytes` 등 특징량 확보 가능
- 규칙 기반 탐지 및 후속 분류기 구현이 쉬움

따라서 최종 원칙은 다음과 같다.

> **운영용 로그는 단순하게 유지하고, 분석용 로그를 추가하며, DB는 3테이블 구조로 통일한다.**

---

## 5. 요청 식별자 정책

### 5.1 최종 정책

- **주 요청 식별자**: `request_id = %{UNIQUE_ID}e`
- **에러 연계 보조 키**: `error_link_id = %L`

### 5.2 이유

- `UNIQUE_ID`는 모든 요청에 안정적으로 부여되므로 상관분석의 주 키로 적합하다.
- `%L`은 error 로그와 연계할 때 유용하지만, 모든 요청에 항상 존재하지 않을 수 있으므로 보조 키로만 사용해야 한다.

### 5.3 연결 기준

- access ↔ security: `request_id`
- security ↔ error: `request_id`, `error_link_id`
- access ↔ error: 가능하면 `request_id`, 보조적으로 `error_link_id`

---

## 6. DB 구조 확정안

### 6.1 DB 이름

DB 이름은 **`web_logs`** 로 통일한다.

### 6.2 이유

- OpenCart, Juice Shop 등 애플리케이션 이름이 바뀌어도 그대로 재사용 가능하다.
- “웹 로그 중앙 저장소”라는 의미가 명확하다.
- 특정 실험 앱 이름에 종속되지 않는다.

### 6.3 최종 테이블 목록

- `apache_access_logs`
- `apache_security_logs`
- `apache_error_logs`

---

## 7. 테이블별 역할

### 7.1 `apache_access_logs`

운영 확인과 기본 통계용 테이블이다.

주요 목적:
- 서비스 동작 확인
- 요청 발생 여부 확인
- 상태코드/URI/IP 기준 기본 조회
- 발표 초반 기본 시연

### 7.2 `apache_security_logs`

탐지·분류용 핵심 테이블이다.

주요 목적:
- SQL Injection, XSS 등 의심 요청 특징량 저장
- 요청 단위 상관분석
- 후속 공격 라벨링
- 위험도 점수 저장

### 7.3 `apache_error_logs`

에러·장애·경고 분석용 보조 테이블이다.

주요 목적:
- 프록시 문제 추적
- 서버 오류와 요청 연계
- access/security 로그와의 상관분석

---

## 8. 최종 CREATE TABLE 기준

### 8.1 `apache_access_logs`

```sql
CREATE TABLE apache_access_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_time DATETIME(3) NULL,
    client_ip VARCHAR(45) NULL,
    method VARCHAR(16) NULL,
    raw_request TEXT NULL,
    uri TEXT NULL,
    query_string TEXT NULL,
    protocol VARCHAR(20) NULL,
    status_code INT NULL,
    response_body_bytes BIGINT NULL,
    referer TEXT NULL,
    user_agent TEXT NULL,
    host VARCHAR(255) NULL,
    vhost VARCHAR(255) NULL,
    raw_log LONGTEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_access_time (log_time),
    INDEX idx_access_ip (client_ip),
    INDEX idx_access_status (status_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 8.2 `apache_security_logs`

```sql
CREATE TABLE apache_security_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_time DATETIME(3) NULL,
    request_id VARCHAR(64) NULL,
    error_link_id VARCHAR(64) NULL,
    vhost VARCHAR(255) NULL,
    src_ip VARCHAR(45) NULL,
    peer_ip VARCHAR(45) NULL,
    method VARCHAR(16) NULL,
    raw_request TEXT NULL,
    uri TEXT NULL,
    query_string TEXT NULL,
    protocol VARCHAR(20) NULL,
    status_code INT NULL,
    response_body_bytes BIGINT NULL,
    in_bytes BIGINT NULL,
    out_bytes BIGINT NULL,
    total_bytes BIGINT NULL,
    duration_us BIGINT NULL,
    ttfb_us BIGINT NULL,
    keepalive_count INT NULL,
    connection_status VARCHAR(8) NULL,
    req_content_type VARCHAR(255) NULL,
    req_content_length BIGINT NULL,
    resp_content_type VARCHAR(255) NULL,
    referer TEXT NULL,
    user_agent TEXT NULL,
    host VARCHAR(255) NULL,
    x_forwarded_for TEXT NULL,
    attack_label VARCHAR(64) NOT NULL DEFAULT 'unknown',
    risk_score DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    matched_rule VARCHAR(255) NULL,
    is_suspicious BOOLEAN NOT NULL DEFAULT FALSE,
    raw_log LONGTEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sec_time (log_time),
    INDEX idx_sec_reqid (request_id),
    INDEX idx_sec_errid (error_link_id),
    INDEX idx_sec_src_ip (src_ip),
    INDEX idx_sec_status (status_code),
    INDEX idx_sec_attack_label (attack_label),
    INDEX idx_sec_suspicious (is_suspicious)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 8.3 `apache_error_logs`

```sql
CREATE TABLE apache_error_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_time DATETIME(3) NULL,
    error_link_id VARCHAR(64) NULL,
    request_id VARCHAR(64) NULL,
    module_name VARCHAR(64) NULL,
    log_level VARCHAR(32) NULL,
    src_ip VARCHAR(45) NULL,
    peer_ip VARCHAR(45) NULL,
    message TEXT NULL,
    raw_log LONGTEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_err_time (log_time),
    INDEX idx_err_errid (error_link_id),
    INDEX idx_err_reqid (request_id),
    INDEX idx_err_level (log_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 9. Apache 적용 전제 조건

아래 모듈 또는 기능이 준비되어 있어야 한다.

### 9.1 필수/권장 모듈

- `mod_proxy`
- `mod_proxy_http`
- `mod_unique_id`
- `mod_logio`

### 9.2 이유

- `ProxyPass`, `ProxyPassReverse` 사용을 위해 `mod_proxy`, `mod_proxy_http`가 필요하다.
- `request_id=%{UNIQUE_ID}e` 사용을 위해 `mod_unique_id`가 필요하다.
- `%I`, `%O`, `%S`, `%^FB`, `LogIOTrackTTFB ON` 사용을 위해 `mod_logio`가 필요하다.

### 9.3 선택 사항

프록시나 로드밸런서가 Apache 앞단에 있는 경우에는 아래 설정을 추가할 수 있다.

```apache
# RemoteIPHeader X-Forwarded-For
# RemoteIPTrustedProxy 127.0.0.1
```

---

## 10. 최종 Apache 사이트 설정 확정안

아래 설정 블록을 표준안으로 사용한다.
sudo nano /etc/apache2/sites-available/juice-shop.conf

```apache
<VirtualHost *:80>
    ServerAdmin admin@example.com
    ServerName localhost

    ProxyRequests Off
    ProxyPass        / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/

    # 프록시/LB가 앞단에 있는 경우에만 사용
    # RemoteIPHeader X-Forwarded-For
    # RemoteIPTrustedProxy 127.0.0.1

    # -----------------------------
    # 1) error 로그: apache_error_logs 기준
    # -----------------------------
    ErrorLogFormat "[%{uc}t] [error_link_id:%L] [request_id:%{UNIQUE_ID}e] [module_name:%-m] [log_level:%-l] [src_ip:%a peer_ip:%{c}a] message=%M"
    ErrorLog ${APACHE_LOG_DIR}/app_error.log

    # -----------------------------
    # 2) access 로그: apache_access_logs 기준
    # 사람이 읽기 쉬운 형태 유지 + host/vhost 보강
    # -----------------------------
    LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" \"%{Host}i\" %v" access_db_aligned
    CustomLog ${APACHE_LOG_DIR}/app_access.log access_db_aligned

    # -----------------------------
    # 3) security 로그: apache_security_logs 기준
    # DB 컬럼명과 최대한 동일한 key 사용
    # -----------------------------
    LogIOTrackTTFB ON

    LogFormat "log_time=%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t \
request_id=%{UNIQUE_ID}e error_link_id=%L \
vhost=%v src_ip=%a peer_ip=%{c}a \
method=%m raw_request=\"%r\" uri=\"%U\" query_string=\"%q\" protocol=%H \
status_code=%>s response_body_bytes=%B \
in_bytes=%I out_bytes=%O total_bytes=%S \
duration_us=%D ttfb_us=%^FB keepalive_count=%k connection_status=%X \
req_content_type=\"%{Content-Type}i\" req_content_length=\"%{Content-Length}i\" \
resp_content_type=\"%{Content-Type}o\" \
referer=\"%{Referer}i\" user_agent=\"%{User-Agent}i\" \
host=\"%{Host}i\" x_forwarded_for=\"%{X-Forwarded-For}i\"" security_db_aligned

    CustomLog ${APACHE_LOG_DIR}/app_security.log security_db_aligned
</VirtualHost>
```

---

## 11. 로그 파일별 저장 목적

### 11.1 `app_access.log`

사람이 익숙한 표준형 access 로그다.

용도:
- 동작 확인
- 기본 통계
- 발표 초반 시연
- 간단한 SQL 조회

### 11.2 `app_security.log`

머신 파싱과 분석을 위한 확장 로그다.

용도:
- 의심 요청 특징량 확보
- 규칙 기반 탐지
- 후속 분류기 학습/평가용 데이터 축적
- 요청 단위 상관분석

### 11.3 `app_error.log`

에러와 경고의 원인 분석용 로그다.

용도:
- 프록시 문제 추적
- 서버 오류 분석
- 요청과 에러의 연결 확인

---

## 12. 로그 키 ↔ DB 컬럼 매핑표

### 12.1 security 로그 매핑표

| Apache security 로그 키 | DB 컬럼명 | 설명 |
|---|---|---|
| `log_time` | `log_time` | 로그 시각 |
| `request_id` | `request_id` | 주 요청 식별자 |
| `error_link_id` | `error_link_id` | error 로그 연계용 보조 키 |
| `vhost` | `vhost` | 가상 호스트 |
| `src_ip` | `src_ip` | 클라이언트 IP |
| `peer_ip` | `peer_ip` | 직접 연결 peer IP |
| `method` | `method` | HTTP 메서드 |
| `raw_request` | `raw_request` | 원본 요청 라인 |
| `uri` | `uri` | 경로 |
| `query_string` | `query_string` | 쿼리 문자열 |
| `protocol` | `protocol` | HTTP 프로토콜 |
| `status_code` | `status_code` | 응답 상태 코드 |
| `response_body_bytes` | `response_body_bytes` | 응답 본문 바이트 |
| `in_bytes` | `in_bytes` | 입력 바이트 |
| `out_bytes` | `out_bytes` | 출력 바이트 |
| `total_bytes` | `total_bytes` | 총 I/O 바이트 |
| `duration_us` | `duration_us` | 처리 시간(us) |
| `ttfb_us` | `ttfb_us` | TTFB(us) |
| `keepalive_count` | `keepalive_count` | keep-alive 요청 수 |
| `connection_status` | `connection_status` | 연결 상태 |
| `req_content_type` | `req_content_type` | 요청 Content-Type |
| `req_content_length` | `req_content_length` | 요청 Content-Length |
| `resp_content_type` | `resp_content_type` | 응답 Content-Type |
| `referer` | `referer` | Referer |
| `user_agent` | `user_agent` | User-Agent |
| `host` | `host` | Host 헤더 |
| `x_forwarded_for` | `x_forwarded_for` | X-Forwarded-For |

### 12.2 access 로그 매핑 기준

access 로그는 사람이 읽기 쉬운 표준형을 유지하므로 security 로그처럼 직접적인 key=value는 아니다. 다만 아래 항목을 기준으로 파싱하여 `apache_access_logs`에 저장한다.

| Access 로그 요소 | DB 컬럼명 |
|---|---|
| `%h` | `client_ip` |
| `%r` | `raw_request` |
| `%>s` | `status_code` |
| `%b` | `response_body_bytes` |
| `%{Referer}i` | `referer` |
| `%{User-Agent}i` | `user_agent` |
| `%{Host}i` | `host` |
| `%v` | `vhost` |
| `%t` | `log_time` |

이때 `method`, `uri`, `query_string`, `protocol`은 `%r` 파싱 결과로 분리 저장한다.

### 12.3 error 로그 매핑표

| Error 로그 요소 | DB 컬럼명 |
|---|---|
| `error_link_id:%L` | `error_link_id` |
| `request_id:%{UNIQUE_ID}e` | `request_id` |
| `module_name:%-m` | `module_name` |
| `log_level:%-l` | `log_level` |
| `src_ip:%a` | `src_ip` |
| `peer_ip:%{c}a` | `peer_ip` |
| `message=%M` | `message` |
| 시간 표현 | `log_time` |

---

## 13. 저장하지 않는 항목과 이유

보안 및 개인정보 최소화 원칙에 따라, 기본 상시 저장에서는 아래 항목을 제외하는 것을 권장한다.

- Authorization 헤더
- 전체 Cookie 값
- 요청 본문 원문
- 응답 본문 원문

이유는 다음과 같다.

- 민감정보가 포함될 수 있다.
- 개인정보 또는 인증정보 노출 위험이 있다.
- 분석 목적상 필수 정보가 아닌 경우가 많다.

---

## 14. 발표 및 구현 관점에서의 사용 방법

### 14.1 발표 시연 흐름

1. access 로그 생성
2. DB 적재 확인
3. 상태코드·URI·IP 기준 조회 시연
4. security 로그에서 `request_id`, `duration_us`, `in_bytes` 등 확장 필드 제시
5. error 로그 발생 시 `request_id` 또는 `error_link_id` 연계 제시

### 14.2 구현 착수 기준

구현은 아래 순서로 진행하는 것이 적절하다.

1. Apache 사이트 설정 적용
2. 로그 파일 생성 확인
3. DB 3테이블 생성
4. 수집기에서 access/security/error 각각 적재
5. 후속 탐지 로직 추가

---

## 15. 최종 의사결정 문구

팀 기준 최종 확정 문구는 아래와 같다.

> **로그 수집 포맷은 Apache 기본 access 로그 + key=value security 로그 + custom error 로그의 3종 구조로 통일한다.**
>
> **DB 구조는 `web_logs` 데이터베이스 아래 `apache_access_logs`, `apache_security_logs`, `apache_error_logs` 3개 테이블로 통일한다.**
>
> **초기 시연과 기본 통계는 access 로그를 기준으로 하고, 공격 탐지·분류 실험은 security 로그를 기준으로 수행한다.**
>
> **요청 상관분석의 주 키는 `request_id(UNIQUE_ID)`로 하고, 에러 연계용 보조 키는 `error_link_id(%L)`로 한다.**

---

## 16. 부록: 팀원 문서와 비교했을 때 바뀐 핵심

- 단일 access 테이블 구조에서 3테이블 구조로 확장
- 앱 종속적 DB 이름 대신 `web_logs` 채택
- `request_uri` 단일 필드 대신 `uri` + `query_string` 분리
- `response_size` 대신 `response_body_bytes`로 명확화
- `request_id`, `error_link_id` 기반 상관분석 구조 반영
- access 로그는 운영용, security 로그는 분석용으로 역할 분리

이 문서를 기준으로 DB 구조와 Apache 사이트 설정 파일은 확정된 것으로 본다.
