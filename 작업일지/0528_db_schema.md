**2026년 5월 28 DB-backed schema 작업일지**

1. 작업날짜: 2026.5.28

2. 작업목표

- DB-backed MVP의 operation/control table을 실제 MariaDB SQL 파일로 분리한다.
- 기존 Apache 로그 source table DDL과 새 analysis job lifecycle table DDL을 문서상 분리한다.
- 운영 문서에서 새 SQL 적용 절차를 찾을 수 있게 연결한다.

3. 완료 내용

### 3.1 analysis job table SQL 추가

추가 파일:

```text
docs/operations/sql/01_analysis_job_tables.sql
```

포함 table:

```text
users
analysis_jobs
analysis_reports
job_events
```

의도적으로 제외한 table:

```text
apache_access_logs
apache_security_logs
apache_error_logs
  - 기존 MariaDB 구축 문서에서 관리

log_collection_checkpoints
  - src/apache_log_shipper.py가 현재 file-state offset tracking을 사용하므로 후속 판단
```

주요 기준:

```text
- MariaDB / InnoDB / utf8mb4
- DATETIME(3)는 UTC naive 저장 기준
- analysis_jobs는 execution lifecycle queue
- operator_queue와 다르다는 주석 포함
- full_report = export + prepare + Stage1 + Stage2 + viewer_payload
- atomic claim SQL 패턴 주석 포함
- error_message / detail_json에는 secret/raw provider error 저장 금지
- artifact_root는 서버 생성 job-scoped path만 허용
```

### 3.2 운영 적용 문서 추가

추가 파일:

```text
docs/operations/07_DB_backed_analysis_job_tables.md
```

내용:

```text
- SQL 적용 전제
- 적용 명령
- 적용 후 SHOW TABLES / DESCRIBE / SHOW INDEX 확인
- 시간대 기준
- full_report 완료 조건
- atomic claim 기준
- secret/redaction 주의
- 다음 구현 연결
```

### 3.3 operations README 연결

수정 파일:

```text
docs/operations/README.md
```

반영:

```text
- docs/operations/sql/01_analysis_job_tables.sql 링크 추가
- docs/operations/07_DB_backed_analysis_job_tables.md 링크 추가
- 기존 Apache 로그 source table DDL은 02_MariaDB 문서에서 관리
- DB-backed MVP operation/control table DDL은 SQL 파일에서 관리
- 읽는 순서에 DB-backed analysis job table setup 추가
```

### 3.4 로그/DB 구조 문서 보정

수정 파일:

```text
docs/operations/03_로그_표준과_DB_구조.md
```

반영:

```text
- 문서 버전 v1.5로 갱신
- 기존 로그 source flow와 DB-backed operation/control flow 분리
- operation/control table 추가 설명
  - users
  - analysis_jobs
  - analysis_reports
  - job_events
- log_collection_checkpoints는 후속 판단으로 명시
- analysis_jobs queue와 operator queue 차이를 다시 명시
- UTC naive DATETIME(3) 저장 / Asia-Seoul 입력·표시 / APACHE_ERROR_LOG_TIMEZONE 기준 반영
```

### 3.5 TODO 갱신

수정 파일:

```text
docs/planning/99_비교실험_후속개선_TODO.md
```

반영:

```text
- MariaDB 기준 DDL 정리 완료 항목에 SQL 파일과 운영 적용 문서 연결
- 다음 우선순위를 SQL 적용 smoke / 문법 검증으로 변경
- validation/redaction policy 구현 기준 확정은 다음 단계로 유지
```

4. 다음 우선순위

```text
1. SQL 적용 smoke / 문법 검증
   - docs/operations/sql/01_analysis_job_tables.sql을 MariaDB test DB에 적용
   - SHOW TABLES / DESCRIBE / SHOW INDEX 확인
   - FK/인덱스/컬럼명 보정 필요 여부 확인

2. validation/redaction policy 구현 기준 확정
   - requested_timezone = Asia/Seoul
   - analysis_mode = full_report
   - max_time_range = 24 hours 후보
   - PENDING/RUNNING 중복 job 처리
   - error_message / job_events redaction

3. analysis_jobs 등록/조회 API

4. 단일 Analysis Agent polling

5. export_db_logs_cli.py 연동

6. artifact_root / analysis_reports 연결
```
