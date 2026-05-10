# Run Analysis Pipeline User Runner UX Review

- 작성일: 2026-05-08
- 문서 역할: `run_analysis_pipeline.py`의 사용자용 실행 UX, 산출물 저장 기준, manifest 역할, lab/ 실험 산출물 경계를 정리하는 설계 검토 문서
- 관련 문서:
  - `src/README.md`
  - `web/README.md`
  - `docs/design/99_web_ui_report_viewer_execution_scope_review.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`
  - `작업일지/0507.md`

## 0. 현재 상태 업데이트 (2026-05-10)

본 문서는 2026-05-08 시점의 runner UX 검토 문서였고, 이후 Web UI loader 정책이 run_dir 중심으로 전환되었다.

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

## 1. 목적

이 문서는 Apache 웹 로그 기반 LLM 침입 로그 분석 파이프라인에서 `run_analysis_pipeline.py`를 어떤 사용자 UX로 제공할지 검토한다.

핵심 목적은 다음과 같다.

- 일반 사용자와 분석 엔지니어의 실행 책임을 분리한다.
- `run_analysis_pipeline.py`를 사용자용 one-shot runner로 단순화할지 검토한다.
- 산출물 저장 위치와 파일명 기준을 정리한다.
- latest manifest와 run별 manifest의 역할을 분리한다.
- 기존 `lab/` 실험 산출물과 일반 운영 산출물의 경계를 명확히 한다.
- Web UI의 read-only viewer 범위와 pipeline runner 범위를 혼동하지 않게 한다.

## 2. 배경

현재 파이프라인의 기본 흐름은 다음과 같다.

```text
export -> prepare -> stage1 -> stage2
````

향후 Web UI 표시를 위해 다음 단계가 추가 후보로 검토된다.

```text
export -> prepare -> stage1 -> stage2 -> viewer_payload
```

현재 `web/`은 read-only viewer 범위를 유지한다.

단기 기준에서 `web/`은 다음을 하지 않는다.

* pipeline 실행
* report rewrite
* DB/SQLite 저장
* raw JSON/body full search
* source IP raw search
* 새 보안 판정 생성
* candidate/severity/category 재계산

따라서 pipeline 실행 UX는 `web/`의 read-only viewer 범위와 분리해서 검토한다.

## 3. 사용자 역할

### 3.1 일반 분석 사용자

일반 분석 사용자는 웹에서 결과를 조회하는 역할이다.

주요 행동:

* Web UI에 접속한다.
* report list/detail/compare/filter를 조회한다.
* findings, context, evidence, recommended actions를 확인한다.
* 필요하면 Stage2 report Markdown/JSON 또는 viewer payload 기반 상세를 확인한다.

하지 않는 일:

* SSH 접속
* CLI 실행
* DB 접속
* export JSON 직접 생성
* 중간 산출물 선택
* pipeline 재실행
* report rewrite

### 3.2 분석 엔지니어

분석 엔지니어는 단기 운영 기준에서 pipeline 실행을 담당한다.

주요 행동:

* Analysis/LLM Server에 접속한다.
* DB export 결과 JSON을 준비하거나 export 절차를 수행한다.
* `run_analysis_pipeline.py`를 실행한다.
* Stage2 report, viewer payload, manifest 생성을 확인한다.
* 품질 검증과 실패 재실행을 수행한다.

단기 CLI 예시:

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

* Target App Server / Log DB Server / Analysis Server 운영
* `apache_log_shipper.py` 상태 확인
* MariaDB 연결 및 권한 관리
* LLM API key와 `.env` 관리
* Web UI 서비스 실행 상태 관리
* 산출물 보존/정리 정책 관리
* 접근 권한 및 감사 정책 관리

### 3.4 개발자 / 실험자

개발자와 실험자는 코드 변경, 회귀 검증, 실험 산출물 관리를 담당한다.

주요 행동:

* `prepare_llm_input.py`, `llm_stage1_classifier.py`, `llm_stage2_reporter.py` 개별 실행
* regression fixture 관리
* `lab/` 산출물 비교
* Stage2 report quality lint 실행
* 신규 coverage 후보 검토
* Web UI 기능 후보 검토

개발자/실험자는 필요 시 중간 산출물 기반 재개 흐름을 사용할 수 있다.

## 4. 서버 역할

이 시스템은 물리적으로 여러 서버로 나뉠 수 있지만, 사용자 관점에서는 하나의 `Security Analysis Console`로 보이게 한다.

운영 관점의 역할은 다음과 같다.

### 4.1 Target App / Web Service Server

역할:

* Juice Shop, OpenCart 또는 기타 Apache 앞단 서비스를 실행한다.
* Apache access/security/error log를 생성한다.
* `apache_log_shipper.py`를 통해 로그를 Log DB Server로 전송한다.

### 4.2 Log DB Server

역할:

* MariaDB에 Apache 로그를 저장한다.
* export 대상 원천 데이터를 제공한다.
* Web UI가 직접 DB를 제어하지 않는다.

### 4.3 Analysis / LLM Server

역할:

* DB export 실행 또는 export JSON 입력 처리
* prepare 실행
* Stage1 classifier 실행
* Stage2 reporter 실행
* viewer payload 생성
* manifest 기록
* report quality lint 실행
* read-only Web UI 실행

### 4.4 사용자 관점

사용자는 위 내부 구성을 몰라도 된다.

사용자 관점에서는 다음처럼 보이는 것이 목표다.

```text
Security Analysis Console
  - 분석 결과 목록
  - 상세 리포트
  - 비교 화면
  - findings/context/evidence 표시
```

단기적으로 이 콘솔은 read-only report console이다.

## 5. `run_analysis_pipeline.py` UX 방향

### 5.1 기본 방향

`run_analysis_pipeline.py`는 사용자용 one-shot runner 방향을 우선 후보로 둔다.

기본 입력은 export JSON 1개로 단순화하는 방향을 검토한다.

```text
export JSON
  -> prepare
  -> stage1
  -> stage2
  -> viewer_payload
```

일반 사용자 또는 분석 엔지니어가 중간 산출물 구조를 알 필요가 없도록 한다.

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

다만 UX 방향은 다음과 같이 정리한다.

* 일반 사용자용 기본 흐름에서는 노출하지 않는 방향을 검토한다.
* 개발/디버그/실험 흐름에서는 유지 가능하다.
* 제거 또는 deprecate 여부는 별도 코드 변경 검토에서 결정한다.
* one-shot runner UX 정리와 resume 제거는 같은 작업으로 묶지 않는다.

### 5.4 단기 결론

본 문서에서는 CLI 변경을 확정하지 않는다.

다만 다음 방향을 우선 후보로 둔다.

```text
일반 사용자/분석 엔지니어 기본 실행:
- export JSON 1개 입력
- pipeline 전체 실행
- viewer_payload까지 자동 생성

개발/실험 실행:
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

### 6.2 현재 기준(2026-05-10)

현재 Web UI 기본 표시 기준은 `runs/*/manifest.json` 기반 run directory 산출물이다.
`reports/` flat 산출물은 pipeline 호환/병행 산출물로 남을 수 있으나, Web UI 기본 scan 대상은 아니다.
Web UI에서 결과를 보이게 하려면 `run_analysis_pipeline.py --run-dir runs/<run_id>` 사용을 기본 운영 흐름으로 둔다.

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

병행 flat 산출물(호환/추적용):

```text
<work-dir>/
  data/raw/
  data/processed/
  reports/
  pipeline_manifest.json
```

### 6.3 디렉터리 역할

#### `data/raw/`

역할:

* DB export 결과 보관
* pipeline의 시작 입력 보관

#### `data/processed/`

역할:

* prepare 및 Stage1 중간 산출물 보관
* 일반 사용자가 직접 볼 필요는 낮음
* 디버그/검증/재현용으로 사용

#### `reports/`

역할:

* 사람이 보거나 운영 스크립트가 참조하는 최종 산출물 보관
* Stage2 report JSON/Markdown 보관
* viewer payload flat 사본 보관
* run별 manifest 보관

주의:

* 현재 Web UI 기본 목록 discovery 기준은 `reports/`가 아니라 `runs/*/manifest.json`이다.

#### `runs/<run_id>/`

역할:

* Web UI 기본 목록 discovery 기준 entry(`manifest.json`)
* list/detail/payload 조회용 표준 run artifact 묶음 보관

#### `pipeline_manifest.json`

역할:

* latest manifest
* 마지막 실행 결과 경로 확인용
* 덮어쓰기 허용

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

### 7.2 실행 시간 기반 이름은 기본값으로 쓰지 않음

다음과 같은 이름은 기본값으로 사용하지 않는다.

```text
run_2026-05-08_15-20-00
```

이유:

* 실행 시각은 알 수 있지만 분석 대상 시간창이 바로 드러나지 않는다.
* 여러 번 재실행하면 같은 로그 구간의 결과가 흩어진다.
* 보안 분석 산출물은 분석 대상 시간창이 파일명에 드러나는 편이 좋다.

실행 시각은 manifest의 `generated_at`에 기록한다.

## 8. Manifest 기준

### 8.1 Manifest는 두 종류로 분리한다

#### latest manifest

경로:

```text
<work-dir>/pipeline_manifest.json
```

역할:

* 마지막 실행 상태 확인
* 최신 산출물 경로 확인
* Web UI나 운영자가 최근 실행 결과를 찾는 용도

특성:

* 계속 덮어써져도 된다.
* 장기 보존용이 아니다.

#### run별 manifest

경로:

```text
reports/<base>_pipeline_manifest.json
runs/<run_id>/manifest.json
```

역할:

* 특정 분석 실행의 산출물 추적
* report/viewer payload와 같은 묶음으로 보존
* 재현 및 검증용 metadata 제공
* `runs/<run_id>/manifest.json`은 Web UI 기본 scan 기준의 primary manifest entry 역할을 수행

특성:

* base별로 분리된다.
* 일반적으로 보존 대상이다.
* report와 함께 archive 가능하다.

### 8.2 Manifest에 포함할 정보

권장 schema:

```json
{
  "schema_version": "pipeline_manifest.v1",
  "meta": {
    "generated_at": "2026-05-08T00:00:00.000+09:00",
    "manifest_role": "latest_and_run_copy",
    "latest_manifest_path": "/opt/web_log_analysis/pipeline_manifest.json",
    "run_manifest_path": "/opt/web_log_analysis/reports/<base>_pipeline_manifest.json",
    "mode": "routine",
    "llm_provider": "openai",
    "base_name": "<base>",
    "work_dir": "/opt/web_log_analysis",
    "processed_dir": "/opt/web_log_analysis/data/processed",
    "reports_dir": "/opt/web_log_analysis/reports"
  },
  "inputs": {
    "export_input": "/opt/web_log_analysis/data/raw/security_...json"
  },
  "artifacts": {
    "llm_input": "/opt/web_log_analysis/data/processed/<base>_llm_input.json",
    "analysis_candidates": "/opt/web_log_analysis/data/processed/<base>_analysis_candidates.json",
    "noise_summary": "/opt/web_log_analysis/data/processed/<base>_noise_summary.json",
    "stage1_results": "/opt/web_log_analysis/data/processed/<base>_stage1_results.json",
    "stage1_errors": "/opt/web_log_analysis/data/processed/<base>_stage1_errors.json",
    "stage2_report_input": "/opt/web_log_analysis/reports/<base>_stage2_report_input.json",
    "stage2_report_json": "/opt/web_log_analysis/reports/<base>_stage2_report.json",
    "stage2_report_md": "/opt/web_log_analysis/reports/<base>_stage2_report.md",
    "viewer_payload": "/opt/web_log_analysis/reports/<base>_viewer_payload.json",
    "pipeline_manifest_run": "/opt/web_log_analysis/reports/<base>_pipeline_manifest.json"
  },
  "steps": [
    {
      "name": "prepare",
      "return_code": 0
    },
    {
      "name": "stage1",
      "return_code": 0
    },
    {
      "name": "stage2",
      "return_code": 0
    },
    {
      "name": "viewer_payload",
      "return_code": 0
    }
  ]
}
```

### 8.3 Manifest 해석 원칙

Manifest는 보안 판정 결과가 아니다.

Manifest는 다음을 위한 metadata다.

* 입력 경로
* 산출물 경로
* 실행 단계 상태
* 실행 모드
* provider/model 정보
* 생성 시각
* 오류 추적

Manifest를 근거로 공격 성공, 침해 성공, 유출 여부를 판단하지 않는다.

현재 Web UI loader는 기본적으로 `runs/*/manifest.json`를 scan한다.
따라서 run_dir manifest는 단순 보조 산출물이 아니라 Web UI 목록 discovery의 기준 entry다.

## 9. Viewer Payload 기준

### 9.1 역할

`viewer_payload.json`은 Web UI 전용 read-only 입력이다.

역할:

* Stage2 report, Stage1 result, prepare context, supporting events를 UI 표시용으로 정규화한다.
* findings/context/evidence/noise를 Web UI에서 읽기 쉽게 제공한다.
* 원본 report의 보안 의미를 새로 만들지 않는다.

### 9.2 저장 위치(현재 기준)

flat 병행 위치:

```text
reports/<base>_viewer_payload.json
```

Web UI default scan 기준 위치:

```text
runs/<run_id>/viewer_payload.json
```

현재 Web UI payload dashboard의 기본 입력은 run_dir `viewer_payload.json`이다.

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

### 9.4 금지

`viewer_payload_builder.py`는 다음을 하지 않는다.

* LLM 호출
* 새 공격 판별
* severity 재계산
* context-only summary를 incident로 승격
* supporting_event를 candidate로 승격
* 성공/침해/유출 추론
* raw POST body 추정
* response body 원문 추정
* lab-* UA 기반 공격 판별

## 10. `lab/` 기준

### 10.1 역할

`lab/`은 일반 운영 산출물 저장소가 아니며, 현재 Web UI 기본 scan 대상도 아니다.

`lab/`은 다음 용도로 유지한다.

* 기존 비교실험 산출물 archive
* fixture 후보 보존
* regression 검증용 샘플 보존
* 모델/provider 비교 결과 보존
* 발표/검토용 과거 결과 보존

### 10.2 일반 운영 출력과 분리

일반 운영 pipeline 결과는 기본적으로 다음 위치에 저장한다.

```text
<work-dir>/data/raw
<work-dir>/data/processed
<work-dir>/reports
<work-dir>/runs
```

`lab/`에 저장하려면 실험자가 명시적으로 `--work-dir` 또는 관련 경로를 지정한다.

예:

```bash
python src/run_analysis_pipeline.py \
  --export-input lab/05-03_G세트R1_산출물/data/raw/security_2026-05-03_G_R1_kst.json \
  --work-dir lab/05-03_G세트R1_산출물 \
  --base-name openai-g_r1_method_behavior \
  --mode routine \
  --pretty
```

### 10.3 lab/ 보존 원칙

* 기존 lab 산출물은 자동 마이그레이션하지 않는다.
* 일반 운영 UX 개선을 이유로 lab 구조를 변경하지 않는다.
* lab 산출물은 필요 시 별도 archive/fixture 정리 작업으로 다룬다.
* legacy `lab/`/`reports/` 산출물을 Web UI가 직접 archive scan하는 방식은 현재 기본 운영 흐름으로 채택하지 않는다.
  * 기존 산출물이 오래되었거나 `viewer_payload`가 없는 경우가 많아, 기본 목록 품질을 떨어뜨릴 수 있기 때문이다.
* 과거 결과를 최신 Web UI에서 다시 보려면 다음 순서를 우선한다.
  1. 보존된 raw export 존재 여부 확인
  2. 최신 `run_analysis_pipeline.py --run-dir runs/<run_id>`로 재실행
  3. 새 run_dir 산출물로 Web UI에서 조회
* archive opt-in scan은 즉시 구현하지 않고 후속 후보로 보류한다.

## 11. Web UI와의 관계

### 11.1 현재 Web UI

현재 `web/`은 read-only report viewer다.

역할:

* report list(`runs/*/manifest.json` 기반)
* detail(run_dir report 기준)
* payload dashboard(run_dir `viewer_payload.json` 기준)
* compare
* filter
* Stage2 quality lint result 표시
* list/detail/payload에서 `run_id` 표시, partial provider compact UI 반영

### 11.2 Viewer Payload 기반 확장

향후 Web UI는 `viewer_payload.json`을 읽어 다음을 더 명확히 표시할 수 있다.

* Overview
* Findings
* Contexts
* Supporting events
* Noise
* Guardrail notes
* Manifest/artifact links

단, Web UI는 여전히 read-only 원칙을 유지한다.

하지 않는 일:

* pipeline 실행
* report rewrite
* DB 제어
* viewer_payload 재생성
* 새 판정 생성
* category/severity 재계산
* raw body full search
* source IP raw search

### 11.3 Phase 2C와의 경계

다음 기능은 Phase 2C execution console 후보로 남긴다.

* New Analysis
* pipeline run button
* live progress
* regression run button
* scheduling
* alerting

본 문서에서는 구현 범위로 승격하지 않는다.

## 12. Apache logs-only 원칙

Runner UX와 Web UI 표시 모두 Apache logs-only 원칙을 유지한다.

단정 금지:

* raw POST body 내용
* response body 원문
* DB query 결과
* 브라우저 실행 여부
* 로그인 성공
* 계정 탈취
* credential stuffing 성공
* lockout 발동
* PUT 업로드 성공
* DELETE 삭제 성공
* TRACE/XST 성공
* CORS 취약점 성공
* protocol bypass 성공
* malformed request exploit success
* 서버 침해 성공
* static file 존재
* robots/sitemap 내용
* JS 실행
* file exposure
* 실제 crawler 여부
* site structure 노출
* WordPress 존재
* admin access
* `.env`, `phpinfo`, `server-status`, backup 노출
* SSRF outbound 성공
* metadata credential 탈취
* JNDI lookup 성공
* RCE 성공
* callback 수신 성공
* webshell 존재
* command execution 성공
* GraphQL schema 노출 성공
* open redirect 성공
* SSTI 실행 성공
* XXE file read 성공
* API key/token exfiltration 성공

또한 다음을 성공 증거로 사용하지 않는다.

* `status_code=200`
* `text/html`
* `response_body_bytes`
* 특정 route
* 특정 IP
* 특정 product name
* `lab-*` user-agent

## 13. 단계별 제안

### Phase R1: 문서 기준 확정

* 본 문서로 사용자 runner UX 방향을 검토한다.
* Web UI read-only scope 문서와 충돌 여부를 확인한다.
* TODO/진행상황에 현재 상태를 반영한다.

### Phase R2: viewer payload 최소 도입 (완료)

* `src/viewer_payload_builder.py` 추가
* Stage2 이후 `reports/<base>_viewer_payload.json` 생성
* `run_analysis_pipeline.py`에서 viewer payload 생성 옵션 추가
* latest manifest와 run별 manifest 분리
* `--run-dir` 병행 산출물 경로 반영

### Phase R3: runner UX 단순화 검토 (완료/반영)

* `run_analysis_pipeline.py`의 일반 사용자 입력을 `--export-input` 중심으로 정리
* `--llm-input`, `--stage1-results` resume 옵션의 유지/deprecate 여부 검토
* 중간 산출물 재개는 개발/디버그 흐름으로 분리

### Phase R4: Web UI run_dir default scan + viewer payload 표시 (완료)

* Web UI loader 기본 scan을 `runs/*/manifest.json`로 전환
* run_dir `viewer_payload.json` resolve/fallback 반영
* Web UI가 `viewer_payload.json`을 read-only로 표시
* findings/context/evidence/noise 탭 또는 섹션 추가
* 기존 Stage2 report detail/compare 기능과 충돌하지 않게 통합
* actual run_dir smoke 완료:
  - `runs/webui_run_dir_smoke_actual_2026-05-10`
  - security export actual LLM 실행 + list/detail/payload 확인

### 후속 후보(미완료)

* archive opt-in scan 정책/구현 여부 검토
* flat/run_dir dedupe는 archive opt-in 필요 확인 시 검토
* canonical_report_key는 후속 후보로 보류
* provider 비교 구조 일반화(openai/anthropic 고정 -> N-provider)는 장기 후보

### Phase 2C 이후: execution console 후보(비범위 유지)

* New Analysis
* Job Runner
* progress/status
* cancellation/retry
* auth/authorization
* audit trail
* retention/cleanup

별도 risk review 전까지 구현하지 않는다.

## 14. 결론

* 단기적으로 일반 사용자는 Web UI에서 read-only 결과를 조회한다.
* 단기적으로 분석 엔지니어가 CLI로 pipeline을 실행한다.
* 현재 기본 실행 흐름은 `export JSON + --run-dir runs/<run_id>`다.
* Web UI 기본 scan 기준은 `runs/*/manifest.json`이다.
* `run_analysis_pipeline.py`는 사용자용 one-shot runner 방향을 유지한다.
* 기본 입력은 export JSON 1개(`--export-input`)가 가장 적절하다.
* 중간 산출물 resume은 즉시 제거하지 않고 개발/디버그 흐름과 분리 검토한다.
* run_dir 산출물은 Web UI 기본 조회 기준이고, flat output은 병행/호환 산출물로 유지한다.
* `viewer_payload.json`은 flat(`reports/<base>_viewer_payload.json`) + run_dir(`runs/<run_id>/viewer_payload.json`)를 함께 다룬다.
* manifest는 latest + run별 보존 manifest로 분리하며, run_dir manifest는 Web UI discovery의 primary entry다.
* legacy `lab/`/`reports/`는 보존하되 기본 scan에서 제외한다.
* 과거 결과를 Web UI에서 다시 보려면 raw export 기반 재실행으로 run_dir 산출물을 생성하는 방식을 우선한다.
* archive opt-in/dedupe/canonical_report_key는 후속 후보로 보류한다.
* Web UI는 read-only viewer 원칙을 유지한다.
* Phase 2C execution console은 별도 risk review 전까지 구현하지 않는다.
* Apache logs-only 원칙을 유지한다.
