# 99_web_ui_run_dir_loader_phase2_plan

- 기준 시점: 2026-05-09
- 문서 목적: Web UI가 기존 flat `reports/` 기반 목록을 유지하면서 향후 `runs/*/manifest.json` 기반 산출물을 안전하게 읽기 위한 Phase 2 설계안을 정의한다.
- 문서 성격: 구현 전 설계/정책 문서
- 관련 문서:
  - `docs/design/99_pipeline_run_dir_output_layout_plan.md`
  - `docs/design/99_pipeline_run_dir_phase1b_phase2_candidate_review.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`
  - `docs/operations/README.md`

## 0. 현재 상태 업데이트 (2026-05-10)

- 본 문서는 Web UI loader Phase 2 구현 전 작성한 설계/정책 문서다.
- 이후 Phase 2A/2B/2C 문서화와 Phase 2D backend 구현이 완료되었다.
- 현재 Web UI 기본 scan은 `runs/*/manifest.json` 기준이다.
- 기존 `reports/`/`lab/` glob은 `LEGACY_REPORT_GLOBS`로 보존되며 기본 scan에서는 제외된다.
- run_dir manifest에서 `stage2_report.json`을 resolve하고 기존 `Report` 모델로 normalize한다.
- run_dir 표준 `viewer_payload.json` resolve 및 `MISSING_FILE`/`MALFORMED_JSON` fallback이 반영되었다.
- route/template/app.py 변경 없이 loader 계층에서 전환했고, Web UI read-only invariant를 유지했다.
- archive opt-in, flat/run_dir dedupe, canonical_report_key는 아직 구현하지 않았으며 후속 후보로 보류한다.

## 1. 목적

- 본 문서는 Web UI loader의 Phase 2 후보( `runs/*/manifest.json` scan )를 구현 전에 명시적으로 설계한다.
- 기존 flat `reports/` 기반 Web UI 동작을 깨지 않으면서 run_dir 병행 산출물 읽기를 추가하기 위한 정책/후보 비교를 정리한다.
- 이번 작업에서는 코드 구현을 수행하지 않는다.

## 2. 현재 상태 요약

- 작성 당시(2026-05-09) Web UI 기준은 flat output(`reports/`)이었다. 이후 기본 scan은 run_dir manifest 중심으로 전환되었으며, 최신 상태는 `0. 현재 상태 업데이트 (2026-05-10)`를 따른다.
- `run_analysis_pipeline.py --run-dir <path>`는 opt-in 병행 산출물 생성 기능이며, 미지정 시 기존 flat output만 생성한다.
- run_dir에는 아래 표준 파일명이 생성된다.
  - `manifest.json`
  - `export.json`
  - `llm_input.json`
  - `stage1_results.json`
  - `stage2_report_input.json`
  - `stage2_report.json`
  - `stage2_report.md`
  - `viewer_payload.json`
  - `noise_summary.json`
- 작성 당시 기준으로는 Web UI loader가 `runs/`를 scan하지 않는 상태였으나, 이후 `runs/*/manifest.json -> stage2_report.json` discover/normalize가 구현 완료되었다.
- 작성 당시 운영 기준은 flat output 우선이었으나, 이후 기본 scan은 run_dir manifest 중심으로 전환되었다.

## 3. 설계 범위

- `runs/*/manifest.json` scan 정책
- manifest 기반 run 목록 구성
- `viewer_payload.json` 존재/부재 처리 정책
- flat `reports/`와 run_dir 결과 간 중복(dedupe) 정책
- `report_id`와 `run_id` 관계 정리
- legacy/lab archive opt-in scan 정책 검토
- 기존 list/detail/payload route 회귀 방지 기준

## 4. 명시적 비범위 (Non-goals)

- 이번 문서 작성 단계에서 코드 구현 금지
- Web UI에서 pipeline 실행 기능 추가 금지
- Web UI에서 DB 제어 기능 추가 금지
- Web UI에서 report rewrite 금지
- severity/category/verdict 재계산 금지
- context-only 항목을 finding/incident로 승격 금지
- Web UI에서 새로운 보안 판정 생성 금지
- `--run-id`, `--overwrite` 구현 금지
- loader/route/template/app.py/pipeline 실행 로직 수정 금지

## 5. Loader 후보 동작

### 5.1 기본 원칙

- 작성 당시 기본 동작은 기존 flat `reports/` scan 유지였다.
- 작성 당시 Phase 2에서 `runs/*/manifest.json` scan은 "추가 후보"였으며, 이후 기본 scan으로 전환 구현이 완료되었다.
- run_dir 결과를 읽더라도 Web UI는 read-only viewer 범위를 유지한다.

### 5.2 `runs/*/manifest.json` scan 후보

- 후보 A: flat 우선 + run_dir 보조
  - 기존 flat 목록을 먼저 구성
  - run_dir manifest에서 유효 항목만 추가/병합
- 후보 B: flat/run_dir 동시 수집 + dedupe
  - 두 소스에서 모두 수집 후 단일 dedupe pass 적용

권장: 후보 B를 우선 검토한다.
- 이유: dedupe 기준을 한 곳에서 일관 적용하기 쉽고, source별 우선순위 정책을 명시적으로 다룰 수 있다.

### 5.3 invalid manifest 처리

- manifest 파일 없음, JSON 파싱 실패, 필수 키 누락, 경로 참조 불능인 run은 안전 처리해야 한다.
- 정책 후보:
  - 정책 1: 목록에서 제외(skip)
  - 정책 2: "invalid run" 상태로 표시(디버그 가시성 확보)

권장: 기본은 정책 1(skip), 필요 시 debug 모드에서만 정책 2를 허용한다.

### 5.4 `viewer_payload.json` 부재 처리

- 정책 후보:
  - 정책 1: payload route 진입 제한 + "payload unavailable" 상태 표시
  - 정책 2: detail은 허용, payload만 unavailable 표시

권장: 정책 2.
- 기존 detail 가용성을 최대한 유지하고 payload 부재를 명시적으로 분리한다.

## 6. Dedupe 기준 후보 및 권장안

### 6.1 후보 키

- manifest 내부 flat file path
- stage2 report path
- viewer_payload path
- export input path
- run_id

주의:
- `report title`, `generated_at` 같은 표시용 값은 dedupe primary key로 사용하지 않는 쪽을 권장한다.

### 6.2 권장안

권장 dedupe primary key는 "정규화된 stage2 report JSON 실경로"를 1순위로 사용한다.

- 1순위: `stage2_report.json` 실경로(절대경로 정규화)
- 2순위: `viewer_payload.json` 실경로
- 3순위: `export input path` + `run_id` 조합

동일 산출물을 flat와 run_dir가 동시에 가리키면 하나로 합치고, source 메타(`storage_type=flat|run_dir|both`)만 보존한다.

## 7. `report_id` / `run_id` 관계 설계

- `run_id`는 run_dir 디렉터리명 기반 추적 ID다.
- `report_id`는 기존 Web UI route/detail 식별자와의 호환을 유지해야 한다.
- 우선 원칙은 기존 flat report_id 체계를 깨지 않는 것이다.

권장 방향:
- 내부 모델에 `storage_type`(예: `flat`, `run_dir`, `both`)와 `run_id`를 분리 보관한다.
- route 파라미터는 기존 `report_id`를 우선 유지한다.
- run_dir 항목은 route를 새로 늘리기보다, 기존 `report_id` 해석 경로 안에서 source metadata로 처리하는 후보를 우선 검토한다.

route 후보 비교(구현 아님):
- 후보 A: 기존 route 유지(`/report/{report_id}`, `/report/{report_id}/payload`)
- 후보 B: run_id 전용 보조 route 추가

권장: 후보 A 우선. 회귀 리스크와 사용자 혼선을 줄이기 쉽다.

## 8. legacy/lab archive opt-in scan

- 기본 scan 대상에는 legacy/lab archive를 포함하지 않는 것을 우선 권장한다.
- 필요 시 명시적 설정/옵션으로만 확장한다.
- 이유:
  - 오래된 archive와 현재 run_dir 결과가 섞이면 중복/혼동 위험이 커진다.
  - active 운영 관찰과 실험 archive 탐색 목적은 분리하는 편이 안전하다.

## 9. 회귀 방지 체크리스트

- legacy flat/lab scan은 기본 제외 정책을 유지해야 하며, archive opt-in이 필요하면 별도 정책으로 검토해야 함
- 기존 detail route가 깨지면 안 됨
- 기존 viewer_payload route가 깨지면 안 됨
- viewer_payload 없는 결과는 안전 처리해야 함
- Web UI는 read-only 유지
- 보안 판정/심각도/카테고리 재계산 없음
- pipeline 실행 버튼/DB 제어 기능 추가 없음
- context-only 승격 없음
- 새 보안 판정 생성 없음

## 10. 권장 단계

- Phase 2A: 문서 설계 및 loader 입력 모델 정리
- Phase 2B: 테스트 fixture 설계
- Phase 2C: flat-only 회귀 테스트 보강
- Phase 2D: run_dir manifest scan 구현
- Phase 2E: legacy/lab opt-in scan 여부 재검토

참고:
- Phase 2A~2D는 이후 구현/검증이 완료되었고, 본 섹션은 작성 당시의 권장 단계 기록이다.

## 11. 검증 계획

- 문서 작성 단계에서는 코드 테스트가 필요 없다.
- 구현 단계 후보 검증:
  - 기존 flat-only list/detail/payload 회귀 테스트
  - run_dir manifest scan fixture 테스트
  - flat + run_dir 중복 fixture 테스트
  - viewer_payload missing fixture 테스트
  - malformed manifest fixture 테스트
  - read-only invariant 테스트

## 12. 유지 원칙

- Apache logs-only 원칙 유지
- raw POST body, response body 원문, DB 결과, 브라우저 실행 여부는 분석 근거로 사용하지 않음
- `status_code=200`, `text/html`, `response_body_bytes`, route name, UA, IP만으로 성공/침해/유출/파일 노출/로그인 성공 단정 금지
- Web UI는 read-only viewer 유지
- pipeline 실행/DB 제어/report rewrite/새 보안 판정 생성 금지
- context-only 승격 금지
- severity/category/verdict 재계산 금지
