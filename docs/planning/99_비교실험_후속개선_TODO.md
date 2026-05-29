# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-05-28
- 문서 역할: 앞으로 해야 할 일만 남기는 TODO
- 완료 이력: [99_비교실험_후속개선_history.md](./99_비교실험_후속개선_history.md)
- 관련 대시보드: [../진행상황.md](../진행상황.md)

## 원칙

- 이 문서는 남은 TODO만 유지한다.
- 완료 기록은 history 문서, `docs/진행상황.md`, 개별 설계 문서, 작업일지로 이관한다.
- Apache logs-only evidence boundary를 유지한다.
- `status_code=200`, `text/html`, `response_body_bytes`, `handler`, `x_forwarded_for`만으로 공격 성공/유출/내부 결과를 단정하지 않는다.
- Web UI는 보안 분석 결과 해석에 대해서는 read-only이며 새 보안 판단/관계/incident를 만들지 않는다.
- DB-backed MVP에서 Web UI는 `analysis_jobs` 등록/조회에는 DB write/read를 수행할 수 있다.
- Sliding Window/Rollup/Operator Queue는 LLM 실행 전 사람이 먼저 볼 운영용 artifact를 만드는 경로다.
- DB-backed MVP의 `analysis_jobs` queue는 사용자가 등록한 분석 실행 queue이고, 기존 `operator queue`는 분석 결과 중 사람이 검토할 rollup 목록이다.
- DB-backed MVP의 기본 `analysis_mode`는 `full_report`이며 Stage1/Stage2/viewer_payload 생성까지 완료되어야 `SUCCEEDED`로 본다.
- Web UI/API/job_events/error_message에는 API key, `.env`, provider secret, raw provider error body를 노출하지 않는다.

## 현재 기준 문서

- Current architecture: [../00_current_architecture.md](../00_current_architecture.md)
- DB-backed log collection + analysis job design: [../design/99_db_backed_log_collection_and_analysis_job_design.md](../design/99_db_backed_log_collection_and_analysis_job_design.md)
- DB-backed Web UI/API safety addendum: [../design/99_db_backed_web_ui_api_safety_addendum.md](../design/99_db_backed_web_ui_api_safety_addendum.md)
- DB-backed analysis job table setup: [../operations/07_DB_backed_analysis_job_tables.md](../operations/07_DB_backed_analysis_job_tables.md)
- Analysis job table SQL: [../operations/sql/01_analysis_job_tables.sql](../operations/sql/01_analysis_job_tables.sql)
- Sliding Window adoption review: [../design/99_sliding_window_adoption_review.md](../design/99_sliding_window_adoption_review.md)
- Rollup input review: [../design/99_sliding_window_rollup_input_review.md](../design/99_sliding_window_rollup_input_review.md)
- Rollup input format: [../design/99_sliding_window_rollup_input_format.md](../design/99_sliding_window_rollup_input_format.md)
- Rollup pipeline integration: [../design/99_sliding_window_rollup_pipeline_integration.md](../design/99_sliding_window_rollup_pipeline_integration.md)
- Rollup quick reference: [../design/99_sliding_window_rollup_quick_reference.md](../design/99_sliding_window_rollup_quick_reference.md)
- Rollup implementation guide: [../design/99_sliding_window_rollup_implementation_guide.md](../design/99_sliding_window_rollup_implementation_guide.md)
- Operator Queue design: [../design/99_sliding_window_operator_queue_design.md](../design/99_sliding_window_operator_queue_design.md)
- Operator Queue item detail: [../design/99_sliding_window_operator_queue_item_detail.md](../design/99_sliding_window_operator_queue_item_detail.md)
- Single Rollup Observation Brief: [../design/99_sliding_window_single_rollup_observation_brief.md](../design/99_sliding_window_single_rollup_observation_brief.md)

## P0. DB-backed log collection / analysis job MVP

### 완료

- [x] DB-backed log collection + analysis job 설계 문서화
  - 문서: [../design/99_db_backed_log_collection_and_analysis_job_design.md](../design/99_db_backed_log_collection_and_analysis_job_design.md)
  - 교수님 피드백을 반영해 Apache 로그 수집, DB 적재, Web UI 기반 분석 작업 등록, Analysis Agent 실행, 결과 표시까지의 상위 운영 흐름으로 정리했다.
  - `analysis_jobs queue`와 기존 `operator queue`를 분리했다.
  - Agent는 AI agent가 아니라 Python background worker/CLI process로 정의했다.
- [x] DB-backed Web UI/API safety addendum 작성
  - 문서: [../design/99_db_backed_web_ui_api_safety_addendum.md](../design/99_db_backed_web_ui_api_safety_addendum.md)
  - 안수홍 검토를 반영해 viewer-only 원칙과 DB-backed MVP의 차이를 정리했다.
  - Web UI read-only 원칙은 보안 결과 해석에 적용하고, `analysis_jobs` 등록/조회 DB write/read는 허용하는 것으로 분리했다.
  - UI 표시 정책, secret/config 보호, time range 상한, 중복 job 처리, artifact overwrite/allowed path, timeout, retention/cleanup 정책을 보강했다.
- [x] MariaDB 기준 DDL 정리
  - 기존 `apache_access_logs`, `apache_security_logs`, `apache_error_logs` 3개 로그 source table은 유지한다.
  - `users`, `analysis_jobs`, `analysis_reports`, `job_events`를 MariaDB/MySQL 기준 SQL로 분리했다.
  - SQL: [../operations/sql/01_analysis_job_tables.sql](../operations/sql/01_analysis_job_tables.sql)
  - 운영 적용 문서: [../operations/07_DB_backed_analysis_job_tables.md](../operations/07_DB_backed_analysis_job_tables.md)
  - DB의 `log_time`, `time_from`, `time_to`는 UTC naive `DATETIME(3)` 저장 기준으로 정리했다.
  - Web UI 입력/표시는 `Asia/Seoul` 기준으로 둔다.
  - `log_collection_checkpoints` DB table은 현재 file-state offset tracking과 비교 후 후속 판단으로 둔다.
- [x] DB-backed MVP full_report 완료 조건 정리
  - MVP 기본 `analysis_mode`는 `full_report`다.
  - `SUCCEEDED`는 export/prepare/rollup 완료가 아니라 Stage1, Stage2, viewer_payload 생성과 report/artifact 저장 완료를 의미한다.
  - `viewer_payload.json` 생성 완료 후에만 완료 job을 Web UI에서 결과로 보여주는 방향으로 정리했다.
- [x] `src/apache_log_shipper.py` error log UTC 저장 보정
  - `APACHE_ERROR_LOG_TIMEZONE` 환경변수를 추가했다.
  - 기본값은 `Asia/Seoul`이다.
  - timezone 없는 error log timestamp를 source timezone으로 해석한 뒤 UTC naive `DATETIME(3)`로 저장하도록 수정했다.
  - timezone 포함 error timestamp 포맷도 수용한다.
  - smoke 확인:
    - 입력: `2026-05-28 18:30:00.000`
    - parse 결과: `2026-05-28 18:30:00+09:00`
    - DB 저장 문자열: `2026-05-28 09:30:00.000`

### 다음 우선순위

- [ ] SQL 적용 smoke / 문법 검증
  - `docs/operations/sql/01_analysis_job_tables.sql`을 MariaDB test DB에 적용한다.
  - `SHOW TABLES`, `DESCRIBE`, `SHOW INDEX`로 `users`, `analysis_jobs`, `analysis_reports`, `job_events` 생성을 확인한다.
  - 필요 시 FK/인덱스/컬럼명 보정 커밋을 별도로 수행한다.
- [ ] DB-backed MVP validation/redaction policy 구현 기준 확정
  - `requested_timezone` v1 허용값: `Asia/Seoul`.
  - `analysis_mode` v1 허용값: `full_report`.
  - 일반 Web UI job 최대 time range 후보: 24시간.
  - PENDING/RUNNING 동일 범위 중복 job 차단 또는 기존 job 반환.
  - job_events/error_message secret redaction.
  - artifact_root는 job 단위 경로만 허용하고 사용자 임의 path 입력 금지.
- [ ] `analysis_jobs` 등록/조회 API 설계 및 구현
  - POST job 등록.
  - GET job list/detail.
  - 상태: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`.
  - Web UI 입력 시간은 `Asia/Seoul`, DB 조회 시간은 UTC `DATETIME(3)` 기준으로 변환한다.
  - missing provider는 `N/A`로 표시하고 missing provider detail link는 만들지 않는다.
- [ ] 단일 Analysis Agent polling MVP 구현
  - PENDING job 조회.
  - atomic claim.
  - RUNNING/SUCCEEDED/FAILED 상태 갱신.
  - `job_events` 기록.
  - step timeout 발생 시 `FAILED` 처리.
- [ ] `src/export_db_logs_cli.py` 연동
  - `analysis_jobs.time_from/time_to` 기반 export.json 생성.
  - primary source: `apache_security_logs`.
  - correlation/reference: `apache_error_logs`, `apache_access_logs`.
- [ ] artifact_root / analysis_reports 연결
  - Stage1 결과 경로 저장.
  - Stage2 report 경로 저장.
  - viewer_payload.json 경로 저장.
  - operator_queue artifact 경로 저장.
  - viewer_payload 생성 완료 후 `SUCCEEDED` 처리.
  - MVP에서는 자동 cleanup/delete를 제공하지 않는다.

## P1. Sliding Window / Rollup / Operator Queue

### 완료

- [x] Sliding Window planner/export/prepare mode 구현 및 문서화
  - `src/sliding_window_scheduler.py` planner/export/prepare mode 추가 완료.
  - prepare mode는 `prepare_llm_input.py --flat-output-names`를 호출한다.
  - stage1/stage2/viewer_payload는 실행하지 않는다.
  - `runs/`는 생성하지 않는다.

<!-- Existing P1+ history intentionally omitted in this compact current TODO. Full completed details remain in history/progress/design docs. -->
