# Pipeline Run Dir Output Layout Plan

- 작성일: 2026-05-09
- 문서 역할: 실행 1회 단위(run) 산출물 묶음 구조(`run_dir`)를 장기 후보로 검토하는 설계 문서
- 관련 문서:
  - `docs/planning/99_비교실험_후속개선_TODO.md`
  - `docs/design/99_run_analysis_pipeline_user_runner_ux_review.md`
  - `docs/design/99_web_ui_report_viewer_execution_scope_review.md`

## 1. 현재 문제

현재 파이프라인 산출물은 flat 구조 중심으로 여러 위치에 분산되어 있다.

- `data/processed/*_llm_input.json`
- `reports/*_stage2_report_input.json`
- `reports/*_stage2_report.json`
- `reports/*_stage2_report.md`
- `reports/*_viewer_payload.json`
- `lab/.../data/processed/*`
- `lab/.../reports/*`

이 구조는 기존 비교 실험과 flat output 호환에는 유리하지만, 실행 1회 단위 추적에는 비용이 크다.

특히 다음 시나리오에서 파일 탐색과 대조 비용이 커진다.

- 특정 실행의 `export -> llm_input -> stage1 -> stage2 -> viewer_payload -> manifest` 연계 확인
- Supporting Events / Related Contexts 조사처럼 복수 산출물 간 비교가 필요한 경우
- run 단위 이력 정리/보존/정리 정책 확장 검토

## 2. 목표

run_dir 구조 도입의 목표는 다음과 같다.

- 실행 1회 단위로 산출물을 단일 디렉터리에 묶는다.
- `manifest.json`을 run 산출물의 source-of-truth로 사용한다.
- Web UI와 CLI가 동일한 run manifest 기준으로 산출물을 찾도록 만든다.
- cleanup/retention/history 확장을 쉽게 한다.

핵심 원칙:

- 기존 flat output 구조는 즉시 제거하지 않는다.
- 초기 방향은 run_dir 병행 생성이다.
- 기존 `reports/`, `data/processed/` 출력과 호환을 유지한다.
- Web UI loader는 추후 flat + run_dir 동시 읽기 호환 모드부터 검토한다.
- pipeline 실행/분석 의미/보안 판정 로직은 변경하지 않는다.
- `viewer_payload_builder`, prepare, Stage1, Stage2의 의미는 변경하지 않는다.
- `severity/category/verdict` 재계산은 하지 않는다.
- context-only 승격은 하지 않는다.

## 3. run_dir 구조 후보

### 3.1 후보 A (우선 검토)

```text
runs/
  <run_id>/
    manifest.json
    export.json
    llm_input.json
    stage1_results.json
    stage2_report_input.json
    stage2_report.json
    stage2_report.md
    viewer_payload.json
    noise_summary.json
    pipeline.log
```

특징:

- 경로가 단순하고 짧다.
- run_id 자체로 실행 단위를 즉시 식별할 수 있다.
- manifest 기준 파일 매핑이 직관적이다.
- run_dir 내부 파일명을 표준 고정 이름으로 단순화할 수 있다.

### 3.2 후보 B

```text
runs/
  2026-05-09/
    12-08-13_v1_test_security/
      manifest.json
      *.json
      *.md
```

특징:

- 날짜 단위 탐색은 쉽다.
- 폴더 depth가 1단계 더 깊다.
- run_id를 단일 문자열로 다루는 경로 규약이 약해질 수 있다.

### 3.3 비교 결론(초기)

- 후보 A는 초기 구현 및 운영 단순성 측면에서 우선 검토한다.
- 후보 B는 날짜별 보관 정책이 강하게 필요해질 때 재검토한다.

### 3.4 run_id/run_dir 기본 규약 (확정 권장)

`src/run_analysis_pipeline.py --export-input <export_json>` 실행 시 기본 run_id는 export input 파일명의 stem을 사용한다.

- 예시 1:
  - export input: `security_2026-05-09_kst.json`
  - run_id: `security_2026-05-09_kst`
  - run_dir: `runs/security_2026-05-09_kst/`
- 예시 2(시간 범위 export):
  - export input: `security_2026-05-09_12-08-13_to_2026-05-09_12-09-27_kst.json`
  - run_id: `security_2026-05-09_12-08-13_to_2026-05-09_12-09-27_kst`
  - run_dir: `runs/security_2026-05-09_12-08-13_to_2026-05-09_12-09-27_kst/`

중요 규칙:

- run_dir 이름에는 `.json` 확장자를 포함하지 않는다.
- 피해야 할 구조: `runs/security_2026-05-09_kst.json/`
- 권장 구조: `runs/security_2026-05-09_kst/`

## 4. manifest 초안

manifest는 run 산출물의 단일 인덱스이자 source-of-truth로 사용한다.

포함 후보 필드:

- `run_id`
- `created_at`
- `scenario`
- `provider` / `model`
- `mode` / `dry_run`
- `prepare_source_tables_requested` / `prepare_source_tables_resolved`
- `files` map
- `counts`
- lint summary
- guardrail/source-of-truth metadata

예시:

```json
{
  "run_id": "security_2026-05-09_kst",
  "run_dir": "runs/security_2026-05-09_kst",
  "source_export_path": "reports/security_2026-05-09_kst.json",
  "created_at": "2026-05-09T12:08:13+09:00",
  "mode": "dry-run",
  "files": {
    "export": "export.json",
    "llm_input": "llm_input.json",
    "stage1_results": "stage1_results.json",
    "stage2_report_input": "stage2_report_input.json",
    "stage2_report_json": "stage2_report.json",
    "stage2_report_md": "stage2_report.md",
    "viewer_payload": "viewer_payload.json"
  },
  "counts": {
    "findings": 10,
    "contexts": 6,
    "supporting_events": 0
  }
}
```

초기 병행 생성 단계(Phase 1)에서는 manifest에 원본 export path(`source_export_path`)와 run_dir 내부 표준 파일 경로(`files`)를 함께 기록하는 방안을 검토한다.

run_dir 내부 파일명은 원본 export 파일명이 길어도 다음 표준 이름을 고정 사용한다.

```text
runs/<run_id>/
  manifest.json
  export.json
  llm_input.json
  stage1_results.json
  stage2_report_input.json
  stage2_report.json
  stage2_report.md
  viewer_payload.json
  noise_summary.json
  pipeline.log
```

## 5. 단계별 전환 계획

### Phase 0

- 문서화만 수행한다.
- 기존 flat output을 그대로 유지한다.

### Phase 1

- run_dir 병행 생성 옵션을 검토한다.
- 기존 `reports/`, `data/processed/` 출력은 유지한다.
- manifest에 flat path와 run_dir path를 모두 기록하는 방안을 검토한다.
- `src/export_db_logs_cli.py`는 기존처럼 export JSON을 생성한다.
  - 예: `security_2026-05-09_kst.json`
  - 예: `security_2026-05-09_12-08-13_to_2026-05-09_12-09-27_kst.json`
- `src/run_analysis_pipeline.py --export-input <json>`은 해당 export JSON의 stem을 기본 run_id로 사용해 run_dir 후보를 만든다.

### Phase 2

- Web UI loader가 flat + run_dir를 모두 읽는 호환 모드를 검토한다.
- 중복 `report_id`/`run_id` dedupe 규칙을 검토한다.

### Phase 3

- 안정화 이후 run_dir를 기본 출력 구조로 전환할지 판단한다.

## 6. Non-goals

이번 문서 범위에서 하지 않는 일:

- 구현 수행 없음
- 기존 flat output 제거 없음
- Web UI loader 수정 없음
- pipeline 실행 방식 변경 없음
- 분석 로직/보안 판정 변경 없음
- report rewrite/DB/SQLite history 구현 없음

## 7. 의사결정 체크포인트

초기 구현 착수 전 확인 항목:

- run_id 규칙(충돌 회피, 재실행 suffix, 시나리오명 sanitize)
- manifest 필수/선택 필드 최소 집합
- flat 경로와 run_dir 경로 동시 기록 규약
- 실패/중단 run의 최소 산출물 기록 기준(`pipeline.log`, partial manifest)
- retention/cleanup 스크립트와의 호환 기준

### 7.1 충돌 정책 (확정 권장)

- 기본 정책은 fail-fast로 한다.
- `runs/<run_id>/`가 이미 존재하면 기본적으로 에러를 내고 중단한다.
- 예시 메시지:

```text
[ERROR] run_dir already exists: runs/<run_id>
Use --run-id to choose another run id or --overwrite to replace it.
```

- `--overwrite`가 명시된 경우에만 기존 run_dir 덮어쓰기/재생성을 허용한다.
- 단, `--overwrite`의 실제 동작은 구현 단계에서 별도 확정한다.
  - 후보 A: 기존 run_dir 삭제 후 재생성
  - 후보 B: known output file만 덮어쓰기
- 안전성 관점에서는 non-empty run_dir 기본 실패를 유지한다.

### 7.2 명시 옵션 후보 (미확정)

아래는 문서상 구현 후보이며, 이번 단계에서 구현하지 않는다.

- `--run-id <name>`: export stem 대신 명시적 run_id 사용
- `--run-dir <path>`: 전체 출력 디렉터리 직접 지정
- `--overwrite`: 기존 run_dir 충돌 시 명시적으로 덮어쓰기 허용
- 기본값: 자동 run_id + fail-fast

## 8. 결론

단기적으로는 flat output 호환을 유지하면서 run_dir 병행 생성을 검토하는 것이 가장 안전하다.

초기 우선안은 후보 A(`runs/<run_id>/...`)이며, manifest를 run 산출물 조회의 기준점으로 삼는다. 이 접근은 현재 분석 의미와 보안 판정 로직을 바꾸지 않고도 실행 단위 추적성과 후속 운영 확장성을 동시에 확보할 수 있다.
