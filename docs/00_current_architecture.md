# 00_current_architecture

- 문서 상태: 현재 기준 아키텍처 요약
- 기준 시점: 2026-05-31
- 목적: Apache 로그 기반 LLM 침입 로그 분석 시스템의 현재 구조, 주요 경계, artifact 흐름, DB-backed MVP 방향을 한 문서에서 확인할 수 있게 한다.
- 관련 문서:
  - [진행상황.md](./진행상황.md)
  - [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md)
  - [design/99_db_backed_log_collection_and_analysis_job_design.md](./design/99_db_backed_log_collection_and_analysis_job_design.md)
  - [design/99_db_backed_web_ui_api_safety_addendum.md](./design/99_db_backed_web_ui_api_safety_addendum.md)
  - [design/99_run_analysis_pipeline_user_runner_ux_review.md](./design/99_run_analysis_pipeline_user_runner_ux_review.md)
  - [design/99_sliding_window_operator_queue_design.md](./design/99_sliding_window_operator_queue_design.md)
  - [planning/99_비교실험_후속개선_TODO.md](./planning/99_비교실험_후속개선_TODO.md)

## 1. 한 문장 요약

본 시스템은 Apache access/security/error 로그를 수집해 MariaDB에 저장하고, 사용자가 Web UI에서 특정 시간 범위의 분석 작업을 등록하면, Analysis Job Worker가 해당 작업을 가져와 기존 direct `full_report` 파이프라인을 실행한 뒤 Stage1/Stage2/report/viewer artifact를 생성하고 Web UI에서 작업 상태와 결과를 확인할 수 있게 하는 DB-backed 웹 기반 로그 분석 플랫폼이다.

핵심 흐름:

```text
Apache 로그
  -> Log Collector Agent
  -> MariaDB
  -> Web UI analysis_jobs 등록
  -> Analysis Job Worker full_report 실행
  -> Stage1 / Stage2 / viewer_payload 생성
  -> Web UI 결과 확인
```

## 2. 현재 기준 흐름

### 2.1 상위 운영 흐름

```text
[Apache]
  access/security/error log 생성
    ↓
[Log Collector Agent]
  src/apache_log_shipper.py
  로그 파싱 및 MariaDB 저장
    ↓
[MariaDB]
  apache_access_logs
  apache_security_logs
  apache_error_logs
    ↓
[Web UI]
  사용자가 분석 시간 범위 등록
  analysis_jobs row 생성
    ↓
[Analysis Agent]
  PENDING job atomic claim
  해당 시간 범위 export
  prepare 실행
  Stage1 / Stage2 / viewer_payload 실행
    ↓
[Artifact Storage]
  export.json
  llm_input.json
  stage1_results.json
  stage2_report.json
  stage2_report.md
  viewer_payload.json
    ↓
[MariaDB]
  analysis_reports
  job_events
  analysis_jobs.status = SUCCEEDED 또는 FAILED
    ↓
[Web UI]
  job list/detail
  report/viewer_payload 표시
```

### 2.2 사용자가 보는 흐름

```text
1. Web UI 접속
2. 분석할 시작 시간 / 종료 시간 입력
3. 분석 작업 등록
4. job 상태 확인
   - PENDING
   - RUNNING
   - SUCCEEDED
   - FAILED
5. 완료된 job 클릭
6. Stage2 report 또는 viewer_payload 기반 결과 확인
```

사용자는 내부의 export JSON, prepare 산출물, Stage1/Stage2 중간 파일을 직접 선택하지 않는다.

### 2.3 실제 smoke 상태

2026-05-31 기준 DB-backed `full_report` MVP는 실제 smoke로 아래 흐름을 확인했다.

```text
analysis_jobs(PENDING)
  -> Analysis Job Worker claim
  -> export_db_logs_cli.py
  -> run_analysis_pipeline.py direct path
  -> prepare
  -> Stage1
  -> Stage2
  -> viewer_payload
  -> analysis_reports 저장
  -> analysis_jobs(SUCCEEDED)
  -> /job/{id}/viewer dashboard 표시
```

확인 범위:

```text
- Web UI job 등록
- shell에서 analysis_job_worker.py --once --run-pipeline 실행
- runs/jobs/5 표준 artifact 생성
- stage2_report.json / stage2_report.md / viewer_payload.json 경로 저장
- /job/5, /job/5/viewer, raw artifact routes 브라우저 표시
- no-data job은 JOB_NO_DATA + SUCCEEDED + export_path only로 닫힘
```

이 smoke는 `full_report` direct pipeline 기준이다. `sliding_window / rollup / operator_queue`는 자동 삽입하지 않았으며 후속 `windowed_triage` mode 범위로 유지한다.

## 3. 주요 구성 요소

### 3.1 Apache / Target App Server

역할:

```text
- Apache access/security/error 로그 생성
- Juice Shop, OpenCart, PHP sample app 등 웹 서비스 앞단 역할
- custom log format을 통해 request/response metadata 기록
```

주의:

```text
- Apache 로그는 관찰 가능한 HTTP metadata를 제공한다.
- Apache 로그만으로 DB 결과, 브라우저 실행, 실제 침해 성공을 확인하지 않는다.
```

### 3.2 Log Collector Agent

현재 구현 후보:

```text
src/apache_log_shipper.py
```

역할:

```text
- Apache access/security/error log 파일 읽기
- log line 파싱
- MariaDB 저장
- file offset state 관리
- 실패 시 spool 재시도
```

저장 대상:

```text
apache_access_logs
apache_security_logs
apache_error_logs
```

시간대 기준:

```text
- access/security 로그: timezone-aware timestamp를 UTC naive DATETIME(3)로 저장
- error 로그: timezone 없는 timestamp는 APACHE_ERROR_LOG_TIMEZONE 기준으로 해석 후 UTC naive DATETIME(3)로 저장
- APACHE_ERROR_LOG_TIMEZONE 기본값: Asia/Seoul
```

### 3.3 MariaDB

MariaDB는 원천 로그, job lifecycle, report metadata를 관리한다.

현재 유지하는 로그 source table:

```text
apache_access_logs
apache_security_logs
apache_error_logs
```

DB-backed MVP operation/control table 후보:

```text
users
analysis_jobs
analysis_reports
job_events
log_collection_checkpoints
```

저장 원칙:

```text
- log_time / time_from / time_to는 UTC naive DATETIME(3) 기준
- 큰 JSON payload는 DB에 직접 저장하지 않음
- DB에는 상태, 색인, 요약, artifact 경로를 저장
- 실제 JSON/report/viewer_payload는 파일 artifact로 보존
```

### 3.4 Web UI

역할:

```text
- 사용자 로그인 후보
- analysis_jobs 등록
- analysis_jobs list/detail 조회
- job_events timeline 표시
- analysis_reports artifact metadata 조회
- Stage2 report / viewer_payload 표시
```

중요한 경계:

```text
Web UI read-only 원칙은 보안 결과 해석에 적용한다.
DB-backed MVP에서는 Web UI가 analysis_jobs 등록/조회에는 DB write/read를 수행할 수 있다.
```

Web UI가 하지 않는 일:

```text
- Stage1/Stage2 report 의미 수정
- severity/category/verdict/success 재계산
- context-only 항목을 finding/incident로 승격
- raw body full search
- source IP raw search
- API key/.env/provider secret 표시
- 임의 파일 path 입력을 통한 pipeline 실행
- destructive cleanup
```

### 3.5 Analysis Agent

역할:

```text
- analysis_jobs에서 PENDING 작업 조회
- atomic claim으로 RUNNING 전환
- 해당 시간 범위 로그 export
- 기존 direct full_report pipeline 실행
- artifact_root에 산출물 저장
- analysis_reports 생성
- job_events 기록
- SUCCEEDED 또는 FAILED 상태 갱신
```

주의:

```text
- 이 문서의 Agent는 AI agent가 아니다.
- Python background worker 또는 CLI process를 의미한다.
- Agent는 UI를 확인하지 않는다.
- Agent는 DB의 analysis_jobs 상태를 기준으로 작업한다.
```

### 3.6 Artifact Storage

현재 기준은 local filesystem이다.

주요 위치:

```text
data/raw/
data/processed/
data/windowed/
data/rollups/
data/operator_queue/
reports/
runs/
```

DB-backed MVP job-scoped artifact root 후보:

```text
runs/jobs/<job_id>/
```

또는:

```text
runs/web_job_<job_id>/
```

원칙:

```text
- 서로 다른 job은 같은 artifact_root를 공유하지 않는다.
- Web UI/API 입력으로 임의 output path를 받지 않는다.
- work_dir 밖 artifact write를 금지한다.
- MVP에서는 자동 cleanup/delete를 제공하지 않는다.
```

## 4. 두 queue의 구분

현재 시스템에서 `queue`라는 말은 두 가지 의미로 쓰인다.

### 4.1 analysis_jobs queue

```text
위치: MariaDB analysis_jobs table
생성 주체: Web UI 또는 API
처리 주체: Analysis Agent
목적: 분석 작업 실행 lifecycle 관리
상태: PENDING / RUNNING / SUCCEEDED / FAILED
```

분석 실행 queue다.

예:

```text
사용자가 2026-05-28 18:00~19:00 KST 구간 분석을 요청
  -> analysis_jobs에 PENDING row 생성
  -> Analysis Agent가 claim
  -> full_report 실행
  -> SUCCEEDED 또는 FAILED
```

### 4.2 operator queue

```text
위치: data/operator_queue/<date>/queue_items.json, queue_summary.json
생성 주체: sliding_window_operator_queue.py
처리 주체: 운영자 또는 Web UI read-only projection
목적: rollup 결과 중 사람이 먼저 검토할 관찰 대상 routing
상태: quiet / needs_review / data_quality_check
```

분석 결과 검토 queue다.

operator queue는 보안 verdict, success 판단, threat score를 만들지 않는다.

### 4.3 기준 문장

```text
analysis_jobs는 실행 queue이고,
operator queue는 분석 결과의 검토 queue다.
두 queue는 목적과 위치가 다르다.
```

## 5. Pipeline / artifact 흐름

### 5.1 기존 full report path

```text
export.json
  -> prepare_llm_input.py
  -> llm_input.json
  -> analysis_candidates.json
  -> noise_summary.json
  -> Stage1
  -> stage1_results.json
  -> Stage2
  -> stage2_report.json
  -> stage2_report.md
  -> viewer_payload_builder.py
  -> viewer_payload.json
```

### 5.2 Sliding Window / Rollup / Operator Queue path

```text
window별 export/prepare
  -> window_summary.json
  -> sliding_window_rollup.py
  -> rollup_input.json
  -> dedup_candidates.json
  -> rollup_summary.json
  -> sliding_window_operator_queue.py
  -> queue_items.json
  -> queue_summary.json
  -> queue item detail preview 후보
```

이 경로는 장시간 로그를 바로 Stage1/Stage2에 넣지 않고, 먼저 사람이 볼 summary/review routing artifact를 만드는 목적이다. DB-backed MVP `full_report` worker에는 자동 삽입하지 않고, 후속 `analysis_mode=windowed_triage`로 분리한다.

### 5.3 DB-backed MVP full_report path

MVP의 `analysis_mode` 기본값은 `full_report`다.

```text
analysis_jobs PENDING
  -> Analysis Job Worker claim
  -> export_db_logs_cli.py
  -> export.json
  -> run_analysis_pipeline.py direct path
  -> prepare
  -> Stage1
  -> Stage2
  -> viewer_payload.json
  -> analysis_reports
  -> analysis_jobs SUCCEEDED 또는 FAILED
```

MVP에서 `SUCCEEDED`는 단순히 export/prepare가 끝났다는 뜻이 아니다.

```text
SUCCEEDED = Stage1 + Stage2 + viewer_payload + report/artifact 저장 완료
```

## 6. 시간대 기준

### 6.1 DB 저장 기준

```text
MariaDB DATETIME(3)에는 timezone 정보가 직접 저장되지 않는다.
따라서 애플리케이션 레벨에서 UTC naive DATETIME(3) 저장 원칙을 고정한다.
```

DB 저장:

```text
log_time
analysis_jobs.time_from
analysis_jobs.time_to
job_events.event_time
created_at / started_at / finished_at
```

기준:

```text
UTC naive DATETIME(3)
```

### 6.2 Web UI 입력/표시 기준

```text
기본 timezone: Asia/Seoul
```

MVP 정책:

```text
- Web UI는 Asia/Seoul 기준으로 시간 범위를 입력/표시한다.
- Analysis Agent 또는 API layer가 Asia/Seoul 입력을 UTC DB 조회 범위로 변환한다.
- requested_timezone v1 허용값은 Asia/Seoul로 제한한다.
```

### 6.3 Artifact label 기준

```text
sliding window / rollup artifact의 사람이 읽는 label과 window_id/rollup_id는 기존 repo 흐름과 맞춰 Asia/Seoul 기준을 유지한다.
```

예:

```text
rollup_20260524_0200_0400
sw_0200_0300
```

## 7. Web UI / API safety 기준

### 7.1 결과 해석 read-only

Web UI는 다음을 하지 않는다.

```text
- Stage2 report 의미 변경
- severity/category/verdict/success 재계산
- context-only를 finding/incident로 승격
- observed request를 exploit success로 강화
```

### 7.2 표시 정책

Web UI 기본 표시 정책:

```text
- IP masking 유지
- raw_log 전체 노출 금지
- raw_request 전체 노출 금지
- raw header/body preview 기본 노출 금지
- Cookie 값 노출 금지
- Authorization 값 노출 금지
- API key/token/secret 후보 문자열 노출 금지
- missing provider는 N/A로 표시
- missing provider detail link 생성 금지
```

### 7.3 Secret 보호

금지:

```text
- Web UI에 API key 표시
- Web UI에 .env 내용 표시
- job_events.detail_json에 API key 저장
- analysis_jobs.error_message에 secret 저장
- provider raw error response를 그대로 UI에 표시
```

허용 예:

```text
STAGE2_FAILED: provider=openai reason=timeout
```

금지 예:

```text
STAGE2_FAILED: Authorization=Bearer sk-...
```

### 7.4 Job 입력 제한

현재 코드/UI 기준:

```text
requested_timezone = Asia/Seoul
analysis_mode = full_report
max_time_range 허용 상한 = 24 hours
```

24시간은 권장 분석 크기가 아니라 Web UI `full_report` 등록 허용 상한이다. 운영상으로는 짧은 구간을 권장하고, 큰 구간은 비용/시간 문제를 보고 후속 `windowed_triage`로 분리 검토한다.

중복 job 처리 후보:

```text
- 같은 requested_by + analysis_mode + time_from + time_to + requested_timezone의 PENDING/RUNNING job이 있으면 새 job을 만들지 않고 기존 job을 반환한다.
- SUCCEEDED/FAILED 재실행 정책은 별도 rerun UX에서 결정한다.
```

## 8. Apache logs-only evidence boundary

canonical 기준:

```text
./00_apache_logs_only_evidence_boundary.md
```

금지되는 단정:

```text
- raw POST body 내용
- response body 원문
- DB query 결과
- 브라우저 실행 여부
- 로그인 성공
- 계정 탈취
- credential stuffing 성공
- lockout 발동
- PUT 업로드 성공
- DELETE 삭제 성공
- TRACE/XST 성공
- CORS 취약점 성공
- protocol bypass 성공
- malformed request exploit success
- 서버 침해 성공
- static file 존재
- robots/sitemap 내용
- JS 실행
- file exposure
- 실제 crawler 여부
- site structure 노출
- WordPress 존재
- admin access
- .env / phpinfo / server-status / backup 노출
- SSRF outbound 성공
- metadata credential 탈취
- JNDI lookup 성공
- RCE 성공
- callback 수신 성공
- webshell 존재
- command execution 성공
- GraphQL schema 노출 성공
- open redirect 성공
- SSTI 실행 성공
- XXE file read 성공
- API key/token exfiltration 성공
```

다음도 성공 증거로 사용하지 않는다.

```text
- status_code=200
- text/html
- response_body_bytes
- 특정 route
- 특정 IP
- 특정 product name
- lab-* user-agent
```

## 9. 현재 구현 완료 상태

### 9.1 기존 full report / Web UI run_dir

```text
- run_analysis_pipeline.py 기반 full path 존재
- Stage1 / Stage2 / viewer_payload 생성 path 존재
- runs/*/manifest.json 기반 Web UI loader 기준 존재
- actual run_dir smoke 완료 이력 있음
```

### 9.2 Sliding Window / Rollup / Operator Queue

완료:

```text
- sliding_window_scheduler.py planner/export/prepare mode
- sliding_window_summary.py window_summary.json
- sliding_window_rollup.py rollup_input/dedup/summary
- sliding_window_operator_queue.py queue_items/queue_summary
- sliding_window_operator_queue_detail.py CLI preview
```

검증 이력:

```text
- operator queue detail unit: 7 passed
- operator queue unit: 17 passed
- sliding window/operator/detail/rollup/scheduler quick bundle: 80 passed
```

### 9.3 DB-backed 설계 / safety

완료:

```text
- DB-backed log collection + analysis job 설계 문서화
- DB-backed Web UI/API safety addendum 작성
- runner UX 문서를 DB-backed MVP 기준으로 갱신
- TODO / 진행상황 / 작업일지 반영
```

### 9.4 apache_log_shipper.py UTC 보정

완료:

```text
- APACHE_ERROR_LOG_TIMEZONE 추가
- 기본값 Asia/Seoul
- timezone 없는 error log timestamp를 source timezone으로 해석 후 UTC naive DATETIME(3) 저장
```

smoke:

```text
input: 2026-05-28 18:30:00.000
parse_error_time: 2026-05-28 18:30:00+09:00
to_mysql_datetime: 2026-05-28 09:30:00.000
```

## 10. 다음 구현 우선순위

DB-backed MVP 구현을 다음 우선순위로 둔다.

```text
1. DB schema/migration 정리
   - 기존 apache_access_logs / apache_security_logs / apache_error_logs 유지
   - analysis_jobs / analysis_reports / job_events 추가
   - log_collection_checkpoints DB table 도입 여부 판단

2. Analysis Job Worker 구현
   - PENDING job 조회
   - atomic claim
   - RUNNING/SUCCEEDED/FAILED 상태 갱신
   - job_events 기록

3. repository lifecycle methods 보강
   - claim
   - heartbeat
   - append event 공통 메서드
   - mark succeeded/failed
   - analysis_reports upsert

4. direct full_report pipeline 연결
   - export_db_logs_cli.py로 time_from/time_to 기반 export.json 생성
   - run_analysis_pipeline.py direct path 호출
   - job-scoped artifact_root 사용

5. analysis_reports 저장
   - Stage1 결과 경로 저장
   - Stage2 report 경로 저장
   - viewer_payload.json 경로 저장

6. validation/redaction policy 구현 기준 유지
   - requested_timezone = Asia/Seoul
   - analysis_mode = full_report
   - max_time_range 허용 상한 24시간
   - PENDING/RUNNING 중복 job 처리
   - secret redaction
   - job-scoped artifact_root

```

후순위 후보:

```text
- Single Rollup Observation Brief CLI preview
- Web UI Operator Queue list
- Web UI item detail / brief panel
- retry / cancellation
- stale worker recovery
- scheduling / alerting
- retention cleanup automation
- object storage
```

## 11. 문서 읽기 순서

처음 보는 사람:

```text
1. README.md
2. docs/README.md
3. docs/00_current_architecture.md
4. docs/진행상황.md
5. docs/planning/99_비교실험_후속개선_TODO.md
```

DB-backed MVP 설계 확인:

```text
1. docs/00_current_architecture.md
2. docs/design/99_db_backed_log_collection_and_analysis_job_design.md
3. docs/design/99_db_backed_web_ui_api_safety_addendum.md
4. docs/design/99_run_analysis_pipeline_user_runner_ux_review.md
```

운영/설치 확인:

```text
1. docs/operations/README.md
2. docs/operations/02_MariaDB_환경_구축_및_설치.md
3. docs/operations/03_로그_표준과_DB_구조.md
4. docs/operations/04_로그_적재_및_운영.md
5. docs/operations/05_Export_LLM_분석_전략.md
```

Sliding Window / Rollup / Operator Queue 확인:

```text
1. docs/design/99_sliding_window_adoption_review.md
2. docs/design/99_sliding_window_rollup_pipeline_integration.md
3. docs/design/99_sliding_window_operator_queue_design.md
4. docs/design/99_sliding_window_operator_queue_item_detail.md
5. docs/design/99_sliding_window_single_rollup_observation_brief.md
```

## 12. 요약

현재 시스템은 다음 두 층을 함께 가진다.

```text
1. 기존 full report pipeline
   export -> prepare -> Stage1 -> Stage2 -> viewer_payload

2. DB-backed 운영 플랫폼 MVP
   Apache logs -> MariaDB -> analysis_jobs -> Analysis Agent -> full_report artifacts -> Web UI
```

그리고 다음 경계를 유지한다.

```text
- Web UI는 job을 등록할 수 있다.
- Analysis Agent는 job을 실행할 수 있다.
- Web UI와 Agent는 Apache logs-only evidence boundary를 넘어 새 성공/침해/유출 판단을 만들 수 없다.
```
