# 99_web_ui_loader_phase2a_input_model_review

- 기준 시점: 2026-05-10
- 문서 목적: Web UI loader Phase 2A에서 기존 flat `reports/` 기반 입력 모델을 조사하고, 향후 `run_dir` 항목을 같은 목록/상세/payload 모델로 표현하기 위한 내부 필드 후보와 회귀 기준을 정리한다.
- 문서 성격: 구현 전 조사/입력 모델 리뷰 문서
- 관련 문서:
  - `docs/design/99_web_ui_run_dir_loader_phase2_plan.md`
  - `docs/design/99_pipeline_run_dir_output_layout_plan.md`
  - `docs/design/99_pipeline_run_dir_phase1b_phase2_candidate_review.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`
  - `docs/operations/README.md`

## 1. 목적

Phase 2A의 목적은 `runs/*/manifest.json` scan 구현이 아니라, 현재 Web UI loader가 어떤 입력을 기준으로 list/detail/payload 화면을 구성하는지 명시적으로 고정하는 것이다.

이를 바탕으로 다음을 결정한다.

- 기존 flat `reports/` loader 흐름의 기준 계약
- list/detail/payload route가 기대하는 `report_id` 구조
- flat 항목과 run_dir 항목을 같은 목록 모델로 표현할 수 있는지 여부
- `storage_type`, `run_id`, `report_id`, `payload_available` 등 내부 필드 후보
- read-only invariant 유지 조건
- 구현 전 fixture/test 후보

## 2. 명시적 비범위

이번 Phase 2A 문서에서는 아래 작업을 하지 않는다.

- `runs/*/manifest.json` scan 구현
- `load_report_from_run_dir(...)` 같은 신규 loader 함수 구현
- Web UI route 추가 또는 변경
- template/app.py/report_loader.py 수정
- `--run-id`, `--overwrite` 구현
- pipeline 실행 버튼, live progress, DB 제어 기능 추가
- report rewrite 또는 viewer_payload 재생성
- severity/category/verdict 재계산
- context-only 항목을 finding/incident로 승격
- Web UI에서 새로운 보안 판정 생성

## 3. 현재 flat loader 입력 기준

### 3.1 scan 대상

현재 Web UI loader의 입력은 `web.config.REPORT_GLOBS`에 의해 결정된다.

현재 기준 scan 대상은 다음과 같다.

```python
REPORT_GLOBS = [
    "reports/*_stage2_report.json",
    "lab/**/reports/*_stage2_report.json",
]
```

즉, 현재 Web UI는 `stage2_report.json` 계열 파일을 primary input으로 삼고, run_dir의 `manifest.json`이나 표준 파일명(`stage2_report.json`, `viewer_payload.json`)은 직접 scan하지 않는다.

### 3.2 scan 흐름

현재 `ReportLoader.scan_reports()` 흐름은 아래와 같다.

1. `_iter_unique_report_paths()`가 `REPORT_GLOBS`에 매칭되는 report JSON 경로를 수집한다.
2. 각 file path를 `_load_single_report(file_path)`로 로드한다.
3. `_load_single_report()`는 파일 경로 기준으로 `report_id`를 생성한다.
4. JSON root가 object인지 확인한다.
5. `meta`와 `report` payload를 읽는다.
6. filename/meta에서 provider, scenario, timeframe, generated_at 등을 추출한다.
7. `notable_incidents` 기준으로 incident/severity/verdict count를 계산한다.
8. stage2 report 파일명에서 sibling `viewer_payload` 경로를 파생해 존재 여부와 summary를 확인한다.
9. 정렬 후 `_reports_by_id`, `_ordered_ids`, `_groups_by_timeframe_id` cache를 갱신한다.

현재 구조에서 list/detail/payload 모두 `Report` dataclass 인스턴스를 기준으로 동작한다.

### 3.3 viewer_payload 연결 방식

현재 viewer_payload는 manifest에서 찾지 않는다.

연결 방식은 stage2 report 파일명을 기준으로 sibling 파일을 파생하는 방식이다.

- 입력: `reports/<base>_stage2_report.json`
- 파생: `reports/<base>_viewer_payload.json`

`_resolve_viewer_payload_path(stage2_report_path)`는 위 규칙으로 payload 경로를 계산한다.

`viewer_payload`가 없거나 로드에 실패해도 stage2 report 자체를 invalid 처리하지 않는다. 대신 `viewer_payload_available=False`, `viewer_payload_error=<reason>` 형태로 detail/payload 화면에서 fallback-safe하게 표시할 수 있게 한다.

## 4. 현재 route별 기대 입력

### 4.1 list route `/`

list route는 다음 흐름을 사용한다.

1. `loader.scan_reports()` 호출
2. 각 report에 `lint_for_report(report)` 결과를 붙임
3. `loader.group_by_timeframe(reports)`로 timeframe group 구성
4. `q/lint/pair/provider/sort` filter 적용
5. `index.html`에 summary/group 전달

list 화면이 기대하는 주요 report summary 필드는 다음과 같다.

- `report_id`
- `filename`
- `repo_relative_path`
- `provider`
- `model`
- `scenario`, `scenario_key`
- `timeframe`, `timeframe_key`, `timeframe_label`, `timeframe_id`
- `generated_at`
- `incident_count`
- `severity_counts`
- `verdict_counts`
- `lint`
- `is_valid`, `error`
- `viewer_payload_available`, `viewer_payload_error`

### 4.2 detail route `/report/{report_id}`

현재 detail route는 `report_id`를 path parameter로 받아 `loader.scan_reports()` 결과에서 동일한 `report_id`를 가진 `Report`를 찾는다.

detail 화면은 stage2 report의 `report` payload를 표시 대상으로 사용한다.

주요 표시 대상은 다음과 같다.

- `overall_assessment`
- `executive_summary`
- `key_findings`
- `notable_incidents`
- `notable_source_ips`
- `recommended_actions`
- `confidence_and_limitations`
- `presentation_takeaway`
- `viewer_payload_summary`
- `viewer_payload_error`

여기서 `report_id`는 현재 route 호환성의 핵심 식별자다. 따라서 run_dir 항목을 추가하더라도 기존 flat `report_id`가 바뀌면 기존 링크/detail/payload/compare 동작이 깨질 수 있다.

### 4.3 payload route `/report/{report_id}/payload`

payload route도 detail route와 동일하게 `report_id`로 report를 찾는다.

그 후 `loader.load_viewer_payload(report)`로 viewer_payload JSON을 로드한다.

- 로드 성공: `payload_obj`의 `findings`, `contexts`, `supporting_events`, `summary` 등을 표시한다.
- 로드 실패 또는 부재: `payload_obj={}`로 fallback하고 `payload_error`를 표시한다.
- source IP masking은 `mask_src_ip` query toggle로 display-only 처리한다.

중요한 점은 matching/association 보정은 Web UI에서 새로 수행하지 않는다는 것이다. Web UI는 viewer_payload에 이미 존재하는 data를 표시하고, source IP masking은 표시 모드로만 분리한다.

### 4.4 compare route `/compare/{timeframe_id}`

compare route는 `timeframe_id`로 group을 찾고, group 내부의 provider별 report summary에서 `report_id`를 꺼내 다시 `loader.get_report_by_id(report_id)`로 원본 `Report`를 찾는다.

따라서 run_dir 항목을 같은 group 모델에 넣으려면 다음 조건이 필요하다.

- group 내부 summary의 `report_id`가 `loader.get_report_by_id()`로 역참조 가능해야 함
- provider별 openai/anthropic/unknown 분류가 기존 summary 구조와 호환되어야 함
- `timeframe_id` 계산 방식이 flat 기존 동작을 깨지 않아야 함

## 5. 현재 `report_id` 구조

현재 `report_id`는 file path 기반 hash다.

```python
def make_report_id(file_path: Path) -> str:
    try:
        relative_path = file_path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        relative_path = file_path.resolve()
    return hashlib.sha256(str(relative_path).encode("utf-8")).hexdigest()[:16]
```

의미:

- flat report의 `report_id`는 stage2 report JSON의 repo-relative path에 의존한다.
- 동일 내용이라도 파일 경로가 달라지면 `report_id`가 달라진다.
- run_dir 내부 표준 파일명(`runs/<run_id>/stage2_report.json`)을 그대로 file path 기반으로 hash하면 기존 flat report와 다른 `report_id`가 된다.
- flat와 run_dir가 같은 산출물을 가리키는 경우 dedupe 없이 둘 다 노출될 위험이 있다.

따라서 Phase 2D 구현 전, Phase 2A/2B에서 `report_id`와 dedupe key를 분리해 생각해야 한다.

## 6. flat 항목과 run_dir 항목의 공통 목록 모델 가능성

### 6.1 가능 여부

가능하다. 다만 기존 `Report` dataclass를 그대로 확장할지, 내부 수집 단계에서 별도 source record를 둔 뒤 최종 `Report`로 normalize할지 결정이 필요하다.

현재 list/detail/payload/compare는 모두 `Report` 객체를 기준으로 동작하므로, 최종적으로는 동일한 `Report` 형태를 제공하는 것이 가장 회귀 위험이 낮다.

### 6.2 권장 방향

권장 방향은 다음과 같다.

1. 수집 단계에서는 flat/run_dir source를 구분한다.
2. normalize 단계에서 공통 report entry로 맞춘다.
3. dedupe 단계에서 동일 산출물 여부를 판단한다.
4. route/template에는 가능한 한 기존 `Report.to_summary()` / `Report.to_detail()` 호환 형태를 유지한다.

즉, 구현 단계에서는 다음 두 계층을 분리하는 편이 안전하다.

- source record: flat file 또는 run_dir manifest에서 읽은 원천 entry
- report model: Web UI route가 소비하는 normalized `Report`

## 7. 내부 필드 후보

### 7.1 `storage_type`

후보 값:

- `flat`
- `run_dir`
- `both`

의미:

- `flat`: 기존 `reports/*_stage2_report.json` 또는 허용된 lab flat 경로에서만 발견된 report
- `run_dir`: run_dir manifest에서만 발견된 report
- `both`: flat와 run_dir가 같은 산출물로 dedupe된 report

권장:

- `Report` model 또는 `Report.meta`와 별도 UI metadata에 보존한다.
- list/detail에서 표시할지 여부는 별도 판단하되, test에서는 보존 여부를 확인할 수 있게 한다.

### 7.2 `run_id`

의미:

- run_dir 디렉터리명 기반 추적 ID
- flat-only report에서는 `None` 또는 빈 문자열
- `both`에서는 run_dir 쪽 source metadata로 보존

주의:

- `run_id`를 route primary key로 즉시 승격하지 않는다.
- 기존 `/report/{report_id}` route를 유지한다.
- run_dir 전용 route는 Phase 2A 범위가 아니다.

### 7.3 `report_id`

현 상태:

- flat stage2 report path 기반 hash
- 기존 route/detail/payload/compare에서 primary key로 사용

후보:

- 후보 A: 모든 entry의 physical stage2 path 기준 hash
- 후보 B: flat와 같은 산출물을 가리키는 run_dir entry는 flat `report_id`를 우선 유지
- 후보 C: manifest 내부 stable id가 생길 때까지 run_dir 전용 report_id는 run_dir stage2 path 기반으로 생성

권장:

- 기존 flat 항목의 `report_id`는 절대 변경하지 않는다.
- flat와 run_dir가 같은 산출물로 dedupe되면 flat `report_id`를 우선 유지한다.
- run_dir-only 항목은 별도 stable id 후보를 fixture로 검증한 뒤 결정한다.

### 7.4 `payload_available`

현재 필드명:

- `viewer_payload_available`
- `viewer_payload_error`
- `viewer_payload_path`
- `viewer_payload_summary`

Phase 2 문서상 후보명 `payload_available`은 개념명으로 유지하되, 구현 시에는 기존 field naming과 호환되도록 `viewer_payload_available`을 유지하는 쪽이 안전하다.

권장:

- 내부 설계에서는 `payload_available` 개념을 사용한다.
- 실제 `Report.to_summary()` / `Report.to_detail()` 호환 필드는 기존 `viewer_payload_available`을 유지한다.
- run_dir에서 `viewer_payload.json`이 없더라도 stage2 report detail은 표시 가능해야 한다.

### 7.5 경로 필드 후보

현재 필드:

- `file_path`
- `filename`
- `repo_relative_path`
- `viewer_payload_path`

run_dir 확장 후보:

- `stage2_report_path`
- `viewer_payload_path`
- `manifest_path`
- `run_dir`
- `source_export_path`
- `storage_type`

권장:

- 기존 `file_path`는 lint/detail 로딩에서 계속 필요하므로 stage2 report JSON 경로를 유지한다.
- `repo_relative_path`는 list/detail 표시와 query filter에 영향이 있으므로 기존 의미를 보존한다.
- run_dir-only 항목의 display path는 `runs/<run_id>/stage2_report.json`처럼 source를 구분할 수 있어야 한다.

## 8. Dedupe와 route 호환성 검토

### 8.1 dedupe key 후보

기존 Phase 2 설계와 동일하게 아래 순서를 우선 검토한다.

1. 정규화된 stage2 report JSON 실경로
2. 정규화된 viewer_payload JSON 실경로
3. export input path + run_id 조합

다만 실제 Phase 2D 구현 전에는 fixture로 아래 케이스를 검증해야 한다.

- flat와 run_dir가 동일 stage2 report를 가리키는 케이스
- flat와 run_dir가 같은 내용이지만 물리 경로가 다른 케이스
- run_dir-only report
- viewer_payload 없는 run_dir report
- malformed manifest 또는 경로 참조 불능 manifest

### 8.2 route 호환성 원칙

- 기존 `/report/{report_id}` 유지
- 기존 `/report/{report_id}/payload` 유지
- 기존 `/compare/{timeframe_id}` 유지
- `run_id`는 route primary key가 아니라 metadata로 먼저 보존
- run_dir route 추가는 Phase 2A/2B/2C 이후 별도 판단

## 9. read-only invariant 유지 조건

run_dir 항목을 추가해도 Web UI의 역할은 read-only viewer다.

유지 조건:

- pipeline 실행 버튼 없음
- DB 제어 없음
- report rewrite 없음
- viewer_payload 재생성 없음
- 파일 삭제/수정 기능 없음
- severity/category/verdict 재계산 없음
- context-only 항목을 finding/incident로 승격하지 않음
- Related Contexts 또는 Supporting Events 관계를 UI에서 새로 추론하지 않음
- source IP masking은 display-only toggle로 유지
- raw log/body 원문 노출은 기존 opt-in 정책을 유지

## 10. 구현 전 fixture/test 후보

### 10.1 Phase 2B fixture 후보

- `flat_only_basic`
  - 기존 `reports/*_stage2_report.json` + sibling viewer_payload
  - 기대: 현재 list/detail/payload 동작 유지

- `flat_only_missing_viewer_payload`
  - stage2 report만 있고 viewer_payload 없음
  - 기대: detail은 표시, payload route는 fallback-safe unavailable 표시

- `run_dir_valid_basic`
  - `runs/<run_id>/manifest.json` + 표준 파일명 세트
  - 기대: 구현 단계에서 run_dir-only 항목을 공통 report model로 normalize 가능

- `run_dir_missing_viewer_payload`
  - manifest와 stage2 report는 있으나 viewer_payload 없음
  - 기대: detail 표시 가능, payload unavailable 처리

- `run_dir_malformed_manifest`
  - JSON parse 실패 또는 필수 키 누락
  - 기대: 기본 정책은 skip, debug 표시 여부는 별도 옵션 후보

- `flat_and_run_dir_duplicate`
  - 동일 산출물이 flat와 run_dir에 동시에 존재
  - 기대: 목록 중복 없음, `storage_type=both` 보존

- `huge_text_report`
  - 긴 URI/request_id/summary/recommended_action 포함
  - 기대: list/detail/payload 레이아웃 회귀 없음

- `missing_optional_fields_report`
  - `notable_incidents`, `recommended_actions`, `viewer_payload.summary` 일부 누락
  - 기대: sanitize/fallback 동작 유지

### 10.2 test 후보

- `ReportLoader` flat-only scan 회귀 테스트
  - 기존 glob 기반 scan 결과가 유지되는지 확인

- `report_id` 안정성 테스트
  - 기존 flat report path의 `report_id`가 변경되지 않는지 확인

- viewer_payload missing fallback 테스트
  - report는 valid, `viewer_payload_available=False`, detail/payload fallback 확인

- common report model normalize 테스트
  - flat source record와 run_dir source record가 같은 summary/detail field set을 제공하는지 확인

- dedupe 테스트
  - flat + run_dir duplicate에서 단일 report로 병합되고 `storage_type=both`가 보존되는지 확인

- read-only invariant 테스트
  - route/template에 pipeline 실행, 삭제, rewrite, DB 제어 액션이 추가되지 않는지 확인

- source IP display-only 테스트 유지
  - raw data matching과 display masking이 분리되는지 확인

## 11. Phase 2A 결론

현재 Web UI loader는 `stage2_report.json` 파일을 primary input으로 삼는 flat-first 구조다. list/detail/payload/compare route 모두 `report_id`로 `Report` 객체를 역참조하는 계약에 의존한다.

따라서 run_dir manifest scan을 구현하기 전에는 다음을 먼저 고정해야 한다.

1. 기존 flat `report_id`는 변경하지 않는다.
2. run_dir 정보는 우선 metadata(`storage_type`, `run_id`, `manifest_path`)로 보존한다.
3. route는 기존 `/report/{report_id}`와 `/report/{report_id}/payload`를 유지한다.
4. viewer_payload 부재는 report invalid가 아니라 payload unavailable로 분리한다.
5. flat/run_dir 중복은 dedupe 후 `storage_type=both`로 표현하는 방향을 우선 검토한다.
6. Phase 2D 구현 전 Phase 2B fixture와 Phase 2C flat-only 회귀 테스트를 먼저 준비한다.

## 12. 다음 단계 후보

- Phase 2B: fixture 설계 문서 작성
  - malformed manifest
  - missing viewer_payload
  - flat/run_dir duplicate
  - run_dir-only valid report
  - huge text/missing field report

- Phase 2C: flat-only Web UI 회귀 테스트 보강
  - list/detail/payload/compare route
  - report_id stability
  - viewer_payload unavailable fallback
  - read-only invariant

- Phase 2D: run_dir manifest scan 구현 여부 판단
  - 구현 시에도 기존 flat output 계약을 먼저 보존
  - Web UI loader는 read-only viewer 범위를 유지
