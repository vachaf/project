# 99_db_backed_web_ui_api_safety_addendum

- 문서 상태: 설계 보강 / 안수홍 검토 반영
- 기준 시점: 2026-05-28
- 목적: `99_db_backed_log_collection_and_analysis_job_design.md`의 DB-backed MVP 방향을 유지하면서 Web UI 표시 정책, API 입력 제한, secret 보호, artifact retention, 기존 viewer-only 문서와의 관계를 명확히 한다.
- 관련 문서:
  - [99_db_backed_log_collection_and_analysis_job_design.md](./99_db_backed_log_collection_and_analysis_job_design.md)
  - [99_run_analysis_pipeline_user_runner_ux_review.md](./99_run_analysis_pipeline_user_runner_ux_review.md)
  - [99_sliding_window_operator_queue_design.md](./99_sliding_window_operator_queue_design.md)
  - [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

안수홍 검토의 핵심은 타당하다.

DB-backed 설계 문서는 다음 항목에서 현재 repo 방향과 정합성이 높다.

```text
- local filesystem artifact storage 유지
- DB는 상태/색인/경로 중심, 큰 JSON은 파일 artifact로 보존
- analysis_jobs queue와 operator queue 분리
- Sliding Window / Rollup / Operator Queue는 후속 `windowed_triage` 흐름으로 분리
- atomic claim
- UTC 저장 / Asia-Seoul 입력·표시 분리
- job_events 기반 단계별 추적
```

다만 기존 Web UI viewer-only 원칙과 DB-backed MVP 방향이 섞이면 혼동이 생긴다.

따라서 다음 기준을 확정한다.

```text
Web UI read-only 원칙은 보안 분석 결과 해석에 적용한다.
Web UI는 analysis_jobs 등록/조회에는 DB write/read를 수행할 수 있다.
Web UI는 Stage1/Stage2 report 의미를 수정하거나 새 보안 판단을 생성하지 않는다.
```

즉, 새 기준은 다음과 같다.

```text
허용:
- Web UI에서 analysis_jobs 등록
- Web UI에서 job list/detail 조회
- Web UI에서 job_events 상태 표시
- Web UI에서 viewer_payload/stage2_report artifact 표시

금지:
- Web UI에서 severity/category/verdict/success 재계산
- Web UI에서 Stage2 report 의미 수정
- Web UI에서 context-only를 finding/incident로 승격
- Web UI에서 raw secret/config/provider key 노출
```

## 2. 기존 viewer-only 문서와의 관계

`99_run_analysis_pipeline_user_runner_ux_review.md`의 2026-05-08 기준은 viewer-only console 검토였다.

당시 기준:

```text
Web UI = read-only report viewer
pipeline 실행 = 분석 엔지니어 CLI 실행
DB write = Web UI 범위 밖
```

2026-05-28 이후 DB-backed MVP 기준:

```text
Web UI = report/security interpretation은 read-only
Web UI = analysis_jobs 등록/조회는 허용
Analysis Job Worker = DB의 PENDING job을 claim하고 full_report pipeline 실행
CLI = fallback/debug/manual path로 유지
```

따라서 과거 문서의 `read-only` 표현은 다음처럼 해석한다.

```text
read-only report/security interpretation:
- 유지

read-only job lifecycle:
- 더 이상 전체 원칙이 아님
- DB-backed MVP에서는 analysis_jobs write/read 허용
```

## 3. DB 사용 금지 원칙의 재해석

과거 Web UI viewer-only 원칙에는 `DB/SQLite 저장 없음` 또는 `DB 사용 금지`에 가까운 표현이 있었다.

DB-backed MVP에서는 이 원칙을 그대로 유지할 수 없다.

새 기준:

```text
Web UI는 보안 분석 결과를 재계산/재판정하기 위해 DB를 쓰지 않는다.
Web UI는 job lifecycle 관리와 artifact metadata 조회를 위해 DB를 사용할 수 있다.
```

허용 DB 사용:

```text
- users 인증/권한 확인
- analysis_jobs 등록/조회
- job_events 조회
- analysis_reports artifact 경로 조회
```

금지 DB 사용:

```text
- UI에서 새 finding/incident 생성
- UI에서 severity/category/verdict 수정
- UI에서 Stage2 report 의미를 덮어쓰기
- UI에서 context-only 항목을 finding으로 승격
```

## 4. Web UI 표시 정책

DB-backed MVP의 Web UI는 job 등록/상태 조회 기능을 갖더라도, report 표시 정책은 기존 Apache logs-only boundary를 유지한다.

### 4.1 Stage2 report 의미 보존

```text
- Stage2 report 원문 의미를 변경하지 않는다.
- viewer_payload는 Stage2 report를 UI 표시용으로 정규화할 수 있지만, 새 결론을 만들지 않는다.
- UI는 Stage2 결과를 더 강한 verdict/success 표현으로 바꾸지 않는다.
```

금지 예:

```text
- suspicious attempt -> confirmed compromise
- observed request -> successful exploit
- context-only auth signal -> account takeover finding
```

### 4.2 IP masking 유지

```text
- Web UI는 기존 IP masking 정책을 유지한다.
- list/detail/search/filter에서 raw source IP 전체 노출을 기본값으로 두지 않는다.
- 운영자/개발자 debug path가 필요하면 별도 권한/환경변수/CLI 범위에서 검토한다.
```

### 4.3 raw preview 과노출 금지

기본 Web UI에서는 다음을 원문 preview로 직접 노출하지 않는다.

```text
- raw_log 전체
- raw_request 전체
- raw header 전체
- Cookie 값
- Authorization 값
- request body
- response body
- API key/token/secret 후보 문자열
```

허용되는 표시는 최소 metadata 중심으로 제한한다.

```text
- method
- uri 또는 normalized route
- status_code
- response_body_bytes
- duration_us / ttfb_us
- masked src_ip
- request_id / error_link_id
- presence flag: has_cookie, has_authorization
```

### 4.4 known asset / metadata 표시 주의

```text
- known asset, static baseline, crawler baseline, topology hint는 context로 표시한다.
- 이 정보를 finding/incident처럼 보이게 하지 않는다.
- metadata는 observed context이지 exploit success evidence가 아니다.
```

### 4.5 missing provider 표시

provider/model/report component가 없을 때는 다음처럼 표시한다.

```text
- 표시값: N/A
- missing provider에는 detail link를 만들지 않는다.
- missing provider를 오류나 보안 신호로 과장하지 않는다.
```

예:

```text
provider: N/A
model: N/A
stage2_report: N/A
```

## 5. Secret / config / provider key 보호

Analysis Agent는 Stage1/Stage2 실행을 위해 LLM provider 설정을 사용할 수 있다.

MVP에서 다음을 금지한다.

```text
- Web UI에 API key 표시
- Web UI에 `.env` 내용 표시
- job_events.detail_json에 API key 저장
- analysis_jobs.error_message에 API key 저장
- provider raw error response를 그대로 UI에 표시
- artifact path 외부에 config dump 저장
```

오류 메시지 저장 원칙:

```text
- provider 이름, step 이름, 실패 종류는 저장 가능
- secret/token/key/value는 redaction 후 저장
- HTTP response body 원문은 기본 저장하지 않음
- 필요 시 local debug log에만 제한적으로 기록하고 Web UI 노출 금지
```

예:

```text
허용:
STAGE2_FAILED: provider=openai reason=timeout

금지:
STAGE2_FAILED: Authorization=Bearer sk-...
```

## 6. analysis_jobs 입력 검증 정책

### 6.1 시간 범위 기본 검증

MVP에서 job 등록 API는 최소 다음을 검증한다.

```text
- time_from < time_to
- requested_timezone == Asia/Seoul
- analysis_mode == full_report
- time range가 최대 허용 범위를 넘지 않음
```

### 6.2 time range 상한

초기 MVP 기본 후보:

```text
max_time_range = 24 hours
```

정책:

```text
- 일반 Web UI 요청은 24시간 이하로 제한한다. 이는 권장값이 아니라 허용 상한이다.
- 더 긴 범위는 관리자/CLI/manual batch path에서 별도 검토한다.
- 제한 초과 요청은 job을 만들지 않고 validation error를 반환한다.
```

주의:

```text
이 값은 운영 성능과 LLM 비용을 보고 조정할 수 있다.
다만 MVP 구현 전에는 상한 없는 job 등록을 허용하지 않는다.
```

### 6.3 requested_timezone

MVP 기본값:

```text
Asia/Seoul
```

정책:

```text
- MVP Web UI는 Asia/Seoul 입력/표시를 기본으로 한다.
- requested_timezone이 Asia/Seoul이 아니면 v1에서는 validation error로 처리한다.
- 다중 timezone 지원은 v1.1 후보로 둔다.
```

### 6.4 analysis_mode

MVP 허용값:

```text
full_report
```

보류 값:

```text
windowed_triage
selected_rollup_brief
selected_rollup_full_report
observation_brief_only
```

## 7. 중복 job 처리 정책

MVP에서는 동일 사용자가 같은 분석 범위를 반복 등록하는 경우를 제한한다.

중복 판단 key 후보:

```text
requested_by
analysis_mode
time_from
time_to
requested_timezone
```

정책:

```text
- 같은 key의 PENDING job이 있으면 새 job을 만들지 않고 기존 job을 반환한다.
- 같은 key의 RUNNING job이 있으면 새 job을 만들지 않고 기존 job을 반환한다.
- 같은 key의 SUCCEEDED job은 새 rerun 허용 여부를 UI에서 명시적으로 선택하게 한다.
- 같은 key의 FAILED job은 rerun 허용 후보로 둔다.
```

MVP 최소 구현 후보:

```text
- PENDING/RUNNING 중복만 차단
- SUCCEEDED/FAILED는 새 job 생성 허용
- 추후 rerun_of_job_id 컬럼 도입 검토
```

## 8. Artifact overwrite / allowed path 정책

### 8.1 artifact_root

MVP artifact root는 job 단위로 분리한다.

예:

```text
runs/jobs/<job_id>/
```

또는:

```text
runs/web_job_<job_id>/
```

정책:

```text
- 서로 다른 job은 같은 artifact_root를 공유하지 않는다.
- 기본값에서는 기존 artifact를 overwrite하지 않는다.
- 재실행이 필요하면 새 job_id 또는 명시적 rerun artifact_root를 사용한다.
```

### 8.2 allowed path

Web UI/API 입력으로 임의의 output path를 받지 않는다.

허용:

```text
- 서버 설정의 ARTIFACT_ROOT 하위 자동 생성 경로
- job_id 기반 deterministic path
```

금지:

```text
- 사용자가 입력한 절대경로로 export/report 저장
- `../` path traversal 포함 경로
- work_dir 밖 artifact write
- Web UI에서 임의 파일 읽기
```

## 9. Export / pipeline timeout 정책

long-running query와 장시간 LLM 실행은 MVP에서 실패 상태로 관리한다.

기본 정책 후보:

```text
- export timeout
- prepare timeout
- Stage1 timeout
- Stage2 timeout
- viewer_payload timeout
```

MVP 최소:

```text
- 각 step timeout 값을 config로 둔다.
- timeout 발생 시 job_events에 실패 step을 기록한다.
- analysis_jobs.status를 FAILED로 변경한다.
- partial artifact_root는 삭제하지 않고 디버깅용으로 보존한다.
```

## 10. Retention / cleanup 정책

MVP에서는 자동 삭제를 하지 않는다.

정책:

```text
- artifact_root는 job_id 기준으로 보존한다.
- Web UI에서 destructive cleanup 버튼은 제공하지 않는다.
- cleanup은 별도 승인 전까지 CLI/manual operation 후보로 둔다.
- retention policy는 v1.1에서 정의한다.
```

표시 가능 항목:

```text
- artifact_root path
- artifact created_at
- artifact size 후보
- retention policy: not_configured
```

금지:

```text
- Web UI에서 임의 artifact 삭제
- failed job artifact 자동 삭제
- old run 자동 정리
```

## 11. Log Collector flag 생성 원칙

`apache_security_logs.has_cookie`, `apache_security_logs.has_authorization`는 raw header 값을 저장하지 않는 privacy-preserving presence flag다.

정책:

```text
- Apache log format 또는 shipper parsing 단계에서 presence만 추출한다.
- Cookie 값과 Authorization 값은 DB에 저장하지 않는다.
- Web UI에는 presence flag만 표시할 수 있다.
- presence flag만으로 로그인 성공, 권한 상승, 계정 탈취를 단정하지 않는다.
```

## 12. Execution Console Risk 대응 상태

안수홍 검토의 risk 항목을 다음처럼 정리한다.

```text
output overwrite
  - job-scoped artifact_root로 대응
  - 기존 artifact overwrite 금지

allowed input path
  - Web UI/API에서 임의 path 입력 금지
  - ARTIFACT_ROOT 하위 자동 경로만 사용

API key/config exposure
  - Web UI/job_events/error_message secret 노출 금지
  - provider raw error redaction

long-running process
  - step timeout + FAILED 상태 + job_events 기록
  - heartbeat/stale worker recovery는 v1.1 후보

failure log display
  - error_message + job_events 표시
  - secret redaction 필요

concurrent execution
  - atomic claim 유지

auth/authorization
  - users 최소 테이블
  - 세밀한 권한은 v1.1 후보
  - MVP에서는 job 등록 가능 사용자 범위를 제한

cleanup/retention
  - MVP 자동 삭제 없음
  - Web UI destructive cleanup 없음
  - retention은 v1.1 후보
```

## 13. 다음 구현 전 체크리스트

DB schema/migration 구현 전에 다음을 반영한다.

```text
- analysis_jobs validation policy
- duplicate PENDING/RUNNING job handling
- artifact_root naming
- secret redaction helper
- job_events message whitelist 또는 redaction rule
- Web UI 표시 정책: IP masking, N/A, missing detail link 금지
- requested_timezone v1 제한
- max_time_range 설정값
```

## 14. 요약

DB-backed MVP 방향은 유지한다.

다만 기존 viewer-only 원칙은 다음처럼 좁혀서 유지한다.

```text
보안 결과 해석은 read-only.
job lifecycle은 DB-backed write/read 허용.
```

MVP의 핵심 경계는 다음이다.

```text
Web UI는 job을 등록할 수 있다.
Analysis Agent는 job을 실행할 수 있다.
하지만 Web UI와 Agent는 Apache logs-only evidence boundary를 넘어 새 성공/침해/유출 판단을 만들 수 없다.
```
