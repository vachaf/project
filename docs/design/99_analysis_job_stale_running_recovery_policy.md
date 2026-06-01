# Analysis Job Stale RUNNING Recovery Policy

- 문서 상태: 설계 정책 초안
- 기준 시점: 2026-06-01
- 목적: DB-backed `analysis_jobs`에서 worker 중단으로 남는 stale `RUNNING` job의 판단/복구 정책을 정한다.
- 범위: `analysis_mode=full_report` DB-backed MVP worker 운영 정책. 이번 문서는 정책 설계이며 코드/DB schema/worker/Web UI 변경을 포함하지 않는다.

관련 문서:

- [99_analysis_job_worker_status_investigation.md](./99_analysis_job_worker_status_investigation.md)
- [../operations/analysis_job_worker.md](../operations/analysis_job_worker.md)
- [../operations/sql/01_analysis_job_tables.sql](../operations/sql/01_analysis_job_tables.sql)
- [99_db_backed_web_ui_api_safety_addendum.md](./99_db_backed_web_ui_api_safety_addendum.md)

## 1. 목적과 범위

현재 DB-backed full_report worker MVP는 다음 경로가 구현되어 있다.

```text
Web UI job 생성
  -> analysis_jobs(PENDING)
  -> worker claim
  -> RUNNING
  -> export_db_logs_cli.py
  -> run_analysis_pipeline.py
  -> runs/jobs/<id> artifact 생성
  -> analysis_reports upsert
  -> SUCCEEDED 또는 FAILED
```

남은 운영 gap은 worker process가 죽거나 host/systemd가 재시작되는 동안 `analysis_jobs.status='RUNNING'` row가 닫히지 않는 경우다. `heartbeat_at`은 실행 중 갱신되지만, stale 판단과 recovery는 아직 자동화되어 있지 않다.

이 문서의 목표:

- stale `RUNNING` 판단 기준 후보를 비교한다.
- 자동 재실행보다 안전한 MVP recovery 정책을 고정한다.
- 후속 repository/CLI/Web/test 구현 후보를 정리한다.

이 문서에서 하지 않는 것:

- 코드 수정
- DB schema 수정
- worker/pipeline 동작 수정
- Web UI 수정
- 자동 requeue 구현
- artifact 삭제/정리 구현

## 2. 현재 lifecycle 요약

### Claim 조건

현재 repository claim은 다음 조건의 job만 가져간다.

```text
status = 'PENDING'
analysis_mode = 'full_report'
attempt_count < max_attempts
ORDER BY created_at ASC, id ASC
FOR UPDATE
```

claim 성공 시 같은 transaction에서 다음 값을 갱신한다.

```text
status = 'RUNNING'
started_at = COALESCE(started_at, UTC_TIMESTAMP(3))
worker_id = <worker_id>
heartbeat_at = UTC_TIMESTAMP(3)
attempt_count = attempt_count + 1
error_message = NULL
JOB_CLAIMED event
```

중요한 결과:

- `RUNNING` job은 다시 claim 대상이 아니다.
- `attempt_count`는 claim 순간 증가한다.
- 기본 `max_attempts=1`이면 한번 claim된 job은 자동 retry 대상이 아니다.
- stale `RUNNING`은 별도 recovery 경로 없이는 남는다.

### Heartbeat update

worker는 pipeline 실행 동안 `HeartbeatLoop`로 `update_job_heartbeat(job_id, worker_id)`를 주기적으로 호출한다.

현재 update 조건:

```text
WHERE id = <job_id>
  AND status = 'RUNNING'
  AND worker_id = <worker_id>
```

의미:

- 같은 worker_id의 `RUNNING` job만 heartbeat를 갱신한다.
- worker가 죽으면 `heartbeat_at`이 멈춘다.
- 다른 worker가 기존 `RUNNING` job heartbeat를 이어받지 않는다.

### Success/failure close

성공 시:

```text
status = 'SUCCEEDED'
finished_at = UTC_TIMESTAMP(3)
heartbeat_at = UTC_TIMESTAMP(3)
error_message = NULL
JOB_SUCCEEDED event
```

실패 시:

```text
status = 'FAILED'
finished_at = UTC_TIMESTAMP(3)
heartbeat_at = UTC_TIMESTAMP(3)
error_message = redacted error
JOB_FAILED event
```

두 close 모두 `status='RUNNING' AND worker_id=<worker_id>` 조건을 요구한다.

### Artifact root 처리

job 생성 후 `artifact_root`는 `runs/jobs/<job_id>` 형태로 저장된다. runner는 실행 시작 시 resolved `artifact_root`가 이미 존재하면 fail-fast 한다.

```text
if artifact_root_path.exists():
    raise FileExistsError(...)
```

의미:

- stale job을 단순히 `PENDING`으로 되돌리면 같은 `artifact_root`를 재사용하게 된다.
- 기존 artifact_root가 partial로 남아 있으면 재실행이 fail-fast 되거나, 정책 없이 삭제하면 디버깅 근거가 사라진다.
- 따라서 stale recovery와 retry/rerun은 분리해야 한다.

### Partial artifact 가능성

worker가 죽은 시점에 따라 다음 상태가 가능하다.

| 중단 시점 | 가능한 잔여물 |
| --- | --- |
| claim 직후 | `analysis_jobs(RUNNING)`, `JOB_CLAIMED`, `JOB_STARTED`, artifact 없음 |
| export 중 | scratch export 일부 또는 없음 |
| no-data materialize 직후 | `runs/jobs/<id>/export.json`은 있으나 job close 전 |
| pipeline 중 | `runs/jobs/<id>` 일부 파일 또는 scratch work dir |
| report upsert 전후 | artifact는 있으나 `analysis_reports`가 없거나 불완전할 수 있음 |
| success/failure close 직전 | `analysis_reports`는 있으나 `analysis_jobs`가 RUNNING일 수 있음 |

이 때문에 자동 artifact 삭제나 자동 requeue는 MVP에서 위험하다.

## 3. stale RUNNING 발생 시나리오

대표 시나리오:

- worker process가 SIGKILL/OOM으로 종료된다.
- host reboot 또는 container stop으로 heartbeat thread가 멈춘다.
- systemd가 worker를 재시작하지만 기존 `RUNNING` job은 `PENDING`이 아니므로 새 worker가 claim하지 않는다.
- LLM provider call 또는 subprocess가 hang 된 뒤 worker가 강제 종료된다.
- DB connection failure 중 worker가 종료되어 close transaction을 수행하지 못한다.
- operator가 worker를 수동 stop 했으나 진행 중 job을 먼저 실패 처리하지 않았다.

현재 systemd restart와의 관계:

- systemd restart는 process availability만 회복한다.
- 기존 `RUNNING` row를 자동 회수하지 않는다.
- 새 worker loop는 `PENDING`만 claim하므로 stale `RUNNING`은 계속 남는다.

## 4. stale 판단 기준 후보

| 후보 | 장점 | 위험/한계 | MVP 판단 |
| --- | --- | --- | --- |
| `heartbeat_at < now - N minutes` | 현재 schema로 가능. worker가 살아 있으면 heartbeat가 갱신된다는 모델과 맞음. | 장시간 blocking 구간에서 heartbeat thread가 DB 갱신 실패하면 오판 가능. N을 너무 짧게 잡으면 실제 job을 stale로 볼 수 있음. | 기본 candidate 기준으로 채택. |
| `heartbeat_at IS NULL AND started_at < now - grace` | claim 직후 heartbeat가 누락된 오래된 RUNNING을 잡을 수 있음. | 현재 claim 시 `heartbeat_at`도 설정하므로 정상 경로에서는 드묾. 구버전/수동 row에 유용. | 보조 기준으로 채택. |
| `started_at < now - max job duration` | heartbeat가 계속 갱신되어도 너무 오래 실행된 job을 감지. | real LLM과 큰 time range에서 정상 장기 실행을 오판할 수 있음. timeout 정책과 결합 필요. | 경고 후보. 자동 recovery 기준으로 쓰지 않음. |
| worker_id별 active worker heartbeat 부재 | worker process 단위 health와 연결 가능. | 현재 worker registry/worker heartbeat table이 없음. process heartbeat와 job heartbeat를 혼동할 수 있음. | 후속 설계. |
| systemd status 실패 | 운영자가 이해하기 쉬움. | DB job 상태와 직접 연결되지 않음. systemd restart 후에도 stale job은 남음. | 운영 확인 신호로만 사용. |

추천 stale candidate 기준:

```text
Primary:
  status = 'RUNNING'
  AND heartbeat_at IS NOT NULL
  AND heartbeat_at < UTC_TIMESTAMP(3) - INTERVAL <stale_after_minutes> MINUTE

Secondary:
  status = 'RUNNING'
  AND heartbeat_at IS NULL
  AND started_at < UTC_TIMESTAMP(3) - INTERVAL <startup_grace_minutes> MINUTE

Default stale_after_minutes:
  30 minutes for MVP dry-run/recovery candidate review

Startup grace:
  5 minutes
```

운영 기본값은 worker `--heartbeat-interval 30` seconds 기준으로 30분을 권장한다. 이는 heartbeat 60회 정도를 놓친 상태라서 순간 DB 지연이나 짧은 LLM call 지연을 stale로 오판할 가능성을 낮춘다. 실제 운영에서는 provider timeout, expected job duration, DB read/write timeout을 본 뒤 조정한다.

## 5. recovery 정책 후보

| 후보 | 설명 | 장점 | 위험 | 판단 |
| --- | --- | --- | --- | --- |
| 운영 SQL만 문서화 | operator가 SELECT로 stale 후보를 확인하고 수동 UPDATE/INSERT 수행 | 구현 전 즉시 운영 가능. destructive 자동화 없음. | 수동 실수 가능. event 일관성 누락 가능. | MVP 문서 정책으로 우선 채택. |
| 별도 CLI `--recover-stale` | dry-run 후보 출력 후 명시 옵션으로 FAILED 처리 | 반복 가능하고 audit/event 일관성 확보 가능. | 구현 필요. 권한/실수 방지 필요. | 1차 후속 구현 추천. |
| worker 시작 시 stale job을 FAILED 처리 | worker loop 시작 때 recovery 수행 | 운영자 개입 감소 | restart 순간 실제 살아 있는 다른 worker job을 죽일 수 있음. 원인 확인 전 상태 변경. | MVP 금지. |
| Web UI stale 표시만 | detail/dashboard에서 Potentially stale badge 표시 | 안전함. operator 판단 지원 | 상태 변경은 해결하지 않음 | 2차 후속 구현 추천. |
| 자동 PENDING requeue | stale job을 다시 claim 가능하게 함 | 자동 복구처럼 보임 | 중복 LLM 실행, artifact_root collision, partial artifact 오염, attempt_count 불일치 | MVP 금지. |
| 자동 artifact 삭제 후 재실행 | stale artifact root를 지우고 retry | 재실행은 쉬움 | 디버깅 증거 삭제, race/destructive 위험 큼 | 금지. |

## 6. 추천 MVP 정책

MVP 정책은 보수적으로 운영한다.

```text
1. stale 자동 재queue 금지
2. stale 자동 artifact 삭제 금지
3. worker 시작 시 stale job 자동 처리 금지
4. Web UI는 후속 구현 시 stale candidate 표시만 수행
5. 복구는 운영자 명령으로 FAILED 처리
6. retry/rerun은 별도 workflow로 분리
7. partial artifact_root는 보존
8. stale 처리도 job_events에 audit event를 남김
```

권장 운영 순서:

```text
1. operator가 stale candidate를 조회한다.
2. systemd/journal/process 상태를 확인한다.
3. artifact_root와 analysis_reports 유무를 확인한다.
4. 실제 실행 중이 아님이 확인되면 stale reason을 적어 FAILED로 닫는다.
5. JOB_MARKED_FAILED_STALE event를 남긴다.
6. 재실행이 필요하면 기존 job을 PENDING으로 되돌리지 않고 별도 retry/rerun workflow로 새 job/artifact_root 정책을 사용한다.
```

수동 SQL은 구현 전 운영 참고용으로만 둔다. 실제 수행 전에는 DB backup과 대상 job id 확인이 필요하다.

```sql
-- candidate 확인
SELECT id, status, worker_id, started_at, heartbeat_at, attempt_count, max_attempts,
       artifact_root, error_message
FROM analysis_jobs
WHERE status = 'RUNNING'
  AND (
    (heartbeat_at IS NOT NULL AND heartbeat_at < UTC_TIMESTAMP(3) - INTERVAL 30 MINUTE)
    OR (heartbeat_at IS NULL AND started_at < UTC_TIMESTAMP(3) - INTERVAL 5 MINUTE)
  )
ORDER BY heartbeat_at ASC, started_at ASC
LIMIT 20;
```

FAILED 처리의 목표 SQL shape:

```sql
START TRANSACTION;

UPDATE analysis_jobs
SET status = 'FAILED',
    finished_at = UTC_TIMESTAMP(3),
    heartbeat_at = UTC_TIMESTAMP(3),
    error_message = 'Marked FAILED by operator: stale RUNNING heartbeat exceeded policy'
WHERE id = <job_id>
  AND status = 'RUNNING';

INSERT INTO job_events (job_id, event_time, event_type, message, detail_json)
VALUES (
  <job_id>,
  UTC_TIMESTAMP(3),
  'JOB_MARKED_FAILED_STALE',
  'Marked FAILED by operator after stale RUNNING review',
  '{"stale_after_minutes":30,"requeue":false,"artifact_deleted":false}'
);

COMMIT;
```

주의:

- 위 SQL은 정책 예시이며, 구현 전에는 application repository method로 event JSON과 secret redaction을 일관화하는 편이 낫다.
- `worker_id` 조건을 넣을지 여부는 CLI 구현 때 결정한다. operator recovery는 죽은 worker_id를 대신 처리해야 하므로 기존 `mark_job_failed(job_id, worker_id)` 재사용만으로는 부족할 수 있다.

## 7. event 설계

후속 구현에서 권장하는 event type:

| event_type | 발생 시점 | message | detail_json 후보 |
| --- | --- | --- | --- |
| `JOB_STALE_DETECTED` | dry-run 또는 Web/API가 stale 후보로 판단할 때. 상태 변경 없음. | `Stale RUNNING candidate detected` | `worker_id`, `heartbeat_at`, `started_at`, `stale_after_minutes`, `detected_by`, `dry_run=true` |
| `JOB_MARKED_FAILED_STALE` | operator/CLI가 stale RUNNING을 FAILED로 닫을 때 | `Marked FAILED after stale RUNNING review` | `worker_id`, `previous_status`, `heartbeat_at`, `started_at`, `stale_after_minutes`, `artifact_root`, `requeue=false`, `artifact_deleted=false`, `operator` |

MVP에서 `JOB_STALE_DETECTED`를 남길지는 선택 사항이다. 단순 조회나 Web UI badge 렌더링마다 event를 남기면 timeline noise가 커질 수 있다. CLI dry-run은 기본적으로 event를 남기지 않고, 명시 `--record-detection-event` 같은 옵션이 있을 때만 기록하는 편이 안전하다.

필수 event:

- 상태를 `FAILED`로 변경하는 recovery는 반드시 `JOB_MARKED_FAILED_STALE` event를 남긴다.

금지 event:

- 실제 requeue 없이 `JOB_REQUEUED` 같은 event를 남기지 않는다.
- artifact 삭제 없이 cleanup 관련 event를 남기지 않는다.

## 8. repository/CLI/Web 후속 구현 후보

### Repository

후속 method 후보:

```text
find_stale_running_jobs(cutoff, limit)
  -> status='RUNNING' and heartbeat/start criteria matched rows 반환

mark_stale_job_failed(job_id, reason, operator=None, stale_after_minutes=None)
  -> RUNNING job을 FAILED로 전환
  -> error_message 설정
  -> JOB_MARKED_FAILED_STALE event 기록
  -> artifact 삭제 없음
  -> requeue 없음

recover_stale_running_jobs(cutoff, limit, dry_run)
  -> dry_run이면 후보만 반환
  -> apply이면 각 job을 mark_stale_job_failed로 닫음
```

repository 구현 원칙:

- `WHERE id=%s AND status='RUNNING'` 조건 유지.
- 가능하면 `heartbeat_at`/`started_at` stale 조건을 UPDATE에도 포함해 TOCTOU를 줄인다.
- 상태 변경과 event insert는 한 transaction에서 수행한다.
- `attempt_count`는 변경하지 않는다.
- `artifact_root`는 변경하지 않는다.
- `analysis_reports`는 변경하지 않는다.

### CLI

후속 CLI 후보:

```bash
python3 src/analysis_job_worker.py \
  --recover-stale \
  --stale-after-minutes 30 \
  --dry-run
```

적용 모드 후보:

```bash
python3 src/analysis_job_worker.py \
  --recover-stale \
  --stale-after-minutes 30 \
  --mark-failed \
  --reason "worker host rebooted; no active process"
```

CLI 원칙:

- 기본은 `--dry-run`.
- `--mark-failed` 같은 명시적 apply flag 없이는 상태 변경 금지.
- `--requeue`는 제공하지 않는다. retry/rerun CLI와 분리한다.
- artifact 삭제 옵션을 제공하지 않는다.
- 처리 결과는 job id, worker_id, started_at, heartbeat_at, artifact_root, action을 표로 출력한다.

### Web

후속 Web 후보:

- dashboard/detail에서 `RUNNING` + old `heartbeat_at`이면 `Potentially stale` badge 표시.
- Web UI는 초기에는 상태 변경 버튼을 제공하지 않는다.
- operator-only action이 필요해지면 별도 권한/CSRF/audit/event 정책을 먼저 설계한다.

표시 기준:

```text
RUNNING
AND heartbeat_at older than configured stale threshold
=> Potentially stale. Verify worker before marking failed.
```

## 9. 테스트 계획

후속 구현 시 테스트 후보:

| 테스트 | 목적 |
| --- | --- |
| stale query test | cutoff보다 오래된 `RUNNING`만 반환하고 PENDING/SUCCEEDED/FAILED는 제외 |
| heartbeat null grace test | `heartbeat_at IS NULL` + old `started_at`만 후보 |
| dry-run recovery test | dry-run은 status/event/artifact를 변경하지 않음 |
| mark failed stale test | stale RUNNING을 FAILED로 닫고 `JOB_MARKED_FAILED_STALE` event 기록 |
| no auto requeue test | recovery가 PENDING으로 되돌리지 않음 |
| partial artifact untouched test | `artifact_root` 파일/경로를 삭제하거나 변경하지 않음 |
| max_attempts respected test | stale failed 처리에서 `attempt_count/max_attempts`를 변경하지 않음 |
| fresh heartbeat protected test | cutoff 이후 heartbeat가 있는 RUNNING은 처리하지 않음 |
| worker mismatch behavior test | operator stale recovery가 죽은 `worker_id`에 종속되지 않는지 정책대로 검증 |
| Web stale badge test | old heartbeat RUNNING만 Potentially stale 표시 |

## 10. risks / do-not-change list

### Risks

- 실제 실행 중인 job을 stale로 오판할 수 있다.
- LLM call이 중복 실행되면 비용과 report 혼선이 생긴다.
- partial artifact를 덮어쓰면 원인 분석이 어려워진다.
- `artifact_root` fail-fast 정책과 자동 requeue가 충돌한다.
- `attempt_count/max_attempts`와 retry semantics가 불일치할 수 있다.
- operator가 journal/artifact/error를 보기 전에 자동 상태 변경되면 원인 파악이 어려워진다.
- systemd restart가 stale recovery처럼 오해될 수 있다.

### Do-not-change list for MVP

- stale job을 자동으로 `PENDING`으로 바꾸지 않는다.
- stale job artifact를 자동 삭제하지 않는다.
- worker startup에서 stale job을 자동 FAILED 처리하지 않는다.
- 기존 `artifact_root`를 재사용한 자동 rerun을 하지 않는다.
- retry/requeue와 stale failed marking을 같은 command로 섞지 않는다.
- Web UI 일반 사용자에게 destructive recovery button을 노출하지 않는다.
- DB schema를 먼저 늘리지 않는다. 현재 schema의 `heartbeat_at`, `started_at`, `worker_id`, `error_message`, `job_events.detail_json`으로 시작한다.

## 11. 권장 커밋 순서

후속 구현을 한다면 다음 순서를 권장한다.

```text
1. docs: stale RUNNING recovery policy 문서 확정
2. repository: stale RUNNING query + mark failed stale method 추가
3. tests: repository stale query/mark failed/no requeue/artifact untouched 검증
4. CLI: --recover-stale dry-run 추가
5. CLI: 명시 --mark-failed apply mode 추가
6. operations docs: 운영 runbook과 SQL/CLI 예시 갱신
7. Web: Potentially stale badge 표시
8. Web/API: operator action은 권한/audit 설계 후 별도 진행
9. retry/rerun workflow는 stale FAILED 처리와 별도 설계/구현
```

첫 구현 단위는 dry-run query까지만 작게 끊는 것이 안전하다. 상태 변경과 Web action은 그 다음 단계로 분리한다.
