# Analysis Job Worker 운영 가이드

## 목적

이 문서는 DB-backed MVP에서 `analysis_jobs` queue를 처리하는 Analysis Job Worker 운영 기준을 정리한다.

현재 운영 모델은 Web UI와 worker를 DB queue로 분리한다. 일반 사용자는 Web UI에서 job을 등록하고 결과를 확인하며, Analysis Job Worker는 운영자가 별도 background process 또는 service로 실행한다.

`full_report`는 direct pipeline mode다. `sliding_window / rollup / operator_queue`는 `full_report` worker에 자동 삽입하지 않는다. 해당 흐름은 후속 `analysis_mode=windowed_triage`에서 다룬다.

## 역할 분리

### 일반 사용자

- Web UI에서 analysis job을 등록한다.
- job list/detail에서 상태를 확인한다.
- `/job/{id}/viewer`에서 결과 dashboard를 확인한다.
- Python CLI를 직접 실행하지 않는다.

### Analysis Job Worker / Agent

- 운영자가 실행하는 background process다.
- `analysis_jobs`의 `PENDING` job을 polling한다.
- atomic claim으로 처리 대상 job을 잡는다.
- `full_report` direct pipeline을 실행한다.
- `analysis_reports`에 report/artifact 경로를 저장한다.
- `analysis_jobs`를 `SUCCEEDED` 또는 `FAILED`로 닫는다.
- no-data job은 실패가 아니라 `SUCCEEDED`와 `JOB_NO_DATA` event로 닫는다.

### 운영자

- worker process/service를 실행한다.
- env, API key, DB 접속 정보를 관리한다.
- worker 로그를 확인한다.
- 실패 job과 stale `RUNNING` job을 운영 처리한다.

### 개발자

- `--once`, `--pipeline-dry-run`, `--max-jobs`로 smoke/debug를 수행한다.

## 현재 검증된 MVP 흐름

다음 흐름은 real LLM smoke 기준으로 검증됐다.

```text
Web UI job registration
  -> analysis_jobs(PENDING)
  -> analysis_job_worker claim
  -> export_db_logs_cli.py
  -> run_analysis_pipeline.py direct path
  -> prepare
  -> Stage1
  -> Stage2
  -> viewer_payload
  -> analysis_reports 저장
  -> analysis_jobs(SUCCEEDED)
  -> /job/{id}/viewer dashboard
```

확인된 smoke:

- real LLM `job_id=5`
- `dry_run=false`
- `provider=openai`
- `selected_model=gpt-5.4-mini`
- Stage1 `success_count=5`, `error_count=0`
- `stage2_report.md` 생성
- `viewer_payload.v1` 생성
- `/job/5/viewer` 확인
- no-data job은 `JOB_NO_DATA` + `SUCCEEDED` + `export_path` only로 처리
- loop smoke는 `--max-jobs 2`로 job 6, 7 순차 처리 확인

## 실행 모드

개발 dry-run smoke:

```bash
python3 src/analysis_job_worker.py \
  --once \
  --worker-id smoke-local \
  --run-pipeline \
  --pipeline-dry-run
```

실제 1건 smoke:

```bash
python3 src/analysis_job_worker.py \
  --once \
  --worker-id smoke-real \
  --run-pipeline
```

loop smoke:

```bash
python3 src/analysis_job_worker.py \
  --run-pipeline \
  --worker-id loop-smoke \
  --max-jobs 2 \
  --sleep-seconds 1 \
  --heartbeat-interval 5
```

운영 loop:

```bash
python3 src/analysis_job_worker.py \
  --run-pipeline \
  --worker-id worker-01 \
  --sleep-seconds 5 \
  --heartbeat-interval 30
```

주의:

- loop mode에서는 `--run-pipeline`이 필수다.
- claim-only loop는 금지한다.
- `--once` 없이 `--run-pipeline`이 없으면 CLI error가 발생한다.
- `--max-jobs`는 smoke/test용이다.
- 운영에서는 보통 `--max-jobs` 없이 실행한다.

## stale RUNNING recovery CLI

stale `RUNNING` recovery는 운영자가 명시적으로 실행하는 CLI 절차다. worker 시작 시 자동 recovery를 수행하지 않고, Web UI도 destructive action button을 제공하지 않는다.

후보 판단 기준은 정책 문서 [Analysis Job Stale RUNNING Recovery Policy](../design/99_analysis_job_stale_running_recovery_policy.md)를 따른다.

- `status='RUNNING'`
- `analysis_mode='full_report'`
- primary: `heartbeat_at`이 있고 `--stale-after-minutes`보다 오래됨
- secondary: `heartbeat_at`이 없고 `started_at`이 `--startup-grace-minutes`보다 오래됨
- 기본값: `--stale-after-minutes 30`, `--startup-grace-minutes 5`, `--limit 20`

dry-run 후보 조회:

```bash
python3 src/analysis_job_worker.py \
  --recover-stale \
  --dry-run \
  --stale-after-minutes 30 \
  --startup-grace-minutes 5 \
  --limit 20
```

명시적 FAILED 처리:

```bash
python3 src/analysis_job_worker.py \
  --recover-stale \
  --mark-failed \
  --reason "worker host rebooted; no active process" \
  --stale-after-minutes 30 \
  --startup-grace-minutes 5 \
  --limit 20
```

CLI 동작:

- `--recover-stale --dry-run`은 candidate를 출력하고 DB를 변경하지 않는다.
- `--recover-stale --mark-failed --reason "..."`는 조회된 stale candidate만 `FAILED`로 닫는다.
- `--dry-run`과 `--mark-failed`는 동시에 사용할 수 없다.
- `--recover-stale` 단독 실행은 CLI error다.
- `--mark-failed`에는 `--reason`이 필수다.
- 처리 시 `JOB_MARKED_FAILED_STALE` event를 남긴다.
- `PENDING` requeue, artifact 삭제, `attempt_count/max_attempts` 변경, `analysis_reports` 변경은 수행하지 않는다.

## 환경 변수와 config/.env

worker code는 환경변수를 통해 DB/LLM 설정을 받는다. 실제 secret 값은 문서나 `config/.env.example`에 쓰지 않는다. 필요한 key 이름은 `config/.env.example`을 기준으로 확인한다.

현재 `config/.env.example` 기준 주요 key:

- 공통 DB: `DB_HOST`, `DB_PORT`, `DB_NAME`
- 로그 export 계정: `LOG_DB_USER`, `LOG_DB_PASSWORD`
- 작업 queue/Web UI 계정: `APP_DB_USER`, `APP_DB_PASSWORD`
- Web UI/session: `SESSION_SECRET_KEY`, `SESSION_MAX_AGE_SECONDS`, `WEB_HOST`, `WEB_PORT`
- artifact root: `ARTIFACT_ROOT`
- OpenAI: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`
- Anthropic: `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS`
- worker 기본값: `AGENT_POLL_INTERVAL_SECONDS`, `AGENT_WORKER_ID`, `MAX_JOB_ATTEMPTS`, `JOB_TIMEOUT_SECONDS`
- 운영: `DEBUG`, `LOG_LEVEL`, `LOG_FILE`
- 선택: `KNOWN_ASSET_IPS`, `ARTIFACT_RETENTION_DAYS`

`LLM_PROVIDER`는 `config/.env.example`에서 기본 env 값으로 고정하지 않는다. provider 선택은 job/runner 또는 실행 계층에서 명시하는 것을 기준으로 한다.

코드 호환성 관점의 DB key 해석:

- `analysis_jobs` queue 접속은 `APP_DB_USER/APP_DB_PASSWORD`를 우선 사용하고, 없으면 `LOG_DB_USER/LOG_DB_PASSWORD`로 fallback한다.
- DB host/name/port는 `DB_HOST/DB_NAME/DB_PORT`를 우선 사용하고, 없으면 `LOG_DB_HOST/LOG_DB_NAME/LOG_DB_PORT`로 fallback한다.
- worker가 호출하는 export 계층은 `LOG_DB_HOST`, `LOG_DB_PORT`, `LOG_DB_USER`, `LOG_DB_PASSWORD`, `LOG_DB_NAME`도 읽을 수 있다. 운영 `config/.env`에서는 배포 환경에 맞게 실제 실행 경로가 요구하는 key가 모두 채워졌는지 확인한다.

수동 실행 예시:

```bash
cd /opt/web_log_analysis
source .venv/bin/activate
set -a
source ./config/.env
set +a

python3 src/analysis_job_worker.py \
  --run-pipeline \
  --worker-id worker-01 \
  --sleep-seconds 5 \
  --heartbeat-interval 30
```

systemd에서는 `source`를 직접 쓰지 않고 `EnvironmentFile`을 사용한다.

중요:

- systemd의 `EnvironmentFile`은 shell script를 실행하는 것이 아니다.
- `config/.env`는 systemd `EnvironmentFile`과 shell `source` 양쪽에서 읽을 수 있는 단순 `KEY=VALUE` 형식을 유지한다.
- `export VAR=...` 형식, command substitution, `source other.env` 같은 shell 전용 문법은 피한다.
- 실제 secret 값은 unit 파일, 문서, `config/.env.example`에 직접 쓰지 않는다.
- 실제 `config/.env` 파일 권한은 제한한다. 예: `chmod 600 config/.env`

## systemd 예시

실제 unit 예시 파일은 `ops/systemd/web-log-analysis-worker.service.example`에 둔다.

`/opt/web_log_analysis`는 예시 경로다. `User`, `Group`, `EnvironmentFile`, `WorkingDirectory`는 운영 환경에 맞게 바꾼다.

```ini
[Unit]
Description=Web Log Analysis Job Worker
After=network.target mariadb.service

[Service]
Type=simple
WorkingDirectory=/opt/web_log_analysis
EnvironmentFile=/opt/web_log_analysis/config/.env
ExecStart=/opt/web_log_analysis/.venv/bin/python3 src/analysis_job_worker.py --run-pipeline --worker-id worker-01 --sleep-seconds 5 --heartbeat-interval 30
Restart=on-failure
RestartSec=5
User=webanalysis
Group=webanalysis

[Install]
WantedBy=multi-user.target
```

주의:

- `User`/`Group`은 실제 운영 계정으로 바꾼다.
- `EnvironmentFile` 경로는 실제 배포 경로에 맞게 수정한다.
- `config/.env` 권한은 제한한다.
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, DB password 같은 secret은 unit 파일에 직접 쓰지 않는다.
- systemd 예시는 1 worker 기준이다.

## systemd 운영 명령

```bash
sudo systemctl daemon-reload
sudo systemctl enable web-log-analysis-worker
sudo systemctl start web-log-analysis-worker
sudo systemctl status web-log-analysis-worker
journalctl -u web-log-analysis-worker -f
sudo systemctl restart web-log-analysis-worker
sudo systemctl stop web-log-analysis-worker
```

## 상태별 운영 해석

### PENDING

- worker가 아직 claim하지 않았다.
- worker가 꺼져 있거나 다른 job을 처리 중일 수 있다.

### RUNNING

- worker가 claim했고 pipeline 실행 중이다.
- `heartbeat_at`은 `RUNNING` job이 살아 있는지 보는 힌트다.
- Web UI는 오래된 heartbeat 또는 오래된 missing heartbeat startup state를 `Potentially stale`로 표시한다.
- `Potentially stale`은 상태 변경이 아니라 운영 확인 신호다.

### SUCCEEDED

- 정상 완료 상태다.
- no-data도 `SUCCEEDED`일 수 있다.
- no-data 여부는 `JOB_NO_DATA` event 또는 `analysis_reports.summary`를 확인한다.

### FAILED

- `analysis_jobs.error_message`와 `job_events`를 확인한다.

## 확인 SQL

최근 job 상태:

```sql
SELECT id, status, worker_id, started_at, heartbeat_at, finished_at, error_message
FROM analysis_jobs
ORDER BY id DESC
LIMIT 20;
```

job events:

```sql
SELECT event_time, event_type, message, detail_json
FROM job_events
WHERE job_id = <job_id>
ORDER BY id ASC;
```

report artifacts:

```sql
SELECT job_id, artifact_root, stage2_report_path, stage2_report_md_path, viewer_payload_path
FROM analysis_reports
WHERE job_id = <job_id>;
```

stale candidate 확인 SQL:

```sql
SELECT id, status, worker_id, started_at, heartbeat_at, attempt_count, max_attempts,
       artifact_root, error_message
FROM analysis_jobs
WHERE status = 'RUNNING'
  AND analysis_mode = 'full_report'
  AND (
    (heartbeat_at IS NOT NULL AND heartbeat_at < UTC_TIMESTAMP(3) - INTERVAL 30 MINUTE)
    OR (heartbeat_at IS NULL AND started_at < UTC_TIMESTAMP(3) - INTERVAL 5 MINUTE)
  )
ORDER BY COALESCE(heartbeat_at, started_at) ASC, started_at ASC, id ASC
LIMIT 20;
```

## stale RUNNING 운영 runbook

1. Web UI dashboard/detail에서 `Potentially stale` 표시가 있는지 확인한다.
2. SQL 또는 CLI dry-run으로 stale candidate를 조회한다.

```bash
python3 src/analysis_job_worker.py \
  --recover-stale \
  --dry-run \
  --stale-after-minutes 30 \
  --startup-grace-minutes 5 \
  --limit 20
```

3. systemd 상태와 journal을 확인한다.

```bash
sudo systemctl status web-log-analysis-worker
journalctl -u web-log-analysis-worker --since "2 hours ago"
```

4. worker process가 실제로 살아 있는지 확인한다. 운영 환경에 맞게 `ps`, supervisor, container status를 확인한다.
5. 대상 job의 `artifact_root`와 `analysis_reports` 유무를 확인한다. partial artifact는 삭제하지 않는다.
6. 실제 실행 중이 아님을 확인한 뒤 명시적 reason으로 FAILED 처리한다.

```bash
python3 src/analysis_job_worker.py \
  --recover-stale \
  --mark-failed \
  --reason "worker process stopped; journal confirmed no active run" \
  --stale-after-minutes 30 \
  --startup-grace-minutes 5 \
  --limit 20
```

7. Web detail 또는 SQL에서 `JOB_MARKED_FAILED_STALE` event를 확인한다.
8. 다시 dry-run을 실행해 candidate가 줄었는지 확인한다.

주의:

- stale recovery는 retry/rerun이 아니다.
- 기존 job을 `PENDING`으로 되돌리지 않는다.
- 기존 artifact를 삭제하거나 덮어쓰지 않는다.
- 재실행이 필요하면 별도 retry/rerun workflow로 새 정책을 적용해야 한다.
- Web UI는 stale 표시만 제공하고 mark failed button을 제공하지 않는다.

## 운영 주의사항

- Web app은 worker를 직접 실행하지 않는다.
- Web app과 worker는 DB queue로 분리된다.
- worker가 꺼져 있으면 job은 `PENDING`에 남는다.
- `artifact_root`가 이미 있으면 fail-fast한다.
- no-data는 실패가 아니다.
- real LLM 실행은 API key와 비용이 필요하다.
- `heartbeat_at`은 `RUNNING` job이 살아 있는지 보는 힌트다.
- stale `RUNNING` recovery는 CLI로 구현되어 있지만 자동으로 수행되지 않는다.
- retry/requeue는 자동으로 수행되지 않는다.
- cancel/cancelled handling은 아직 구현되지 않았다.
- stage-level `job_events`는 Phase 1 coarse boundary 기준으로 기록된다.
- `lint_result_path`는 schema/UI key가 있으나 현재 full_report runner가 채우지 않는다.
- systemd 예시는 1 worker 기준이다.
- 다중 worker는 atomic claim 덕분에 가능하지만, 실제 multi-worker 운영 검증 전까지 현재 운영 권장은 보수적으로 1 worker다.

## 남은 TODO

- retry/requeue CLI/API/UI
- cancel/cancelled semantics
- failed/partial artifact policy 고도화
- worker health endpoint 또는 Web UI worker status 표시
- lint_result_path / manifest / stage2_report_input artifact mapping 결정
- legacy `/report/*` 정리
- Markdown report HTML rendering
- `windowed_triage` 후속 mode
