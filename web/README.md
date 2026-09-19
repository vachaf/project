# web/

## 1. 역할

`web/`은 프로젝트의 **FastAPI 기반 Web 계층**이다.

현재 Web 계층은 다음 사용자 흐름을 제공한다.

- Analysis Job dashboard
- 시간 범위 기반 새 Analysis Job 생성
- Live Monitoring
- Live에서 선택한 로그 기반 Analysis Job 생성
- Job Detail 및 lifecycle/event 조회
- Job artifact 조회
- Analysis Viewer
- 기존 file-based report / compare viewer

전체 runtime 구조는 [../docs/00_current_architecture.md](../docs/00_current_architecture.md)를 따른다.

Web request handler는 Export, Prepare, Stage1, Security Standards Mapping, Stage2를 직접 실행하지 않는다. 사용자의 분석 요청은 `analysis_jobs`에 등록되고, 실제 `full_report` pipeline은 별도의 **Analysis Job Worker**가 실행한다.

또한 Web의 read-only 원칙은 Web 전체가 DB write를 하지 않는다는 뜻이 아니다.

~~~text
Web UI / API
  -> Analysis Job 생성과 상태 조회를 위해 DB read/write 가능

Analysis Viewer
  -> 완료된 분석 결과의 의미를 다시 판정하지 않는
     read-only interpretation layer
~~~

---

## 2. Web 계층의 책임 경계

현재 Web 계층의 책임은 크게 네 부분으로 나뉜다.

~~~text
Job Operations
  Dashboard / New Job / Job Detail / Artifact

Live Monitoring
  Recent security logs / raw row / security observation /
  selected-log Job creation

Analysis Viewer
  viewer_payload.v1 read-only presentation

Legacy Report Viewer
  file-based report list / detail / compare
~~~

Web 계층이 직접 소유하지 않는 책임:

- Apache log ingest
- Analysis Job Worker 실행
- Export
- Prepare candidate/scoring/filtering
- Stage1 LLM classification
- Security Standards Mapping 계산
- Stage2 report synthesis
- Security Standards Summary 계산
- viewer_payload 생성

이 단계들은 Worker와 분석 pipeline의 책임이다.

---

## 3. 주요 파일 구조

~~~text
web/
├─ app.py
│
├─ routes/
│  ├─ live.py
│  └─ reports.py
│
├─ services/
│  ├─ analysis_job_policy.py
│  ├─ analysis_job_repository.py
│  ├─ live_log_repository.py
│  ├─ live_log_service.py
│  ├─ live_security_observation.py
│  ├─ report_loader.py
│  ├─ report_comparator.py
│  └─ qa_runner.py
│
├─ templates/
│  ├─ job_base.html
│  ├─ job_dashboard.html
│  ├─ new_job.html
│  ├─ job_detail.html
│  ├─ live_dashboard.html
│  ├─ payload_detail.html
│  ├─ index.html
│  ├─ detail.html
│  └─ compare.html
│
└─ static/
   ├─ job-dashboard.css
   ├─ job-ui-additions.css
   ├─ live-monitoring.css
   ├─ live-monitoring.js
   ├─ payload-dashboard.css
   ├─ style.css
   ├─ theme-dark.css
   └─ theme-toggle.js
~~~

### `app.py`

Job 중심 Web route와 공통 FastAPI app 구성을 담당한다.

주요 route:

~~~text
GET  /
GET  /new-job
POST /new-job
POST /api/jobs/create
GET  /api/jobs/count
GET  /api/jobs/list

GET  /job/{job_id}
GET  /job/{job_id}/artifact/{artifact_key}
GET  /job/{job_id}/viewer
GET  /api/job/{job_id}/status

GET  /health
~~~

### `routes/live.py`

Live Monitoring 화면/API와 Live selected-log Job 생성을 담당한다.

~~~text
GET  /live
GET  /api/live/snapshot
GET  /api/live/logs/{row_id}/raw
POST /api/live/jobs/create
~~~

### `routes/reports.py`

기존 file-based report viewer 경로를 담당한다.

~~~text
GET /reports
GET /report/{report_id}
GET /report/{report_id}/payload
GET /compare/{timeframe_id}

GET /api/reports
GET /api/report/{report_id}
GET /api/compare/{timeframe_id}
~~~

---

## 4. Analysis Job Web 흐름

Web에서 만드는 현재 canonical analysis mode는 `full_report`다.

입력 방식은 두 가지다.

### 4.1 시간 범위 기반 Job

~~~text
/new-job
  -> time_from / time_to
  -> validate_analysis_job_request()
  -> AnalysisJobRepository
  -> analysis_jobs: PENDING
~~~

Job policy 계층은 다음을 검증한다.

- 지원 timezone: `Asia/Seoul`
- 지원 analysis mode: `full_report`
- 입력 시간 범위
- 최대 시간 범위
- server-generated artifact path

중복된 active 요청은 기존 PENDING/RUNNING Job 계약에 따라 처리한다.

### 4.2 Live selected-log Job

Live에서 선택한 row는 시간 범위 입력으로 변환하지 않는다.

~~~text
Live checkbox selection
  -> selected_log_ids
  -> POST /api/live/jobs/create
  -> validate_selected_log_request()
  -> AnalysisJobRepository.create_live_selected_logs_job()
  -> analysis_jobs
  -> analysis_job_selected_input_rows
  -> PENDING
~~~

주요 입력 경계:

- source table: `apache_security_logs`
- input kind: `live_selected_logs`
- positive integer ID만 허용
- 최대 50개
- 선택 순서 보존
- stable input fingerprint 사용
- 일부 source row가 없으면 missing identity를 구분
- 모든 row가 없으면 Job을 만들지 않는 NO_DATA 가능
- 동일 active selected-input Job의 중복 생성 방지

이 API는 Job만 등록한다. 실제 Export/Prepare/LLM pipeline을 HTTP request 처리 중 직접 실행하지 않는다.

---

## 5. AnalysisJobRepository와 APP DB

`web/services/analysis_job_repository.py`는 DB-backed Analysis Job의 Web/Worker 공용 repository다.

주요 책임:

- Job 생성
- Job 목록/상태 조회
- selected-input metadata 저장/조회
- PENDING Job atomic claim
- heartbeat
- lifecycle event 기록
- terminal status 변경
- analysis report metadata 저장/조회

주요 DB 구조:

~~~text
analysis_jobs
  -> 실행 queue / Job identity

analysis_job_selected_input_rows
  -> Live selected-input row identity

job_events
  -> lifecycle / stage trace

analysis_reports
  -> artifact path / report metadata index
~~~

Web route에서 발생한 DB error text는 사용자에게 노출하기 전에 제한적으로 redaction한다.

---

## 6. Live Monitoring

### 6.1 조회 경로

Live snapshot/raw 조회는 `LiveLogRepository`와 `LiveLogService`를 사용한다.

주 원천:

~~~text
web_logs.apache_security_logs
~~~

대표 조회 기능:

- 기본 최신 50건
- period filter
- HTTP status class filter
- HTTP method filter
- source IP exact filter
- Request Target keyword filter
- `(log_time, id)` 기반 cursor pagination
- 선택 row raw log 조회
- DB 최신 로그 시각과 마지막 조회 시각 구분
- KST 표시

목록 API는 raw log 전체를 기본 payload에 포함하지 않고, 선택한 row의 raw 값은 별도 endpoint로 조회한다.

Live UI는 polling 기반이다. WebSocket/SSE stream이 아니다.

### 6.2 Live Security Observation

`LiveLogService`는 조회된 row에 대해 `live_security_observation.py`의 observation을 구성할 수 있다.

Live Security Observation은 shared security signal extractor의 결과를 Live용 allowlist/policy로 투영한다.

핵심 상태는 다음 두 축으로 나뉜다.

~~~text
processing_status
  complete
  partial
  unavailable
  error

assessment
  review_required
  no_signal
  undetermined
~~~

의미 경계:

~~~text
review_required
!= attack verdict
!= severity
!= exploit success

no_signal
!= benign
!= safe
~~~

Live 화면은 observation을 검토 보조 정보로 보여줄 뿐 공격 성공을 확정하지 않는다.

### 6.3 Live 조회와 Job 생성의 DB 경계

Live 조회와 selected-log Job 생성은 책임과 DB 권한 경계가 다르다.

~~~text
GET /api/live/snapshot
GET /api/live/logs/{row_id}/raw
  -> LiveLogRepository
  -> 원천 로그 조회

POST /api/live/jobs/create
  -> AnalysisJobRepository
  -> Analysis Job metadata write
~~~

따라서 “Live는 SELECT-only”라는 표현은 **snapshot/raw 조회 경로에 한정해서** 사용해야 한다.

Live 화면 전체에는 selected-log Job 생성 POST가 존재한다.

---

## 7. Job Dashboard와 Job Detail

### 7.1 Job Dashboard

`/`는 DB-backed Analysis Job 목록과 상태를 보여주는 운영 시작점이다.

지원하는 대표 상태:

~~~text
PENDING
RUNNING
SUCCEEDED
FAILED
~~~

상태, 날짜 범위, stale-running 조건 등을 사용한 조회를 지원한다.

### 7.2 Job Detail

`/job/{job_id}`는 한 Analysis Job의 실행과 결과를 추적한다.

대표 정보:

- Job identity
- analysis mode
- input kind
- requested range 또는 selected-input 정보
- current status
- worker / heartbeat / attempt 정보
- lifecycle events
- artifact root
- 주요 artifact
- Stage1 / Stage2 usage 정보가 artifact에 존재하는 경우 usage summary
- filtered reason summary
- Analysis Viewer 진입

Job Detail은 보안 finding을 새로 계산하는 화면이 아니라 **작업과 산출물의 provenance를 추적하는 화면**이다.

---

## 8. Artifact Route

Job artifact route는 DB의 `analysis_reports`에 저장된 artifact metadata를 기준으로 파일을 제공한다.

~~~text
GET /job/{job_id}/artifact/{artifact_key}
~~~

주요 안전 경계:

- user가 임의 filesystem path를 직접 전달하지 않는다.
- artifact path는 relative path 검증을 거친다.
- project root 밖으로 벗어나는 path를 허용하지 않는다.
- resolved file은 해당 Job의 artifact root 아래에 있어야 한다.
- 존재하지 않거나 허용되지 않는 artifact는 404 처리한다.

대표 artifact key는 export, llm_input, analysis_candidates, noise_summary, stage1_result, stage2_report, stage2_report_md, viewer_payload 등이다.

---

## 9. Analysis Viewer

Job Viewer route:

~~~text
GET /job/{job_id}/viewer
~~~

Viewer는 완료된 `viewer_payload.v1`과 관련 artifact를 읽어 사람이 검토하기 쉬운 형태로 표시한다.

### 9.1 Read-only interpretation

Viewer는 다음을 새로 수행하지 않는다.

- Finding 생성
- Stage1/Stage2 verdict 변경
- severity 재계산
- confidence 재계산
- Standards Mapping 재계산
- Standards Summary 재계산
- Context의 Finding 승격
- 공격 성공 여부 추론

~~~text
viewer_payload
  -> sanitize
  -> presentation label / ordering
  -> HTML display

!= security re-classification
~~~

### 9.2 표시용 변환

Viewer는 안전한 표시와 가독성을 위해 다음과 같은 presentation 처리를 할 수 있다.

- field sanitize
- source IP display policy 적용
- timeline ordering
- 한국어 우선 label
- canonical English label 병기
- verdict를 근거로 한 presentation-only display label

이러한 처리는 source `viewer_payload`의 category/verdict contract를 변경하는 것이 아니다.

### 9.3 정보 역할

Viewer의 주요 정보 역할:

~~~text
Finding
  = 주요 탐지 요청

Context
  = Finding을 이해하기 위한 해석 정보

Supporting Event
  = 주변 참고 요청
~~~

~~~text
Finding != exploit success
Context != Finding
Supporting Event != Finding
~~~

---

## 10. Legacy Report Viewer

기존 file-based Stage2 report viewer는 계속 유지한다.

관련 template:

- `index.html`
- `detail.html`
- `compare.html`

관련 route:

- `/reports`
- `/report/{report_id}`
- `/compare/{timeframe_id}`
- 관련 JSON API

기존 report list/filter/compare 기능은 호환 경로로 유지되지만, 현재 DB-backed 사용자 흐름의 중심은 다음이다.

~~~text
Job Dashboard
  -> Live Monitoring 또는 New Job
  -> Analysis Job
  -> Job Detail
  -> Analysis Viewer
~~~

Legacy viewer의 존재를 현재 Analysis Job runtime과 동일한 실행 경로로 해석하지 않는다.

---

## 11. Frontend 구조

현재 frontend는 별도 SPA framework 없이 Jinja2 template, Plain CSS, JavaScript로 구성한다.

~~~text
FastAPI
  -> Jinja2 templates
  -> CSS
  -> plain JavaScript
~~~

주요 UI 자산:

### Job UI

- `templates/job_base.html`
- `templates/job_dashboard.html`
- `templates/new_job.html`
- `templates/job_detail.html`
- `static/job-dashboard.css`
- `static/job-ui-additions.css`

### Live

- `templates/live_dashboard.html`
- `static/live-monitoring.css`
- `static/live-monitoring.js`

### Analysis Viewer

- `templates/payload_detail.html`
- `static/payload-dashboard.css`

### 공통 / legacy

- `templates/base.html`
- `templates/index.html`
- `templates/detail.html`
- `templates/compare.html`
- `static/style.css`
- `static/theme-dark.css`
- `static/theme-toggle.js`

Live의 동적 DB 문자열은 DOM에 표시할 때 HTML 실행을 피하도록 안전한 text rendering 경계를 유지한다.

---

## 12. Web 보안·의미 경계

현재 Web 계층에서 유지해야 할 주요 경계는 다음과 같다.

### Pipeline execution

~~~text
Web request handler
  -> Job 생성 / 조회

Worker
  -> pipeline 실행
~~~

Web route에서 임의 pipeline 실행 버튼이나 user-controlled arbitrary command/path 실행을 제공하지 않는다.

### Artifact path

사용자 입력 임의 경로를 artifact filesystem lookup에 직접 사용하지 않는다.

### Secret / sensitive data

- Job error/event 표시에는 secret redaction 경계를 둔다.
- raw authorization/cookie/secret 등의 표시를 보수적으로 제한한다.
- Viewer sanitize 경계를 유지한다.

### Evidence semantics

~~~text
HTTP status
response size
Content-Type
route
User-Agent
source IP
Live observation
Viewer label

각각 단독으로
!= exploit success
!= compromise
!= vulnerability confirmation
~~~

세부 의미 경계는 [../docs/00_apache_logs_only_evidence_boundary.md](../docs/00_apache_logs_only_evidence_boundary.md)를 따른다.

---

## 13. 기술 의존성

`web/requirements.txt`의 기본 Web runtime 의존성:

~~~text
fastapi
uvicorn
jinja2
pymysql
~~~

Web UI는 현재 React/Vue 같은 별도 SPA framework를 요구하지 않는다.

---

## 14. 관련 문서

| 문서 | 역할 |
| --- | --- |
| [../README.md](../README.md) | 프로젝트 전체 소개 |
| [../docs/00_current_architecture.md](../docs/00_current_architecture.md) | 전체 runtime architecture |
| [../docs/00_apache_logs_only_evidence_boundary.md](../docs/00_apache_logs_only_evidence_boundary.md) | 보안 결과 해석의 의미 경계 |
| [../docs/operations/README.md](../docs/operations/README.md) | DB / 환경 / Worker runtime support |

이 문서는 과거 UI phase나 특정 polish 작업의 진행 기록을 관리하지 않는다. 그런 기록은 historical report/review 문서에서 관리하고, 이 문서는 **현재 Web 계층의 실제 책임과 코드 경계**를 설명하는 데 집중한다.
