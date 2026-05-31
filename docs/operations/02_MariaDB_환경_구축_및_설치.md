# 02_MariaDB_환경_구축_및_설치

- 문서 상태: 구축문서
- 버전: v1.5
- 작성일: 2026-05-23
- 최근 갱신: 2026-05-31
- 기준 코드:
  - `src/apache_log_shipper.py`
  - `src/export_db_logs_cli.py`
  - `src/prepare_llm_input.py`
- 기준 로그 포맷:
  - `docs/operations/examples/apache_security_logformat_v1.conf`
  - `docs/operations/examples/apache_security_logformat_v2.conf`
- 관련 SQL:
  - `docs/operations/sql/00_database_and_log_accounts.sql`
  - `docs/operations/sql/01_apache_log_tables.sql`
  - `docs/operations/sql/01_analysis_job_tables.sql`
  - `docs/operations/sql/10_log_source_table_grants.sql`
  - `docs/operations/sql/11_analysis_app_grants.sql`
  - `docs/operations/sql/90_verify_mariadb_setup.sql`

## 1. 목적

이 문서는 Ubuntu 22.04 Server에 MariaDB를 설치하고, 현재 로그 파이프라인이 요구하는 `web_logs` 데이터베이스, 계정, 테이블, 인덱스를 재현 가능한 수준으로 구축하는 절차서다.

실행 가능한 SQL 원문은 이 문서 본문에 직접 두지 않고 `docs/operations/sql/` 아래에 둔다. 이 문서는 적용 순서, 권한 경계, 검증 방법, source log table 해석 기준을 설명한다.

## 2. 최종 구성

- DB 서버 호스트 예시: `maria`
- DB 서버 IP 예시: `192.168.56.109`
- DB 이름: `web_logs`
- 문자셋: `utf8mb4`
- source log table:
  - `apache_access_logs`
  - `apache_security_logs`
  - `apache_error_logs`
- DB-backed MVP operation/control table:
  - `users`
  - `analysis_jobs`
  - `analysis_reports`
  - `job_events`
- 계정:
  - `log_writer`: 웹서버 shipper 전용 source log 적재 계정
  - `log_reader`: LLM/Analysis 서버 export 조회 전용 source log 읽기 계정
  - `analysis_app`: Web UI backend / Analysis Agent의 job lifecycle metadata 기록 계정

## 3. 사전 조건

- Ubuntu 22.04 Server 설치 완료
- DB 서버에 `sudo` 가능한 계정으로 로그인 가능
- 웹서버와 LLM/Analysis 서버 IP를 알고 있어야 함
- 예시 IP
  - juice 웹서버: `192.168.56.105`
  - opencart 웹서버: `192.168.56.111`
  - LLM/Analysis 서버: `192.168.56.110`

주의:

- SQL 파일의 IP와 password 예시는 실제 환경에 맞게 수정해야 한다.
- SQL 파일에 들어 있는 password 값은 재현용 임시값 또는 placeholder다. 그대로 운영/공유 환경에 적용하지 않는다.
- SQL 적용 전에 `docs/operations/sql/00_database_and_log_accounts.sql`, `docs/operations/sql/10_log_source_table_grants.sql`, `docs/operations/sql/11_analysis_app_grants.sql`의 계정 host/IP와 password를 먼저 점검하고 교체한다.
- SQL 적용 후에는 `config/.env`와 웹서버 shipper env에 같은 실제 DB 접속 정보를 반영한다.
- 실제 password를 문서, git commit, issue, PR, 공유 로그에 남기지 않는다.
- `log_reader`는 원본 로그 조회 전용이다.
- DB-backed MVP의 `analysis_jobs`, `analysis_reports`, `job_events` 쓰기는 `analysis_app` 같은 별도 계정을 사용한다.

## 4. 구축 순서

1. 시스템 업데이트
2. MariaDB 설치
3. 서비스 시작
4. `bind-address` 설정
5. SQL 예시 IP/password 교체
6. DB와 계정 생성 SQL 적용
7. source log table DDL 적용
8. DB-backed MVP operation/control table DDL 적용
9. source log table grant 적용
10. analysis app grant 적용
11. 접속 및 schema 검증
12. 웹서버/LLM 서버에서 외부 접속 검증

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

## 7. SQL 적용 순서

repo root 기준으로 실행한다.
```bash
cd ~
git clone https://github.com/vachaf/project
cd ~/project
```

### 7.0 SQL 예시값 교체

`docs/operations/sql/` 아래 SQL은 재현 가능한 초기 구축을 위해 예시 IP와 임시 password를 포함할 수 있다.

실제 DB에 적용하기 전에 아래 항목을 먼저 교체한다.

- 웹서버/LLM 서버 host 또는 IP
- `log_writer` password
- `log_reader` password
- `analysis_app` password
- 필요 시 계정 host 범위

점검 예시:

```bash
grep -RniE "password|change_me|YOUR|192\.168\.56" docs/operations/sql
```

주의:

- 예시 password를 그대로 운영 DB에 적용하지 않는다.
- 실제 password를 SQL 파일에 넣은 상태로 commit하지 않는다.
- SQL 적용 후 실제 접속 값은 `config/.env`와 웹서버 shipper env에도 동일하게 반영한다.

### 7.1 DB와 기본 계정 생성

```bash
sudo mariadb < docs/operations/sql/00_database_and_log_accounts.sql
```

포함 내용:

- `web_logs` database
- `log_writer` 예시 계정
- `log_reader` 예시 계정

이 파일은 계정을 만들지만 source log table별 grant는 적용하지 않는다. table 생성 이후 `10_log_source_table_grants.sql`에서 최소 권한으로 부여한다.

### 7.2 source Apache log table 생성

```bash
sudo mariadb < docs/operations/sql/01_apache_log_tables.sql
```

생성 table:

- `apache_access_logs`
- `apache_security_logs`
- `apache_error_logs`

### 7.3 DB-backed MVP operation/control table 생성

```bash
sudo mariadb < docs/operations/sql/01_analysis_job_tables.sql
```

생성 table:

- `users`
- `analysis_jobs`
- `analysis_reports`
- `job_events`

자세한 적용 기준은 `docs/operations/07_DB_backed_analysis_job_tables.md`를 따른다.

### 7.4 source log table grant 적용

```bash
sudo mariadb < docs/operations/sql/10_log_source_table_grants.sql
```

권한 기준:

- `log_writer`: `apache_access_logs`, `apache_security_logs`, `apache_error_logs`에만 `SELECT`, `INSERT`, `UPDATE`
- `log_reader`: `apache_access_logs`, `apache_security_logs`, `apache_error_logs`에만 `SELECT`

기존처럼 `web_logs.*` 전체에 `log_writer` 쓰기 권한을 주면 DB-backed MVP operation/control table까지 쓰기 범위에 들어갈 수 있으므로 피한다.

### 7.5 analysis app grant 적용

```bash
sudo mariadb < docs/operations/sql/11_analysis_app_grants.sql
```

권한 기준:

- `analysis_app`: `analysis_jobs`, `analysis_reports`에 `SELECT`, `INSERT`, `UPDATE`
- `analysis_app`: `job_events`에 `SELECT`, `INSERT`
- `analysis_app`: `users`에 `SELECT`
- `analysis_app`: source Apache log table에는 쓰기 권한 없음

## 8. 권한 분리 기준

### 8.1 `log_writer`

`log_writer`는 웹서버의 `src/apache_log_shipper.py`가 Apache 로그를 MariaDB source log table에 적재하기 위한 계정이다.

허용 범위:

- `apache_access_logs`
- `apache_security_logs`
- `apache_error_logs`

MVP 기준에서는 기존 운영 편의를 위해 `SELECT`, `INSERT`, `UPDATE`를 허용할 수 있다. 다만 operation/control table에는 권한을 주지 않는다.

### 8.2 `log_reader`

`log_reader`는 LLM/Analysis 서버가 `src/export_db_logs_cli.py`로 원본 로그를 export하기 위한 읽기 전용 계정이다.

허용 범위:

- source Apache log table `SELECT`

금지/비권장 범위:

- `analysis_jobs` insert/update
- `analysis_reports` insert/update
- `job_events` insert
- source log table write

따라서 분석서버 위에 DB-backed MVP 대시보드를 두더라도 `log_reader` 하나로 운영하지 않는다.

### 8.3 `analysis_app`

`analysis_app`는 Web UI backend와 Analysis Agent가 job lifecycle metadata를 기록하기 위한 계정이다.

허용 범위:

- job 생성
- job claim/update
- report/artifact path metadata 기록
- job event append
- Web UI job/report 조회

금지/비권장 범위:

- source Apache log table write
- provider secret 저장
- `.env` 내용 저장
- raw request body/response body 저장

## 9. DDL 설계 기준

`apache_security_logs` DDL은 Apache security log의 key=value 필드에 대응되는 컬럼만 둔다.

유지 원칙:

- v1/v2/remoteip_v2를 별도 테이블로 나누지 않는다.
- schema 차이는 `log_schema` 값으로만 구분한다.
- security log의 client-supplied Host header는 DB에서 `req_host` 컬럼 하나로 통일한다.
- legacy v1 로그가 `host` key를 남기더라도 shipper가 `req_host`로 fallback 매핑한다.
- `apache_access_logs.host`는 access log 전용 컬럼이므로 그대로 둔다.
- v2에만 있는 `request_target`, `client_ip_source`, `has_cookie`, `has_authorization`, `remoteip_proxy_chain`은 nullable 컬럼으로 둔다.
- 특정 log format에 없는 필드는 `NULL` 상태가 정상이다.
- `raw_log`는 항상 보존한다.
- Apache가 `-` placeholder를 남긴 값은 shipper에서 `NULL`로 정규화한다.
- `export_db_logs_cli.py`는 DB에서 `SELECT *`로 조회하고, export 단계에서 `raw_log`를 자동 재파싱하지 않는다.

DDL에 두지 않는 prepare 산출 필드:

- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`

위 3개는 DB 원본 컬럼이 아니다. `prepare_llm_input.py` 단계에서 `raw_request`, `uri`, `resp_content_type`, `response_body_bytes`, `raw_log` 등을 바탕으로 보강·정규화되어 downstream 분석에 사용된다. 따라서 MariaDB DDL에는 추가하지 않는다.

주의:

- `request_target`은 v2 security log format에서 DB에 저장될 수 있는 원본 관찰 컬럼이다.
- `raw_request_target`은 prepare 단계에서 `raw_request`의 request line에서 추출하는 산출 필드다.
- 두 이름은 비슷하지만 저장 위치와 생성 단계가 다르다.

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

## 10. 적용 검증

전체 검증 SQL:

```bash
sudo mariadb < docs/operations/sql/90_verify_mariadb_setup.sql
```

주요 기대 결과:

- `web_logs` 존재
- source log table 3개 존재
- DB-backed MVP operation/control table 4개 존재
- 각 인덱스 존재
- `apache_security_logs`에 v1/v2 key=value 대응 컬럼 존재
- `apache_security_logs`에는 `req_host`가 있고 `host`는 없음
- `raw_request_target`, `path_normalized_from_raw_request`, `likely_html_fallback_response`는 DB 컬럼으로 없음
- `log_writer`, `log_reader`, `analysis_app` 계정과 권한 확인 가능

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

- source log table 이름이 출력되어야 한다.

### 11.3 LLM/Analysis 서버에서 source log export 연결 검증

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

### 11.4 LLM/Analysis 서버에서 DB-backed MVP 계정 검증

```bash
mariadb -u analysis_app -p -h 192.168.56.109 -D web_logs -e "SHOW TABLES LIKE 'analysis_%';"
```

쓰기 권한은 operation/control table에만 있어야 한다.

## 12. 운영 체크포인트

- `bind-address` 가 내부망 IP로 설정되었는가
- SQL 예시 IP/password를 실제 환경 값으로 교체했는가
- 예시 password를 그대로 적용하지 않았는가
- 실제 password가 git commit, 문서, issue, PR, 공유 로그에 남지 않았는가
- `log_writer`, `log_reader`, `analysis_app` 계정이 분리되었는가
- 웹서버에서 `log_writer` 접속이 되는가
- LLM/Analysis 서버에서 `log_reader` 접속이 되는가
- LLM/Analysis 서버에서 `analysis_app` 접속이 되는가
- source log table 3개가 모두 존재하는가
- DB-backed MVP operation/control table 4개가 모두 존재하는가
- 인덱스가 생성되었는가
- `apache_security_logs.log_time` 인덱스가 scheduler window export에 적합한가
- v1/v2/remoteip_v2가 섞여도 `log_schema`로 구분 가능한가
- security log Host header가 `req_host`로 통일되어 저장되는가
- `raw_log`가 항상 보존되는가
- prepare 산출 필드를 DB 원본 컬럼으로 오해하지 않았는가
- `log_reader`를 job/artifact metadata write 계정으로 사용하지 않는가

## 13. v1/v2/remoteip_v2 처리 기준

### 13.1 v1/v2 구분

운영 화면이나 발표에서는 v1/v2를 크게 구분하지 않아도 된다. 다만 DB에는 `log_schema`를 보존한다.

이유:

- 어떤 컬럼이 `NULL`인 이유를 설명할 수 있다.
- v1, v2, remoteip_v2가 섞여도 migration/debug가 가능하다.
- scheduler window별로 어떤 schema의 로그가 들어왔는지 확인할 수 있다.

### 13.2 Host header 처리

- v1 security log는 legacy key로 `host`를 사용한다.
- v2 security log는 `req_host` key를 사용한다.
- 신규 `apache_security_logs` DDL은 DB 컬럼을 `req_host`로 통일한다.
- shipper는 `req_host`를 우선 사용하고, 없으면 legacy v1 `host` key를 `req_host`로 fallback 매핑한다.
- `apache_access_logs.host`는 access log 전용 컬럼이므로 유지한다.

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

## 14. shipper / export / prepare 연동 메모

`apache_log_shipper.py`는 Apache key=value 로그를 파싱하고, `-` placeholder를 `NULL`로 정규화한다.

새 구축 DDL은 v1/v2 key=value 필드 중심으로 정리되어 있으므로, shipper insert mapping도 이 DDL과 일치해야 한다.

확인할 DB 저장 항목:

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
- `req_host` (`req_host` 우선, legacy `host` fallback)
- `x_real_ip`
- `forwarded`
- `has_cookie`
- `has_authorization`
- `remoteip_proxy_chain`

`export_db_logs_cli.py`는 DB에서 `SELECT *`로 조회한다. 따라서 downstream에서 v2 원본 관찰 필드를 별도 JSON field로 사용하려면 해당 값이 DB 컬럼으로 저장되어 있어야 한다. `raw_log`는 원문 보존용이며, export 단계에서 자동 재파싱하지 않는다.

`prepare_llm_input.py`는 export JSON을 입력받아 downstream 분석용 필드를 추가로 만든다. 대표적으로 `raw_request_target`, `path_normalized_from_raw_request`, `likely_html_fallback_response`는 이 단계의 산출 필드다.

## 15. Apache logs-only 해석 경계

DB에 v2 필드가 추가되어도 해석 경계는 바뀌지 않는다.

- `status_code=200`으로 공격 성공/침해 성공을 단정하지 않는다.
- `status_code=403/404/500/503`만으로 취약점/공격 성공/침해를 단정하지 않는다.
- `response_body_bytes`, `resp_content_type`, `text/html`로 파일 노출/정보 유출을 단정하지 않는다.
- `likely_html_fallback_response=True`로 파일 노출/path traversal 성공/침해 성공을 단정하지 않는다.
- POST metadata만으로 로그인 성공/업로드 저장 성공을 단정하지 않는다.
- Cookie/Auth presence flag만으로 인증 성공을 단정하지 않는다.
- `x_forwarded_for`, `x_real_ip`, `forwarded`만으로 attacker identity를 확정하지 않는다.
- raw POST body, response body, DB 결과, browser execution은 Apache security log에 없으므로 추론하지 않는다.
