# Runtime Support

`docs/operations/`는 과거 운영 문서를 계속 누적하는 보관소가 아니라, **현재 시스템을 다시 실행하거나 DB를 재현할 때 필요한 최소 절차와 실행 자산**을 관리한다.

전체 구조는 [../00_current_architecture.md](../00_current_architecture.md), 결과 해석 경계는 [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)를 따른다.

## 1. 환경 설정

기준 예시는 repository의 `config/.env.example`이다.

~~~bash
cp config/.env.example config/.env
chmod 600 config/.env

set -a
source ./config/.env
set +a
~~~

실제 API key, DB password 등 secret은 Git에 커밋하지 않는다.

주요 역할:

- `LOG_DB_*`: Apache source log 조회 / export
- `APP_DB_*`: Analysis Job / report / event metadata
- `OPENAI_*`, `ANTHROPIC_*`: provider 설정
- `ARTIFACT_ROOT`: Job artifact root

배포 환경에 따라 `DB_HOST/DB_PORT/DB_NAME`과 `LOG_DB_*` fallback 관계는 실제 코드와 `config/.env.example`을 함께 확인한다.

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
