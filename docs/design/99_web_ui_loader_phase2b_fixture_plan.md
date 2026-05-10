# 99_web_ui_loader_phase2b_fixture_plan

- 기준 시점: 2026-05-10
- 문서 목적: Web UI loader를 향후 `run_dir` 중심 scan으로 전환하기 전에 필요한 fixture 케이스, 파일 구조, 기대 동작, 테스트 후보를 고정한다.
- 문서 성격: 구현 전 fixture/test 설계 문서
- 관련 문서:
  - `docs/design/99_web_ui_loader_phase2a_input_model_review.md`
  - `docs/design/99_web_ui_run_dir_loader_phase2_plan.md`
  - `docs/design/99_pipeline_run_dir_output_layout_plan.md`
  - `docs/design/99_pipeline_run_dir_phase1b_phase2_candidate_review.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`

## 1. 목적

Phase 2B의 목적은 Web UI loader 구현을 바로 시작하는 것이 아니라, 구현 전에 반드시 통과해야 할 입력 케이스를 fixture 수준에서 정의하는 것이다.

Phase 2A 결론에 따라 향후 운영 기준은 아래 방향을 우선 검토한다.

- 기본 scan은 `runs/*/manifest.json` 기반 `run_dir` 중심으로 전환한다.
- 기존 `lab/`, `data/`, root `reports/` 산출물은 기본 scan에서 제외한다.
- legacy/archive 확인이 필요할 때만 명시적 opt-in archive scan 후보로 분리한다.
- 기존 route contract(`/report/{report_id}`, `/report/{report_id}/payload`, `/compare/{timeframe_id}`)는 유지한다.
- Web UI는 read-only viewer 범위를 유지한다.

이 문서는 위 방향을 실제 구현 전에 검증할 수 있도록 fixture set과 기대 결과를 정의한다.

## 2. 명시적 비범위

이번 Phase 2B 문서에서는 아래 작업을 하지 않는다.

- 실제 fixture JSON 파일 생성
- `runs/*/manifest.json` scan 구현
- legacy flat/lab scan 제거 구현
- Web UI route/template/app.py 수정
- `web/services/report_loader.py` 수정
- `--run-id`, `--overwrite` 구현
- pipeline 실행 버튼 또는 live progress 추가
- DB 제어, report rewrite, viewer_payload 재생성 추가
- severity/category/verdict 재계산
- context-only 항목을 finding/incident로 승격
- Web UI에서 Related Contexts 또는 Supporting Events 관계를 새로 추론

## 3. fixture root 후보

실제 fixture 생성 단계에서는 아래 경로 후보를 검토한다.

```text
tests/fixtures/web_loader_phase2/
```

권장 하위 구조:

```text
tests/fixtures/web_loader_phase2/
  runs/
    run_dir_valid_basic/
    run_dir_missing_viewer_payload/
    run_dir_malformed_viewer_payload/
    run_dir_malformed_manifest/
    run_dir_missing_stage2_report/
    run_dir_missing_optional_fields/
    run_dir_huge_text_report/
  archive/
    flat_legacy_without_viewer_payload/
    flat_and_run_dir_duplicate/
```

주의:

- `runs/`는 기본 운영 scan fixture다.
- `archive/`는 기본 scan 제외 및 opt-in archive scan 후보 검증용이다.
- fixture root는 실제 구현 단계에서 `project_root` 또는 loader 설정을 통해 주입 가능해야 한다.
- 실제 repo의 운영 `reports/`, `lab/`, `data/`를 테스트 입력으로 직접 사용하지 않는다.

## 4. 공통 run_dir 파일 구조

정상 run_dir fixture는 아래 표준 파일명을 기본으로 한다.

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
```

Phase 2B fixture에서 모든 파일을 항상 완전하게 만들 필요는 없다. loader scan과 화면 표시의 최소 입력은 다음으로 본다.

필수 후보:

- `manifest.json`
- `stage2_report.json`

payload route 가용성 확인용:

- `viewer_payload.json`

보조/추적 metadata 후보:

- `export.json`
- `noise_summary.json`
- `stage2_report.md`

## 5. manifest 최소 스키마 후보

Phase 2D 구현 전 fixture에서 사용할 manifest 최소 스키마 후보는 아래와 같다.

```json
{
  "run_id": "run_dir_valid_basic",
  "run_dir_enabled": true,
  "run_dir": "tests/fixtures/web_loader_phase2/runs/run_dir_valid_basic",
  "run_dir_files": {
    "stage2_report_json": "stage2_report.json",
    "stage2_report_md": "stage2_report.md",
    "viewer_payload": "viewer_payload.json",
    "noise_summary": "noise_summary.json"
  },
  "flat_files": {},
  "source_export_path": "export.json",
  "created_at": "2026-05-10T00:00:00+09:00"
}
```

주의:

- 실제 구현에서는 기존 `pipeline_manifest.json` / run별 manifest의 현재 key와 맞춰 조정한다.
- fixture는 manifest key가 일부 없을 때의 fallback도 검증해야 한다.
- `created_at` 또는 `generated_at` 같은 표시용 시간만으로 dedupe primary key를 만들지 않는다.

## 6. 공통 기대 내부 모델

run_dir fixture를 scan한 뒤 Web UI route가 소비하는 normalized report는 기존 `Report.to_summary()` / `Report.to_detail()`와 호환되는 field set을 제공해야 한다.

필수 summary 호환 필드:

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

run_dir 확장 metadata 후보:

- `storage_type`: `run_dir`, `flat`, `legacy_lab`, `both`
- `run_id`
- `manifest_path`
- `run_dir`
- `stage2_report_path`
- `stage2_report_md_path`
- `viewer_payload_path`
- `viewer_payload_error_code`
- `canonical_report_key`

권장:

- 기본 운영 scan에서 `storage_type=run_dir`를 표준으로 한다.
- legacy flat/lab/data/report 항목은 기본 scan에 포함하지 않는다.
- archive opt-in 모드에서만 `flat`, `legacy_lab`, `both`를 허용한다.

## 7. viewer_payload error code 후보

`viewer_payload_error` 문자열만으로는 fixture 기대값을 안정적으로 검증하기 어렵다. Phase 2B에서는 아래 code 후보를 고정한다.

- `NONE`: viewer_payload 로드 성공
- `MISSING_FILE`: viewer_payload 파일 부재
- `MALFORMED_JSON`: JSON 문법 오류
- `SCHEMA_INCOMPLETE`: root object가 아니거나 핵심 key가 누락된 경우
- `DECODE_FAIL`: 파일 읽기/인코딩 실패
- `UNKNOWN`: 그 외 예외

권장:

- UI 표시 메시지는 `viewer_payload_error` 문자열로 유지한다.
- 테스트와 badge 분기는 `viewer_payload_error_code` 후보를 사용한다.
- viewer_payload 문제는 stage2 report 자체를 invalid로 만들지 않는다.

## 8. fixture case 상세

### 8.1 `run_dir_valid_basic`

목적:

- 정상 run_dir 산출물이 기본 scan에서 목록/detail/payload에 표시되는지 확인한다.

파일 구성:

```text
runs/run_dir_valid_basic/
  manifest.json
  stage2_report.json
  stage2_report.md
  viewer_payload.json
  export.json
  noise_summary.json
```

핵심 데이터:

- stage2 report root는 object
- `meta.provider`, `meta.selected_model`, `meta.generated_at` 포함
- `report.notable_incidents` 1건 이상
- viewer_payload root는 object
- `summary.finding_count`, `summary.context_count`, `findings`, `contexts`, `supporting_events` 포함

기대 동작:

- 기본 scan에 포함된다.
- `storage_type=run_dir`
- `run_id=run_dir_valid_basic`
- `viewer_payload_available=True`
- `viewer_payload_error_code=NONE`
- `/report/{report_id}` detail 표시 가능
- `/report/{report_id}/payload` payload dashboard 표시 가능

### 8.2 `run_dir_missing_viewer_payload`

목적:

- viewer_payload가 없어도 stage2 report detail은 유지되는지 확인한다.

파일 구성:

```text
runs/run_dir_missing_viewer_payload/
  manifest.json
  stage2_report.json
  stage2_report.md
```

핵심 데이터:

- manifest에는 viewer_payload entry가 있거나 없을 수 있다.
- 물리 `viewer_payload.json`은 존재하지 않는다.

기대 동작:

- 기본 scan에 포함된다.
- `storage_type=run_dir`
- `viewer_payload_available=False`
- `viewer_payload_error_code=MISSING_FILE`
- detail route는 표시 가능
- payload route는 crash 없이 unavailable 상태를 표시
- report 자체를 invalid 처리하지 않는다.

### 8.3 `run_dir_malformed_viewer_payload`

목적:

- viewer_payload JSON 파싱 실패가 report detail 전체 장애로 번지지 않는지 확인한다.

파일 구성:

```text
runs/run_dir_malformed_viewer_payload/
  manifest.json
  stage2_report.json
  viewer_payload.json  # malformed JSON
```

핵심 데이터:

- `stage2_report.json`은 정상 object
- `viewer_payload.json`은 JSON parse 실패를 유발

기대 동작:

- 기본 scan에 포함된다.
- `viewer_payload_available=False`
- `viewer_payload_error_code=MALFORMED_JSON`
- detail route는 표시 가능
- payload route는 fallback-safe하게 error 표시

### 8.4 `run_dir_malformed_manifest`

목적:

- manifest 파싱 실패 또는 root schema 오류가 loader 전체 장애로 번지지 않는지 확인한다.

파일 구성:

```text
runs/run_dir_malformed_manifest/
  manifest.json  # malformed JSON 또는 root object 아님
  stage2_report.json  # 존재해도 manifest가 유효하지 않으면 기본 정책상 skip 후보
```

기대 동작:

- 기본 정책은 해당 run skip
- loader 전체 scan은 계속 진행
- list route는 crash 없이 나머지 report를 표시
- debug/diagnostic mode에서 invalid run 표시를 할지는 별도 후보로 둔다.

### 8.5 `run_dir_missing_stage2_report`

목적:

- manifest는 있으나 stage2 report 경로가 없을 때의 정책을 고정한다.

파일 구성:

```text
runs/run_dir_missing_stage2_report/
  manifest.json
  viewer_payload.json  # 있어도 stage2 report가 없으면 primary report 없음
```

기대 동작:

- 기본 정책은 해당 run skip
- 또는 향후 invalid run diagnostic entry로 분리 가능
- 일반 list/detail route에는 report로 노출하지 않는다.
- loader 전체 scan은 실패하지 않는다.

### 8.6 `run_dir_missing_optional_fields`

목적:

- stage2 report 또는 viewer_payload의 optional field 누락 시 UI가 `undefined`/traceback 없이 fallback하는지 확인한다.

파일 구성:

```text
runs/run_dir_missing_optional_fields/
  manifest.json
  stage2_report.json
  viewer_payload.json
```

누락 후보:

- `report.notable_incidents`
- `report.recommended_actions`
- `report.key_findings`
- `report.notable_source_ips`
- `viewer_payload.summary.context_count`
- `viewer_payload.summary.supporting_event_count`
- `viewer_payload.findings[].display_time`
- `viewer_payload.contexts[].reason_hints`

기대 동작:

- 기본 scan에 포함된다.
- 누락 list field는 빈 list로 normalize된다.
- 누락 scalar field는 `unknown`, `N/A`, `-` 등 기존 fallback을 사용한다.
- payload route는 crash 없이 표시된다.

### 8.7 `run_dir_huge_text_report`

목적:

- 긴 URI, request_id, summary, recommended_action이 list/detail/payload layout을 깨지 않는지 확인한다.

파일 구성:

```text
runs/run_dir_huge_text_report/
  manifest.json
  stage2_report.json
  viewer_payload.json
```

데이터 조건:

- 긴 URI 또는 query string
- 긴 `incident_ref` 또는 `request_id`
- 긴 `why_it_matters`
- 긴 `recommended_action`
- 긴 `reasoning_summary`
- contexts 다수 또는 supporting_events 다수

기대 동작:

- table/card layout이 가로로 과도하게 깨지지 않는다.
- 모바일 breakpoint에서 카드형 표시가 유지된다.
- text는 wrap/ellipsis 정책에 따라 표시된다.
- data truncation은 표시 전용이어야 하며 raw payload를 변경하지 않는다.

### 8.8 `archive_flat_legacy_without_viewer_payload`

목적:

- legacy flat/lab/data 산출물이 기본 운영 scan에서 제외되는지 확인한다.

파일 구성 후보:

```text
archive/flat_legacy_without_viewer_payload/
  reports/legacy_stage2_report.json
```

기대 동작:

- 기본 run_dir-only scan에는 포함되지 않는다.
- archive opt-in scan 후보에서만 포함된다.
- 포함될 경우 `storage_type=flat` 또는 `legacy_lab`
- viewer_payload 없음은 `viewer_payload_error_code=MISSING_FILE` 후보

### 8.9 `archive_flat_and_run_dir_duplicate`

목적:

- archive opt-in scan에서 flat와 run_dir가 같은 산출물을 가리킬 때 dedupe 정책을 검증한다.

파일 구성 후보:

```text
archive/flat_and_run_dir_duplicate/
  reports/duplicate_stage2_report.json
  reports/duplicate_viewer_payload.json
  runs/duplicate_run/
    manifest.json
    stage2_report.json
    viewer_payload.json
```

기대 동작:

- 기본 run_dir-only scan에서는 run_dir 항목만 포함된다.
- archive opt-in scan에서는 중복이 단일 report로 병합되는지 검토한다.
- 병합 시 `storage_type=both` 후보를 보존한다.
- route primary key는 기존 contract를 깨지 않도록 별도 정책을 적용한다.

## 9. canonical identity 후보

Phase 2B에서는 `canonical_report_key`를 구현하지 않는다. 다만 dedupe fixture를 위해 후보와 fallback 순서를 문서화한다.

후보:

1. manifest에 명시된 source export path + run_id
2. stage2 report JSON 실경로
3. viewer_payload JSON 실경로
4. 향후 source log hash 또는 source log fingerprint
5. 향후 analyzer/schema/model version metadata

주의:

- 현재 산출물에 `source_log_hash`, `stage2_model_version`, `analyzer_timestamp`가 항상 있다고 가정하지 않는다.
- 표시용 `generated_at`만으로 canonical key를 만들지 않는다.
- canonical key는 `report_id`와 별도 역할이다.

## 10. Phase 2C 테스트 후보

Phase 2B fixture 계획이 확정되면 Phase 2C에서 아래 테스트를 우선 작성한다.

### 10.1 run_dir-only 기본 scan

검증:

- `runs/*/manifest.json` 기반 report만 기본 scan에 포함된다.
- legacy `reports/`, `lab/`, `data/` archive fixture는 기본 scan에서 제외된다.

### 10.2 route contract 유지

검증:

- `/report/{report_id}` detail 역참조 가능
- `/report/{report_id}/payload` payload route fallback-safe
- `/compare/{timeframe_id}` group 역참조 가능

### 10.3 payload unavailable fallback

검증:

- missing viewer_payload는 report invalid가 아니다.
- malformed viewer_payload는 report invalid가 아니다.
- payload route는 빈 payload와 error message를 안전하게 표시한다.

### 10.4 manifest failure isolation

검증:

- malformed manifest 하나 때문에 전체 scan이 실패하지 않는다.
- missing stage2 report run은 기본 list에 일반 report로 노출되지 않는다.

### 10.5 storage_type metadata

검증:

- 기본 run_dir 항목은 `storage_type=run_dir`
- archive opt-in flat 항목은 `flat` 또는 `legacy_lab`
- duplicate 병합 후보는 `both`

### 10.6 read-only invariant

검증:

- template/route에 pipeline 실행, 삭제, rewrite, DB 제어 액션이 추가되지 않는다.
- severity/category/verdict 재계산 로직이 loader/UI에 추가되지 않는다.
- context-only 승격 로직이 추가되지 않는다.

### 10.7 source IP display-only 유지

검증:

- raw source IP는 matching/data 기준으로 유지된다.
- masking은 display copy에만 적용된다.
- UI가 Related Contexts 또는 Supporting Events 관계를 새로 추론하지 않는다.

## 11. fixture 작성 시 데이터 원칙

- Apache logs-only 원칙을 유지한다.
- fixture의 stage2 report 문구가 성공/침해/유출을 단정하지 않도록 한다.
- `status_code=200`, `text/html`, `response_body_bytes`, route name, UA, IP만으로 성공을 단정하는 문구를 넣지 않는다.
- context-only item은 finding/incident로 승격하지 않는다.
- raw POST body, response body 원문, DB 결과, 브라우저 실행 여부를 fixture 근거로 만들지 않는다.
- 긴 payload/URI는 layout 검증용 문자열로만 사용하고, 분석 성공 근거로 해석하지 않는다.

## 12. 결정 사항 요약

- Phase 2B의 기본 fixture는 run_dir 중심으로 설계한다.
- legacy flat/lab/data/report fixture는 기본 scan 제외 및 archive opt-in 검증용으로만 둔다.
- viewer_payload 부재/파손은 report invalid가 아니라 payload unavailable 상태로 분리한다.
- manifest 파손 또는 stage2 report 부재는 기본 scan에서 skip하는 정책을 우선 검토한다.
- route contract는 기존 `/report/{report_id}`, `/report/{report_id}/payload`, `/compare/{timeframe_id}`를 유지한다.
- `storage_type`, `run_id`, `manifest_path`, `viewer_payload_error_code`, `canonical_report_key`는 구현 전 field 후보로 문서화한다.
- Phase 2D 구현 전 Phase 2C 테스트에서 run_dir-only scan, legacy exclusion, fallback, read-only invariant를 먼저 고정한다.

## 13. 다음 단계

1. Phase 2B fixture plan 리뷰
2. 필요 시 fixture case 수를 줄이거나 이름을 확정
3. Phase 2C 테스트 설계/최소 테스트 추가
4. 테스트가 고정된 뒤 Phase 2D `runs/*/manifest.json` scan 구현 검토
