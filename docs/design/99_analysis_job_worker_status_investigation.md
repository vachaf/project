# Analysis Job Worker Status Investigation

- 문서 상태: 조사 기록
- 기준 시점: 2026-06-01
- 목적: DB-backed `analysis_jobs` worker/agent 연결 구현 상태와 문서 상태의 mismatch를 코드 수정 없이 확인한다.
- 범위: `full_report` DB-backed MVP worker/runner/Web UI/report artifact 연결.

## 1. 조사 기준

기준 관련 커밋:

- `28a819e`: Finding <-> Contexts / supporting_events 조사 문서
- `870f532`: viewer_payload relation contract 도입
- `ee1e5d5`: Web UI theme/readability polish

현재 checkout의 최근 로그 기준 HEAD는 `ee1e5d5`이고, 그 사이 `13ce8d9 ops: add analysis job worker systemd example`, `1f268f9 systemd`, `1006085 feat: improve job status guidance in web UI`, `a8e807e fix: require artifact root for job artifact routes` 등이 worker/UI 운영 문서와 상태 표시를 보강했다.

실행한 명령:

```bash
git status --short
git log --oneline -12
rg -n "analysis_job_worker|full_report_job_runner|AnalysisJobRepository|analysis_jobs|analysis_reports|job_events|PENDING|RUNNING|SUCCEEDED|FAILED|claim|worker|agent|run_analysis_pipeline|viewer_payload_path|stage2_report_path|lint_result|artifact_root|attempt_count|retry|stale|poll" src web tests docs 작업일지 README* pyproject.toml
find src web tests docs 작업일지 -maxdepth 4 -type f | sort | rg "analysis_job|full_report|worker|runner|pipeline|report|viewer|진행상황|TODO|design|operation|job"
find tests -maxdepth 2 -type f | sort | rg "job|worker|runner|full_report|pipeline|viewer"
python3 -m py_compile src/analysis_job_worker.py src/full_report_job_runner.py src/run_analysis_pipeline.py web/app.py
python3 -m pytest -q tests/test_analysis_job_worker.py tests/test_full_report_job_runner.py tests/test_web_job_viewer_route.py
rg -n "runs/jobs|job-scoped|analysis_reports|viewer_payload_path|PENDING -> RUNNING|RUNNING -> SUCCEEDED|worker smoke|full_report job|job runner|agent" docs 작업일지 tests src web
rg -n "JOB_STARTED|JOB_CLAIMED|JOB_SUCCEEDED|JOB_FAILED|JOB_NO_DATA|EXPORT_STARTED|STAGE1_STARTED|STAGE2_STARTED|VIEWER_PAYLOAD_WRITTEN" src web tests docs 작업일지
rg -n "retry|attempt_count|max_attempts|stale|heartbeat|recover|recovery|CANCELLED|cancel|requeue|PENDING" src web tests docs/operations docs/design docs/planning 작업일지
```

명령 결과 요약:

- `git status --short`: 출력 없음.
- `git log --oneline -12`: HEAD `ee1e5d5`, 최근 worker/systemd 관련 커밋 `13ce8d9`, `1f268f9` 확인.
- 첫 `rg`는 `pyproject.toml` 부재로 exit code 2였지만 관련 hit는 출력됨. repo root에 `pyproject.toml`이 없다.
- `py_compile`: 통과.
- 핵심 테스트: `68 passed in 0.48s`.

조사한 주요 코드/테스트/문서:

- 코드: `src/analysis_job_worker.py`, `src/full_report_job_runner.py`, `src/run_analysis_pipeline.py`, `web/app.py`, `web/services/analysis_job_repository.py`, `web/services/analysis_job_policy.py`
- schema/ops: `docs/operations/sql/01_analysis_job_tables.sql`, `docs/operations/analysis_job_worker.md`, `ops/systemd/web-log-analysis-worker.service.example`
- 테스트: `tests/test_analysis_job_worker.py`, `tests/test_full_report_job_runner.py`, `tests/test_analysis_job_repository_lifecycle.py`, `tests/test_web_job_viewer_route.py`, `tests/test_web_job_artifact_routes.py`, `tests/test_web_job_status_guidance.py`
- 문서: `docs/진행상황.md`, `docs/planning/99_비교실험_후속개선_TODO.md`, `docs/design/99_db_backed_log_collection_and_analysis_job_design.md`, `docs/design/99_analysis_job_modes_and_sliding_window_integration.md`, `docs/operations/analysis_job_worker.md`, `README.md`, `web/README.md`, `작업일지/0531.md`

## 2. 현재 구현 상태 요약

| 기능 | 상태 | 근거 파일/테스트 | 비고 |
| --- | --- | --- | --- |
| job 생성 | implemented | `web/app.py`, `web/services/analysis_job_repository.py`, `web/services/analysis_job_policy.py` | `/new-job`, `/api/jobs/create`가 validation 후 `analysis_jobs(PENDING)` 생성. PENDING/RUNNING duplicate active job 방지 포함. |
| job claim | implemented | `web/services/analysis_job_repository.py`, `tests/test_analysis_job_repository_lifecycle.py` | `SELECT ... FOR UPDATE` 후 `UPDATE ... WHERE id=%s AND status='PENDING'`. `attempt_count < max_attempts` 조건 포함. |
| PENDING -> RUNNING | implemented | `claim_next_pending_full_report_job`, `tests/test_analysis_job_repository_lifecycle.py` | `worker_id`, `started_at`, `heartbeat_at`, `attempt_count+1`, `error_message=NULL` 갱신. |
| full_report runner 연결 | implemented | `src/analysis_job_worker.py`, `src/full_report_job_runner.py`, `tests/test_analysis_job_worker.py`, `tests/test_full_report_job_runner.py` | worker가 `FullReportJobRunner.run()`을 호출하고 runner가 `export_db_logs_cli.py`와 `run_analysis_pipeline.py`를 subprocess로 실행. |
| artifact 생성 | implemented | `src/full_report_job_runner.py`, `tests/test_full_report_job_runner.py`, `작업일지/0531.md` | 정상 full_report는 `runs/jobs/<id>`에 export, llm_input, noise_summary, stage1, stage2, viewer payload 생성. no-data는 export only. |
| analysis_reports mapping | partial | `FullReportRunResult`, `AnalysisJobRepository.upsert_analysis_report`, tests | direct full_report 필수 경로는 저장됨. `lint_result_path`는 현재 runner에서 항상 `None`; `manifest_path`, `stage2_report_input_path`는 schema/upsert 대상 아님. |
| viewer_payload_path 연결 | implemented | `src/full_report_job_runner.py`, `web/app.py`, `web/templates/job_detail.html`, `tests/test_web_job_viewer_route.py` | report row의 `viewer_payload_path`로 `/job/{id}/viewer`와 raw artifact route 연결. job-scoped path 검증 포함. |
| job_events 기록 | partial | `web/services/analysis_job_repository.py`, `src/analysis_job_worker.py`, tests | `JOB_CREATED`, `JOB_CLAIMED`, `JOB_STARTED`, `JOB_NO_DATA`, `JOB_SUCCEEDED`, `JOB_FAILED` 기록. schema 문서의 세부 stage event(`EXPORT_STARTED`, `STAGE1_STARTED` 등)는 아직 미기록. |
| failure handling | implemented | `src/analysis_job_worker.py`, `mark_job_failed`, tests | runner/upsert 예외 시 redaction 후 `FAILED`, `error_message`, `JOB_FAILED` 기록. claim 전 예외는 job id가 없어 mark failed 하지 않음. |
| retry/attempt_count | partial | schema/repository/tests | claim 시 `attempt_count` 증가 및 `attempt_count < max_attempts` skip은 구현. FAILED를 PENDING으로 되돌리는 retry API/UI/CLI는 없음. 기본 `max_attempts=1`. |
| stale RUNNING recovery | missing | `docs/operations/analysis_job_worker.md`, `docs/design/99_db_backed_log_collection_and_analysis_job_design.md` | heartbeat update는 구현됐지만 stale 판단/복구/재queue/실패 전환 없음. 문서도 후속 TODO로 둠. |
| UI job detail/report link | implemented | `web/app.py`, `web/templates/job_detail.html`, `tests/test_web_job_status_guidance.py`, `tests/test_web_job_artifact_routes.py` | job detail, events, report artifact list, Open Viewer, artifact open route 제공. |
| tests | implemented | `tests/test_analysis_job_worker.py`, `tests/test_full_report_job_runner.py`, `tests/test_web_job_viewer_route.py` | 요청된 핵심 테스트 68개 통과. repository lifecycle, artifact routes, status guidance 테스트도 존재. |

## 3. 구현 흐름도

### Web job creation

```text
GET /new-job
  -> form default range 표시

POST /new-job 또는 POST /api/jobs/create
  -> validate_analysis_job_request()
  -> AnalysisJobRepository.create_job()
  -> duplicate active PENDING/RUNNING job 확인
  -> analysis_jobs row 생성(status=PENDING)
  -> artifact_root = runs/jobs/<job_id> 저장
  -> JOB_CREATED event 저장
  -> /job/<job_id> redirect 또는 JSON 반환
```

### Worker claim

```text
python3 src/analysis_job_worker.py --once --run-pipeline
또는
python3 src/analysis_job_worker.py --run-pipeline --sleep-seconds 5

  -> claim_next_pending_full_report_job(worker_id)
  -> transaction
  -> SELECT PENDING full_report attempt_count < max_attempts FOR UPDATE
  -> UPDATE status=RUNNING, worker_id, started_at, heartbeat_at, attempt_count+1
  -> JOB_CLAIMED event
```

### Runner execution

```text
analysis_job_worker._run_claimed_pipeline()
  -> JOB_STARTED event
  -> HeartbeatLoop start
  -> FullReportJobRunner.run(claimed)
     -> validate full_report / Asia/Seoul / artifact_root
     -> fail-fast if artifact_root already exists
     -> export_db_logs_cli.py --start ... --end ... --out runs/jobs/.scratch/job_<id>/job_<id>_export.json
     -> no-data이면 runs/jobs/<id>/export.json만 materialize
     -> 아니면 run_analysis_pipeline.py --export-input ... --work-dir scratch --run-dir runs/jobs/<id>
  -> HeartbeatLoop stop
```

### Artifact persistence

```text
normal full_report:
  runs/jobs/<id>/export.json
  runs/jobs/<id>/llm_input.json
  runs/jobs/<id>/analysis_candidates.json  # 있으면 저장
  runs/jobs/<id>/noise_summary.json
  runs/jobs/<id>/stage1_results.json
  runs/jobs/<id>/stage2_report.json
  runs/jobs/<id>/stage2_report.md
  runs/jobs/<id>/viewer_payload.json

no-data:
  runs/jobs/<id>/export.json
  stage/viewer paths = NULL
  JOB_NO_DATA event
```

### DB report row

```text
FullReportRunResult
  -> _result_to_upsert_kwargs()
  -> AnalysisJobRepository.upsert_analysis_report()
  -> analysis_reports UNIQUE(job_id) upsert
  -> mark_job_succeeded()
  -> analysis_jobs.status=SUCCEEDED
  -> JOB_SUCCEEDED event
```

### Web detail/viewer display

```text
/job/{id}
  -> get_job()
  -> get_job_events()
  -> get_latest_report_for_job()
  -> job_detail.html
     -> status/worker/heartbeat/attempt/error
     -> event timeline
     -> analysis_reports artifact links
     -> Open Viewer if viewer_payload_path exists

/job/{id}/viewer
  -> latest report row
  -> validate viewer_payload_path is relative, under project root, under artifact_root, existing file
  -> load viewer_payload JSON
  -> payload_detail.html read-only dashboard
```

## 4. DB schema/route 상태

| 영역 | 현재 상태 |
| --- | --- |
| `analysis_jobs` fields | DDL과 repository가 `requested_by`, `time_from`, `time_to`, `requested_timezone`, `status`, `analysis_mode`, `created_at`, `started_at`, `finished_at`, `worker_id`, `heartbeat_at`, `attempt_count`, `max_attempts`, `error_message`, `artifact_root`를 사용한다. `created_by/requested_user_id`라는 별도 컬럼은 없고 `requested_by`가 그 역할이다. |
| `job_events` fields | DDL은 `id`, `job_id`, `event_time`, `event_type`, `message`, `detail_json`. 코드도 같은 컬럼에 append한다. `created_at`이 아니라 `event_time`이다. |
| `analysis_reports` fields | DDL/repository는 direct report paths와 window/rollup/operator future paths를 포함한다. `manifest_path`, `stage2_report_input_path`는 없음. |
| worker/runner | claim, heartbeat, export, direct pipeline, report upsert, success/failure close가 구현됨. idempotency/resume은 제한적이다. 기존 `artifact_root`가 있으면 fail-fast하고 stale/retry resume은 없다. |
| Web UI | `/`, `/new-job`, `/api/jobs/create`, `/job/{id}`, `/job/{id}/artifact/{artifact_key}`, `/job/{id}/viewer`, `/api/job/{id}/status`가 있다. UI가 worker/pipeline을 직접 실행하지 않는 테스트가 있다. 시작/재시도/취소 버튼은 없다. |

## 5. 문서 상태 비교

| 문서 | 현재 주장 | 실제 코드 상태와 일치 여부 | 필요한 수정 |
| --- | --- | --- | --- |
| `docs/진행상황.md` | 2026-05-31 smoke 기준으로 Web UI 등록, worker `--run-pipeline`, Stage1/Stage2/viewer, `analysis_reports`, `/job/{id}/viewer` 확인. 다음 우선순위에 worker loop/daemon 운영화 포함. | 부분 일치. smoke와 core 구현 설명은 맞다. 다만 현재 코드는 loop mode, heartbeat loop, systemd 예시까지 있으므로 "worker loop/daemon 운영화"는 너무 넓은 TODO다. | "loop CLI/systemd 예시는 구현됨, 남은 것은 운영 배포/health/stale recovery/graceful shutdown"처럼 좁혀야 한다. |
| `docs/planning/99_비교실험_후속개선_TODO.md` | 완료: DB-backed smoke. TODO: worker loop/daemon 운영화, timeout/heartbeat 정책 강화. | 부분 mismatch. loop CLI는 `--run-pipeline`, `--sleep-seconds`, `--max-jobs`로 구현됐고 systemd 예시도 있다. heartbeat update도 구현됐지만 운영 정책/stale recovery는 남았다. | TODO를 `worker loop/daemon 배포 검증`, `worker health/stale recovery`, `retry/cancel UI` 등으로 재분류. |
| `docs/design/99_db_backed_log_collection_and_analysis_job_design.md` | 설계 문서로 Analysis Agent claim/full_report/report 저장을 정의. 다음 구현 후보에 schema/API/worker/repository/runner/artifact 연결이 남은 것처럼 적힌 섹션 존재. | 부분 mismatch. 설계 원칙은 맞지만 15.2 "다음 구현 후보"의 다수 항목은 이미 구현됐다. stage별 job_events를 기록한다고 쓰인 부분은 실제보다 강하다. | 구현 완료 표시 또는 "historical plan" 표시 추가. stage-level events는 remaining gap으로 표시. |
| `docs/design/99_analysis_job_modes_and_sliding_window_integration.md` | 2026-05-31 smoke 기준 full_report direct path 확인, sliding_window는 후속 mode. | 일치. | 큰 수정 불필요. worker loop/systemd 최신 상태 링크 추가 정도. |
| `docs/operations/analysis_job_worker.md` | worker polling/claim/full_report/report close, loop smoke, systemd 예시, stale recovery TODO. | 대체로 일치. | 가장 최신 운영 문서로 보인다. retry/cancel 미구현, stage-level events 미기록을 더 명시하면 좋다. |
| `ops/systemd/web-log-analysis-worker.service.example` | background worker service 예시. | 일치. | 실제 배포 검증 여부만 별도 운영 로그로 남기면 된다. |
| `작업일지/0531.md` | 실제 `--once --run-pipeline` smoke와 no-data smoke 기록. 후속 TODO에 worker loop/daemon 운영화. | 부분 mismatch. 당시 기록으로는 맞지만 이후 loop/systemd 커밋이 들어왔다. | 작업일지 자체를 고치기보다 최신 진행상황/TODO에서 "0531 당시 TODO였으나 이후 일부 구현"으로 연결하는 편이 안전하다. |
| `README.md`, `web/README.md` | DB-backed MVP에서 worker가 full_report를 실행하고 Web UI는 등록/조회/read-only display를 담당. | 일치. | 현 상태 유지 가능. |

## 6. Confirmed / Likely / Unknown

### Confirmed implemented

- Web UI job 생성과 duplicate active job 처리.
- `analysis_jobs` PENDING -> RUNNING claim.
- claim transaction과 row lock 기반 race 방지.
- worker CLI entrypoint: `src/analysis_job_worker.py`.
- one-shot 실행: `--once`.
- polling loop: `--run-pipeline` loop mode, `--sleep-seconds`, `--max-jobs`.
- heartbeat update loop.
- `full_report` runner 연결: `export_db_logs_cli.py` + `run_analysis_pipeline.py`.
- job-scoped `runs/jobs/<id>` artifact root.
- `analysis_reports` upsert와 job detail/report artifact display.
- `/job/{id}/viewer` viewer payload dashboard 연결.
- failure handling: `FAILED`, `error_message`, `JOB_FAILED`, secret redaction.
- no-data handling: `JOB_NO_DATA`, `SUCCEEDED`, export only.
- systemd example file.

### Confirmed missing

- FAILED job retry API/CLI/UI.
- stale `RUNNING` recovery.
- cancel/cancelled state UI/API/worker handling.
- worker health endpoint 또는 Web UI worker status 표시.
- stage-level job event emission for export/prepare/stage1/stage2/viewer payload.
- Web UI에서 실행 시작/재시도/취소 기능. 현재 Web UI는 job 등록만 하고 worker 실행은 운영자/서비스 책임이다.
- `lint_result_path` 생성/저장 연결. schema와 UI key는 있지만 runner는 `None`을 반환한다.
- `manifest_path`와 `stage2_report_input_path`의 DB mapping. 현재 schema에 없다.

### Partial

- retry/attempt count: `attempt_count`와 `max_attempts` 기반 claim skip은 있으나 retry workflow는 없다.
- concurrency: claim race 방지는 transaction/`FOR UPDATE`/conditional update로 구현됐지만, 운영 권장은 아직 1 worker이고 multi-worker 운영 검증은 문서상 제한적이다.
- analysis_reports mapping completeness: direct full_report 핵심 viewer/report paths는 저장하지만 lint/manifest/stage2 input은 빠져 있다.
- daemon 운영화: CLI loop와 systemd 예시는 구현됐지만 실제 운영 배포/health/recovery까지 완료로 보기 어렵다.
- job_events: lifecycle 핵심 event는 있지만 schema 문서의 세부 단계 event는 없다.

### Unknown / needs live DB smoke

- 현재 운영 DB에서 최신 schema가 모두 적용되어 있는지.
- systemd unit이 실제 서버 계정/경로/env로 enable/start되어 장시간 실행 중인지.
- 다중 worker를 실제 MariaDB에서 동시에 실행했을 때 lock wait/timeout 운영 특성이 허용 가능한지.
- real LLM 장시간 실행 중 heartbeat interval/timeout 값이 운영 환경에서 충분한지.
- partial artifact가 남은 실패 job의 수동 복구 절차가 실제 운영에서 충분한지.

## 7. 다음 작업 후보

### 문서 반영 후보

- `docs/진행상황.md`: worker loop CLI와 systemd 예시는 구현됨으로 갱신하고, 남은 항목을 stale recovery/health/retry/cancel/운영 배포 검증으로 좁힌다.
- `docs/planning/99_비교실험_후속개선_TODO.md`: `worker loop/daemon 운영화`를 더 이상 단일 미구현 항목으로 두지 말고, 완료/남은 작업을 분리한다.
- `docs/design/99_db_backed_log_collection_and_analysis_job_design.md`: 15.2 구현 후보 중 구현 완료된 항목을 표시하거나 historical plan으로 격리한다.
- `docs/operations/analysis_job_worker.md`: stage-level events, retry/cancel, lint/manifest mapping 미구현을 운영 주의사항에 명시한다.
- `작업일지/0531.md`: 과거 일지라 직접 수정보다 최신 진행상황에서 후속 커밋으로 일부 해소됐음을 참조하는 방식이 적절하다.

### 코드 보완 후보

- retry/requeue CLI 또는 repository method: `FAILED` 중 retry 가능한 job만 `PENDING`으로 전환.
- stale `RUNNING` recovery: heartbeat timeout 기준, manual recovery CLI, event 기록.
- worker health/status: Web UI 또는 `/api`에서 worker heartbeat/last claim visibility 제공.
- stage-level job_events: export/pipeline/stage artifacts 단계 이벤트를 runner 또는 worker wrapper에서 기록.
- `lint_result_path` 연결: Stage2 lint 실행 여부를 정하고 artifact mapping에 포함.
- optional artifact mapping 검토: `manifest_path`, `stage2_report_input_path`를 DB에 저장할지 결정.
- Web UI retry/cancel buttons: 실제 repository/worker semantics가 정리된 뒤 추가.
