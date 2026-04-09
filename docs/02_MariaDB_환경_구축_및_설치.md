# 02_MariaDB_환경_구축_및_설치

- 문서 상태: 구축문서
- 버전: v1.3
- 작성일: 2026-04-09
- 기준 코드:
  - `src/apache_log_shipper.py`
  - `src/export_db_logs_cli.py`

## 1. 목적

이 문서는 Ubuntu 22.04 Server에 MariaDB를 설치하고, 현재 로그 파이프라인이 요구하는 `web_logs` 데이터베이스와 계정, 테이블, 인덱스를 재현 가능한 수준으로 구축하는 절차서다.

## 2. 최종 구성

- DB 서버 호스트 예시: `maria`
- DB 서버 IP 예시: `192.168.35.223`
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
  - 웹서버: `192.168.35.113`
  - LLM 서버: `192.168.35.120`
  - OpenCart 서버를 함께 쓰면 추가 웹서버: `192.168.35.193`

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
bind-address = 192.168.35.223
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

CREATE USER IF NOT EXISTS 'log_writer'@'192.168.35.113' IDENTIFIED BY 'change_writer_password';
CREATE USER IF NOT EXISTS 'log_reader'@'192.168.35.120' IDENTIFIED BY 'change_reader_password';

GRANT SELECT, INSERT, UPDATE ON web_logs.* TO 'log_writer'@'192.168.35.113';
GRANT SELECT ON web_logs.* TO 'log_reader'@'192.168.35.120';

FLUSH PRIVILEGES;
```

OpenCart 서버도 적재 대상으로 포함하면 추가:

```sql
CREATE USER IF NOT EXISTS 'log_writer'@'192.168.35.193' IDENTIFIED BY 'change_writer_password';
GRANT SELECT, INSERT, UPDATE ON web_logs.* TO 'log_writer'@'192.168.35.193';
FLUSH PRIVILEGES;
```

현재 코드 기준:

- shipper는 INSERT만 사용하지만 기존 운영 편의를 위해 `UPDATE`까지 부여해도 된다.
- `log_reader`는 `SELECT`만 주는 것이 기준이다.

## 8. full DDL

DB 선택:

```sql
USE web_logs;
```

### 8.1 `apache_access_logs`

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

### 8.2 `apache_security_logs`

```sql
CREATE TABLE IF NOT EXISTS apache_security_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) NOT NULL,
    request_id VARCHAR(128) DEFAULT NULL,
    error_link_id VARCHAR(128) DEFAULT NULL,
    vhost VARCHAR(255) DEFAULT NULL,
    src_ip VARCHAR(45) DEFAULT NULL,
    peer_ip VARCHAR(45) DEFAULT NULL,
    method VARCHAR(16) DEFAULT NULL,
    raw_request TEXT,
    uri TEXT,
    query_string TEXT,
    protocol VARCHAR(16) DEFAULT NULL,
    status_code SMALLINT UNSIGNED DEFAULT NULL,
    response_body_bytes BIGINT UNSIGNED DEFAULT NULL,
    in_bytes BIGINT UNSIGNED DEFAULT NULL,
    out_bytes BIGINT UNSIGNED DEFAULT NULL,
    total_bytes BIGINT UNSIGNED DEFAULT NULL,
    duration_us BIGINT UNSIGNED DEFAULT NULL,
    ttfb_us BIGINT UNSIGNED DEFAULT NULL,
    keepalive_count INT UNSIGNED DEFAULT NULL,
    connection_status VARCHAR(8) DEFAULT NULL,
    req_content_type VARCHAR(255) DEFAULT NULL,
    req_content_length BIGINT UNSIGNED DEFAULT NULL,
    resp_content_type VARCHAR(255) DEFAULT NULL,
    referer TEXT,
    user_agent TEXT,
    host VARCHAR(255) DEFAULT NULL,
    x_forwarded_for TEXT,
    attack_label VARCHAR(64) NOT NULL DEFAULT 'unknown',
    risk_score DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    matched_rule VARCHAR(255) DEFAULT NULL,
    is_suspicious TINYINT(1) NOT NULL DEFAULT 0,
    resp_html_norm_fingerprint VARCHAR(255) DEFAULT NULL,
    resp_html_fingerprint_version VARCHAR(64) DEFAULT NULL,
    resp_html_baseline_name VARCHAR(128) DEFAULT NULL,
    resp_html_baseline_match TINYINT(1) DEFAULT NULL,
    resp_html_baseline_confidence VARCHAR(64) DEFAULT NULL,
    resp_html_features_json LONGTEXT,
    raw_log LONGTEXT,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_security_log_time (log_time),
    KEY idx_security_request_id (request_id),
    KEY idx_security_error_link_id (error_link_id),
    KEY idx_security_src_ip (src_ip),
    KEY idx_security_status_code (status_code),
    KEY idx_security_attack_label (attack_label),
    KEY idx_security_is_suspicious (is_suspicious)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### 8.3 `apache_error_logs`

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

## 9. DDL 적용 검증

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

계정 확인:

```sql
SELECT User, Host FROM mysql.user WHERE User IN ('log_writer', 'log_reader');
SHOW GRANTS FOR 'log_writer'@'192.168.35.113';
SHOW GRANTS FOR 'log_reader'@'192.168.35.120';
```

기대 결과:

- `web_logs` 존재
- 3개 테이블 존재
- 각 인덱스 존재
- `log_writer`, `log_reader` 계정과 권한 확인 가능

## 10. 서버별 접속 검증

### 10.1 DB 서버 자체 검증

```bash
mariadb -u log_reader -p -h 127.0.0.1 -D web_logs -e "SHOW TABLES;"
```

### 10.2 웹서버에서 검증

웹서버에서 shipper 계정으로 접속:

```bash
mariadb -u log_writer -p -h 192.168.35.223 -D web_logs -e "SHOW TABLES;"
```

기대 결과:

- 3개 테이블 이름이 출력되어야 한다.

### 10.3 LLM 서버에서 검증

LLM 서버에서 조회 계정으로 접속:

```bash
mariadb -u log_reader -p -h 192.168.35.223 -D web_logs -e "SHOW TABLES;"
```

또는 Python 패키지 설치 후 export 연결 점검:

```bash
python3 /opt/web_log_analysis/src/export_db_logs_cli.py \
  --host 192.168.35.223 \
  --user log_reader \
  --password 'reader_password' \
  --today \
  --table security \
  --test-connection
```

기대 결과:

- `[OK] DB 연결 성공: ...`

## 11. 운영 체크포인트

- `bind-address` 가 내부망 IP로 설정되었는가
- `log_writer` 와 `log_reader` 계정이 분리되었는가
- 웹서버에서 `log_writer` 접속이 되는가
- LLM 서버에서 `log_reader` 접속이 되는가
- 3개 테이블이 모두 존재하는가
- 인덱스가 생성되었는가

## 12. `resp_html_*` 처리 기준

현재 코드 기준으로 `apache_security_logs` 에 `resp_html_*` 컬럼은 남아 있다. 따라서 DDL에는 포함한다.

하지만 현재 운영 기준은 아래와 같다.

- `resp_html_*` 는 선택 또는 보류 컬럼이다.
- 현재 핵심 분석 기준이 아니다.
- 값 생성 로직이 별도로 없으면 `NULL` 상태가 정상일 수 있다.

현재 실제 분석과 더 직접적으로 연결되는 필드는 아래 축이다.

- `resp_content_type`
- `response_body_bytes`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`

즉, DDL에는 포함하되 구축 핵심 기능처럼 설명하지 않는다.
