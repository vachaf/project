# 99_web_ui_loader_phase2a_input_model_review

- 기준 시점: 2026-05-10
- 문서 목적: Web UI loader Phase 2A에서 기존 flat `reports/` 기반 입력 모델을 조사하고, 향후 운영 기준을 `run_dir` 중심 scan으로 전환하기 위한 내부 모델/fixture/test 후보를 정리한다.
- 문서 성격: 구현 전 조사/입력 모델 리뷰 문서
- 관련 문서:
  - `docs/design/99_web_ui_run_dir_loader_phase2_plan.md`
  - `docs/design/99_pipeline_run_dir_output_layout_plan.md`
  - `docs/design/99_pipeline_run_dir_phase1b_phase2_candidate_review.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`
  - `docs/operations/README.md`

## 1. 목적

Phase 2A의 목적은 `runs/*/manifest.json` scan 구현이 아니라, 현재 Web UI loader가 어떤 입력을 기준으로 list/detail/payload 화면을 구성하는지 명시적으로 고정하는 것이다.

동시에 향후 운영 방향을 아래와 같이 재검토한다.

- 현재 Web UI는 기존 flat `reports/` 및 `lab/**/reports/` 산출물을 scan한다.
- 그러나 기존 `lab/`, `data/`, `reports/`에는 viewer_payload 도입 이전 산출물이 많이 섞여 있다.
- 이 경우 payload route가 빈 상태 또는 unavailable 상태로 자주 보이며, 운영 관찰 목록과 과거 실험 archive가 혼재된다.
- 따라서 향후 기본 scan 방향은 `run_dir` 중심으로 전환하고, legacy flat/lab/data/report 계열은 기본 scan에서 제외하거나 명시적 opt-in archive scan으로 분리하는 방안을 우선 검토한다.

이 문서는 다음을 결정하기 위한 기준을 제공한다.

- 기존 flat `reports/` loader 흐름의 기준 계약
- list/detail/payload route가 기대하는 `report_id` 구조
- run_dir-only 운영 목록 모델이 가능한지 여부
- flat 항목과 run_dir 항목을 같은 모델로 표현해야 하는 최소 호환 범위
- `storage_type`, `run_id`, `report_id`, `payload_available`, `viewer_payload_error_code` 등 내부 필드 후보
- read-only invariant 유지 조건
- 구현 전 fixture/test 후보

## 2. 명시적 비범위

이번 Phase 2A 문서에서는 아래 작업을 하지 않는다.

- `runs/*/manifest.json` scan 구현
- legacy flat/lab scan 제거 구현
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

### 3.2 현재 구조의 운영상 문제

현재 flat/lab scan은 과거 실험 산출물을 빠르게 보는 데는 유용하지만, 운영 기준으로는 다음 문제가 있다.

- viewer_payload 도입 이전 산출물이 많이 포함되어 payload dashboard 가용성이 낮다.
- `lab/**/reports/`는 비교실험/archive 성격이 강해 현재 운영 결과와 섞이면 목록 의미가 흐려진다.
- `reports/` flat output은 latest 성격과 과거 산출물이 함께 존재할 수 있어 run 단위 추적성이 약하다.
- `data/` 또는 기타 archive까지 scan 대상에 포함하면 중복/오래된 결과/누락 payload 문제가 커질 수 있다.

따라서 향후 기본 방향은 다음과 같이 잡는다.

- 기본 scan: `runs/*/manifest.json` 기반 run_dir만 대상으로 하는 방향을 우선 검토
- legacy flat/lab/data/report scan: 기본 제외
- archive 확인이 필요할 때만 명시적 opt-in 옵션 또는 별도 debug/archive mode로 분리

### 3.3 scan 흐름

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

### 3.4 viewer_payload 연결 방식

현재 viewer_payload는 manifest에서 찾지 않는다.

연결 방식은 stage2 report 파일명을 기준으로 sibling 파일을 파생하는 방식이다.

- 입력: `reports/<base>_stage2_report.json`
- 파생: `reports/<base>_viewer_payload.json`

`_resolve_viewer_payload_path(stage2_report_path)`는 위 규칙으로 payload 경로를 계산한다.

`viewer_payload`가 없거나 로드에 실패해도 stage2 report 자체를 invalid 처리하지 않는다. 대신 `viewer_payload_available=False`, `viewer_payload_error=<reason>` 형태로 detail/payload 화면에서 fallback-safe하게 표시할 수 있게 한다.

run_dir 기준으로 전환할 경우에는 sibling filename 추론보다 manifest의 표준 파일 entry 또는 run_dir 표준 파일명(`viewer_payload.json`)을 우선 참조하는 편이 더 명시적이다.

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

여기서 `report_id`는 현재 route 호환성의 핵심 식별자다. run_dir-only 전환 시에도 `/report/{report_id}` contract 자체는 유지하는 편이 안전하다.

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
- `timeframe_id` 계산 방식이 기존 compare 동작을 깨지 않아야 함

## 5. 현재 `report_id` 구조와 운영 전환 시 고려점

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
- flat와 run_dir가 같은 산출물을 동시에 scan하는 경우 dedupe 없이 둘 다 노출될 위험이 있다.

운영 방향을 run_dir-only로 잡으면 flat/run_dir duplicate 문제는 기본 scan에서는 크게 줄어든다. 다만 archive opt-in mode를 제공할 경우에는 여전히 dedupe 기준이 필요하다.

따라서 `report_id`와 canonical identity를 분리해 생각한다.

- `report_id`: Web UI route 호환을 위한 표시/라우팅 식별자
- `canonical_report_key`: 동일 분석 산출물 여부를 판단하기 위한 dedupe anchor 후보

## 6. run_dir-only 운영 모델 검토

### 6.1 권장 운영 방향

향후 기본 운영 scan은 다음 방향을 우선 검토한다.

- 기본: `runs/*/manifest.json`만 scan
- 제외: 기존 `lab/`, `data/`, root `reports/` archive성 산출물
- 예외: legacy/archive 확인이 필요한 경우에만 명시적 opt-in scan

이 방향의 장점:

- viewer_payload 존재 가능성이 높은 최신 run 산출물 중심으로 목록이 구성된다.
- run 단위 manifest를 통해 stage2 report, markdown, viewer_payload, export/noise summary를 함께 추적할 수 있다.
- 과거 실험 archive와 현재 운영 결과가 섞이지 않는다.
- payload dashboard 중심의 Web UI 경험이 일관된다.

주의점:

- flat-only 산출물 확인 경로가 사라지면 기존 실험 결과 접근성이 낮아질 수 있다.
- 전환 직후에는 run_dir 생성이 누락된 과거/수동 실행 결과가 목록에서 보이지 않을 수 있다.
- 따라서 flat/lab/data는 삭제가 아니라 기본 scan 제외 + opt-in archive mode 후보로 남기는 것이 안전하다.

### 6.2 공통 목록 모델 가능성

run_dir-only로 가더라도 최종 route/template 입력은 기존 `Report` 형태와 호환되는 것이 안전하다.

권장 방향:

1. 수집 단계에서는 run_dir manifest source를 읽는다.
2. normalize 단계에서 기존 `Report`와 같은 summary/detail field set을 만든다.
3. route/template에는 가능한 한 기존 `Report.to_summary()` / `Report.to_detail()` 호환 형태를 유지한다.
4. legacy flat/lab scan은 opt-in source로만 붙일 수 있게 분리한다.

즉, 구현 단계에서는 다음 두 계층을 분리하는 편이 안전하다.

- source record: run_dir manifest 또는 legacy flat file에서 읽은 원천 entry
- report model: Web UI route가 소비하는 normalized `Report`

## 7. 내부 필드 후보

### 7.1 `storage_type`

후보 값:

- `run_dir`
- `flat`
- `legacy_lab`
- `both`

의미:

- `run_dir`: 기본 운영 scan에서 발견된 report
- `flat`: root `reports/` archive/legacy scan에서 발견된 report
- `legacy_lab`: `lab/**/reports/` archive scan에서 발견된 report
- `both`: opt-in archive scan까지 포함했을 때 동일 산출물이 run_dir와 legacy flat/lab 양쪽에서 발견된 report

권장:

- 기본 운영 모드에서는 `run_dir`가 표준값이 된다.
- `flat`, `legacy_lab`, `both`는 archive/compatibility mode에서만 등장하게 한다.
- list/detail에서 표시할지 여부는 별도 판단하되, test에서는 보존 여부를 확인할 수 있게 한다.

### 7.2 `run_id`

의미:

- run_dir 디렉터리명 기반 추적 ID
- 기본 운영 모드에서는 필수에 가까운 metadata
- legacy flat/lab report에서는 `None` 또는 빈 문자열

주의:

- `run_id`를 route primary key로 즉시 승격하지 않는다.
- 기존 `/report/{report_id}` route를 유지한다.
- run_id 전용 route는 Phase 2A 범위가 아니다.

### 7.3 `report_id`

현 상태:

- flat stage2 report path 기반 hash
- 기존 route/detail/payload/compare에서 primary key로 사용

run_dir-only 전환 후보:

- 후보 A: run_dir `stage2_report.json` physical path 기준 hash
- 후보 B: `run_id` + manifest stage2 report entry 기준 hash
- 후보 C: canonical key가 충분히 안정화된 뒤 canonical key 기반 hash 사용

권장:

- 당장 Phase 2D 구현 후보에서는 physical path 또는 `run_id + stage2_report_path` 기반을 우선 검토한다.
- 기존 flat 항목의 `report_id` 안정성은 archive/compatibility mode 테스트로 유지한다.
- canonical key 기반 report_id 전환은 route 안정성 영향이 크므로 별도 단계로 분리한다.

### 7.4 `canonical_report_key`

역할:

- `report_id`와 별도로 동일 분석 산출물 여부를 판단하는 dedupe anchor 후보
- archive opt-in scan이나 flat/run_dir duplicate 검증에서 사용 가능

후보:

- `source_export_path` 또는 source log fingerprint
- stage2 report JSON path
- viewer_payload JSON path
- `run_id`
- manifest의 source metadata
- 향후 별도 생성 가능한 `source_log_hash`, analyzer/schema version, generated_at 계열 metadata

주의:

- 현재 산출물에 `source_log_hash`, `stage2_model_version`, `analyzer_timestamp`가 항상 존재한다고 가정하지 않는다.
- 없으면 canonical key는 단계적으로 fallback해야 한다.
- 표시용 `generated_at`만으로 dedupe primary key를 만들지는 않는다.

### 7.5 `payload_available` / `viewer_payload_error_code`

현재 필드명:

- `viewer_payload_available`
- `viewer_payload_error`
- `viewer_payload_path`
- `viewer_payload_summary`

Phase 2 문서상 후보명 `payload_available`은 개념명으로 유지하되, 구현 시에는 기존 field naming과 호환되도록 `viewer_payload_available`을 유지하는 쪽이 안전하다.

에러 범주 후보:

- `MISSING_FILE`: viewer_payload 물리 파일 부재
- `MALFORMED_JSON`: JSON 문법 오류
- `SCHEMA_INCOMPLETE`: root object 또는 핵심 key 누락
- `DECODE_FAIL`: 인코딩/읽기 실패
- `UNKNOWN`: 그 외 예외

권장:

- 기존 `viewer_payload_error` 문자열은 사용자/디버그 메시지로 유지한다.
- 내부 test와 UI badge에는 `viewer_payload_error_code` 후보를 검토한다.
- run_dir 운영 모드에서는 viewer_payload가 없을 때도 report detail은 표시 가능해야 하지만, payload dashboard는 unavailable 상태를 명확히 표시해야 한다.

### 7.6 경로 필드 후보

현재 필드:

- `file_path`
- `filename`
- `repo_relative_path`
- `viewer_payload_path`

run_dir 확장 후보:

- `stage2_report_path`
- `stage2_report_md_path`
- `viewer_payload_path`
- `manifest_path`
- `run_dir`
- `source_export_path`
- `storage_type`

권장:

- 기존 `file_path`는 lint/detail 로딩에서 계속 필요하므로 stage2 report JSON 경로를 유지한다.
- `repo_relative_path`는 list/detail 표시와 query filter에 영향이 있으므로 기존 의미를 보존한다.
- run_dir-only 항목의 display path는 `runs/<run_id>/stage2_report.json`처럼 source를 구분할 수 있어야 한다.

## 8. scan mode 후보

### 8.1 후보 A: compatibility mode 유지

- 기본 scan: 기존 `reports/`, `lab/**/reports/`
- run_dir scan: 보조로 추가
- 장점: 기존 결과 접근성 유지
- 단점: viewer_payload 없는 구산출물과 운영 결과 혼재 지속

### 8.2 후보 B: run_dir-only 기본 전환

- 기본 scan: `runs/*/manifest.json`
- legacy flat/lab/data/report: 기본 제외
- 필요 시 opt-in archive mode
- 장점: 운영 목록이 run 단위 최신 산출물 중심으로 정리됨
- 단점: 기존 flat-only 결과는 기본 화면에서 사라짐

권장: 후보 B를 우선 검토한다.

이유:

- Web UI가 payload dashboard 중심으로 진화한 현재 상태와 맞다.
- viewer_payload 없는 과거 산출물이 기본 목록에 섞이는 문제를 줄일 수 있다.
- `run_id`, manifest, 표준 파일명 기반으로 결과물 추적성이 좋아진다.

## 9. Dedupe와 route 호환성 검토

### 9.1 dedupe key 후보

run_dir-only 기본 모드에서는 dedupe 범위가 작아지지만, archive opt-in scan을 고려하면 아래 기준이 필요하다.

1. manifest에 기록된 stage2 report JSON 실경로 또는 표준 run_dir `stage2_report.json`
2. viewer_payload JSON 실경로
3. source export path + run_id 조합
4. 향후 `canonical_report_key`

실제 Phase 2D 구현 전에는 fixture로 아래 케이스를 검증해야 한다.

- run_dir-only report
- run_dir report with viewer_payload
- run_dir report missing viewer_payload
- malformed manifest 또는 경로 참조 불능 manifest
- archive opt-in 시 flat/run_dir duplicate

### 9.2 route 호환성 원칙

- 기존 `/report/{report_id}` 유지
- 기존 `/report/{report_id}/payload` 유지
- 기존 `/compare/{timeframe_id}` 유지
- `run_id`는 route primary key가 아니라 metadata로 먼저 보존
- run_dir route 추가는 Phase 2A/2B/2C 이후 별도 판단

## 10. read-only invariant 유지 조건

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

## 11. 구현 전 fixture/test 후보

### 11.1 Phase 2B fixture 후보

- `run_dir_valid_basic`
  - `runs/<run_id>/manifest.json` + 표준 파일명 세트
  - 기대: 기본 운영 scan에서 목록/detail/payload 표시 가능

- `run_dir_missing_viewer_payload`
  - manifest와 stage2 report는 있으나 viewer_payload 없음
  - 기대: detail 표시 가능, payload unavailable 처리, `viewer_payload_error_code=MISSING_FILE` 후보

- `run_dir_malformed_manifest`
  - JSON parse 실패 또는 필수 키 누락
  - 기대: 기본 정책은 skip, debug 표시 여부는 별도 옵션 후보

- `run_dir_missing_stage2_report`
  - manifest는 있으나 stage2 report 경로 참조 불능
  - 기대: 기본 scan에서 제외하거나 invalid run으로 분리

- `run_dir_huge_text_report`
  - 긴 URI/request_id/summary/recommended_action 포함
  - 기대: list/detail/payload 레이아웃 회귀 없음

- `run_dir_missing_optional_fields_report`
  - `notable_incidents`, `recommended_actions`, `viewer_payload.summary` 일부 누락
  - 기대: sanitize/fallback 동작 유지

- `archive_flat_legacy_without_viewer_payload`
  - opt-in archive scan에서만 사용하는 fixture
  - 기대: 기본 운영 scan에는 나오지 않음

- `archive_flat_and_run_dir_duplicate`
  - opt-in archive scan에서 동일 산출물이 flat와 run_dir에 동시에 존재
  - 기대: 목록 중복 없음, `storage_type=both` 보존

### 11.2 test 후보

- run_dir-only scan 후보 테스트
  - 기본 scan 대상이 `runs/*/manifest.json` 중심으로 구성되는지 확인

- legacy flat/lab exclusion 테스트
  - 기본 모드에서 `reports/`, `lab/**/reports/`, `data/` archive 산출물이 제외되는지 확인

- archive opt-in 테스트 후보
  - opt-in mode에서만 legacy flat/lab report가 포함되는지 확인

- `report_id` stability 테스트
  - run_dir 항목의 `report_id`가 route/detail/payload 역참조에 안정적으로 사용되는지 확인
  - 기존 flat report path hash는 compatibility/archive mode에서만 유지 확인

- viewer_payload missing fallback 테스트
  - report는 valid, `viewer_payload_available=False`, detail/payload fallback 확인

- common report model normalize 테스트
  - run_dir source record가 기존 summary/detail field set을 제공하는지 확인

- dedupe 테스트
  - archive opt-in 시 flat + run_dir duplicate에서 단일 report로 병합되고 `storage_type=both`가 보존되는지 확인

- read-only invariant 테스트
  - route/template에 pipeline 실행, 삭제, rewrite, DB 제어 액션이 추가되지 않는지 확인

- source IP display-only 테스트 유지
  - raw data matching과 display masking이 분리되는지 확인

## 12. Phase 2A 결론

현재 Web UI loader는 `stage2_report.json` 파일을 primary input으로 삼는 flat-first 구조다. list/detail/payload/compare route 모두 `report_id`로 `Report` 객체를 역참조하는 계약에 의존한다.

그러나 향후 운영 기준에서는 기존 `lab/`, `data/`, root `reports/` 산출물을 기본 scan에서 제외하고, `run_dir` manifest 중심으로 전환하는 방향이 더 적합하다.

이유:

1. 기존 실험 디렉터리에는 viewer_payload 도입 전 산출물이 많다.
2. payload dashboard 중심 Web UI에서는 viewer_payload 없는 항목이 기본 목록에 많을수록 운영 가시성이 떨어진다.
3. run_dir는 manifest와 표준 파일명을 통해 run 단위 추적성이 좋다.
4. legacy archive는 삭제 대상이 아니라 기본 scan 제외 + opt-in archive mode 후보로 두는 편이 안전하다.

따라서 다음 원칙을 우선 검토한다.

1. 기본 운영 scan은 `runs/*/manifest.json` 중심으로 전환한다.
2. 기존 flat/lab/data/report scan은 기본 제외한다.
3. 필요한 경우에만 legacy/archive opt-in scan을 제공한다.
4. route는 기존 `/report/{report_id}`와 `/report/{report_id}/payload`를 유지한다.
5. run_dir 정보는 metadata(`storage_type`, `run_id`, `manifest_path`)로 보존한다.
6. viewer_payload 부재는 report invalid가 아니라 payload unavailable로 분리한다.
7. Phase 2D 구현 전 Phase 2B fixture와 Phase 2C run_dir-only/legacy-exclusion 회귀 테스트를 먼저 준비한다.

## 13. 다음 단계 후보

- Phase 2B: run_dir 중심 fixture 설계 문서 작성
  - valid run_dir
  - missing viewer_payload
  - malformed manifest
  - missing stage2 report
  - huge text/missing field report
  - legacy flat without viewer_payload
  - archive opt-in duplicate

- Phase 2C: Web UI loader 회귀 테스트 보강
  - run_dir-only 기본 scan
  - legacy flat/lab/data 기본 제외
  - archive opt-in 후보
  - list/detail/payload/compare route
  - report_id stability
  - viewer_payload unavailable fallback
  - read-only invariant

- Phase 2D: run_dir manifest scan 구현 여부 판단
  - 구현 시 기존 route contract를 먼저 보존
  - Web UI loader는 read-only viewer 범위를 유지
