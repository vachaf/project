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
  2026-05-09_12-08-13_v1_test_security/
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
  "run_id": "2026-05-09_12-08-13_v1_test_security",
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

초기 병행 생성 단계(Phase 1)에서는 `files` 내부에 flat 경로와 run_dir 상대 경로를 함께 기록하는 방안을 검토한다.

## 5. 단계별 전환 계획

### Phase 0

- 문서화만 수행한다.
- 기존 flat output을 그대로 유지한다.

### Phase 1

- run_dir 병행 생성 옵션을 검토한다.
- 기존 `reports/`, `data/processed/` 출력은 유지한다.
- manifest에 flat path와 run_dir path를 모두 기록하는 방안을 검토한다.

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

## 8. 결론

단기적으로는 flat output 호환을 유지하면서 run_dir 병행 생성을 검토하는 것이 가장 안전하다.

초기 우선안은 후보 A(`runs/<run_id>/...`)이며, manifest를 run 산출물 조회의 기준점으로 삼는다. 이 접근은 현재 분석 의미와 보안 판정 로직을 바꾸지 않고도 실행 단위 추적성과 후속 운영 확장성을 동시에 확보할 수 있다.
