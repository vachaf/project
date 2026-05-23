# 02_MariaDB_환경_구축_및_설치

- 문서 상태: 구축문서
- 버전: v1.4
- 작성일: 2026-05-23
- 기준 코드:
  - `src/apache_log_shipper.py`
  - `src/export_db_logs_cli.py`
- 기준 로그 포맷:
  - `docs/operations/examples/apache_security_logformat_v1.conf`
  - `docs/operations/examples/apache_security_logformat_v2.conf`

## 1. 목적

이 문서는 Ubuntu 22.04 Server에 MariaDB를 설치하고, 현재 로그 파이프라인이 요구하는 `web_logs` 데이터베이스와 계정, 테이블, 인덱스를 재현 가능한 수준으로 구축하는 절차서다.

이 문서의 DDL은 새 서버 구축 기준이다. 기존 DB를 점진 변경하는 `ALTER TABLE` 절차가 아니라, 새 환경에서 바로 읽고 적용하기 쉬운 `CREATE TABLE` 기준으로 유지한다.

## 2. 최종 구성

- DB 서버 호스트 예시: `maria`
- DB 서버 IP 예시: `192.168.56.109`
- DB 이름: `web_logs`
- 문자셋: `utf8mb4`
- 테이블:
  - `apache_access_logs`
  - `apache_security_logs`
  - `apache_error_logs`
- 계정:
  - `log_writer`: 웹서버 shipper 전용
  - `log_reader`: LLM 서버 export/조회 전용

## 3. 사전 조건

- Ubuntu 22.04 Server 설치 완료
- DB 서버에 `sudo` 가능한 계정으로 로그인 가능
- 웹서버와 LLM 서버 IP를 알고 있어야 함
- 예시 IP
  - juice 웹서버: `192.168.56.105`
  - opencart 웹서버: `192.168.56.111`
  - LLM 서버: `192.168.56.110`

## 4. 구축 순서

1. 시스템 업데이트
2. MariaDB 설치
3. 서비스 시작
4. `bind-address` 설정
5. `web_logs` 생성
6. 계정 생성
7. 테이블 및 인덱스 생성
8. 접속 검증
9. 웹서버/LLM 서버에서 외부 접속 검증

## 5. MariaDB 설치

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y mariadb-server mariadb-client
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo systemctl status mariadb
mariadb --version
```

필요하면 초기 보안 설정:

```bash
sudo mysql_secure_installation
```

원격 `root` 접속은 열지 않는다.

## 6. bind-address 설정

설정 파일:

```bash
sudo nano /etc/mysql/mariadb.conf.d/50-server.cnf
```

아래처럼 DB 서버 IP로 맞춘다.

```ini
bind-address = 192.168.56.109
```

설정 반영:

```bash
sudo systemctl restart mariadb
sudo systemctl status mariadb
ss -lntp | grep 3306
```

기대 결과:

- `3306` 이 DB 서버 IP에 바인딩되어 보여야 한다.

## 7. DB와 계정 생성 SQL

MariaDB 접속:

```bash
sudo mariadb
```

아래 SQL을 실행한다.

```sql
CREATE DATABASE IF NOT EXISTS web_logs
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

CREATE USER IF NOT EXISTS 'log_writer'@'192.168.56.105' IDENTIFIED BY 'YourPass'; -- JUICE SHOP
CREATE USER IF NOT EXISTS 'log_writer'@'192.168.56.111' IDENTIFIED BY 'YourPass'; -- OPENCART
CREATE USER IF NOT EXISTS 'log_reader'@'192.168.56.110' IDENTIFIED BY 'YourPass'; -- LLM

GRANT SELECT, INSERT, UPDATE ON web_logs.* TO 'log_writer'@'192.168.56.105'; -- JUICE SHOP
GRANT SELECT, INSERT, UPDATE ON web_logs.* TO 'log_writer'@'192.168.56.111'; -- OPENCART
GRANT SELECT ON web_logs.* TO 'log_reader'@'192.168.56.110'; -- LLM

FLUSH PRIVILEGES;
```

현재 코드 기준:

- shipper는 INSERT만 사용하지만 기존 운영 편의를 위해 `UPDATE`까지 부여해도 된다.
- `log_reader`는 `SELECT`만 주는 것이 기준이다.

## 8. DDL 설계 기준

이 문서의 `apache_security_logs` DDL은 Apache security log의 key=value 필드에 대응되는 컬럼만 둔다.

유지 원칙:

- v1/v2/remoteip_v2를 별도 테이블로 나누지 않는다.
- schema 차이는 `log_schema` 값으로만 구분한다.
- v1에만 있는 `host`와 v2에 있는 `req_host`는 둘 다 nullable 컬럼으로 둔다.
- v2에만 있는 `request_target`, `client_ip_source`, `has_cookie`, `has_authorization`, `remoteip_proxy_chain`은 nullable 컬럼으로 둔다.
- 특정 log format에 없는 필드는 `NULL` 상태가 정상이다.
- `raw_log`는 항상 보존한다.
- Apache가 `-` placeholder를 남긴 값은 shipper에서 `NULL`로 정규화한다.

제거한 파생/비로그 컬럼:

- `attack_label`
- `risk_score`
- `matched_rule`
- `is_suspicious`
- `resp_html_norm_fingerprint`
- `resp_html_fingerprint_version`
- `resp_html_baseline_name`
- `resp_html_baseline_match`
- `resp_html_baseline_confidence`
- `resp_html_features_json`

위 값들은 Apache key=value 원본 로그 필드가 아니다. 필요하면 LLM pipeline 산출물 또는 별도 분석 테이블에서 관리한다.

## 9. full DDL

DB 선택:

```sql
USE web_logs;
```

### 9.1 `apache_access_logs`

```sql
CREATE TABLE IF NOT EXISTS apache_access_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) NOT NULL,
    client_ip VARCHAR(45) DEFAULT NULL,
    method VARCHAR(16) DEFAULT NULL,
    raw_request TEXT,
    uri TEXT,
    query_string TEXT,
    protocol VARCHAR(16) DEFAULT NULL,
    status_code SMALLINT UNSIGNED DEFAULT NULL,
    response_body_bytes BIGINT UNSIGNED DEFAULT NULL,
    referer TEXT,
    user_agent TEXT,
    host VARCHAR(255) DEFAULT NULL,
    vhost VARCHAR(255) DEFAULT NULL,
    raw_log LONGTEXT,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_access_log_time (log_time),
    KEY idx_access_client_ip (client_ip),
    KEY idx_access_status_code (status_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### 9.2 `apache_security_logs`

```sql
CREATE TABLE IF NOT EXISTS apache_security_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    -- schema / time / correlation
    log_schema VARCHAR(64) DEFAULT NULL,
    log_time DATETIME(3) NOT NULL,
    request_id VARCHAR(128) DEFAULT NULL,
    error_link_id VARCHAR(128) DEFAULT NULL,

    -- vhost / server identity
    vhost VARCHAR(255) DEFAULT NULL,
    server_name VARCHAR(255) DEFAULT NULL,
    server_port INT UNSIGNED DEFAULT NULL,
    local_ip VARCHAR(45) DEFAULT NULL,

    -- client / peer identity observations
    client_ip_source VARCHAR(64) DEFAULT NULL,
    src_ip VARCHAR(45) DEFAULT NULL,
    peer_ip VARCHAR(45) DEFAULT NULL,
    remoteip_proxy_chain TEXT,

    -- request line / target
    method VARCHAR(16) DEFAULT NULL,
    raw_request TEXT,
    request_target TEXT,
    uri TEXT,
    query_string TEXT,
    protocol VARCHAR(16) DEFAULT NULL,

    -- response / IO metadata
    status_code SMALLINT UNSIGNED DEFAULT NULL,
    original_status_code SMALLINT UNSIGNED DEFAULT NULL,
    response_body_bytes BIGINT UNSIGNED DEFAULT NULL,
    in_bytes BIGINT UNSIGNED DEFAULT NULL,
    out_bytes BIGINT UNSIGNED DEFAULT NULL,
    total_bytes BIGINT UNSIGNED DEFAULT NULL,
    duration_us BIGINT UNSIGNED DEFAULT NULL,
    ttfb_us BIGINT UNSIGNED DEFAULT NULL,
    keepalive_count INT UNSIGNED DEFAULT NULL,
    connection_status VARCHAR(8) DEFAULT NULL,
    handler VARCHAR(255) DEFAULT NULL,

    -- request / response headers as observed metadata
    req_content_type VARCHAR(255) DEFAULT NULL,
    req_content_length BIGINT UNSIGNED DEFAULT NULL,
    resp_content_type VARCHAR(255) DEFAULT NULL,
    location TEXT,
    referer TEXT,
    origin TEXT,
    user_agent TEXT,
    host VARCHAR(255) DEFAULT NULL,
    req_host VARCHAR(255) DEFAULT NULL,
    x_forwarded_for TEXT,
    x_real_ip TEXT,
    forwarded TEXT,

    -- privacy-preserving presence flags only
    has_cookie TINYINT(1) DEFAULT NULL,
    has_authorization TINYINT(1) DEFAULT NULL,

    raw_log LONGTEXT,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    PRIMARY KEY (id),
    KEY idx_security_log_time (log_time),
    KEY idx_security_request_id (request_id),
    KEY idx_security_error_link_id (error_link_id),
    KEY idx_security_src_ip (src_ip),
    KEY idx_security_status_code (status_code),
    KEY idx_security_log_schema (log_schema),
    KEY idx_security_client_ip_source (client_ip_source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### 9.3 `apache_error_logs`

```sql
CREATE TABLE IF NOT EXISTS apache_error_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) NOT NULL,
    error_link_id VARCHAR(128) DEFAULT NULL,
    request_id VARCHAR(128) DEFAULT NULL,
    module_name VARCHAR(128) DEFAULT NULL,
    log_level VARCHAR(64) DEFAULT NULL,
    src_ip VARCHAR(45) DEFAULT NULL,
    peer_ip VARCHAR(45) DEFAULT NULL,
    message LONGTEXT,
    raw_log LONGTEXT,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_error_log_time (log_time),
    KEY idx_error_error_link_id (error_link_id),
    KEY idx_error_request_id (request_id),
    KEY idx_error_log_level (log_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

## 10. DDL 적용 검증

테이블 확인:

```sql
USE web_logs;
SHOW TABLES;
DESCRIBE apache_access_logs;
DESCRIBE apache_security_logs;
DESCRIBE apache_error_logs;
SHOW INDEX FROM apache_access_logs;
SHOW INDEX FROM apache_security_logs;
SHOW INDEX FROM apache_error_logs;
```

v1/v2 호환 필드 확인:

```sql
DESCRIBE apache_security_logs;

SELECT
  COLUMN_NAME,
  DATA_TYPE,
  IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'web_logs'
  AND TABLE_NAME = 'apache_security_logs'
  AND COLUMN_NAME IN (
    'log_schema',
    'request_target',
    'client_ip_source',
    'host',
    'req_host',
    'x_forwarded_for',
    'x_real_ip',
    'forwarded',
    'has_cookie',
    'has_authorization',
    'remoteip_proxy_chain'
  )
ORDER BY ORDINAL_POSITION;
```

계정 확인:

```sql
SELECT User, Host FROM mysql.user WHERE User IN ('log_writer', 'log_reader');
SHOW GRANTS FOR 'log_writer'@'192.168.56.105';
SHOW GRANTS FOR 'log_writer'@'192.168.56.111';
SHOW GRANTS FOR 'log_reader'@'192.168.56.110';
```

기대 결과:

- `web_logs` 존재
- 3개 테이블 존재
- 각 인덱스 존재
- `apache_security_logs`에 v1/v2 key=value 대응 컬럼 존재
- `log_writer`, `log_reader` 계정과 권한 확인 가능

## 11. 서버별 접속 검증

### 11.1 DB 서버 자체 검증

```bash
mariadb -u log_reader -p -h 127.0.0.1 -D web_logs -e "SHOW TABLES;"
```

### 11.2 웹서버에서 검증

웹서버에서 shipper 계정으로 접속:

```bash
mariadb -u log_writer -p -h 192.168.56.109 -D web_logs -e "SHOW TABLES;"
```

기대 결과:

- 3개 테이블 이름이 출력되어야 한다.

### 11.3 LLM 서버에서 검증

LLM 서버에서 조회 계정으로 접속:

```bash
mariadb -u log_reader -p -h 192.168.56.109 -D web_logs -e "SHOW TABLES;"
```

또는 Python 패키지 설치 후 export 연결 점검:

```bash
python3 /opt/web_log_analysis/src/export_db_logs_cli.py \
  --host 192.168.56.109 \
  --user log_reader \
  --password 'YourPass' \
  --today \
  --table security \
  --test-connection
```

기대 결과:

- `[OK] DB 연결 성공: ...`

## 12. 운영 체크포인트

- `bind-address` 가 내부망 IP로 설정되었는가
- `log_writer` 와 `log_reader` 계정이 분리되었는가
- 웹서버에서 `log_writer` 접속이 되는가
- LLM 서버에서 `log_reader` 접속이 되는가
- 3개 테이블이 모두 존재하는가
- 인덱스가 생성되었는가
- `apache_security_logs.log_time` 인덱스가 있어 scheduler window export에 적합한가
- v1/v2/remoteip_v2가 섞여도 `log_schema`로 구분 가능한가
- `raw_log`가 항상 보존되는가

## 13. v1/v2/remoteip_v2 처리 기준

### 13.1 v1/v2 구분

운영 화면이나 발표에서는 v1/v2를 크게 구분하지 않아도 된다. 다만 DB에는 `log_schema`를 보존한다.

이유:

- 어떤 컬럼이 `NULL`인 이유를 설명할 수 있다.
- v1, v2, remoteip_v2가 섞여도 migration/debug가 가능하다.
- scheduler window별로 어떤 schema의 로그가 들어왔는지 확인할 수 있다.

### 13.2 Host header 처리

- v1 security log는 `host` key를 사용한다.
- v2 security log는 `req_host` key를 사용한다.
- DB에는 둘 다 nullable 컬럼으로 둔다.
- downstream에서 통합 표시가 필요하면 `COALESCE(req_host, host)` 방식으로 처리한다.

### 13.3 client IP / forwarding header 처리

- `src_ip`와 `peer_ip`는 Apache가 관찰한 peer/client metadata다.
- `x_forwarded_for`, `x_real_ip`, `forwarded`는 요청 header 관찰값이다.
- `client_ip_source`는 direct 또는 trusted remoteip 정책을 구분하기 위한 literal metadata다.
- `remoteip_proxy_chain`은 remoteip trusted-proxy schema에서만 채워질 수 있다.

이 값들은 attribution proof가 아니다. 특히 trusted proxy 정책 없이 `X-Forwarded-For`를 실제 client IP로 재해석하지 않는다.

### 13.4 Cookie/Auth presence flags

- `has_cookie`와 `has_authorization`는 v2의 privacy-preserving presence flag다.
- Cookie/Authorization 값 자체는 기록하지 않는다.
- 이 값들은 인증 성공, 로그인 성공, 계정 탈취 성공의 근거가 아니다.
- `-`, 빈 값, missing 값은 `NULL` 또는 false-equivalent로 처리한다.

## 14. shipper / export 연동 메모

`apache_log_shipper.py`는 Apache key=value 로그를 파싱하고, `-` placeholder를 `NULL`로 정규화한다.

새 구축 DDL은 v1/v2 key=value 필드 중심으로 정리되어 있으므로, shipper insert mapping도 이 DDL과 일치해야 한다.

확인할 항목:

- `log_schema`
- `server_name`
- `server_port`
- `local_ip`
- `client_ip_source`
- `request_target`
- `original_status_code`
- `handler`
- `location`
- `origin`
- `req_host`
- `x_real_ip`
- `forwarded`
- `has_cookie`
- `has_authorization`
- `remoteip_proxy_chain`

`export_db_logs_cli.py`는 DB에서 `SELECT *`로 조회한다. 따라서 downstream에서 v2 필드를 별도 JSON field로 사용하려면 해당 값이 DB 컬럼으로 저장되어 있어야 한다. `raw_log`는 원문 보존용이며, export 단계에서 자동 재파싱하지 않는다.

## 15. Apache logs-only 해석 경계

DB에 v2 필드가 추가되어도 해석 경계는 바뀌지 않는다.

- `status_code=200`으로 공격 성공/침해 성공을 단정하지 않는다.
- `status_code=403/404/500/503`만으로 취약점/공격 성공/침해를 단정하지 않는다.
- `response_body_bytes`, `resp_content_type`, `text/html`로 파일 노출/정보 유출을 단정하지 않는다.
- POST metadata만으로 로그인 성공/업로드 저장 성공을 단정하지 않는다.
- Cookie/Auth presence flag만으로 인증 성공을 단정하지 않는다.
- `x_forwarded_for`, `x_real_ip`, `forwarded`만으로 attacker identity를 확정하지 않는다.
- raw POST body, response body, DB 결과, browser execution은 Apache security log에 없으므로 추론하지 않는다.
