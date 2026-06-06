# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-06-06
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
- Analysis job stage events design: [../design/99_analysis_job_stage_events_design.md](../design/99_analysis_job_stage_events_design.md)
- Stale RUNNING recovery policy: [../design/99_analysis_job_stale_running_recovery_policy.md](../design/99_analysis_job_stale_running_recovery_policy.md)
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
  - `SUCCEEDED`는 export/prepare 완료가 아니라 Stage1, Stage2, viewer_payload 생성과 report/artifact 저장 완료를 의미한다.
  - `viewer_payload.json` 생성 완료 후에만 완료 job을 Web UI에서 결과로 보여주는 방향으로 정리했다.
  - `sliding_window / rollup / operator_queue`는 후속 `analysis_mode=windowed_triage`로 분리한다.
- [x] `src/apache_log_shipper.py` error log UTC 저장 보정
  - `APACHE_ERROR_LOG_TIMEZONE` 환경변수를 추가했다.
  - 기본값은 `Asia/Seoul`이다.
  - timezone 없는 error log timestamp를 source timezone으로 해석한 뒤 UTC naive `DATETIME(3)`로 저장하도록 수정했다.
  - timezone 포함 error timestamp 포맷도 수용한다.
  - smoke 확인:
    - 입력: `2026-05-28 18:30:00.000`
    - parse 결과: `2026-05-28 18:30:00+09:00`
    - DB 저장 문자열: `2026-05-28 09:30:00.000`
- [x] DB-backed full_report MVP 실제 smoke
  - Web UI job 등록 후 `python3 src/analysis_job_worker.py --once --worker-id smoke-real --run-pipeline` 실행을 확인했다.
  - job_id=5 기준 `runs/jobs/5`에 direct pipeline artifact가 생성됐다.
  - `analysis_reports`에 `artifact_root`, `stage2_report_path`, `stage2_report_md_path`, `viewer_payload_path`가 저장됐다.
  - manifest 기준 `dry_run=false`, `provider=openai`, `run_dir=runs/jobs/5`, `run_dir_collision_policy=fail_fast`를 확인했다.
  - Stage1 기준 `selected_model=gpt-5.4-mini`, `success_count=5`, `error_count=0`을 확인했다.
  - viewer payload 기준 `schema_version=viewer_payload.v1`, `finding_count=5`, `context_count=2`, `supporting_event_count=0`을 확인했다.
  - `/job/5`, `/job/5/viewer`, `/job/5/artifact/viewer_payload`, `/job/5/artifact/stage2_report_md` 브라우저 표시를 확인했다.
  - no-data smoke는 `JOB_NO_DATA`, `SUCCEEDED`, `analysis_reports.summary`, `export_path`만 저장, stage/viewer paths `NULL` 기준으로 확인했다.
- [x] DB-backed full_report worker/agent 연결 구현 상태 조사
  - 조사 문서: [../design/99_analysis_job_worker_status_investigation.md](../design/99_analysis_job_worker_status_investigation.md)
  - 구현 확인: job 생성/조회, full_report worker claim/run/close, one-shot/loop CLI, heartbeat update, systemd example, job detail/viewer 연결.
  - 2026-05-31 당시 `worker loop/daemon 운영화` TODO 중 loop CLI와 systemd example은 이후 구현된 것으로 정리했다.
- [x] Phase 1 analysis job stage-level `job_events` 구현 및 smoke
  - 설계 문서: [../design/99_analysis_job_stage_events_design.md](../design/99_analysis_job_stage_events_design.md)
  - 구현 범위는 현재 worker/runner가 정확히 관찰 가능한 coarse boundary로 제한했다.
  - 기록 이벤트: `EXPORT_STARTED`, `EXPORT_COMPLETED`, `EXPORT_FAILED`, `EXPORT_NO_DATA`, `PIPELINE_STARTED`, `PIPELINE_COMPLETED`, `PIPELINE_FAILED`, `REPORT_SAVE_STARTED`, `REPORT_SAVE_COMPLETED`, `REPORT_SAVE_FAILED`.
  - 기존 lifecycle event인 `JOB_CREATED`, `JOB_CLAIMED`, `JOB_STARTED`, `JOB_NO_DATA`, `JOB_SUCCEEDED`, `JOB_FAILED`는 유지했다.
  - `JOB_FAILED.detail_json.failed_at_stage`는 Phase 1에서 `export`, `pipeline`, `report_save`까지만 기록한다.
  - `job_events.detail_json`에는 recursive redaction을 적용했다.
  - DB-backed smoke 결과 정상 job, no-data job, pipeline failure job의 event 순서와 `failed_at_stage=pipeline` 전파를 확인했다.
  - `REPORT_SAVE_*`에는 `duration_seconds`, `JOB_SUCCEEDED.detail_json`에는 `worker_id`를 보강했다.
  - Web UI `/job/{id}` 실행 타임라인은 저장된 `job_events`를 read-only로 표시하며, Phase 1 이벤트 렌더링 회귀 테스트를 추가했다.
  - 검증: `PYTHONPATH=. pytest -q` → `319 passed`.
- [x] stale RUNNING recovery CLI와 Web UI hint 구현
  - 정책 문서: [../design/99_analysis_job_stale_running_recovery_policy.md](../design/99_analysis_job_stale_running_recovery_policy.md)
  - 운영 문서: [../operations/analysis_job_worker.md](../operations/analysis_job_worker.md)
  - `--recover-stale --dry-run` 후보 조회를 구현했다.
  - `--recover-stale --mark-failed --reason "..."` 명시 FAILED 처리를 구현했다.
  - `--stale-after-minutes`, `--startup-grace-minutes`, `--limit` 옵션을 지원한다.
  - `JOB_MARKED_FAILED_STALE` event를 기록한다.
  - `PENDING` requeue, artifact 삭제, `attempt_count/max_attempts` 변경, `analysis_reports` 변경은 하지 않는다.
  - Web UI dashboard/detail은 `Potentially stale` 표시만 제공하며 mark failed button은 제공하지 않는다.

### 다음 우선순위

- [ ] live DB long-running worker smoke
  - `--run-pipeline` loop mode를 실제 DB/LLM 환경에서 장시간 실행한다.
  - systemd `enable/start/status/journalctl` 운영 검증을 남긴다.
  - 운영 권장은 여전히 보수적으로 1 worker 기준이며, multi-worker는 명시적으로 검증한 뒤 확대한다.
- [ ] retry/requeue workflow
  - `attempt_count/max_attempts` 기반 claim skip은 있으나 FAILED job retry/requeue CLI/API/UI는 없다.
  - retry 가능한 오류와 artifact overwrite/fail-fast 정책을 함께 정한다.
  - stale failed marking과 retry/rerun은 별도 workflow로 유지한다.
- [ ] cancel/cancelled handling
  - `CANCELLED` 상태와 cancel API/UI/worker semantics는 아직 구현하지 않는다.
- [ ] worker health/status UI
  - worker process 생존 여부, last heartbeat, last claim 같은 운영 visibility를 Web UI/API에 노출할지 정한다.
- [ ] failed event detail hardening
  - `EXPORT_FAILED` / `PIPELINE_FAILED` detail에서 stdout/stderr tail 저장을 더 줄이고, return code와 redacted summary 중심으로 정리할지 검토한다.
- [ ] optional artifact mapping 결정
  - `lint_result_path`는 schema/UI key가 있으나 현재 runner가 채우지 않는다.
  - `manifest_path`, `stage2_report_input_path`를 DB에 저장할지 결정한다.
  - `filtered_reasons.json`은 prepare/run artifact로 생성되지만 `analysis_reports` DB mapping은 아직 없다.
  - `filtered_reasons.json`을 DB에 mapping할지, run artifact로만 둘지 결정한다.
- [ ] filtered reason Web display 연결 여부 결정
  - Web dashboard/detail에서 후보 제외 사유를 표시할지 검토한다.
  - 표시하더라도 “후보 제외 != 정상 판정”과 Apache logs-only guardrail을 함께 유지한다.
- [ ] filtered reason taxonomy 품질 개선
  - `static_asset_like`, `known_baseline_like`, `crawler_or_bot_like`, `low_signal_request`, `duplicate_or_repeated_low_signal`, `outside_candidate_policy`, `context_only_represented_elsewhere`, `unknown_excluded_reason` 분류 품질을 운영 샘플로 점검한다.
  - `normal`/`benign` 확정 표현으로 되돌리지 않는다.
- [ ] LLM token usage 실제 provider run artifact smoke
  - OpenAI 실제 run에서 Stage1 `results[*].llm_usage`, Stage1 `meta.llm_usage_totals`, Stage2 `meta.llm_usage.calls/totals`가 채워지는지 확인한다.
  - Anthropic 실제 run 또는 통제된 repair fixture에서 initial/repair usage 분리가 운영 artifact에서도 확인되는지 점검한다.
  - dry-run은 계속 `available=false`, `dry_run_no_provider_call`로 유지한다.
- [ ] LLM token usage Web 표시 여부 결정
  - Web detail/artifact viewer에서 token counts를 요약 표시할지 검토한다.
  - 표시하더라도 비용 추정이나 provider raw response는 노출하지 않는다.
- [ ] LLM token usage job_events aggregate 여부 결정
  - 현재 구현은 artifact-only이며 `job_events.detail_json`에는 usage aggregate를 저장하지 않는다.
  - 후속으로 필요하면 `PIPELINE_COMPLETED` 또는 `JOB_SUCCEEDED`에 aggregate totals만 제한적으로 기록할지 검토한다.
- [ ] LLM token usage DB mapping/table 여부 결정
  - `analysis_reports` column은 추가하지 않았다.
  - 운영 조회/집계 요구가 생기면 artifact-only 유지, `analysis_reports` mapping, 별도 usage table 중 하나를 설계한다.
- [ ] LLM cost estimate 설계 여부 결정
  - 현재 구현은 token counts만 기록하고 비용 계산은 하지 않는다.
  - 비용 추정은 provider/model pricing snapshot, currency, pricing source/date를 고정하는 설계 이후 별도 작업으로 진행한다.
- [ ] Q&A/발표 자료 wording 반영
  - “후보 제외 != 정상 판정” 표현을 Q&A와 발표 자료에 반영한다.
  - `status_code`, response size, route, User-Agent만으로 성공/정상/무해를 단정하지 않는다는 설명을 유지한다.
- [ ] failed/partial artifact 정책 고도화
  - runner 실패 후 partial artifact scan/save 여부를 정한다.
  - secret redaction 기준은 유지한다.
- [ ] legacy `/report/*` UI 정리
  - DB-backed `/job/{id}/viewer`를 primary viewer로 두고 기존 run_dir/manifest scanner route는 legacy로 분리한다.
- [ ] Markdown report HTML 렌더링 UX 개선
  - 현재 artifact route는 raw markdown/text 표시가 가능하다.
  - HTML report viewer는 후속 UX 개선으로 둔다.
- [ ] `windowed_triage` 후속 mode 설계/연결
  - `full_report` worker에 sliding_window / rollup / operator_queue를 자동 삽입하지 않는다.
  - operator queue 기반 triage는 후속 mode에서 연결한다.

## P1. Sliding Window / Rollup / Operator Queue

### 완료

- [x] Sliding Window planner/export/prepare mode 구현 및 문서화
  - `src/sliding_window_scheduler.py` planner/export/prepare mode 추가 완료.
  - prepare mode는 `prepare_llm_input.py --flat-output-names`를 호출한다.
  - stage1/stage2/viewer_payload는 실행하지 않는다.
  - `runs/`는 생성하지 않는다.

<!-- Existing P1+ history intentionally omitted in this compact current TODO. Full completed details remain in history/progress/design docs. -->
