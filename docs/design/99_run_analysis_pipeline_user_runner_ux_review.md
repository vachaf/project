# Run Analysis Pipeline User Runner UX Review

- 작성일: 2026-05-08
- 최근 갱신: 2026-05-28
- 문서 역할: `run_analysis_pipeline.py`의 사용자용 실행 UX, 산출물 저장 기준, Web UI 표시 범위, DB-backed MVP 이후의 job lifecycle 경계를 정리한다.
- 관련 문서:
  - `src/README.md`
  - `web/README.md`
  - `docs/design/99_db_backed_log_collection_and_analysis_job_design.md`
  - `docs/design/99_db_backed_web_ui_api_safety_addendum.md`
  - `docs/design/99_web_ui_report_viewer_execution_scope_review.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`
  - `작업일지/0507.md`
  - `작업일지/0528.md`

## 0. 현재 상태 업데이트

### 0.1 2026-05-10 업데이트

본 문서는 원래 2026-05-08 시점의 runner UX 검토 문서였고, 이후 Web UI loader 정책이 run_dir 중심으로 전환되었다.

- 현재 Web UI 기본 scan:
  - `REPORT_GLOBS=["runs/*/manifest.json"]`
- legacy flat/lab glob:
  - `LEGACY_REPORT_GLOBS=["reports/*_stage2_report.json", "lab/**/reports/*_stage2_report.json"]`
  - 기본 scan 제외, 호환/보존 후보로 유지
- Web UI 표시를 운영 기본 흐름으로 사용할 때는 `run_analysis_pipeline.py --run-dir runs/<run_id>` 지정을 기준으로 둔다.
- run_dir 표준 산출물:
  - `manifest.json`
  - `export.json`
  - `llm_input.json`
  - `stage1_results.json`
  - `stage2_report_input.json`
  - `stage2_report.json`
  - `stage2_report.md`
  - `viewer_payload.json`
  - `noise_summary.json`
- actual smoke 완료:
  - `runs/webui_run_dir_smoke_actual_2026-05-10`
  - security export 기준 actual LLM 실행
  - Web UI list/detail/payload 확인 완료
- `archive opt-in` / `flat-run_dir dedupe` / `canonical_report_key`는 후속 후보로 보류한다.

### 0.2 2026-05-28 업데이트: DB-backed MVP 방향 전환

교수님 피드백 반영 후, 상위 운영 방향은 DB-backed 웹 기반 로그 분석 플랫폼으로 전환한다.

새 상위 흐름:

```text
Apache 로그 수집
  -> MariaDB 적재
  -> Web UI에서 분석 작업 등록
  -> analysis_jobs PENDING 생성
  -> Analysis Agent가 job claim
  -> export / prepare / Stage1 / Stage2 / viewer_payload 실행
  -> analysis_reports와 artifact 저장
  -> Web UI에서 상태와 결과 확인
```

따라서 이 문서의 기존 viewer-only 표현은 다음처럼 재해석한다.

```text
유지:
- Web UI는 보안 분석 결과 해석에 대해서는 read-only다.
- Web UI는 Stage2 report 의미를 수정하지 않는다.
- Web UI는 severity/category/verdict/success를 재계산하지 않는다.

변경:
- DB-backed MVP에서는 Web UI가 analysis_jobs 등록/조회 DB read/write를 수행할 수 있다.
- pipeline 실행은 Web UI 프로세스가 직접 수행하지 않고, Analysis Agent가 DB job을 claim해 수행한다.
- 기존 CLI runner는 fallback/debug/manual path로 유지한다.
```

핵심 기준:

```text
Web UI read-only 원칙 = 보안 결과 해석 read-only
DB-backed job lifecycle = analysis_jobs 등록/조회 허용
```

## 1. 목적

이 문서는 Apache 웹 로그 기반 LLM 침입 로그 분석 파이프라인에서 runner UX와 Web UI의 책임 경계를 정리한다.

핵심 목적은 다음과 같다.

- 일반 사용자, 분석 엔지니어, 시스템 관리자, 개발자의 실행 책임을 분리한다.
- `run_analysis_pipeline.py`를 manual/fallback/debug용 one-shot runner로 유지한다.
- DB-backed MVP에서 사용자는 Web UI로 `analysis_jobs`를 등록하고, Analysis Agent가 실행하는 구조를 명확히 한다.
- 산출물 저장 위치와 파일명 기준을 정리한다.
- latest manifest와 run별 manifest의 역할을 분리한다.
- 기존 `lab/` 실험 산출물과 일반 운영 산출물의 경계를 명확히 한다.
- Web UI의 보안 결과 read-only 범위와 DB-backed job lifecycle 범위를 혼동하지 않게 한다.

## 2. 배경

기존 파이프라인의 기본 흐름은 다음과 같다.

```text
export -> prepare -> stage1 -> stage2
```

Web UI 표시를 위해 다음 단계가 추가되었다.

```text
export -> prepare -> stage1 -> stage2 -> viewer_payload
```

2026-05-08 기준에서는 `web/`을 read-only viewer로 두고 pipeline 실행 UX를 분리했다.
당시 `web/`은 다음을 하지 않는다고 정리했다.

```text
- pipeline 실행
- report rewrite
- DB/SQLite 저장
- raw JSON/body full search
- source IP raw search
- 새 보안 판정 생성
- candidate/severity/category 재계산
```

2026-05-28 DB-backed MVP 기준에서는 이 중 일부를 재해석한다.

```text
계속 금지:
- report rewrite
- raw JSON/body full search
- source IP raw search
- 새 보안 판정 생성
- candidate/severity/category 재계산
- Stage2 report 의미 변경

허용:
- analysis_jobs 등록
- analysis_jobs 목록/상세 조회
- job_events 조회
- analysis_reports artifact path 조회
```

즉, Web UI는 더 이상 완전한 viewer-only 컴포넌트가 아니다.
다만 보안 결과 해석과 report 의미에 대해서는 계속 read-only다.

## 3. 사용자 역할

### 3.1 일반 분석 사용자

일반 분석 사용자는 웹에서 분석 작업을 등록하고 결과를 조회하는 역할이다.

주요 행동:

- Web UI에 접속한다.
- 분석할 시작/종료 시간을 입력해 `analysis_jobs`를 등록한다.
- job list/detail에서 `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED` 상태를 확인한다.
- 완료된 job의 Stage2 report 또는 `viewer_payload.json` 기반 상세를 확인한다.
- findings, context, evidence, recommended actions를 확인한다.

하지 않는 일:

- SSH 접속
- CLI 직접 실행
- DB 직접 접속
- export JSON 직접 생성
- 중간 산출물 직접 선택
- report rewrite
- severity/category/verdict/success 재계산

### 3.2 분석 엔지니어

분석 엔지니어는 DB-backed MVP 이전/이후 모두 fallback/debug/manual 실행을 담당할 수 있다.

주요 행동:

- Analysis/LLM Server에 접속한다.
- DB export 결과 JSON을 준비하거나 export 절차를 수행한다.
- `run_analysis_pipeline.py`를 직접 실행해 manual full report path를 확인한다.
- Stage2 report, viewer payload, manifest 생성을 확인한다.
- 품질 검증과 실패 재실행을 수행한다.
- DB-backed Analysis Agent 실패 시 artifact와 job_events를 확인한다.

manual CLI 예시:

```bash
python ./src/run_analysis_pipeline.py \
  --llm-provider openai \
  --export-input ./data/raw/security_2026-04-24_13-20-00_to_2026-04-24_13-37-00_kst.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --pretty
```

### 3.3 시스템 관리자

시스템 관리자는 실행 환경과 보존 정책을 관리한다.

주요 행동:

- Target App Server / Log DB Server / Analysis Server 운영
- `apache_log_shipper.py` 상태 확인
- MariaDB 연결 및 권한 관리
- LLM API key와 `.env` 관리
- Web UI 서비스 실행 상태 관리
- Analysis Agent 서비스 실행 상태 관리
- 산출물 보존/정리 정책 관리
- 접근 권한 및 감사 정책 관리

### 3.4 개발자 / 실험자

개발자와 실험자는 코드 변경, 회귀 검증, 실험 산출물 관리를 담당한다.

주요 행동:

- `prepare_llm_input.py`, `llm_stage1_classifier.py`, `llm_stage2_reporter.py` 개별 실행
- regression fixture 관리
- `lab/` 산출물 비교
- Stage2 report quality lint 실행
- 신규 coverage 후보 검토
- Web UI 기능 후보 검토
- DB-backed job lifecycle regression 추가

개발자/실험자는 필요 시 중간 산출물 기반 재개 흐름을 사용할 수 있다.

## 4. 서버 역할

이 시스템은 물리적으로 여러 서버로 나뉠 수 있지만, 사용자 관점에서는 하나의 `Security Analysis Console`로 보이게 한다.

### 4.1 Target App / Web Service Server

역할:

- Juice Shop, OpenCart 또는 기타 Apache 앞단 서비스를 실행한다.
- Apache access/security/error log를 생성한다.
- `apache_log_shipper.py`를 통해 로그를 Log DB Server로 전송한다.

### 4.2 Log DB Server

역할:

- MariaDB에 Apache 로그를 저장한다.
- 기존 3개 로그 source table을 유지한다.
  - `apache_access_logs`
  - `apache_security_logs`
  - `apache_error_logs`
- export 대상 원천 데이터를 제공한다.
- `analysis_jobs`, `analysis_reports`, `job_events` 같은 operation/control table을 보유할 수 있다.

### 4.3 Analysis / LLM Server

역할:

- DB export 실행 또는 export JSON 입력 처리
- prepare 실행
- Stage1 classifier 실행
- Stage2 reporter 실행
- viewer payload 생성
- manifest 기록
- report quality lint 실행
- Analysis Agent 실행
- read-only report display용 Web UI 실행 후보

### 4.4 Web UI / Security Analysis Console

사용자 관점에서는 다음처럼 보이는 것이 목표다.

```text
Security Analysis Console
  - 분석 작업 등록
  - 작업 상태 목록
  - 완료 보고서 목록
  - 상세 리포트
  - viewer_payload dashboard
  - findings/context/evidence 표시
```

주의:

```text
Web UI는 job lifecycle을 관리할 수 있다.
하지만 Web UI는 보안 결과를 새로 판단하지 않는다.
```

## 5. `run_analysis_pipeline.py` UX 방향

### 5.1 기본 방향

`run_analysis_pipeline.py`는 DB-backed MVP 이후에도 유지한다.

역할:

```text
- manual one-shot runner
- fallback/debug runner
- regression/smoke runner
- Analysis Agent 내부에서 재사용 가능한 pipeline wrapper 후보
```

기본 입력은 export JSON 1개로 단순화하는 방향을 유지한다.

```text
export JSON
  -> prepare
  -> stage1
  -> stage2
  -> viewer_payload
```

DB-backed MVP에서는 이 흐름을 Analysis Agent가 job-scoped artifact root에서 실행하는 방향을 우선한다.

```text
analysis_jobs PENDING
  -> Analysis Agent claim
  -> export_db_logs_cli.py
  -> export.json
  -> run_analysis_pipeline.py 또는 동등한 pipeline wrapper
  -> viewer_payload.json
  -> analysis_reports
  -> SUCCEEDED
```

### 5.2 기본 입력

우선 후보:

```text
--export-input <path>
```

`--export-input`은 DB export 결과 JSON이다.

예:

```bash
python ./src/run_analysis_pipeline.py \
  --export-input ./data/raw/security_2026-04-24_13-20-00_to_2026-04-24_13-37-00_kst.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --pretty
```

### 5.3 중간 산출물 resume 옵션

현재 또는 기존 runner에는 다음과 같은 재개 흐름이 있을 수 있다.

```text
--llm-input
--stage1-results
```

이 옵션들은 즉시 제거하지 않는다.

UX 방향:

- 일반 사용자용 Web UI에서는 노출하지 않는다.
- 개발/디버그/실험 흐름에서는 유지 가능하다.
- 제거 또는 deprecate 여부는 별도 코드 변경 검토에서 결정한다.
- one-shot runner UX 정리와 resume 제거는 같은 작업으로 묶지 않는다.

### 5.4 단기 결론

본 문서에서는 CLI 변경을 확정하지 않는다.

다만 다음 방향을 우선한다.

```text
일반 사용자:
- Web UI에서 analysis_jobs 등록
- Web UI에서 결과 확인

Analysis Agent:
- export JSON 생성
- pipeline 전체 실행
- viewer_payload까지 자동 생성

분석 엔지니어/개발자:
- run_analysis_pipeline.py manual/fallback 실행
- 개별 stage script 직접 실행
- 필요 시 중간 산출물 기반 재개
```

## 6. 산출물 저장 기준

### 6.1 과거 기준(2026-05-08)

작성 당시 단기 기준은 flat output 중심이었다.

```text
<work-dir>/
  data/
    raw/
      security_...json

    processed/
      <base>_llm_input.json
      <base>_analysis_candidates.json
      <base>_noise_summary.json
      <base>_stage1_results.json
      <base>_stage1_errors.json

  reports/
      <base>_stage2_report_input.json
      <base>_stage2_report.json
      <base>_stage2_report.md
      <base>_viewer_payload.json
      <base>_pipeline_manifest.json

  pipeline_manifest.json
```

### 6.2 현재 기준: run_dir

현재 Web UI 기본 표시 기준은 `runs/*/manifest.json` 기반 run directory 산출물이다.
`reports/` flat 산출물은 pipeline 호환/병행 산출물로 남을 수 있으나, Web UI 기본 scan 대상은 아니다.

현재 run_dir 구조 예시:

```text
<work-dir>/
  runs/
    <run_id>/
      manifest.json
      export.json
      llm_input.json
      noise_summary.json
      stage1_results.json
      stage2_report_input.json
      stage2_report.json
      stage2_report.md
      viewer_payload.json
```

DB-backed MVP에서는 job 단위 artifact root를 둔다.

후보:

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
- Web UI/API 입력으로 임의 output path를 받지 않는다.
- work_dir 밖 artifact write를 금지한다.
```

### 6.3 디렉터리 역할

#### `data/raw/`

역할:

- DB export 결과 보관
- pipeline의 시작 입력 보관

#### `data/processed/`

역할:

- prepare 및 Stage1 중간 산출물 보관
- 일반 사용자가 직접 볼 필요는 낮음
- 디버그/검증/재현용으로 사용

#### `reports/`

역할:

- 사람이 보거나 운영 스크립트가 참조하는 최종 산출물 보관
- Stage2 report JSON/Markdown 보관
- viewer payload flat 사본 보관
- run별 manifest 보관

주의:

- 현재 Web UI 기본 목록 discovery 기준은 `reports/`가 아니라 `runs/*/manifest.json`이다.

#### `runs/<run_id>/` / `runs/jobs/<job_id>/`

역할:

- Web UI 기본 목록 discovery 기준 entry(`manifest.json`)
- list/detail/payload 조회용 표준 run artifact 묶음 보관
- DB-backed MVP에서는 job-scoped artifact root 후보

#### `pipeline_manifest.json`

역할:

- latest manifest
- 마지막 실행 결과 경로 확인용
- 덮어쓰기 허용
- 장기 보존용이 아님

## 7. 파일명 기준

### 7.1 base name

`base_name`은 산출물 묶음을 식별하는 접두어다.

기본 후보:

```text
<provider>-<export_input_stem>
```

또는 기존 관례가 있는 경우:

```text
op-security_2026-04-24_13-20-00_to_2026-04-24_13-37-00_kst
```

DB-backed MVP에서는 `job_id` 기반 이름을 우선 후보로 둔다.

```text
web_job_<job_id>
```

### 7.2 실행 시간 기반 이름은 기본값으로 쓰지 않음

다음과 같은 이름은 기본값으로 사용하지 않는다.

```text
run_2026-05-08_15-20-00
```

이유:

- 실행 시각은 알 수 있지만 분석 대상 시간창이 바로 드러나지 않는다.
- 여러 번 재실행하면 같은 로그 구간의 결과가 흩어진다.
- 보안 분석 산출물은 분석 대상 시간창 또는 job_id가 드러나는 편이 좋다.

실행 시각은 manifest의 `generated_at`에 기록한다.

## 8. Manifest 기준

### 8.1 Manifest는 두 종류로 분리한다

#### latest manifest

경로:

```text
<work-dir>/pipeline_manifest.json
```

역할:

- 마지막 실행 상태 확인
- 최신 산출물 경로 확인용
- 장기 보존용이 아님

#### run별 manifest

경로:

```text
reports/<base>_pipeline_manifest.json
runs/<run_id>/manifest.json
runs/jobs/<job_id>/manifest.json
```

역할:

- 특정 분석 실행의 산출물 추적
- report/viewer payload와 같은 묶음으로 보존
- 재현 및 검증용 metadata 제공
- Web UI 목록 discovery의 기준 entry

### 8.2 Manifest에 포함할 정보

권장 schema 후보:

```json
{
  "schema_version": "pipeline_manifest.v1",
  "meta": {
    "generated_at": "2026-05-08T00:00:00.000+09:00",
    "manifest_role": "run_copy",
    "run_manifest_path": "/opt/web_log_analysis/runs/<run_id>/manifest.json",
    "mode": "routine",
    "llm_provider": "openai",
    "base_name": "<base>",
    "work_dir": "/opt/web_log_analysis"
  },
  "inputs": {
    "export_input": "/opt/web_log_analysis/runs/<run_id>/export.json"
  },
  "artifacts": {
    "llm_input": "/opt/web_log_analysis/runs/<run_id>/llm_input.json",
    "analysis_candidates": "/opt/web_log_analysis/runs/<run_id>/analysis_candidates.json",
    "noise_summary": "/opt/web_log_analysis/runs/<run_id>/noise_summary.json",
    "stage1_results": "/opt/web_log_analysis/runs/<run_id>/stage1_results.json",
    "stage2_report_input": "/opt/web_log_analysis/runs/<run_id>/stage2_report_input.json",
    "stage2_report_json": "/opt/web_log_analysis/runs/<run_id>/stage2_report.json",
    "stage2_report_md": "/opt/web_log_analysis/runs/<run_id>/stage2_report.md",
    "viewer_payload": "/opt/web_log_analysis/runs/<run_id>/viewer_payload.json"
  },
  "steps": [
    {"name": "prepare", "return_code": 0},
    {"name": "stage1", "return_code": 0},
    {"name": "stage2", "return_code": 0},
    {"name": "viewer_payload", "return_code": 0}
  ]
}
```

### 8.3 Manifest 해석 원칙

Manifest는 보안 판정 결과가 아니다.

Manifest는 다음을 위한 metadata다.

- 입력 경로
- 산출물 경로
- 실행 단계 상태
- 실행 모드
- provider/model 정보
- 생성 시각
- 오류 추적

Manifest를 근거로 공격 성공, 침해 성공, 유출 여부를 판단하지 않는다.

## 9. Viewer Payload 기준

### 9.1 역할

`viewer_payload.json`은 Web UI 전용 read-only 입력이다.

역할:

- Stage2 report, Stage1 result, prepare context, supporting events를 UI 표시용으로 정규화한다.
- findings/context/evidence/noise를 Web UI에서 읽기 쉽게 제공한다.
- 원본 report의 보안 의미를 새로 만들지 않는다.

### 9.2 저장 위치

flat 병행 위치:

```text
reports/<base>_viewer_payload.json
```

Web UI default scan 기준 위치:

```text
runs/<run_id>/viewer_payload.json
runs/jobs/<job_id>/viewer_payload.json
```

### 9.3 생성 시점

`viewer_payload.json`은 Stage2 완료 후 생성한다.

```text
stage2_report.json
stage2_report_input.json
stage1_results.json
llm_input.json
noise_summary.json
raw export JSON
  -> viewer_payload_builder.py
  -> viewer_payload.json
```

DB-backed MVP에서 `analysis_jobs.status=SUCCEEDED`는 `viewer_payload.json` 생성 완료 이후에만 가능하다.

### 9.4 금지

`viewer_payload_builder.py`는 다음을 하지 않는다.

- LLM 호출
- 새 공격 판별
- severity 재계산
- context-only summary를 incident로 승격
- supporting_event를 candidate로 승격
- 성공/침해/유출 추론
- raw POST body 추정
- response body 원문 추정
- lab-* UA 기반 공격 판별

## 10. `lab/` 기준

### 10.1 역할

`lab/`은 일반 운영 산출물 저장소가 아니며, 현재 Web UI 기본 scan 대상도 아니다.

`lab/`은 다음 용도로 유지한다.

- 기존 비교실험 산출물 archive
- fixture 후보 보존
- regression 검증용 샘플 보존
- 모델/provider 비교 결과 보존
- 발표/검토용 과거 결과 보존

### 10.2 일반 운영 출력과 분리

일반 운영 pipeline 결과는 기본적으로 다음 위치에 저장한다.

```text
<work-dir>/data/raw
<work-dir>/data/processed
<work-dir>/reports
<work-dir>/runs
```

DB-backed MVP에서는 job-scoped artifact root를 추가 후보로 둔다.

```text
<work-dir>/runs/jobs/<job_id>
```

`lab/`에 저장하려면 실험자가 명시적으로 `--work-dir` 또는 관련 경로를 지정한다.

### 10.3 lab/ 보존 원칙

- 기존 lab 산출물은 자동 마이그레이션하지 않는다.
- 일반 운영 UX 개선을 이유로 lab 구조를 변경하지 않는다.
- lab 산출물은 필요 시 별도 archive/fixture 정리 작업으로 다룬다.
- legacy `lab/`/`reports/` 산출물을 Web UI가 직접 archive scan하는 방식은 현재 기본 운영 흐름으로 채택하지 않는다.
- 과거 결과를 최신 Web UI에서 다시 보려면 raw export 기반 재실행으로 run_dir 산출물을 생성하는 방식을 우선한다.
- archive opt-in scan은 즉시 구현하지 않고 후속 후보로 보류한다.

## 11. Web UI와의 관계

### 11.1 기존 Web UI viewer 기준

기존 `web/`은 read-only report viewer였다.

역할:

- report list(`runs/*/manifest.json` 기반)
- detail(run_dir report 기준)
- payload dashboard(run_dir `viewer_payload.json` 기준)
- compare
- filter
- Stage2 quality lint result 표시
- list/detail/payload에서 `run_id` 표시

이 기준은 보안 결과 해석에 대해서는 계속 유지한다.

### 11.2 DB-backed MVP 기준

DB-backed MVP에서는 Web UI가 다음을 추가로 수행할 수 있다.

- `analysis_jobs` 등록
- `analysis_jobs` list/detail 조회
- `job_events` timeline 조회
- `analysis_reports` artifact metadata 조회
- 완료 job의 `viewer_payload.json` / `stage2_report.md` 표시

하지만 Web UI가 직접 수행하지 않는 것은 유지한다.

- pipeline stage 직접 실행
- report rewrite
- viewer_payload 재생성
- 새 판정 생성
- category/severity 재계산
- raw body full search
- source IP raw search
- API key/config 표시

실행은 다음 구조로 분리한다.

```text
Web UI
  -> analysis_jobs INSERT
  -> DB status 표시

Analysis Agent
  -> PENDING job claim
  -> export/prepare/stage1/stage2/viewer_payload 실행
  -> SUCCEEDED/FAILED 상태 갱신
```

### 11.3 Viewer Payload 기반 확장

향후 Web UI는 `viewer_payload.json`을 읽어 다음을 더 명확히 표시할 수 있다.

- Overview
- Findings
- Contexts
- Supporting events
- Noise
- Guardrail notes
- Manifest/artifact links

단, Web UI는 보안 결과 해석에 대해서는 read-only 원칙을 유지한다.

### 11.4 Phase 2C와의 경계 재정의

기존 Phase 2C execution console 후보는 다음이었다.

- New Analysis
- pipeline run button
- live progress
- regression run button
- scheduling
- alerting

2026-05-28 DB-backed MVP에서는 이 중 일부를 제한적으로 승격한다.

```text
MVP에 포함 가능:
- New Analysis = time range 기반 analysis_jobs 등록
- progress/status = PENDING/RUNNING/SUCCEEDED/FAILED 표시

MVP에서 제외:
- regression run button
- arbitrary pipeline run button
- arbitrary input/output path 지정
- scheduling
- alerting
- cancellation/retry
- destructive cleanup
```

즉, DB-backed MVP는 임의 실행 console이 아니다.
허용 범위는 time range 기반 `full_report` job lifecycle로 제한한다.

## 12. Web UI / API safety policy

DB-backed MVP는 다음 표시/보호 정책을 따른다.

### 12.1 Stage2 의미 보존

- Stage2 report 원문 의미를 변경하지 않는다.
- viewer_payload는 Stage2 report를 UI 표시용으로 정규화할 수 있지만, 새 결론을 만들지 않는다.
- UI는 Stage2 결과를 더 강한 verdict/success 표현으로 바꾸지 않는다.

### 12.2 IP masking 유지

- Web UI는 기존 IP masking 정책을 유지한다.
- list/detail/search/filter에서 raw source IP 전체 노출을 기본값으로 두지 않는다.
- 운영자/개발자 debug path가 필요하면 별도 권한/환경변수/CLI 범위에서 검토한다.

### 12.3 raw preview 과노출 금지

기본 Web UI에서는 다음을 원문 preview로 직접 노출하지 않는다.

- raw_log 전체
- raw_request 전체
- raw header 전체
- Cookie 값
- Authorization 값
- request body
- response body
- API key/token/secret 후보 문자열

### 12.4 missing provider 표시

provider/model/report component가 없을 때는 다음처럼 표시한다.

```text
provider: N/A
model: N/A
stage2_report: N/A
```

정책:

- missing provider에는 detail link를 만들지 않는다.
- missing provider를 오류나 보안 신호로 과장하지 않는다.

### 12.5 secret/config 보호

금지:

- Web UI에 API key 표시
- Web UI에 `.env` 내용 표시
- job_events.detail_json에 API key 저장
- analysis_jobs.error_message에 API key 저장
- provider raw error response를 그대로 UI에 표시
- artifact path 외부에 config dump 저장

## 13. Apache logs-only 원칙

Runner UX, Analysis Agent, Web UI 표시 모두 Apache logs-only 원칙을 유지한다.

단정 금지:

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
- `.env`, `phpinfo`, `server-status`, backup 노출
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

또한 다음을 성공 증거로 사용하지 않는다.

- `status_code=200`
- `text/html`
- `response_body_bytes`
- 특정 route
- 특정 IP
- 특정 product name
- `lab-*` user-agent

## 14. 단계별 제안

### Phase R1: 문서 기준 확정

- runner UX 방향 검토.
- Web UI viewer-only scope 문서와 충돌 여부 확인.
- TODO/진행상황 반영.

상태: 완료.

### Phase R2: viewer payload 최소 도입

- `src/viewer_payload_builder.py` 추가.
- Stage2 이후 `reports/<base>_viewer_payload.json` 생성.
- `run_analysis_pipeline.py`에서 viewer payload 생성 옵션 추가.
- latest manifest와 run별 manifest 분리.
- `--run-dir` 병행 산출물 경로 반영.

상태: 완료.

### Phase R3: runner UX 단순화 검토

- `run_analysis_pipeline.py`의 manual/fallback 입력을 `--export-input` 중심으로 정리.
- `--llm-input`, `--stage1-results` resume 옵션의 유지/deprecate 여부 검토.
- 중간 산출물 재개는 개발/디버그 흐름으로 분리.

상태: 완료/반영.

### Phase R4: Web UI run_dir default scan + viewer payload 표시

- Web UI loader 기본 scan을 `runs/*/manifest.json`로 전환.
- run_dir `viewer_payload.json` resolve/fallback 반영.
- Web UI가 `viewer_payload.json`을 read-only로 표시.
- findings/context/evidence/noise 탭 또는 섹션 추가.
- 기존 Stage2 report detail/compare 기능과 충돌하지 않게 통합.
- actual run_dir smoke 완료:
  - `runs/webui_run_dir_smoke_actual_2026-05-10`
  - security export actual LLM 실행 + list/detail/payload 확인.

상태: 완료.

### Phase DB-MVP: DB-backed analysis job lifecycle

다음 우선순위:

```text
1. DB schema/migration 정리
2. validation/redaction policy 구현 기준 확정
3. analysis_jobs 등록/조회 API
4. 단일 Analysis Agent polling
5. export_db_logs_cli.py 연동
6. artifact_root / analysis_reports 연결
```

MVP 포함:

- time range 기반 job 등록
- `analysis_mode=full_report`
- `requested_timezone=Asia/Seoul`
- 일반 Web UI job 최대 time range 허용 상한 24시간
- PENDING/RUNNING 동일 범위 중복 job 차단 또는 기존 job 반환
- job-scoped artifact root
- Stage1/Stage2/viewer_payload 완료 후 `SUCCEEDED`

MVP 제외:

- arbitrary pipeline run button
- arbitrary file path input
- regression run button
- scheduling
- alerting
- cancellation/retry
- destructive cleanup
- object storage

## 15. 결론

2026-05-08 기준 결론은 다음이었다.

```text
단기적으로 일반 사용자는 Web UI에서 read-only 결과를 조회한다.
단기적으로 분석 엔지니어가 CLI로 pipeline을 실행한다.
```

2026-05-28 이후 기준은 다음으로 갱신한다.

```text
일반 사용자는 Web UI에서 time range 기반 analysis_jobs를 등록하고 상태를 확인한다.
Analysis Agent가 DB의 PENDING job을 claim해 full_report pipeline을 실행한다.
Stage1/Stage2/viewer_payload 생성과 report/artifact 저장이 끝나면 SUCCEEDED로 본다.
기존 run_analysis_pipeline.py는 manual/fallback/debug runner로 유지한다.
Web UI는 보안 결과 해석에 대해서는 read-only 원칙을 유지한다.
```

최종 경계:

```text
허용:
- Web UI job 등록/조회
- Analysis Agent job 실행
- viewer_payload/stage2_report 표시

금지:
- Web UI 보안 verdict 재계산
- Stage2 report 의미 변경
- raw secret/config 노출
- arbitrary execution console화
```

Apache logs-only 원칙은 계속 유지한다.
