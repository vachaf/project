# operations

## 목적

- `operations/`는 실행 가이드, 운영 기준, 환경 구축, 로그 구조 문서를 둔다.
- 현재 상위 운영 기준은 [../00_current_architecture.md](../00_current_architecture.md)의 DB-backed MVP 흐름이다.
- 기존 `export -> prepare -> stage1 -> stage2 -> viewer_payload` 흐름은 DB-backed MVP의 `full_report` direct path이자 수동 운영/검증 경로로 유지한다.
- `sliding_window / rollup / operator_queue` 흐름은 후속 `analysis_mode=windowed_triage` 또는 수동/운영 triage 경로로 분리한다.

## 현재 운영 기준

```text
Apache logs
  -> apache_log_shipper.py
  -> MariaDB web_logs
  -> Web UI analysis_jobs 등록
  -> Analysis Job Worker full_report 실행
  -> export / prepare
  -> Stage1 / Stage2 / viewer_payload 생성
  -> analysis_reports / job_events 기록
  -> Web UI 결과 확인
```

- `analysis_jobs` queue는 MariaDB table 기반의 분석 실행 queue다.
- `operator queue`는 sliding window / rollup 결과를 사람이 검토하기 위한 artifact queue다.
- Web UI read-only 원칙은 보안 결과 해석 read-only를 뜻한다.
- Web UI는 `analysis_jobs` 등록/조회와 job lifecycle 표시를 위해 DB write/read를 수행할 수 있다.
- `full_report`의 완료 조건은 Stage1, Stage2, `viewer_payload`, report/artifact 저장 완료다.
- 현재 구현에는 job claim, direct pipeline 호출, `analysis_reports` 저장, SUCCEEDED/FAILED 전이를 수행하는 worker가 아직 없다.

## 문서 목록

- 현재 기준
  - [../00_current_architecture.md](../00_current_architecture.md): 현재 canonical architecture overview와 DB-backed MVP 운영 흐름
- 전체 흐름/실행
  - [00_전체_흐름_요약_가이드.md](./00_전체_흐름_요약_가이드.md): 전체 파이프라인 흐름 요약
  - [01_운영_기준_실행_가이드.md](./01_운영_기준_실행_가이드.md): 운영 기준과 실행 절차(`export --table`, pipeline auto prepare source table 해석, Web UI run_dir default scan 기준 포함)
  - [06_통합_스크립트_설명_정리본.md](./06_통합_스크립트_설명_정리본.md): 통합 스크립트 설명(`run_analysis_pipeline.py`, `--run-dir`, run_dir manifest/Web UI 연결 기준 포함)
- 프로젝트/실험 대상
  - [01_프로젝트_방향과_실험대상.md](./01_프로젝트_방향과_실험대상.md): 프로젝트 방향과 실험 대상 정리
- 환경 구축
  - [02_LLM_환경_구축_및_설치.md](./02_LLM_환경_구축_및_설치.md): LLM 환경 구축과 설치
  - [02_Juice_shop_환경_구축_및_설치.md](./02_Juice_shop_환경_구축_및_설치.md): Juice Shop 환경 구축과 설치
  - [02_MariaDB_환경_구축_및_설치.md](./02_MariaDB_환경_구축_및_설치.md): MariaDB 환경 구축, SQL 적용 순서, 계정 권한 경계
  - [02_OpenCart_환경_구축_및_설치.md](./02_OpenCart_환경_구축_및_설치.md): OpenCart 환경 구축과 설치
- 로그/DB/export
  - [03_로그_표준과_DB_구조.md](./03_로그_표준과_DB_구조.md): 로그 표준과 DB 구조
  - [04_로그_적재_및_운영.md](./04_로그_적재_및_운영.md): `apache_log_shipper.py` 기반 로그 적재와 운영
  - [05_Export_LLM_분석_전략.md](./05_Export_LLM_분석_전략.md): `export_db_logs_cli.py`와 LLM 분석 전략(`table_option/counts/data` 기반 auto resolution, run_dir 표준 산출물/manifest 중심 흐름 포함)
  - [07_DB_backed_analysis_job_tables.md](./07_DB_backed_analysis_job_tables.md): DB-backed MVP용 `users`, `analysis_jobs`, `analysis_reports`, `job_events` 적용 절차
  - [99_output_retention_policy.md](./99_output_retention_policy.md): 산출물 보존/정리 기준
- SQL
  - [sql/00_database_and_log_accounts.sql](./sql/00_database_and_log_accounts.sql): `web_logs`, `log_writer`, `log_reader` 생성
  - [sql/01_apache_log_tables.sql](./sql/01_apache_log_tables.sql): Apache source log table DDL
  - [sql/01_analysis_job_tables.sql](./sql/01_analysis_job_tables.sql): DB-backed MVP operation/control table DDL
  - [sql/10_log_source_table_grants.sql](./sql/10_log_source_table_grants.sql): source log table 단위 `log_writer`/`log_reader` 권한
  - [sql/11_analysis_app_grants.sql](./sql/11_analysis_app_grants.sql): DB-backed MVP `analysis_app` 권한
  - [sql/90_verify_mariadb_setup.sql](./sql/90_verify_mariadb_setup.sql): MariaDB 구축 검증 쿼리

## 읽는 순서

1. [../00_current_architecture.md](../00_current_architecture.md)
2. [02_MariaDB_환경_구축_및_설치.md](./02_MariaDB_환경_구축_및_설치.md)
3. [07_DB_backed_analysis_job_tables.md](./07_DB_backed_analysis_job_tables.md)
4. [03_로그_표준과_DB_구조.md](./03_로그_표준과_DB_구조.md)
5. [04_로그_적재_및_운영.md](./04_로그_적재_및_운영.md)
6. [05_Export_LLM_분석_전략.md](./05_Export_LLM_분석_전략.md)
7. [06_통합_스크립트_설명_정리본.md](./06_통합_스크립트_설명_정리본.md)
8. [99_output_retention_policy.md](./99_output_retention_policy.md)

환경을 처음 구축할 때는 다음 순서로 필요한 문서만 이어서 본다.

1. [02_MariaDB_환경_구축_및_설치.md](./02_MariaDB_환경_구축_및_설치.md)
2. [07_DB_backed_analysis_job_tables.md](./07_DB_backed_analysis_job_tables.md)
3. 필요한 대상 앱 환경 구축 문서
4. [04_로그_적재_및_운영.md](./04_로그_적재_및_운영.md)
5. [05_Export_LLM_분석_전략.md](./05_Export_LLM_분석_전략.md)

기존 수동 full_report 실행/검증은 아래 순서로 본다.

1. [01_운영_기준_실행_가이드.md](./01_운영_기준_실행_가이드.md)
2. [05_Export_LLM_분석_전략.md](./05_Export_LLM_분석_전략.md)
3. [06_통합_스크립트_설명_정리본.md](./06_통합_스크립트_설명_정리본.md)

## 관리 원칙

- 실행 방법, 환경 구축, 로그 구조, 운영 절차는 `operations/`에 둔다.
- 실험 요청 세트는 `experiments/`에 둔다.
- 실험 결과 산출물은 `lab/`에 둔다.
- 실행 가능한 MariaDB DDL/DCL/검증 SQL은 `docs/operations/sql/`에 둔다.
- [02_MariaDB_환경_구축_및_설치.md](./02_MariaDB_환경_구축_및_설치.md)는 SQL 원문 보관 문서가 아니라 적용 순서와 권한 경계 문서다.
- Apache source log table DDL은 [sql/01_apache_log_tables.sql](./sql/01_apache_log_tables.sql)에 둔다.
- DB-backed MVP operation/control table DDL은 [sql/01_analysis_job_tables.sql](./sql/01_analysis_job_tables.sql)에 둔다.

## DB-backed MVP operation/control tables

- 적용 문서: [07_DB_backed_analysis_job_tables.md](./07_DB_backed_analysis_job_tables.md)
- SQL: [sql/01_analysis_job_tables.sql](./sql/01_analysis_job_tables.sql)
- 포함 table:
  - `users`
  - `analysis_jobs`
  - `analysis_reports`
  - `job_events`
- `log_collection_checkpoints`는 현재 `src/apache_log_shipper.py`의 file-state offset tracking과 비교 후 후속 판단한다.

## Web UI run_dir default scan

이 섹션은 기존 run_dir 기반 Web UI loader 운영 기준이다. DB-backed MVP에서는 Web UI job detail이 `analysis_reports`와 job-scoped artifact root를 통해 같은 표준 산출물을 찾는 방향으로 해석한다.

- Web UI 기본 목록은 `runs/*/manifest.json`을 기준으로 구성한다.
  - `REPORT_GLOBS=["runs/*/manifest.json"]`
- 기존 flat/lab glob은 호환성 후보로만 보존하며 기본 scan에서 제외한다.
  - `LEGACY_REPORT_GLOBS=["reports/*_stage2_report.json", "lab/**/reports/*_stage2_report.json"]`
- 따라서 `reports/` 또는 `lab/**/reports/` 산출물만 있는 경우 Web UI 기본 목록에 나오지 않는 것이 정상이다.

## Run Directory Output Flow

- Web UI 표시를 운영 기본 흐름으로 사용할 때는 pipeline 실행 시 `--run-dir runs/<run_id>`를 지정한다.
- run_dir 표준 파일은 `manifest.json`, `export.json`, `llm_input.json`, `stage1_results.json`, `stage2_report_input.json`, `stage2_report.json`, `stage2_report.md`, `viewer_payload.json`, `noise_summary.json`이다.
- `--run-dir` 없이 flat output만 생성하는 실행은 분석 자체는 가능하지만 Web UI 기본 목록 연동 대상이 아니다.
- DB-backed MVP에서는 job-scoped artifact root 후보로 `runs/jobs/<job_id>/` 또는 `runs/web_job_<job_id>/`를 사용한다.
- Web UI `full_report` 시간 범위는 코드/UI 기준 최대 24시간까지 허용하지만, 24시간은 권장값이 아니라 허용 상한이다. 운영상 큰 구간은 비용/시간을 보고 후속 `windowed_triage`로 분리 검토한다.

## Operational Output Hygiene

- `data/raw/`, `data/processed/`, `reports/`, `runs/`는 운영 산출물이며 기본적으로 repo에 커밋하지 않는다.
- `runs/`는 runtime artifact로 관리한다.
- `.gitignore`에 `/runs/`가 있어야 하며, 실수로 tracked 된 경우 아래처럼 index에서만 제거한다.

```bash
git rm -r --cached runs/
```

- `pathspec did not match any files`가 나오면 현재 index에 `runs/` tracked 항목이 없다는 의미다.
- MVP에서는 Web UI destructive cleanup을 제공하지 않는다.

## Smoke Check

- loader 회귀:
  - `tests/test_web_loader_run_dir_scan.py`: `5 passed`
  - 관련 묶음: `24 passed`
- actual smoke:
  - scenario: `Mixed_Context_Heavy`
  - security export 기준 actual LLM 실행
  - run_dir: `runs/webui_run_dir_smoke_actual_2026-05-10`
  - Web UI list/detail/payload 표시 확인
  - payload 요약: `finding_count=2`, `context_count=3`, `supporting_event_count=0`
- DB-backed table setup:
  - `docs/operations/sql/01_analysis_job_tables.sql` 적용 후 `analysis_jobs`, `analysis_reports`, `job_events`, `users` 존재 확인
