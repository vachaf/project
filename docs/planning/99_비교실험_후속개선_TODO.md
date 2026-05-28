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

- DB-backed log collection + analysis job design: [../design/99_db_backed_log_collection_and_analysis_job_design.md](../design/99_db_backed_log_collection_and_analysis_job_design.md)
- DB-backed Web UI/API safety addendum: [../design/99_db_backed_web_ui_api_safety_addendum.md](../design/99_db_backed_web_ui_api_safety_addendum.md)
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
  - `users`, `analysis_jobs`, `analysis_reports`, `job_events`, `log_collection_checkpoints`를 MariaDB/MySQL 기준 DDL로 정리했다.
  - 기존 `apache_access_logs`, `apache_security_logs`, `apache_error_logs` 3개 로그 source table은 유지한다.
  - DB의 `log_time`, `time_from`, `time_to`는 UTC naive `DATETIME(3)` 저장 기준으로 정리했다.
  - Web UI 입력/표시는 `Asia/Seoul` 기준으로 둔다.
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

- [ ] DB schema/migration 정리
  - 기존 `apache_access_logs`, `apache_security_logs`, `apache_error_logs` 유지.
  - `analysis_jobs`, `analysis_reports`, `job_events` 추가.
  - 필요 시 `log_collection_checkpoints` DB table 도입 여부를 현재 file-state 방식과 비교한다.
  - MariaDB 기준 DDL을 실제 migration 또는 setup SQL로 분리한다.
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
- [x] `window_summary.json` v1 생성 및 검증
  - `src/sliding_window_summary.py` 추가 완료.
  - `candidate_index`에는 `request_id`, `src_ip`, `method`, `uri`, `status_code`, `score`, `verdict_hint`, `reason_hint_prefixes`만 넣는다.
  - raw log/raw request/user agent/referer/final verdict/success 판단은 복제하지 않는다.
- [x] Rollup v1.0 최소 구현 및 검증
  - `src/sliding_window_rollup.py` 추가 완료.
  - request_id dedup, missing/invalid window 기록, candidate_index/distribution merge, `rollup_input.json` / `dedup_candidates.json` / `rollup_summary.json` 생성.
  - Stage1/Stage2 실행, `runs/` 생성, Stage1 projection, 새 score/verdict_hint/confidence/threat_level 생성은 제외한다.
  - 검증: `tests/test_sliding_window_rollup.py` → 10 passed.
- [x] Rollup v1.0 output reuse policy 구현 및 검증
  - output 3종이 모두 있으면 기본 `skipped_existing` 처리한다.
  - 일부만 있으면 실패한다.
  - `--overwrite` 지정 시 재생성한다.
- [x] Operator Queue v1 설계 및 구현
  - `src/sliding_window_operator_queue.py` 추가 완료.
  - 입력: `data/rollups/<date>/rollup_*/rollup_input.json`, `rollup_summary.json`.
  - 출력: `data/operator_queue/<date>/queue_items.json`, `queue_summary.json`.
  - quiet/needs_review/data_quality_check routing, data_quality_status, llm_eligible, top_observed, output reuse, atomic write 구현.
  - Stage1/Stage2/LLM/Web UI/DB/API 실행 및 보안 verdict/confidence/threat_level/success 판단 생성은 제외한다.
- [x] Operator Queue allowlist 보정 및 검증
  - `PAYLOAD_LIKE_REASON_HINTS`에 실제 관찰 prefix `sqli`, `xss` 추가.
  - 기존 `sqli_hint`, `xss_hint`는 유지.
  - `upload`, `login_endpoint`, `auth_payload_content_type`, `error_linked`, `error_status`는 payload-like allowlist에서 제외 유지.
  - 검증: operator queue unit 13 passed, quick bundle 69 passed.
- [x] Operator Queue source selection / cadence 분리 구현 및 검증
  - `src/sliding_window_operator_queue.py --rollup-pattern` 추가 완료.
  - 기본값은 `rollup_*`.
  - fnmatch 기반으로 rollup directory basename만 필터링한다.
  - `source_selection`: `rollup_root`, `rollup_pattern`, `matched_rollup_count`.
  - empty queue는 quiet day가 아니므로 `quiet=0`으로 유지한다.
  - 검증: operator queue unit 17 passed, quick bundle 73 passed.
- [x] 운영용 rollup naming generation 판단
  - 결정: 지금은 보류한다. `--rollup-id-prefix`를 추가하지 않는다.
  - 기본 rollup_id 생성은 기존 `rollup_YYYYMMDD_HHMM_HHMM` 형식을 유지한다.
  - 이유: `--rollup-pattern`으로 source selection이 가능하며, 생성 시점 naming 강제는 scheduler/cron/smoke/사용자 명령 복잡도를 높인다.
- [x] Operator Queue item detail 설계
  - 문서: [../design/99_sliding_window_operator_queue_item_detail.md](../design/99_sliding_window_operator_queue_item_detail.md)
  - 결론: queue item schema 즉시 확장과 별도 detail artifact는 보류한다.
  - 기존 queue item의 counts/signals/top_observed/source paths를 Web UI/CLI view projection으로 재배열하는 방향을 우선한다.
- [x] Single Rollup Observation Brief 설계
  - 문서: [../design/99_sliding_window_single_rollup_observation_brief.md](../design/99_sliding_window_single_rollup_observation_brief.md)
  - 결론: LLM 기반 Single Rollup Reporter는 지금 구현하지 않는다.
  - Observation Brief는 Stage2 report가 아니며 detection engine이 아니다.
- [x] Operator Queue item detail CLI preview 구현 및 검증
  - 구현: `src/sliding_window_operator_queue_detail.py`.
  - 테스트: `tests/test_sliding_window_operator_queue_detail.py`.
  - 입력: `data/operator_queue/<date>/queue_items.json` 및 payload-like prefix 보강용 `rollup_input.json`.
  - 출력: stdout only. `--format text`, `--format markdown`, `--format json` 지원.
  - 새 artifact 생성 없음.
  - Stage1/Stage2/LLM 호출 없음.
  - 보안 verdict/success/threat score 생성 없음.
  - 기본 text 출력은 markdown `##` heading을 쓰지 않는다.
  - `matched_payload_like_reason_prefixes`를 표시해 top_observed limit에 가려지는 `sqli` 같은 payload-like prefix도 확인 가능하게 했다.
  - 검증: `tests/test_sliding_window_operator_queue_detail.py` → 7 passed.
  - 검증: sliding window/operator/rollup/scheduler/candidate policy quick bundle → 80 passed.
  - actual smoke: `rollup_20260524_0200_0400` detail 출력에서 `matched_payload_like_reason_prefixes: xss (5), sqli (1)` 확인.

### 다음 우선순위

- [ ] Single Rollup Observation Brief CLI preview 구현 여부 판단
  - DB-backed MVP 우선순위가 올라가면서 기존 pipeline 연속 작업의 후순위 후보로 둔다.
  - 구현 후보: `src/sliding_window_rollup_observation_brief.py`.
  - selected rollup 하나를 markdown/text로 stdout 출력한다.
  - 새 artifact 생성 없음.
  - Stage1/Stage2/LLM 호출 없음.
  - 보안 verdict/success/threat score 생성 없음.
- [ ] Web UI queue list 구현 여부 판단
  - 입력: `queue_summary.json`, `queue_items.json`.
  - read-only 표시만 한다.
  - severity/category/verdict 재계산 금지.
- [ ] Web UI item detail / brief panel 구현 여부 판단
  - CLI preview에서 안정화한 표시 계약을 Web UI로 옮긴다.
  - read-only drilldown 중심.
- [ ] Rollup v1.1 hint 설계 여부 판단
  - `uri_family_hints`, `low_and_slow_hints`, repeated src_ip / uri / reason_hint_prefix.
  - hint를 candidate_index나 Stage1 후보로 승격하지 않는다.
- [ ] Rollup v1.5 Stage1 projection 검토
  - DB-backed MVP의 `full_report` 경로와 충돌하지 않도록 selected/job-scoped projection으로만 검토한다.
  - 별도 fixture/test 전까지 보류한다.
  - projection 과정에서 score/verdict_hint/severity/confidence를 새로 만들지 않는다.

## P2. observability 후속 판단

- [ ] `proxy_error_check`를 정식 scenario catalog extension으로 뺄지 검토
- [ ] external client 기반 reverse proxy topology run 필요성 판단
- [ ] OpenCart v2 추가 진행 여부 검토
- [ ] `mod_remoteip`/remoteIP 환경 구성 여부 검토

## P3. candidate policy 관찰

- [x] `obs_php_sample_v2_error_heavy_external_001` EH01~EH12 전체 external run을 수행하고 `explain_prepare_candidates.py` 결과를 baseline과 비교
  - 결과: local/internal baseline과 같은 `payload 3 / probe 4 / status-error 3 / auth 1 / upload 1` shape 유지.
  - stale explanation artifact를 최신 `/opt/web_log_analysis` 기준으로 재생성한 뒤 EH01~EH12 label이 정상 표시됨.
  - prepare/scoring/filtering 변경 없음.
- [ ] upload/sql-comment narrow guard가 실제 strong SQLi를 과소탐지하지 않는지 계속 관찰
- [ ] broad status/error-only demotion은 계속 보류 유지
- [ ] scanner/probe broad demotion은 계속 보류 유지

## P4. Web UI read-only 관찰

- [ ] Interpretation Aid와 context badge가 과도하게 findings처럼 보이지 않는지 관찰
- [ ] Related Contexts / Supporting Events 표시가 새 관계 추론처럼 보이지 않는지 점검
- [ ] backend unavailable / proxy error badge는 scenario 정식화 여부가 정리된 뒤 다시 검토

## P5. wording / taxonomy guard

- [ ] actual LLM 출력에서 context-only 과승격이 반복되는지 관찰
- [ ] file disclosure 성공, admin 접근 성공, upload 저장 성공 같은 과해석이 재발하는지 관찰

## P6. run_dir / archive / retention

- [ ] `--run-id` 필요성 관찰
- [ ] legacy/lab archive opt-in scan 정책 후속 검토
- [ ] raw observability log의 보관/커밋 정책 점검
- [ ] output cleanup의 실제 삭제 기능은 별도 승인 전까지 계속 보류

## P7. 새 coverage 후보

- [ ] API key / secret token probe fixture plan 작성 여부 판단
- [ ] Webshell command query fixture plan 작성 여부 판단
- [ ] request smuggling / header anomaly 로그 가시성 검토
- [ ] deserialization / object injection, LDAP / NoSQL injection-like payload는 계속 보류할지 재확인
