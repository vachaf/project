# 02_MariaDB_환경_구축_및_설치

- 문서 상태: 정리본
- 버전: v1.2
- 작성일: 2026-04-09
- 기준 코드:
  - `src/apache_log_shipper.py`
  - `src/export_db_logs_cli.py`

## 1. 목적

MariaDB 저장 서버를 현재 로그 파이프라인 기준으로 설치하고, `web_logs` 스키마를 운영하는 최소 기준을 정리한다.

## 2. 서버 역할

- 웹서버: Apache 로그 생성, shipper 실행
- DB 서버: `web_logs` 저장
- LLM 서버: 읽기 전용 export 및 분석

## 3. 기준 환경

- Ubuntu 22.04 Server
- MariaDB 10.6 계열
- DB 이름: `web_logs`
- 문자셋: `utf8mb4`

## 4. 구축 순서

1. MariaDB 설치
2. `bind-address` 설정
3. `web_logs` 생성
4. 3개 로그 테이블 생성
5. `log_writer`, `log_reader` 계정 생성
6. 원격 접속 검증

## 5. 설치 명령

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y mariadb-server mariadb-client
sudo systemctl enable mariadb
sudo systemctl start mariadb
```

## 6. bind-address

웹서버와 LLM 서버에서 접근해야 하면 DB 서버 IP로 설정한다.

예:

```ini
bind-address = 192.168.35.223
```

## 7. DB와 계정

### 7.1 데이터베이스

```sql
CREATE DATABASE web_logs CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
```

### 7.2 계정 분리

- `log_writer`: shipper 전용
- `log_reader`: export/분석 전용

`log_reader` 는 `SELECT` 만 주는 것이 기준이다.

## 8. 테이블

운영 기준 테이블:

- `apache_access_logs`
- `apache_security_logs`
- `apache_error_logs`

각 테이블의 세부 컬럼 표준은 `03_로그_표준과_DB_구조.md` 기준을 따른다.

## 9. `resp_html_*` 관련 정리

현재 DB 측 기준:

- `resp_html_*` 컬럼은 있어도 된다.
- 하지만 현재 운영 핵심 기능으로 보지 않는다.
- 값 생성 로직은 보류 상태로 본다.

즉, `resp_html_*` 는 “현재 필수 운영 기능”이 아니라 선택 또는 보류 컬럼이다.

현재 실제 분석과 더 직접적으로 연결되는 필드는 downstream 기준으로 아래 항목이다.

- `resp_content_type`
- `response_body_bytes`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`

## 10. 운영 확인 항목

- `log_writer` 로 INSERT 가능
- `log_reader` 로 SELECT 가능
- `web_logs` 와 3개 테이블 존재
- 웹서버에서 DB 연결 가능
- LLM 서버에서 export 조회 가능
