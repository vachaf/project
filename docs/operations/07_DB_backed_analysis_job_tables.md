# 07_DB_backed_analysis_job_tables

- 문서 상태: 운영 적용 문서
- 기준 시점: 2026-05-28
- 관련 SQL: [`sql/01_analysis_job_tables.sql`](./sql/01_analysis_job_tables.sql)
- 관련 설계:
  - [`../00_current_architecture.md`](../00_current_architecture.md)
  - [`../design/99_db_backed_log_collection_and_analysis_job_design.md`](../design/99_db_backed_log_collection_and_analysis_job_design.md)
  - [`../design/99_db_backed_web_ui_api_safety_addendum.md`](../design/99_db_backed_web_ui_api_safety_addendum.md)

## 1. 목적

이 문서는 DB-backed MVP를 위해 MariaDB `web_logs` 데이터베이스에 추가하는 운영/control table 적용 절차를 정리한다.

기존 Apache 로그 source table은 다음 문서에서 관리한다.

```text
docs/operations/02_MariaDB_환경_구축_및_설치.md
```

이 문서는 그 위에 추가되는 job lifecycle table만 다룬다.

```text
users
analysis_jobs
analysis_reports
job_events
```

## 2. 기존 로그 source table과의 관계

기존 source table은 그대로 유지한다.

```text
apache_access_logs
apache_security_logs
apache_error_logs
```

이 테이블들은 Apache log shipper와 export path의 원천 데이터다.

DB-backed MVP에서 추가되는 table은 분석 작업 실행 상태와 artifact 경로를 관리한다.

```text
analysis_jobs
  - 사용자가 Web UI에서 등록한 분석 실행 queue

analysis_reports
  - job별 report/artifact metadata

job_events
  - job 실행 단계 timeline

users
  - Web UI 사용자/요청자 후보
```

주의:

```text
analysis_jobs queue와 operator queue는 다르다.

analysis_jobs queue:
- MariaDB table
- 실행 lifecycle 관리
- PENDING/RUNNING/SUCCEEDED/FAILED

operator queue:
- data/operator_queue/<date>/queue_items.json
- rollup 결과 중 사람이 검토할 관찰 대상 목록
- quiet/needs_review/data_quality_check
```

## 3. SQL 파일

적용 SQL:

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

## 4. 적용 전 전제

MariaDB와 기존 `web_logs` DB가 준비되어 있어야 한다.

기존 구축 문서:

```text
docs/operations/02_MariaDB_환경_구축_및_설치.md
```

기대 상태:

```sql
USE web_logs;
SHOW TABLES;
```

기존 로그 source table이 보여야 한다.

```text
apache_access_logs
apache_security_logs
apache_error_logs
```

## 5. 적용 방법

repo root 기준:

```bash
mariadb -u root -p < docs/operations/sql/01_analysis_job_tables.sql
```

또는 DB를 명시한다.

```bash
mariadb -u root -p web_logs < docs/operations/sql/01_analysis_job_tables.sql
```

운영 계정으로 적용하는 경우 `CREATE TABLE`, `INDEX`, `FOREIGN KEY` 생성 권한이 필요하다.

## 6. 적용 후 확인

MariaDB 접속:

```bash
mariadb -u root -p web_logs
```

테이블 확인:

```sql
SHOW TABLES LIKE 'analysis_%';
SHOW TABLES LIKE 'job_events';
SHOW TABLES LIKE 'users';
```

기대 결과:

```text
analysis_jobs
analysis_reports
job_events
users
```

구조 확인:

```sql
DESCRIBE analysis_jobs;
DESCRIBE analysis_reports;
DESCRIBE job_events;
DESCRIBE users;
```

주요 index 확인:

```sql
SHOW INDEX FROM analysis_jobs;
SHOW INDEX FROM analysis_reports;
SHOW INDEX FROM job_events;
```

기대 index 후보:

```text
analysis_jobs:
- idx_analysis_jobs_status_created_at
- idx_analysis_jobs_time_range
- idx_analysis_jobs_requested_by
- idx_analysis_jobs_mode_status
- idx_analysis_jobs_worker_status

analysis_reports:
- uk_analysis_reports_job_id
- idx_analysis_reports_created_at

job_events:
- idx_job_events_job_time
- idx_job_events_event_type
```

## 7. 시간대 기준

`analysis_jobs.time_from`, `analysis_jobs.time_to`, `job_events.event_time`, `created_at`, `started_at`, `finished_at`은 UTC naive `DATETIME(3)` 기준으로 저장한다.

Web UI 입력/표시는 MVP에서 `Asia/Seoul` 기준이다.

```text
Web UI Asia/Seoul input
  -> API layer에서 UTC naive DATETIME(3)로 변환
  -> analysis_jobs.time_from/time_to 저장
```

MariaDB `DATETIME(3)`은 timezone 정보를 직접 저장하지 않으므로 애플리케이션 레벨에서 UTC 저장 원칙을 유지해야 한다.

## 8. full_report 완료 조건

MVP의 기본 `analysis_mode`는 `full_report`다.

`analysis_jobs.status=SUCCEEDED`는 단순히 export/prepare가 끝났다는 뜻이 아니다.

```text
SUCCEEDED = Stage1 + Stage2 + viewer_payload + report/artifact metadata 저장 완료
```

최소 artifact 후보:

```text
export.json
llm_input.json
analysis_candidates.json
noise_summary.json
stage1_results.json
stage2_report.json
stage2_report.md
viewer_payload.json
```

## 9. atomic claim 기준

Analysis Agent는 `PENDING` job을 읽기만 하고 실행하면 안 된다.

여러 worker 또는 재시작 상황을 고려해 atomic claim을 사용한다.

예:

```sql
UPDATE analysis_jobs
SET status = 'RUNNING',
    started_at = CURRENT_TIMESTAMP(3),
    worker_id = 'worker-1',
    heartbeat_at = CURRENT_TIMESTAMP(3),
    attempt_count = attempt_count + 1
WHERE id = 1
  AND status = 'PENDING';
```

`affected_rows == 1`일 때만 해당 worker가 job을 실행한다.

## 10. 보안/표시 정책

DB-backed MVP의 DB table에는 다음을 저장하지 않는다.

```text
API key
.env 내용
provider secret
raw provider error body
raw request body
response body
Cookie 값
Authorization 값
```

`analysis_jobs.error_message`와 `job_events.detail_json`에는 redacted summary만 저장한다.

허용 예:

```text
STAGE2_FAILED: provider=openai reason=timeout
```

금지 예:

```text
STAGE2_FAILED: Authorization=Bearer sk-...
```

## 11. 다음 구현 연결

이 SQL 적용 후 다음 구현 후보는 다음이다.

```text
1. analysis_jobs 등록/조회 API
2. validation/redaction helper
3. 단일 Analysis Agent polling
4. src/export_db_logs_cli.py 연동
5. artifact_root / analysis_reports 연결
```

MVP API validation 후보:

```text
requested_timezone = Asia/Seoul
analysis_mode = full_report
max_time_range = 24 hours
PENDING/RUNNING 동일 범위 중복 job 차단 또는 기존 job 반환
```
