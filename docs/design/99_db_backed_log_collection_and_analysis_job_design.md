# 99_db_backed_log_collection_and_analysis_job_design

- 문서 상태: 설계 초안 / 교수님 피드백 반영 정리
- 기준 시점: 2026-05-28
- 목적: Apache 로그 수집부터 Web UI 기반 분석 작업 등록, Agent 분석 실행, 결과 표시까지의 DB-backed 운영 흐름을 정의한다.
- 관련 구현 후보:
  - FastAPI Web UI
  - Log Collector Agent
  - Analysis Agent
  - DB-backed analysis_jobs queue
  - artifact storage integration
- 관련 기존 구현:
  - `src/prepare_llm_input.py`
  - `src/sliding_window_scheduler.py`
  - `src/sliding_window_summary.py`
  - `src/sliding_window_rollup.py`
  - `src/sliding_window_operator_queue.py`
  - `src/sliding_window_operator_queue_detail.py`

관련 문서:

- [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
- [99_sliding_window_adoption_review.md](./99_sliding_window_adoption_review.md)
- [99_sliding_window_rollup_pipeline_integration.md](./99_sliding_window_rollup_pipeline_integration.md)
- [99_sliding_window_operator_queue_design.md](./99_sliding_window_operator_queue_design.md)
- [99_sliding_window_operator_queue_item_detail.md](./99_sliding_window_operator_queue_item_detail.md)
- [99_sliding_window_single_rollup_observation_brief.md](./99_sliding_window_single_rollup_observation_brief.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

교수님 피드백을 반영한 상위 구조는 단순히 Web UI에서 분석 작업 queue를 등록하는 수준이 아니다.

전체 목표는 다음 흐름을 하나의 운영 시스템으로 묶는 것이다.

```text
Apache 로그 수집
  -> DB 적재
  -> 사용자의 시간 범위 기반 분석 요청
  -> Analysis Agent의 비동기 분석 실행
  -> JSON/report/viewer artifact 저장
  -> Web UI에서 상태와 결과 확인
```

따라서 시스템은 크게 두 agent 역할로 나눈다.

```text
1. Log Collector Agent
   - Apache access/security/error log를 읽는다.
   - 로그를 파싱한다.
   - DB의 로그 테이블에 저장한다.
   - 수집 위치/checkpoint를 관리한다.

2. Analysis Agent
   - DB의 analysis_jobs 테이블에서 PENDING 작업을 확인한다.
   - 작업을 atomic하게 claim한 뒤 RUNNING으로 바꾼다.
   - 해당 시간 범위의 로그를 DB에서 조회한다.
   - 기존 prepare / sliding window / rollup / Stage1 / Stage2 / viewer pipeline을 실행한다.
   - 결과 artifact를 파일로 저장하고 DB에는 경로와 요약을 남긴다.
   - job 상태를 SUCCEEDED 또는 FAILED로 변경한다.
```

중요한 원칙:

```text
- Agent는 UI를 확인하지 않는다.
- Agent는 DB의 job 상태를 확인한다.
- UI는 DB 상태를 표시한다.
- DB의 analysis_jobs.status가 작업 상태의 source of truth다.
```

## 2. 기존 Operator Queue와의 관계

이 문서의 `analysis_jobs queue`와 기존 `operator queue`는 다른 개념이다.

```text
analysis_jobs queue
  - 사용자가 Web UI에서 등록한 분석 실행 작업 목록
  - DB table: analysis_jobs
  - 상태: PENDING / RUNNING / SUCCEEDED / FAILED
  - 목적: 분석 작업 실행 lifecycle 관리

operator queue
  - rollup 이후 사람이 먼저 검토할 운영용 관찰 대상 목록
  - artifact: queue_items.json / queue_summary.json
  - 상태: quiet / needs_review / data_quality_check
  - 목적: rollup 결과 중 사람이 볼 대상을 routing
```

따라서 다음 문장을 기준으로 한다.

```text
analysis_jobs는 실행 queue이고,
operator queue는 분석 결과의 검토 queue다.
두 queue는 목적과 위치가 다르다.
```

혼동되는 표현:

```text
잘못 표현될 수 있는 문장:
- Agent가 UI에서 대기 상태를 확인한다.
- Web UI queue와 Operator Queue가 같다.
- queue item이 곧 analysis job이다.
```

권장 표현:

```text
- Analysis Agent는 DB의 analysis_jobs 테이블에서 status='PENDING'인 작업을 확인한다.
- UI는 DB의 analysis_jobs 상태를 읽어서 대기/작업중/완료/실패를 표시한다.
- Operator Queue는 Analysis Agent가 생성한 rollup 검토 artifact 중 하나다.
```

## 3. 전체 운영 흐름

권장 메인 흐름:

```text
[Apache]
   ↓
[Log Collector Agent]
   ↓
[DB: apache_logs]

[User]
   ↓
[FastAPI Web UI]
   ↓
[DB: analysis_jobs]

[Analysis Agent]
   ↓
DB에서 PENDING job atomic claim
   ↓
해당 시간 범위의 로그 조회
   ↓
분석 파이프라인 실행
   ↓
artifact 저장
   ↓
[DB: analysis_reports / report_artifacts]
   ↓
job 상태 SUCCEEDED 또는 FAILED

[User]
   ↓
Web UI에서 job 상태 확인
   ↓
완료 job 클릭
   ↓
viewer_payload 기반 보고서 확인
```

사용자 관점의 최소 흐름:

```text
1. 웹 메인 대시보드 접속
2. 분석 작업 요청 버튼 클릭
3. 분석할 시작 시간 / 종료 시간 입력
4. 등록
5. 작업이 PENDING 상태로 표시됨
6. Analysis Agent가 가져가면 RUNNING으로 변경됨
7. 분석 완료 시 SUCCEEDED로 변경됨
8. 실패 시 FAILED와 error_message 표시
9. 완료 작업 클릭
10. viewer_payload 또는 report 화면 확인
```

## 4. 구성 요소

### 4.1 FastAPI Web UI

책임:

```text
- 사용자 로그인
- 분석 작업 등록
- analysis_jobs 목록 표시
- job 상태 표시
- 완료 report 링크 제공
- viewer_payload 기반 보고서 표시
```

하지 않는 일:

```text
- Apache 로그 파일 직접 tail
- Agent 대신 분석 실행
- job 상태의 source of truth 역할
- Stage1/Stage2 결과 재판정
- 보안 verdict 재계산
```

UI는 DB 상태와 artifact를 보여주는 presentation layer다.

### 4.2 Log Collector Agent

책임:

```text
- Apache log source 읽기
- 신규 log line 감지
- log line 파싱
- DB 저장
- checkpoint 저장
- logrotate 또는 파일 변경 감지 후보 관리
```

입력 후보:

```text
/var/log/apache2/access.log
/var/log/apache2/error.log
/var/log/apache2/app_security.log
/var/log/apache2/app_access.log
/var/log/apache2/app_error.log
```

출력:

```text
DB: apache_logs
DB: log_collection_checkpoints
```

주의:

```text
- Log Collector Agent는 보안 판단을 만들지 않는다.
- Log Collector Agent는 LLM을 호출하지 않는다.
- Log Collector Agent는 로그를 수집/파싱/저장하는 역할에 제한한다.
```

### 4.3 Analysis Agent

책임:

```text
- analysis_jobs에서 PENDING 작업 조회
- atomic claim
- RUNNING 상태 갱신
- 해당 시간 범위의 로그 export
- 기존 분석 pipeline 실행
- artifact 저장
- report DB record 생성
- SUCCEEDED 또는 FAILED 상태 갱신
- job_events 기록
```

분석 pipeline 후보:

```text
DB apache_logs
  -> export.json
  -> prepare_llm_input.py
  -> llm_input.json / analysis_candidates.json / noise_summary.json
  -> sliding_window_scheduler.py
  -> window_summary.json
  -> sliding_window_rollup.py
  -> rollup_input.json / dedup_candidates.json / rollup_summary.json
  -> sliding_window_operator_queue.py
  -> queue_items.json / queue_summary.json
  -> optional Stage1
  -> optional Stage2
  -> viewer_payload.json
```

v1에서는 기존 파일 artifact pipeline을 최대한 유지한다.

### 4.4 DB

DB는 상태와 색인을 관리한다.

주요 책임:

```text
- 사용자 정보 저장
- 수집된 Apache 로그 저장
- 분석 작업 상태 저장
- report metadata 저장
- artifact 경로 저장
- job event 기록
- log collection checkpoint 저장
```

큰 JSON을 DB에 전부 넣는 방식은 v1 기본값으로 두지 않는다.

권장:

```text
DB:
- job 상태
- 시간 범위
- 요청자
- 요약
- artifact 경로
- 오류 메시지

파일:
- export.json
- llm_input.json
- analysis_candidates.json
- noise_summary.json
- window_summary.json
- rollup_input.json
- dedup_candidates.json
- rollup_summary.json
- queue_items.json
- queue_summary.json
- stage1_results.json
- stage2_report.json
- stage2_report.md
- viewer_payload.json
- lint_result.json
```

### 4.5 Artifact Storage

v1은 local filesystem 기반 artifact storage를 우선한다.

예시:

```text
data/
  windowed/
  rollups/
  operator_queue/

runs/
  <job_id_or_run_id>/
    manifest.json
    export.json
    llm_input.json
    analysis_candidates.json
    noise_summary.json
    stage1_results.json
    stage2_report.json
    stage2_report.md
    viewer_payload.json
```

DB에는 artifact root와 주요 파일 경로를 저장한다.

```text
analysis_reports.viewer_payload_path
analysis_reports.stage1_result_path
analysis_reports.stage2_report_path
analysis_reports.stage2_report_md_path
analysis_reports.operator_queue_path
```

## 5. DB table 초안

### 5.1 users

MVP 최소:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

역할:

```text
- Web UI 로그인
- analysis_jobs.requested_by 참조
```

v1에서 복잡한 권한 체계는 보류한다.

### 5.2 apache_logs

`apache_access_logs`

```sql
CREATE TABLE apache_logs (
    id INTEGER PRIMARY KEY,
    log_time TIMESTAMP NOT NULL,
    log_source TEXT NOT NULL,
    vhost TEXT,
    server_name TEXT,
    server_port INTEGER,
    local_ip TEXT,
    src_ip TEXT,
    peer_ip TEXT,
    method TEXT,
    raw_request TEXT,
    uri TEXT,
    query_string TEXT,
    protocol TEXT,
    status_code INTEGER,
    original_status_code INTEGER,
    response_body_bytes INTEGER,
    in_bytes INTEGER,
    out_bytes INTEGER,
    total_bytes INTEGER,
    duration_us INTEGER,
    ttfb_us INTEGER,
    request_id TEXT,
    error_link_id TEXT,
    user_agent TEXT,
    referer TEXT,
    raw_line TEXT,
    parsed_json TEXT,
    ingested_at TIMESTAMP NOT NULL
);
```

권장 index:

```sql
CREATE INDEX idx_apache_logs_log_time ON apache_logs(log_time);
CREATE INDEX idx_apache_logs_src_ip ON apache_logs(src_ip);
CREATE INDEX idx_apache_logs_request_id ON apache_logs(request_id);
CREATE INDEX idx_apache_logs_status_code ON apache_logs(status_code);
```

주의:

```text
- parsed_json은 디버깅용 원본 파싱 결과 보존 후보다.
- raw_line은 원본 확인용으로 보존할 수 있다.
- LLM 입력에는 raw_line/raw_request/raw query string을 무제한 복제하지 않는다.
```

### 5.3 log_collection_checkpoints

Log Collector Agent 재시작과 logrotate 대응을 위한 checkpoint 테이블이다.

```sql
CREATE TABLE log_collection_checkpoints (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    inode TEXT,
    last_offset INTEGER NOT NULL DEFAULT 0,
    last_log_time TIMESTAMP,
    updated_at TIMESTAMP NOT NULL
);
```

역할:

```text
- 파일을 어디까지 읽었는지 저장
- agent 재시작 시 중복 수집 방지
- logrotate 이후 source 변경 감지 후보 제공
```

MVP에서는 `source_name`, `file_path`, `last_offset`만 사용해도 된다.

### 5.4 analysis_jobs

사용자가 Web UI에서 등록한 분석 작업 queue다.

```sql
CREATE TABLE analysis_jobs (
    id INTEGER PRIMARY KEY,
    requested_by INTEGER,
    time_from TIMESTAMP NOT NULL,
    time_to TIMESTAMP NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    analysis_mode TEXT NOT NULL DEFAULT 'standard',
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    worker_id TEXT,
    heartbeat_at TIMESTAMP,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    report_id INTEGER,
    artifact_root TEXT,
    FOREIGN KEY (requested_by) REFERENCES users(id)
);
```

상태 후보:

```text
PENDING
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

MVP UI 표시는 다음 네 개로 시작한다.

```text
PENDING   = 대기
RUNNING   = 작업중
SUCCEEDED = 완료
FAILED    = 실패
```

`CANCELLED`는 v1.1 후보로 둔다.

### 5.5 analysis_reports

분석 결과 metadata와 artifact 경로를 저장한다.

```sql
CREATE TABLE analysis_reports (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE,
    summary TEXT,
    artifact_root TEXT NOT NULL,
    export_path TEXT,
    llm_input_path TEXT,
    analysis_candidates_path TEXT,
    noise_summary_path TEXT,
    rollup_input_path TEXT,
    rollup_summary_path TEXT,
    operator_queue_items_path TEXT,
    operator_queue_summary_path TEXT,
    stage1_result_path TEXT,
    stage2_report_path TEXT,
    stage2_report_md_path TEXT,
    viewer_payload_path TEXT,
    lint_result_path TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
);
```

주의:

```text
- 큰 JSON payload를 DB에 직접 넣는 것은 v1 기본값이 아니다.
- DB에는 경로와 compact summary를 저장한다.
- 파일 artifact를 기준으로 재현성과 디버깅 가능성을 유지한다.
```

### 5.6 job_events

job 진행 상황과 오류를 기록한다.

```sql
CREATE TABLE job_events (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    event_time TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT,
    detail_json TEXT,
    FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
);
```

event_type 후보:

```text
JOB_CREATED
JOB_CLAIMED
EXPORT_STARTED
EXPORT_FINISHED
PREPARE_STARTED
PREPARE_FINISHED
WINDOW_STARTED
WINDOW_FINISHED
ROLLUP_STARTED
ROLLUP_FINISHED
OPERATOR_QUEUE_STARTED
OPERATOR_QUEUE_FINISHED
STAGE1_STARTED
STAGE1_FINISHED
STAGE2_STARTED
STAGE2_FINISHED
VIEWER_PAYLOAD_WRITTEN
JOB_SUCCEEDED
JOB_FAILED
```

## 6. Job 상태 전이

기본 상태 전이:

```text
PENDING
  -> RUNNING
  -> SUCCEEDED

PENDING
  -> RUNNING
  -> FAILED
```

v1.1 후보:

```text
PENDING
  -> CANCELLED

RUNNING
  -> FAILED
  -> PENDING  # retry 후보

RUNNING
  -> FAILED_STALE_WORKER  # heartbeat 기반 후보
```

MVP 상태 정의:

```text
PENDING
  - 사용자가 등록했지만 아직 agent가 가져가지 않은 상태

RUNNING
  - Analysis Agent가 claim했고 분석 중인 상태

SUCCEEDED
  - 분석이 끝났고 report/artifact 저장이 완료된 상태

FAILED
  - 분석 중 오류가 발생했고 error_message 또는 job_events로 원인을 확인해야 하는 상태
```

주의:

```text
- 실패 상태는 반드시 필요하다.
- 실패 상태가 없으면 export 실패, prepare 실패, LLM 실패, JSON 생성 실패, artifact write 실패를 UI에서 설명할 수 없다.
```

## 7. Agent claim 방식

Analysis Agent는 단순히 PENDING job을 읽고 실행하면 안 된다.

여러 agent가 동시에 실행될 수 있으므로 atomic claim이 필요하다.

권장 개념:

```sql
UPDATE analysis_jobs
SET status = 'RUNNING',
    started_at = CURRENT_TIMESTAMP,
    worker_id = :worker_id,
    heartbeat_at = CURRENT_TIMESTAMP,
    attempt_count = attempt_count + 1
WHERE id = :job_id
  AND status = 'PENDING';
```

이 update의 affected row가 1개일 때만 해당 worker가 job을 실행한다.

동작:

```text
1. PENDING job 후보 조회
2. 특정 job에 대해 atomic update 시도
3. affected row == 1이면 claim 성공
4. affected row == 0이면 다른 worker가 이미 가져간 것으로 보고 skip
5. claim 성공한 worker만 분석 실행
```

MVP에서는 단일 Analysis Agent만 운영하더라도, 문서상으로는 atomic claim 원칙을 둔다.

## 8. Analysis Agent 내부 처리 단계

표준 흐름 후보:

```text
1. job claim
2. artifact_root 생성
3. DB apache_logs에서 time_from/time_to 범위 조회
4. export.json 생성
5. prepare 실행
6. sliding window 필요 시 window artifact 생성
7. rollup artifact 생성
8. operator queue artifact 생성
9. optional Stage1 실행
10. optional Stage2 실행
11. viewer_payload 생성
12. analysis_reports record 생성
13. job status SUCCEEDED
```

오류 처리:

```text
- 단계별 시작/완료 event를 job_events에 기록한다.
- 예외 발생 시 error_message를 analysis_jobs에 기록한다.
- 가능한 경우 실패 직전까지 생성된 artifact_root를 보존한다.
- job status를 FAILED로 변경한다.
```

## 9. 기존 Sliding Window / Rollup / Operator Queue와의 연결

기존 pipeline의 위치는 다음과 같다.

```text
Analysis Agent
  -> DB time range export
  -> prepare
  -> sliding window
  -> rollup
  -> operator queue
  -> optional LLM stage
  -> report/viewer
```

기존 artifact 의미는 유지한다.

```text
data/windowed/
  - prepare-only window 중간 산출물
  - 기본 Web UI report list에 직접 노출하지 않음

data/rollups/
  - multi-window rollup 입력/요약 산출물
  - Stage1/Stage2 전의 summary/index artifact

data/operator_queue/
  - 사람이 먼저 볼 rollup review queue
  - LLM 또는 Stage1/Stage2 실행 결과가 아님

runs/
  - Stage2 report와 viewer_payload가 있는 report run
  - Web UI report 상세 화면과 연결 가능
```

Operator Queue의 역할:

```text
- rollup 결과 중 quiet / needs_review / data_quality_check 상태를 표시한다.
- llm_eligible을 표시할 수 있다.
- llm_required는 v1에서 false를 유지한다.
- 보안 verdict, success 판단, threat score를 만들지 않는다.
```

## 10. Web UI 화면 후보

### 10.1 Analysis Jobs 화면

목적:

```text
사용자가 등록한 분석 작업의 상태를 확인한다.
```

표시 필드 후보:

```text
- job id
- requested_by
- time_from
- time_to
- status
- created_at
- started_at
- finished_at
- error_message
- report link
```

상태 표시:

```text
PENDING   대기
RUNNING   작업중
SUCCEEDED 완료
FAILED    실패
```

### 10.2 Job 등록 화면

입력:

```text
- analysis start time
- analysis end time
- analysis mode
- memo 또는 label 후보
```

등록 동작:

```text
INSERT INTO analysis_jobs (...)
status='PENDING'
```

### 10.3 Job 상세 화면

표시:

```text
- job metadata
- status
- job_events timeline
- artifact paths
- report summary
- error_message
```

SUCCEEDED일 경우:

```text
- viewer_payload 열기
- stage2_report.md 보기
- operator queue 보기
```

FAILED일 경우:

```text
- error_message 표시
- 마지막 성공 event 표시
- artifact_root가 있으면 생성된 artifact 확인 링크 제공
```

### 10.4 Operator Queue 화면

목적:

```text
Analysis job 결과 중 rollup review queue를 표시한다.
```

표시 후보:

```text
- rollup_id
- time range
- data_quality_status
- review_status
- candidate_index_count
- windows_missing_or_failed
- llm_eligible
- recommended_action
```

이 화면은 analysis_jobs 화면과 구분한다.

```text
analysis_jobs screen
  - 작업 실행 상태

operator_queue screen
  - rollup 검토 대상
```

## 11. Apache logs-only guardrails

이 설계는 Apache logs-only 한계를 유지한다.

금지:

```text
- status_code=200만으로 공격 성공 판단
- response_body_bytes만으로 파일 유출 판단
- raw_request만으로 DB 영향 판단
- 로그인 성공/계정 탈취 확정
- 브라우저 실행 결과 추론
- 서버 compromise 성공 판단
- 업로드 지속성 판단
- context-only 항목을 finding으로 승격
- rollup 단계에서 새 보안 verdict 생성
- operator queue에서 threat score 생성
```

허용:

```text
- 관찰된 요청/응답 metadata 표시
- candidate count 표시
- source window 완전성 표시
- top observed src_ip/uri/status/reason prefix 분포 표시
- data quality 상태 표시
- 사람이 drilldown할 경로 제공
- optional LLM briefing 가능 여부 표시
```

## 12. MVP 범위

MVP에 포함:

```text
- users 최소 테이블
- apache_logs 저장
- analysis_jobs 등록
- Analysis Agent의 PENDING job polling
- atomic claim 원칙 적용
- time range 기반 export
- 기존 prepare pipeline 호출
- artifact_root 저장
- analysis_reports metadata 저장
- PENDING/RUNNING/SUCCEEDED/FAILED UI 표시
- 완료 job에서 viewer_payload 또는 stage2_report 링크 제공
```

MVP에서 보류:

```text
- 다중 worker 고가용성
- heartbeat 기반 stale worker 복구
- retry policy
- CANCELLED 상태
- 세밀한 권한 관리
- 실시간 WebSocket 상태 push
- DB에 대형 JSON 전체 저장
- object storage 연동
- 실시간 차단 기능
- WAF 기능
- 자동 대응 기능
```

## 13. v1에서 하지 않는 것

v1 설계에서 명시적으로 제외한다.

```text
- Web UI가 로그를 직접 분석하지 않는다.
- Web UI가 job 상태의 source of truth가 되지 않는다.
- Agent가 UI를 scrape하거나 UI 상태를 확인하지 않는다.
- Log Collector Agent가 보안 판단을 하지 않는다.
- Analysis Agent가 Apache logs-only boundary를 넘는 성공/침해 판단을 만들지 않는다.
- Operator Queue가 Stage1/Stage2 report를 대체하지 않는다.
- analysis_jobs queue와 operator queue를 같은 개념으로 취급하지 않는다.
- Stage1/Stage2를 모든 window마다 자동 남발하지 않는다.
```

## 14. 향후 확장 후보

### 14.1 Retry

후보 필드:

```text
attempt_count
max_attempts
last_error
```

동작 후보:

```text
FAILED job 중 retry 가능한 오류만 PENDING으로 되돌린다.
```

### 14.2 Heartbeat / stale worker recovery

후보 필드:

```text
worker_id
heartbeat_at
```

동작 후보:

```text
RUNNING 상태인데 heartbeat_at이 오래된 job은 stale로 판단한다.
```

주의:

```text
자동 재시도는 중복 분석과 artifact overwrite 위험이 있으므로 v1에서는 보류한다.
```

### 14.3 WebSocket 또는 polling 개선

MVP:

```text
Web UI가 주기적으로 job list를 polling한다.
```

향후:

```text
WebSocket 또는 Server-Sent Events로 상태 변경을 push한다.
```

### 14.4 Artifact storage abstraction

MVP:

```text
local filesystem
```

향후:

```text
S3-compatible object storage
NAS
artifact retention policy
```

### 14.5 Analysis mode 분리

후보:

```text
standard
sliding_window_rollup
operator_queue_only
stage1_stage2_full
observation_brief_only
```

주의:

```text
analysis_mode 이름은 보안 verdict 의미를 만들지 않는다.
실행 profile을 구분하기 위한 운영 설정일 뿐이다.
```

## 15. 다음 구현 후보

문서화 이후 구현 후보는 다음 순서가 적절하다.

```text
1. Single Rollup Observation Brief CLI preview
   - selected rollup 하나를 markdown/text로 stdout 출력
   - Stage1/Stage2/LLM 호출 없음
   - 새 보안 verdict/success/threat score 생성 없음

2. Web UI Operator Queue list
   - queue_items.json / queue_summary.json 표시
   - read-only projection
   - 새 보안 판단 없음

3. Web UI Operator Queue item detail panel
   - 기존 queue item detail projection 재사용
   - CLI preview와 같은 해석 유지

4. DB-backed analysis_jobs MVP
   - analysis_jobs table
   - PENDING/RUNNING/SUCCEEDED/FAILED 상태
   - 단일 Analysis Agent polling
   - artifact_root 저장

5. Log Collector Agent MVP
   - Apache log file tail/read
   - apache_logs insert
   - checkpoint 저장
```

## 16. 요약

교수님 피드백 반영 후 시스템의 한 문장 요약은 다음과 같다.

```text
본 시스템은 Apache 로그를 Log Collector Agent가 수집하여 DB에 저장하고,
사용자가 Web UI에서 특정 시간 범위의 분석 작업을 등록하면,
Analysis Agent가 DB의 PENDING 작업을 가져와 기존 LLM 기반 분석 pipeline을 실행한 뒤,
결과 JSON과 viewer artifact를 저장하고,
Web UI에서 작업 상태와 최종 보고서를 확인할 수 있게 하는 DB-backed 웹 기반 로그 분석 플랫폼이다.
```

핵심 경계:

```text
analysis_jobs queue
  - 사용자가 등록한 분석 실행 queue

operator queue
  - rollup 이후 사람이 검토할 관찰 대상 queue

DB
  - job 상태의 source of truth

Web UI
  - DB 상태와 artifact를 표시하는 presentation layer

Agent
  - DB 상태를 기준으로 작업을 수행하는 background worker
```
