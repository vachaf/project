# 02_MariaDB_환경_구축_및_설치

- 문서 상태: 통합본(개정)
- 버전: v1.1
- 작성일: 2026-04-08
- 적용 대상: Ubuntu 22.04 Server 기반 MariaDB 로그 저장 서버 구축 및 운영 중 스키마 확장 기준 문서
- 연계 문서:
  - `01_프로젝트_방향과_실험대상.md`
  - `02_Juice_shop_환경_구축_및_설치.md`
  - `02_LLM_환경_구축_및_설치.md`
  - `03_로그_표준과_DB_구조.md`
  - `04_로그_적재_및_운영.md`
  - `05_Export_LLM_분석_전략.md`

---

## 1. 문서 목적

이 문서는 **Ubuntu 22.04 Server 환경에서 MariaDB를 설치하고, Apache 로그를 중앙 저장할 `web_logs` 데이터베이스를 구축·확장하는 절차**를 정리한 설치 문서다.

이번 프로젝트에서 MariaDB 서버의 역할은 단순한 DB 설치가 아니라, **웹서버가 생성한 access / security / error 로그를 안정적으로 적재하고, 이후 export·LLM 분석까지 이어질 수 있는 중앙 저장 계층을 만드는 것**이다.

따라서 이 문서는 다음 항목을 한 번에 다룬다.

- Ubuntu 22.04 Server 준비
- MariaDB 설치
- 서버 바인딩 주소 설정
- `web_logs` 데이터베이스 생성
- 3개 로그 테이블 생성
- 적재용 / 조회용 계정 생성
- 원격 접속 검증
- 운영 중 스키마 확장 절차
- 기본 운영 체크포인트 정리

반면 아래 항목은 이 문서의 직접 범위에서 제외한다.

- Apache VirtualHost 설정 상세
- Python shipper 서비스 등록 상세
- JSON export 및 LLM 분석 상세
- 공격 탐지 규칙 상세
- LLM 프롬프트 상세

즉, 이 문서는 **로그 저장 계층을 실제로 구축하고, 이후 스키마 확장까지 안전하게 적용하는 절차서**다.

---

## 2. 대상 환경

기준 환경은 아래와 같다.

- 운영체제: **Ubuntu 22.04.5 LTS Server**
- DB 서버 호스트명 예시: **`maria`**
- DB 서버 IP 예시: **`192.168.35.223`**
- DBMS: **MariaDB 10.6.x**
- DB 이름: **`web_logs`**
- 문자셋: **`utf8mb4`**
- 저장 대상:
  - `apache_access_logs`
  - `apache_security_logs`
  - `apache_error_logs`

구조는 다음과 같다.

```text
클라이언트 / 공격 도구 / 실험 스크립트
                ↓
          Apache 웹서버 (juice)
                ↓
      app_access.log / app_security.log / app_error.log
                ↓
        apache_log_shipper.py
                ↓
        MariaDB 서버 (maria)
                ↓
             web_logs
```

이 구조를 사용하는 이유는 다음과 같다.

1. Apache가 로그 생성 지점, MariaDB가 중앙 저장소가 되어 **역할이 명확하게 분리**된다.
2. 파일 로그 원본과 DB 저장을 분리하면 **원본 보존과 후처리를 동시에 가져갈 수 있다**.
3. 3개 로그 테이블로 나누면 운영 확인용 / 분석용 / 장애 확인용 데이터를 **역할별로 분리**할 수 있다.
4. 이후 export, 통계, LLM 분석, 보고서 생성으로 확장하기 쉽다.
5. 운영 중 보수적 해석 강화를 위한 추가 메타데이터 컬럼을 안전하게 확장할 수 있다.

---

## 3. 사전 준비 사항

### 3.1 권장 가상머신 사양

- CPU: 2코어 이상
- RAM: 4GB 이상
- 디스크: 30GB 이상
- 네트워크: 웹서버와 LLM 서버에서 접근 가능한 내부 네트워크

### 3.2 설치 이미지

가상머신에 서버를 설치할 목적이라면 다음 이미지를 기준으로 한다.

- `ubuntu-22.04.5-live-server-amd64.iso`

### 3.3 기본 전제

- DB 서버에 관리자 권한 계정으로 로그인할 수 있어야 한다.
- 웹서버 IP와 LLM 서버 IP가 확정되어 있어야 한다.
- 이번 기준 예시는 다음과 같다.
  - 웹서버: `192.168.35.113`
  - DB 서버: `192.168.35.223`
- 원격 `root` 접속은 사용하지 않는다.
- DB 쓰기 계정과 조회 계정을 분리한다.
- 구조 변경 시 **nullable 컬럼 추가 → shipper 갱신 → export/분석 반영** 순서를 지킨다.

---

## 4. 전체 구축 절차

전체 순서는 아래와 같다.

1. Ubuntu 22.04 Server 준비
2. 시스템 업데이트
3. MariaDB 설치 및 기동 확인
4. `bind-address` 설정
5. `web_logs` 데이터베이스 생성
6. 3개 로그 테이블 생성
7. `log_writer` / `log_reader` 계정 생성 및 권한 부여
8. 원격 접속 검증
9. 웹서버 shipper 연동 점검
10. export 도구 조회 점검
11. 운영 체크포인트 확인
12. 필요 시 운영 중 스키마 확장 적용

---

## 5. 단계별 설치 절차

### 5.1 시스템 업데이트 및 기본 유틸리티 설치

먼저 패키지와 기본 유틸리티를 정리한다.

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y curl wget unzip ca-certificates gnupg lsb-release
```

설치 후 기본 정보를 점검한다.

```bash
uname -a
lsb_release -a
ip addr
hostnamectl
```

---

### 5.2 MariaDB 설치

Ubuntu 22.04 기본 저장소 기준으로 MariaDB 서버를 설치한다.

```bash
sudo apt install -y mariadb-server mariadb-client
```

서비스를 활성화하고 시작한다.

```bash
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo systemctl status mariadb
```

버전을 확인한다.

```bash
mariadb --version
```

---

### 5.3 초기 보안 점검

기본 상태를 먼저 확인한다.

```bash
sudo mariadb
```

MariaDB 프롬프트에서 현재 사용자와 버전을 점검할 수 있다.

```sql
SELECT USER(), CURRENT_USER(), VERSION();
EXIT;
```

필요 시 아래 명령으로 초기 보안 설정을 진행한다.

```bash
sudo mysql_secure_installation
```

이번 프로젝트에서는 **원격 root 접속을 열지 않는 것**이 중요하다.

---

### 5.4 MariaDB 바인딩 주소 설정

현재 구성 기준에서 DB 서버는 웹서버와 LLM 서버가 원격 접속해야 하므로, `bind-address`를 DB 서버 IP로 맞춘다.

설정 파일을 연다.

```bash
sudo nano /etc/mysql/mariadb.conf.d/50-server.cnf
```

아래 항목을 확인하거나 수정한다.

```ini
bind-address = 192.168.35.223
```

수정 후 재시작한다.

```bash
sudo systemctl restart mariadb
sudo systemctl status mariadb
```

수신 상태를 확인한다.

```bash
ss -lntp | grep 3306
```

예상 형태는 다음과 같다.

```text
LISTEN 0 80 192.168.35.223:3306 ...
```

---

### 5.5 방화벽 및 네트워크 점검

`ufw`를 사용하는 경우 필요한 호스트만 허용한다.

웹서버와 LLM 서버가 확정되어 있다면 예시는 다음과 같다.

```bash
sudo ufw allow from 192.168.35.113 to any port 3306 proto tcp
sudo ufw allow from 192.168.35.0/24 to any port 3306 proto tcp
sudo ufw status
```

가능하면 **전체 개방보다 특정 IP 허용**을 우선한다.

네트워크 점검은 다음처럼 할 수 있다.

```bash
ping -c 3 192.168.35.113
```

---

### 5.6 데이터베이스 생성

MariaDB에 접속한다.

```bash
sudo mariadb
```

아래 SQL을 실행한다.

```sql
CREATE DATABASE IF NOT EXISTS web_logs
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

SHOW DATABASES LIKE 'web_logs';
```

`web_logs`는 애플리케이션 이름과 무관하게 재사용 가능한 **웹 로그 중앙 저장소**라는 의미로 통일한다.

---

### 5.7 로그 테이블 생성

이번 프로젝트의 최종 표준은 아래 3개 테이블이다.

- `apache_access_logs`
- `apache_security_logs`
- `apache_error_logs`

아래 SQL을 순서대로 실행한다.

```sql
USE web_logs;

CREATE TABLE IF NOT EXISTS apache_access_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) NOT NULL,
    client_ip VARCHAR(45) NULL,
    method VARCHAR(16) NULL,
    raw_request TEXT NULL,
    uri TEXT NULL,
    query_string TEXT NULL,
    protocol VARCHAR(16) NULL,
    status_code INT NULL,
    response_body_bytes BIGINT NULL,
    referer TEXT NULL,
    user_agent TEXT NULL,
    host VARCHAR(255) NULL,
    vhost VARCHAR(255) NULL,
    raw_log LONGTEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_access_log_time (log_time),
    KEY idx_access_client_ip (client_ip),
    KEY idx_access_status_code (status_code),
    KEY idx_access_vhost (vhost),
    KEY idx_access_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS apache_security_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) NOT NULL,
    request_id VARCHAR(128) NULL,
    error_link_id VARCHAR(128) NULL,
    vhost VARCHAR(255) NULL,
    src_ip VARCHAR(45) NULL,
    peer_ip VARCHAR(45) NULL,
    method VARCHAR(16) NULL,
    raw_request TEXT NULL,
    uri TEXT NULL,
    query_string TEXT NULL,
    protocol VARCHAR(16) NULL,
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
    req_content_length VARCHAR(64) NULL,
    resp_content_type VARCHAR(255) NULL,
    referer TEXT NULL,
    user_agent TEXT NULL,
    host VARCHAR(255) NULL,
    x_forwarded_for TEXT NULL,
    attack_label VARCHAR(64) NULL,
    risk_score INT NULL,
    matched_rule VARCHAR(255) NULL,
    is_suspicious TINYINT(1) NULL,
    raw_log LONGTEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_security_log_time (log_time),
    KEY idx_security_request_id (request_id),
    KEY idx_security_error_link_id (error_link_id),
    KEY idx_security_src_ip (src_ip),
    KEY idx_security_status_code (status_code),
    KEY idx_security_uri (uri(255)),
    KEY idx_security_attack_label (attack_label),
    KEY idx_security_is_suspicious (is_suspicious),
    KEY idx_security_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS apache_error_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    log_time DATETIME(3) NULL,
    error_link_id VARCHAR(128) NULL,
    request_id VARCHAR(128) NULL,
    module_name VARCHAR(128) NULL,
    log_level VARCHAR(64) NULL,
    src_ip VARCHAR(45) NULL,
    peer_ip VARCHAR(45) NULL,
    message LONGTEXT NULL,
    raw_log LONGTEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_error_log_time (log_time),
    KEY idx_error_request_id (request_id),
    KEY idx_error_error_link_id (error_link_id),
    KEY idx_error_src_ip (src_ip),
    KEY idx_error_log_level (log_level),
    KEY idx_error_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

이 컬럼 구성은 현재 Apache 로그 포맷 기준과 shipper 적재 컬럼 순서에 맞춘 것이다. 특히 `apache_security_logs`에는 향후 규칙 기반 탐지와 LLM 분석을 위한 `attack_label`, `risk_score`, `matched_rule`, `is_suspicious` 확장 컬럼을 포함한다.

테이블 생성 후 확인한다.

```sql
SHOW TABLES;
DESCRIBE apache_access_logs;
DESCRIBE apache_security_logs;
DESCRIBE apache_error_logs;
```

---

### 5.8 계정 생성 및 권한 부여

이번 기준 계정은 두 가지다.

- `log_writer`: 웹서버 shipper가 사용하는 적재 계정
- `log_reader`: export 및 LLM 분석 서버가 사용하는 조회 계정

MariaDB에서 아래 SQL을 실행한다.

```sql
CREATE USER IF NOT EXISTS 'log_writer'@'192.168.35.113' IDENTIFIED BY '강한비밀번호';
CREATE USER IF NOT EXISTS 'log_reader'@'192.168.35.%' IDENTIFIED BY '강한비밀번호';

GRANT SELECT, INSERT, UPDATE ON web_logs.* TO 'log_writer'@'192.168.35.113';
GRANT SELECT ON web_logs.* TO 'log_reader'@'192.168.35.%';

FLUSH PRIVILEGES;
```

권한을 확인한다.

```sql
SHOW GRANTS FOR 'log_writer'@'192.168.35.113';
SHOW GRANTS FOR 'log_reader'@'192.168.35.%';
```

권장 원칙은 다음과 같다.

- `log_writer`는 **웹서버 한 대에서만 사용**
- `log_reader`는 **조회 전용**
- 원격 `root` 사용 금지
- 비밀번호는 코드에 하드코딩하지 않고 환경변수나 별도 설정 파일로 관리

---

### 5.9 로컬 접속 검증

DB 서버 내부에서 먼저 접속을 확인한다.

```bash
mariadb -u log_reader -p -h 127.0.0.1 -D web_logs -e "SHOW TABLES;"
```

또는 관리자 계정으로 간단히 데이터베이스 상태를 점검한다.

```bash
sudo mariadb -e "SHOW DATABASES;"
sudo mariadb -e "USE web_logs; SHOW TABLES;"
```

---

### 5.10 웹서버에서 원격 접속 검증

웹서버에서 아래처럼 접속을 확인한다.

```bash
mysql -h 192.168.35.223 -u log_writer -p -D web_logs -e "SHOW TABLES;"
```

또는 shipper 테스트 모드를 사용한다.

```bash
python3 /opt/apache_log_shipper.py --test-db
```

이 단계가 성공해야 실제 로그 적재가 가능하다.

---

### 5.11 LLM 서버 또는 export 환경에서 조회 검증

조회 전용 계정으로 export 테스트를 진행한다.

```bash
python3 /opt/log_export/export_db_logs_cli.py \
  --host 192.168.35.223 \
  --user log_reader \
  --password '비밀번호' \
  --today \
  --table all \
  --test-connection
```

또는 간단한 조회 테스트를 수행한다.

```bash
python3 /opt/log_export/export_db_logs_cli.py \
  --host 192.168.35.223 \
  --user log_reader \
  --password '비밀번호' \
  --date 2026-04-02 \
  --table all \
  --pretty \
  --out test_export.json
```

이 export 도구는 **DB 저장 시각은 UTC 기준으로 보고, 사용자 입력과 출력은 KST 기준으로 처리**하는 것을 전제로 한다.

---

## 6. 운영 중 스키마 확장 기준

이 프로젝트는 원본 보존 계층과 분석 계층을 분리하는 구조이므로, 운영 중 신규 컬럼을 추가할 때도 **기존 적재 안정성을 깨지 않도록 nullable 컬럼 추가를 우선**한다.

### 6.1 적용 순서

권장 순서는 아래와 같다.

1. `ALTER TABLE`로 nullable 컬럼 추가
2. `DESCRIBE`, `SHOW INDEX`로 반영 확인
3. shipper가 새 컬럼을 채우도록 수정
4. 최근 샘플 적재로 값 채움 여부 검증
5. export / prepare / stage1 / stage2 반영 확인

즉, **스키마를 먼저 넓히고, 적재기를 나중에 따라오게 한다.**

### 6.2 HTML fallback fingerprint 확장 컬럼

4단계 path traversal 보수 해석 강화를 위해 `apache_security_logs`에는 아래 확장 컬럼을 둘 수 있다.

```sql
ALTER TABLE apache_security_logs
  ADD COLUMN resp_html_norm_fingerprint CHAR(64) NULL COMMENT '정규화 HTML fingerprint (SHA-256 hex)',
  ADD COLUMN resp_html_fingerprint_version VARCHAR(16) NULL COMMENT 'fingerprint 알고리즘 버전',
  ADD COLUMN resp_html_baseline_name VARCHAR(64) NULL COMMENT '비교한 baseline 이름',
  ADD COLUMN resp_html_baseline_match TINYINT(1) NULL COMMENT 'baseline HTML과 fingerprint 일치 여부',
  ADD COLUMN resp_html_baseline_confidence VARCHAR(16) NULL COMMENT 'none/low/medium/high',
  ADD COLUMN resp_html_features_json TEXT NULL COMMENT 'HTML 구조 특징 요약(JSON 문자열)';
```

권장 인덱스는 아래와 같다.

```sql
ALTER TABLE apache_security_logs
  ADD KEY idx_security_resp_html_baseline_match (resp_html_baseline_match),
  ADD KEY idx_security_resp_html_baseline_name (resp_html_baseline_name);
```

이 확장은 다음 목적을 가진다.

- traversal 200 + `text/html` 응답이 실제 파일이 아니라 **기본 HTML fallback**인지 더 강하게 해석
- 응답 본문 전체 대신 **정규화된 구조 fingerprint**만 저장
- 이후 `prepare_llm_input.py`와 LLM 보고서에서 더 보수적인 판단 근거로 사용

중요 원칙:

- 응답 본문 전체는 상시 저장하지 않는다.
- fingerprint match는 **fallback 가능성 강화** 근거일 뿐, 침해 성공 증거가 아니다.
- fingerprint mismatch만으로 실제 파일 노출 성공을 단정하지 않는다.

### 6.3 스키마 확장 검증 명령

```bash
mysqldump -u root -p web_logs apache_security_logs > apache_security_logs_before_schema_change.sql
```

```sql
USE web_logs;
DESCRIBE apache_security_logs;
SHOW INDEX FROM apache_security_logs;
```

```sql
SELECT
  id, log_time, request_id, uri, resp_content_type,
  resp_html_norm_fingerprint,
  resp_html_fingerprint_version,
  resp_html_baseline_name,
  resp_html_baseline_match,
  resp_html_baseline_confidence
FROM apache_security_logs
ORDER BY id DESC
LIMIT 10;
```

처음 컬럼을 추가한 직후에는 새 값이 모두 `NULL`이어도 정상이다. 값이 채워지는 것은 shipper 갱신 후부터다.

---

## 7. 설치 후 핵심 체크포인트

설치가 끝난 뒤 아래 항목을 점검한다.

- MariaDB 서비스가 실행 중인가
- `bind-address`가 `192.168.35.223` 로 설정되었는가
- 3306 포트가 의도한 네트워크에만 열려 있는가
- `web_logs` 데이터베이스가 생성되었는가
- `apache_access_logs`, `apache_security_logs`, `apache_error_logs` 3개 테이블이 생성되었는가
- `log_writer` / `log_reader` 계정이 생성되었는가
- 웹서버에서 `log_writer`로 접속 가능한가
- export 도구에서 `log_reader`로 조회 가능한가
- root 원격 접속을 사용하고 있지 않은가
- 운영 중 확장 컬럼이 필요할 때 nullable 추가 기준을 지키고 있는가

---

## 8. 자주 틀리는 부분

### 8.1 `bind-address` 를 `127.0.0.1` 로 둔 경우

이 경우 DB 서버 내부에서는 접속되지만, 웹서버와 LLM 서버에서는 원격 접속이 되지 않는다.

현재 기준에서는 아래처럼 맞춰야 한다.

```ini
bind-address = 192.168.35.223
```

### 8.2 계정 host 범위를 잘못 주는 경우

예를 들어 `log_writer@localhost` 로만 만들면 웹서버 원격 접속이 실패한다.

현재 기준은 아래와 같다.

- `log_writer@192.168.35.113`
- `log_reader@192.168.35.%`

### 8.3 root 원격 접속으로 진행하는 경우

실습 초기에는 편해 보여도, 운영 분리 원칙과 맞지 않는다.
반드시 적재용 계정과 조회용 계정을 분리한다.

### 8.4 테이블 구조와 shipper 컬럼이 안 맞는 경우

`apache_log_shipper.py` 의 INSERT 대상 컬럼과 실제 테이블 컬럼이 어긋나면 적재가 실패한다.

특히 다음 컬럼 누락 여부를 확인한다.

- access: `raw_log`
- security: `attack_label`, `risk_score`, `matched_rule`, `is_suspicious`, `raw_log`
- error: `message`, `raw_log`

확장 컬럼을 추가하는 경우에는 다음 원칙을 지킨다.

- 먼저 nullable 컬럼으로 추가
- 그다음 shipper 수정
- 마지막으로 export / 분석 파이프라인 반영

### 8.5 `error` 로그가 비어 있다고 문제라고 보는 경우

정상 운영 중에는 `apache_error_logs` 가 비어 있을 수 있다.
이는 장애가 없다는 뜻일 수 있으므로, 자동으로 비정상이라고 판단할 필요는 없다.

### 8.6 fingerprint mismatch 를 성공 증거로 오해하는 경우

HTML fingerprint 확장은 path traversal의 **fallback HTML 가능성 강화용**이다.
`resp_html_baseline_match = 0` 이라고 해서 곧바로 실제 파일 노출 성공으로 해석하면 안 된다.

---

## 9. 겸사겸사 같이 해야 할 일

MariaDB 서버를 구축할 때 아래 항목도 같이 정리해 두는 편이 좋다.

1. **DB 서버 호스트명과 IP 확정**
   - 예: `maria`, `192.168.35.223`

2. **웹서버 / LLM 서버의 접근 IP 확정**
   - 권한과 방화벽 규칙에 바로 반영해야 한다.

3. **DB 계정 비밀번호 관리 방식 확정**
   - 코드 하드코딩 대신 `.env` 또는 별도 설정 파일 사용

4. **백업 정책 최소안 정리**
   - 예: `mysqldump web_logs` 주기, 보관 기간

5. **로그 보관 기간과 정리 정책 정리**
   - DB는 계속 커지므로 삭제/아카이브 기준이 필요하다.

6. **Export 디렉터리와 조회 위치 정리**
   - LLM 서버에서 어디로 export 파일을 저장할지 미리 고정

7. **테스트 데이터 주입 순서 정리**
   - 웹 요청 발생 → DB 적재 확인 → export → 전처리 → stage1 → stage2

8. **민감정보 최소 저장 원칙 확인**
   - Authorization, Cookie 전체값, 요청 본문 원문, 응답 본문 전체는 기본 상시 저장 대상에서 제외

9. **구조 fingerprint baseline 확보**
   - 정상 `/` 또는 대표 fallback HTML의 구조 특징을 baseline 으로 확보

---

## 10. 이 문서 다음 단계

MariaDB 구축이 끝났다면 다음 순서로 진행한다.

1. 웹서버의 Apache 로그 3종이 실제 생성되는지 확인
2. `apache_log_shipper.py` 를 배포하고 `--test-db` 로 연결 점검
3. 실제 요청을 발생시켜 DB 적재 확인
4. `export_db_logs_cli.py` 로 KST 기준 export 수행
5. LLM 서버에서 전처리와 단계별 분석 파이프라인 실행
6. 필요 시 `apache_security_logs` 확장 컬럼과 shipper 동작을 함께 갱신

즉, 이 문서는 **저장 계층을 준비하고 운영 중 스키마 확장까지 안전하게 적용하는 단계**까지를 다룬다.

---

## 11. 요약

이번 DB 서버는 **Ubuntu 22.04 Server + MariaDB 10.6.x** 조합을 기준으로 구축한다.

핵심은 `web_logs` 데이터베이스를 만들고, `apache_access_logs`, `apache_security_logs`, `apache_error_logs` 3개 테이블을 생성한 뒤, 웹서버의 shipper가 `log_writer` 계정으로 적재하고, export 및 LLM 분석 서버가 `log_reader` 계정으로 조회하는 구조를 만드는 것이다.

설치 단계에서 가장 중요한 것은 다음 여섯 가지다.

1. `bind-address` 를 DB 서버 IP에 맞출 것
2. 3개 로그 테이블을 표준 컬럼으로 생성할 것
3. `log_writer` / `log_reader` 계정을 분리할 것
4. 웹서버에서 적재 접속, LLM 서버에서 조회 접속을 각각 검증할 것
5. root 원격 접속 대신 역할 분리 계정 구조를 유지할 것
6. 운영 중 확장 컬럼은 nullable 추가 → shipper 갱신 → downstream 반영 순서로 적용할 것
