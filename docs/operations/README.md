# Runtime Support

`docs/operations/`는 과거 운영 문서를 계속 누적하는 보관소가 아니라, **현재 시스템을 다시 실행하거나 DB를 재현할 때 필요한 최소 절차와 실행 자산**을 관리한다.

전체 구조는 [../00_current_architecture.md](../00_current_architecture.md), 결과 해석 경계는 [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)를 따른다.

## 1. 환경 설정

기준 예시는 repository의 `config/.env.example`이다. 프로젝트가 지원하는
`.env` 문법은 `KEY=value`, `KEY="value"`, `KEY='value'`, 빈 줄, 전체 줄
`#` comment뿐이다. 첫 `=`만 delimiter이며 quoted value 내부 공백만 허용한다.

다음은 지원하지 않으며 executable startup 전에 configuration error가 된다.

- `KEY = value`, `KEY= value`, `KEY =value` 같은 assignment 주변 공백
- `export KEY=value`, duplicate key, invalid key
- `$VAR`, `${VAR}`, `$(command)`, backtick 등 shell interpolation/command syntax

~~~bash
cp config/.env.example config/.env
chmod 600 config/.env

set -a
source ./config/.env
set +a
~~~

실제 API key, DB password 등 secret은 Git에 커밋하지 않는다.

해석 우선순위는 **process environment 우선, `config/.env` fallback**이다.
즉 systemd `EnvironmentFile` 또는 shell export가 같은 key를 제공하면 Python
fallback loader는 이를 덮어쓰지 않는다.

주요 역할:

- `DB_HOST/DB_PORT/DB_NAME`: 공통 DB endpoint
- `LOG_DB_*`: Apache source log reader (Live / export)
- `APP_DB_*`: Analysis Job / report / event metadata credential
- `SHIPPER_DB_*`: Apache source log writer credential
- `OPENAI_*`, `ANTHROPIC_*`: provider 설정
- `ARTIFACT_ROOT`: Job artifact root

endpoint fallback은 `src/runtime_config.py`가 단일 source of truth다. reader는
`LOG_DB_* → DB_*`, app은 `APP_DB_* → DB_* → legacy LOG_DB_*`, shipper는
`SHIPPER_DB_* → DB_* → legacy LOG_DB_*` 순서다. credential은 role 간 fallback하지
않는다. 특히 Shipper에 `LOG_DB_USER=log_reader`를 writer credential로 사용하지 않는다.

fallback loader는 Worker/Exporter/Shipper executable bootstrap에서 한 번만 적용된다.
repository/service getter와 generic Web module import는 `.env`를 읽거나 process env를
변경하지 않는다. 한 terminal의 `source`는 다른 terminal, 이미 실행 중인 process,
systemd service에 영향을 주지 않는다. `.env`를 바꿔도 이미 실행 중인 process env는
바뀌지 않는다.

## 2. MariaDB 초기화

실행 가능한 SQL은 `sql/` 아래에 둔다.

권장 적용 순서:

~~~bash
sudo mariadb < docs/operations/sql/00_database_and_log_accounts.sql
sudo mariadb < docs/operations/sql/01_apache_log_tables.sql
sudo mariadb < docs/operations/sql/01_analysis_job_tables.sql
sudo mariadb < docs/operations/sql/02_live_selected_input_v1.sql
sudo mariadb < docs/operations/sql/10_log_source_table_grants.sql
sudo mariadb < docs/operations/sql/11_analysis_app_grants.sql
sudo mariadb < docs/operations/sql/90_verify_mariadb_setup.sql
~~~

SQL에 포함된 host/IP/password 예시는 실제 환경에 맞게 검토하고, 실제 secret을 repository에 기록하지 않는다.

권한 경계:

~~~text
log_writer
  -> Apache source log 적재

log_reader
  -> Apache source log SELECT

analysis_app
  -> analysis_jobs / analysis_reports / job_events
  -> 필요한 source log SELECT
~~~

일부 테스트는 다음 SQL 파일의 내용을 직접 읽는다.

- `sql/01_analysis_job_tables.sql`
- `sql/02_live_selected_input_v1.sql`
- `sql/11_analysis_app_grants.sql`
- `sql/90_verify_mariadb_setup.sql`

따라서 이 경로는 현재 test/runtime-support 계약의 일부다.

## 3. Apache log format

Apache security log 예시는 `examples/`에 둔다.

~~~text
examples/apache_security_logformat_v1.conf
examples/apache_security_logformat_v2.conf
~~~

실제 배포에서는 Apache 설정과 `src/apache_log_shipper.py` parser가 같은 log contract를 사용해야 한다.

## 4. Log Shipper

대표 동작:

~~~text
Apache access/security/error logs
  -> src/apache_log_shipper.py
  -> apache_access_logs
  -> apache_security_logs
  -> apache_error_logs
~~~

대표 점검:

~~~bash
python3 src/apache_log_shipper.py --test-db
python3 src/apache_log_shipper.py --once
~~~

`--reset-state`는 offset을 초기화하여 중복 적재 위험이 있으므로 테스트 상황에서만 제한적으로 사용한다.

DB 연결 실패 시에는 DB 접속 정보, 네트워크, 권한, table 존재 여부를 먼저 확인한다. spool이 누적되면 원인 해결 전 spool을 임의 삭제하지 않는다.

## 5. Web 실행

~~~bash
source .venv/bin/activate

set -a
source ./config/.env
set +a

uvicorn web.app:app --host 127.0.0.1 --port 8000
~~~

개발 시에만 필요하면 `--reload`를 사용한다.

현재 Web 구조는 [../../web/README.md](../../web/README.md)를 따른다.

## 6. Analysis Job Worker

### Production: systemd

운영/발표 Worker는 systemd service 하나만 사용한다. `EnvironmentFile`이 env를
자동 주입하므로 shell `source`는 필요하지 않다. unit example의 `DEPLOY_USER`와
`DEPLOY_GROUP`은 반드시 실제 existing deployment account로 교체한다.

Worker는 startup에서 effective DB endpoint/provenance(credential 값 제외), static
runtime file, APP DB `SELECT 1`, source log DB read-only query를 확인한다. 이후
polling 중에는 TTL 기반 pre-claim dependency gate를 사용한다. gate가 실패하면
`claim_next_pending_full_report_job()`를 호출하지 않고 temporary failure(75)로 종료하여
systemd가 재시작한다. 이는 health check 직후의 DB failure race까지 없앤다는 뜻은 아니다.

~~~bash
systemctl show web-log-analysis-worker.service -p MainPID -p ActiveState -p SubState
pgrep -af analysis_job_worker.py
~~~

운영 Worker는 하나여야 한다. `MainPID`와 실제 Worker PID/cgroup을 대조하고, 별도
manual Worker가 있으면 production polling과 동시에 실행하지 않는다.

### Development/manual

운영 loop 예:

~~~bash
python3 src/analysis_job_worker.py \
  --run-pipeline \
  --worker-id worker-01 \
  --sleep-seconds 5 \
  --heartbeat-interval 30
~~~

개발/점검용 1회 실행:

~~~bash
python3 src/analysis_job_worker.py \
  --once \
  --run-pipeline \
  --worker-id smoke-local
~~~

Worker는 Web process와 분리된다. Web에서 Job을 등록하고 Worker가 `PENDING` Job을 claim하여 `full_report` pipeline을 실행한다.

systemd 예시는 repository의 다음 파일을 사용한다.

~~~text
ops/systemd/web-log-analysis-worker.service.example
~~~

실제 `User`, `Group`, `WorkingDirectory`, `EnvironmentFile`은 배포 환경에 맞게 수정한다. secret을 unit file에 직접 넣지 않는다.

### Restart safety

배포 또는 `systemctl restart` 전에는 반드시 `RUNNING` Job과 실제 Worker PID를 확인한다.
`RUNNING=0`이거나 해당 Job이 실행 중이 아님을 확인하기 전에는 임의 restart하지 않는다.
강제 restart/kill은 stale `RUNNING` Job을 만들 수 있다. automatic retry/requeue는 제공하지 않는다.

## 7. Stale RUNNING 점검

stale 후보 조회는 먼저 dry-run으로 확인한다.

~~~bash
python3 src/analysis_job_worker.py \
  --recover-stale \
  --dry-run \
  --stale-after-minutes 30 \
  --startup-grace-minutes 5 \
  --limit 20
~~~

실제로 실행 중이 아님을 확인한 후에만 명시적 reason과 함께 FAILED 처리한다.

~~~bash
python3 src/analysis_job_worker.py \
  --recover-stale \
  --mark-failed \
  --reason "worker process stopped; confirmed no active run" \
  --stale-after-minutes 30 \
  --startup-grace-minutes 5 \
  --limit 20
~~~

stale recovery runbook:

1. service 상태와 `MainPID`, 별도 manual Worker 존재 여부를 확인한다.
2. `--recover-stale --dry-run`으로 candidate의 `started_at`/`heartbeat_at`을 확인한다.
3. 해당 Worker PID가 없고 실제 pipeline이 실행 중이 아님을 확인한다.
4. 명시적 reason으로만 `--mark-failed`를 실행한다.
5. `job_event` 기록과 systemd Worker의 polling 상태를 확인한다.

stale recovery는 retry/requeue가 아니며 기존 artifact를 삭제하거나 Job을 `PENDING`으로 되돌리지 않는다.

## 8. Job artifacts

기본 Job artifact root는 deployment 설정에 따라 정해지며 대표 구조는 다음과 같다.

~~~text
runs/jobs/<job_id>/
  export.json
  llm_input.json
  analysis_candidates.json
  noise_summary.json
  filtered_reasons.json
  stage1_results.json
  stage2_report_input.json
  stage2_report.json
  stage2_report.md
  viewer_payload.json
  manifest.json
~~~

no-data 등 실행 경로에 따라 일부 downstream artifact가 생성되지 않을 수 있다.

## 9. 문서 정책

과거 특정 Job ID의 smoke 결과, 오래된 test count, 구현 전 TODO, `windowed_triage` 계획은 이 README에서 current 운영 기준으로 관리하지 않는다.

현재 실행 방식은 코드와 다음 문서를 우선한다.

- [../00_current_architecture.md](../00_current_architecture.md)
- [../../src/README.md](../../src/README.md)
- [../../web/README.md](../../web/README.md)
- `config/.env.example`
- `ops/systemd/web-log-analysis-worker.service.example`

과거 상세 운영 절차가 필요한 경우 Git history에서 확인한다.
