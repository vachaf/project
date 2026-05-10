# 99_web_ui_loader_phase2c_test_plan

- 기준 시점: 2026-05-10
- 문서 목적: Web UI loader의 `run_dir` 중심 scan 전환을 구현하기 전에 고정해야 할 최소 테스트 축, fixture 의존성, 기대 assertion을 정리한다.
- 문서 성격: 구현 전 테스트 설계 문서
- 관련 문서:
  - `docs/design/99_web_ui_loader_phase2a_input_model_review.md`
  - `docs/design/99_web_ui_loader_phase2b_fixture_plan.md`
  - `docs/design/99_web_ui_run_dir_loader_phase2_plan.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`

## 0. 구현 결과 업데이트 (2026-05-10)

본 문서는 Phase 2C 시점의 설계 문서이며, 아래는 Phase 2D까지의 실제 구현/검증 결과를 기록한 상태 업데이트다.

- Phase 2C 최소 fixture helper/테스트가 실제로 추가됨
  - `tests/helpers/web_loader_phase2_fixtures.py`
  - `tests/test_web_loader_run_dir_scan.py`
- 초기 xfail 5개 테스트가 Phase 2D-1~2D-5에서 단계적으로 pass 전환됨
- 현재 `tests/test_web_loader_run_dir_scan.py`: `6 passed`
- `q` 검색 확장 테스트가 추가되어 `run_id`/display label/path 검색 회귀를 포함한다.
- Phase 2D에서 완료된 항목:
  - `runs/*/manifest.json -> stage2_report.json` manifest scan 최소 구현
  - run_dir 표준 `viewer_payload.json` resolve
  - missing payload fallback: `viewer_payload_error="MISSING_FILE"`
  - malformed payload fallback: `viewer_payload_error="MALFORMED_JSON"`
  - 기본 `REPORT_GLOBS=["runs/*/manifest.json"]` 전환
- UI polish 후속으로 Search & Filters breakpoint 조정이 반영되었다(본 문서의 핵심 테스트 범위에는 미포함).
- 기본 정책:
  - `reports/`/`lab/` legacy glob은 `LEGACY_REPORT_GLOBS`로 보존
  - 기본 scan에서는 제외
- 남은 후속 후보:
  - archive opt-in
  - flat/run_dir dedupe
  - canonical_report_key
  - schema incomplete 세부 처리
  - huge text/layout fixture
  - list UI의 `run_id`/`storage_type` 표시 여부

## 1. 목적

Phase 2C의 목적은 `runs/*/manifest.json` scan 구현 전에 테스트 기준을 먼저 고정하는 것이다.

Phase 2A/2B에서 정리한 방향은 다음과 같다.

- 기본 운영 scan은 `run_dir` 중심으로 전환한다.
- 기존 `reports/`, `lab/`, `data/` 계열 산출물은 기본 scan에서 제외한다.
- legacy/archive 확인은 별도 opt-in 후보로 분리한다.
- 기존 route contract(`/report/{report_id}`, `/report/{report_id}/payload`, `/compare/{timeframe_id}`)는 유지한다.
- viewer_payload 부재/파손은 report invalid가 아니라 payload unavailable 상태로 분리한다.
- Web UI는 read-only viewer 범위를 유지한다.

Phase 2C에서는 실제 loader 구현을 시작하지 않고, 위 방향을 코드로 바꾸기 전에 어떤 테스트가 먼저 필요할지 정의한다.

## 2. 명시적 비범위

이번 Phase 2C 문서에서는 아래 작업을 하지 않는다.

- 실제 테스트 코드 작성
- 실제 fixture JSON 파일 생성
- `runs/*/manifest.json` scan 구현
- legacy flat/lab/data scan 제거 구현
- Web UI route/template/app.py 수정
- `web/services/report_loader.py` 수정
- pipeline 실행, DB 제어, report rewrite 기능 추가
- severity/category/verdict 재계산
- context-only 항목을 finding/incident로 승격
- UI에서 Related Contexts 또는 Supporting Events 관계를 새로 추론

## 3. 테스트 작성 순서 권장안

Phase 2C 테스트는 한 번에 모두 만들기보다, 구현 리스크가 낮은 순서로 나누어 작성한다.

권장 순서:

1. fixture 생성 helper 또는 fixture root 주입 방식 확정
2. run_dir-only 기본 scan 테스트
3. legacy flat/lab/data 기본 제외 테스트
4. viewer_payload unavailable fallback 테스트
5. malformed manifest / missing stage2 report isolation 테스트
6. route contract 테스트
7. storage_type/run_id/manifest_path metadata 테스트
8. read-only invariant 테스트
9. source IP display-only 회귀 테스트 유지
10. archive opt-in / duplicate dedupe 테스트는 후순위

## 4. 테스트 파일 후보

테스트 파일 후보는 아래처럼 분리한다.

```text
tests/test_web_loader_run_dir_scan.py
```

주요 대상:

- run_dir-only scan
- legacy exclusion
- manifest failure isolation
- missing stage2 report skip
- storage_type/run_id metadata

```text
tests/test_web_loader_payload_fallback.py
```

주요 대상:

- missing viewer_payload
- malformed viewer_payload
- schema incomplete viewer_payload
- report valid 유지
- payload route fallback-safe

```text
tests/test_web_loader_route_contract.py
```

주요 대상:

- `/report/{report_id}`
- `/report/{report_id}/payload`
- `/compare/{timeframe_id}`
- `report_id` 역참조 안정성

```text
tests/test_web_loader_read_only_invariant.py
```

주요 대상:

- pipeline 실행 버튼 없음
- delete/rewrite/db control 액션 없음
- severity/category/verdict 재계산 없음
- context-only 승격 없음

초기에는 파일을 과하게 나누지 않고 `tests/test_web_loader_run_dir_scan.py` 하나에서 시작한 뒤, fallback/route/read-only 테스트가 커지면 분리해도 된다.

## 5. fixture 의존성

Phase 2C 테스트는 Phase 2B에서 제안한 fixture를 사용한다.

기본 fixture root 후보:

```text
tests/fixtures/web_loader_phase2/
```

기본 scan 대상 fixture:

```text
tests/fixtures/web_loader_phase2/runs/
  run_dir_valid_basic/
  run_dir_missing_viewer_payload/
  run_dir_malformed_viewer_payload/
  run_dir_malformed_manifest/
  run_dir_missing_stage2_report/
  run_dir_missing_optional_fields/
  run_dir_huge_text_report/
```

archive opt-in 후보 fixture:

```text
tests/fixtures/web_loader_phase2/archive/
  flat_legacy_without_viewer_payload/
  flat_and_run_dir_duplicate/
```

주의:

- 실제 repo의 `reports/`, `lab/`, `data/`를 테스트 입력으로 직접 사용하지 않는다.
- 테스트는 전용 fixture root를 주입할 수 있어야 한다.
- fixture는 Apache logs-only guardrail을 깨는 문구를 포함하지 않는다.

## 6. 최소 fixture case 및 helper 방식 결정

### 6.1 최소 fixture case 수

Phase 2C 최소 fixture case는 6개로 고정한다.

필수 run_dir fixture 5개:

1. `run_dir_valid_basic`
   - 정상 run_dir report
   - list/detail/payload route contract와 metadata preservation의 기준 fixture

2. `run_dir_missing_viewer_payload`
   - stage2 report는 정상, viewer_payload 없음
   - payload unavailable fallback 기준 fixture

3. `run_dir_malformed_viewer_payload`
   - stage2 report는 정상, viewer_payload JSON 파싱 실패
   - malformed payload fallback 기준 fixture

4. `run_dir_malformed_manifest`
   - manifest JSON 파싱 실패 또는 root schema 오류
   - manifest failure isolation 기준 fixture

5. `run_dir_missing_stage2_report`
   - manifest는 있으나 primary stage2 report 없음
   - missing primary report skip 기준 fixture

필수 archive fixture 1개:

6. `archive_flat_legacy_without_viewer_payload`
   - legacy flat/lab/data archive가 기본 scan에서 제외되는지 확인하는 fixture
   - archive opt-in 구현 전에는 기본 exclusion 검증만 담당

### 6.2 후순위 fixture

아래 fixture는 초기 최소 세트에서 제외하고, 필요가 확인될 때 추가한다.

- `run_dir_missing_optional_fields`
  - schema incomplete/fallback 세부 검증용
  - 초기 missing/malformed payload 테스트가 안정화된 뒤 추가

- `run_dir_huge_text_report`
  - layout/mobile smoke 검증용
  - loader scan 구현과 직접 관련이 낮으므로 후순위

- `archive_flat_and_run_dir_duplicate`
  - archive opt-in + dedupe 검증용
  - archive opt-in이 구현 후보로 승격될 때 추가

### 6.3 fixture root 방식 결정

초기 Phase 2C/2D 테스트는 커밋된 정적 JSON fixture 디렉터리를 대량으로 만들지 않고, pytest `tmp_path` 기반 runtime fixture root를 우선 사용한다.

권장 runtime root:

```text
<tmp_path>/web_loader_phase2/
  runs/
    run_dir_valid_basic/
    run_dir_missing_viewer_payload/
    run_dir_malformed_viewer_payload/
    run_dir_malformed_manifest/
    run_dir_missing_stage2_report/
  archive/
    flat_legacy_without_viewer_payload/
```

이유:

- 실제 repo의 `reports/`, `lab/`, `data/`와 테스트 입력을 분리할 수 있다.
- fixture case별 파일 생성/누락/파손 상태를 테스트 안에서 명시적으로 만들 수 있다.
- JSON fixture 파일 대량 커밋을 피할 수 있다.
- run_dir scan 구현 전후로 path 주입 방식을 검증하기 쉽다.

### 6.4 helper 방식 결정

초기 helper는 전용 test helper module로 둔다.

후보 경로:

```text
tests/helpers/web_loader_phase2_fixtures.py
```

helper 함수 후보:

```python
def build_web_loader_phase2_fixture_root(tmp_path) -> Path:
    """Create the minimal Phase 2C fixture tree under tmp_path and return project_root."""


def write_run_dir_case(root: Path, run_id: str, *, include_stage2: bool = True, include_payload: bool = True, malformed_manifest: bool = False, malformed_payload: bool = False) -> Path:
    """Create a single run_dir fixture case."""


def write_legacy_archive_case(root: Path) -> Path:
    """Create a legacy flat report fixture that must be excluded by default scan."""
```

초기에는 helper를 지나치게 일반화하지 않는다. 최소 테스트 5개가 필요로 하는 JSON만 생성한다.

### 6.5 정적 fixture 디렉터리 사용 기준

정적 fixture 파일은 아래 경우에만 후속으로 검토한다.

- browser/manual layout 확인용 huge text fixture가 필요해진 경우
- 여러 테스트 파일에서 같은 payload를 반복 사용해 helper보다 정적 파일이 더 읽기 쉬운 경우
- fixture 자체를 문서화된 sample artifact로 보존해야 하는 경우

현재 단계에서는 runtime helper를 기본으로 한다.

## 7. 테스트 축 상세

### 7.1 run_dir-only 기본 scan

목적:

- 기본 Web UI loader scan이 향후 `runs/*/manifest.json` 중심으로 전환될 때의 기대 동작을 고정한다.

필요 fixture:

- `run_dir_valid_basic`
- `run_dir_missing_viewer_payload`
- `run_dir_malformed_viewer_payload`
- `archive_flat_legacy_without_viewer_payload`

기대 assertion:

- 정상 run_dir report가 scan 결과에 포함된다.
- 기본 scan 결과의 모든 report는 `storage_type=run_dir`이다.
- 기본 scan 결과에는 legacy `reports/`, `lab/`, `data/` archive fixture가 포함되지 않는다.
- scan 결과 report는 기존 `Report.to_summary()` 호환 필드를 제공한다.
- `run_id`와 `manifest_path` metadata가 보존된다.

비고:

- 이 테스트는 Phase 2D 구현 전에는 pending/xfail 후보로 둘 수 있다.
- 구현 후에는 기본 회귀 테스트로 승격한다.

### 7.2 legacy flat/lab/data 기본 제외

목적:

- 기존 실험/legacy 산출물이 운영 목록에 섞이지 않도록 기본 제외 정책을 고정한다.

필요 fixture:

- `archive_flat_legacy_without_viewer_payload`

기대 assertion:

- 기본 scan에서는 archive fixture report가 0건이다.
- legacy flat report가 viewer_payload를 갖지 않아도 기본 list에 unavailable report로 노출되지 않는다.
- archive opt-in이 없는 상태에서 `storage_type=flat`, `legacy_lab`, `both`가 나오지 않는다.

후순위 assertion:

- archive opt-in mode가 구현되면 해당 mode에서만 legacy report가 포함된다.
- `archive_flat_and_run_dir_duplicate` fixture는 이때 추가한다.

### 7.3 malformed manifest isolation

목적:

- manifest 하나가 깨져도 loader 전체 scan이 실패하지 않도록 보장한다.

필요 fixture:

- `run_dir_malformed_manifest`
- `run_dir_valid_basic`

기대 assertion:

- scan 호출이 exception 없이 완료된다.
- malformed manifest run은 기본 report list에 포함되지 않는다.
- 정상 run_dir report는 계속 포함된다.
- diagnostic/invalid run list는 구현 전에는 필수로 요구하지 않는다.

### 7.4 missing stage2 report skip

목적:

- manifest는 있으나 primary stage2 report가 없는 run을 일반 report로 노출하지 않는 정책을 고정한다.

필요 fixture:

- `run_dir_missing_stage2_report`
- `run_dir_valid_basic`

기대 assertion:

- missing stage2 report run은 기본 list에 포함되지 않는다.
- scan 전체는 실패하지 않는다.
- viewer_payload만 있는 run은 일반 report로 승격되지 않는다.
- stage2 report 부재는 새 보안 판정이나 synthetic report 생성으로 보정하지 않는다.

### 7.5 missing viewer_payload fallback

목적:

- viewer_payload 부재를 report invalid와 분리한다.

필요 fixture:

- `run_dir_missing_viewer_payload`

기대 assertion:

- report는 scan 결과에 포함된다.
- `is_valid=True` 또는 stage2 report valid 상태가 유지된다.
- `viewer_payload_available=False`
- `viewer_payload_error_code=MISSING_FILE` 후보
- `viewer_payload_error` 문자열이 비어 있지 않다.
- detail route는 표시 가능하다.
- payload route는 crash 없이 unavailable 상태를 표시한다.

### 7.6 malformed viewer_payload fallback

목적:

- viewer_payload JSON 파싱 실패가 detail/report list 전체 장애로 번지지 않도록 보장한다.

필요 fixture:

- `run_dir_malformed_viewer_payload`

기대 assertion:

- report는 scan 결과에 포함된다.
- `viewer_payload_available=False`
- `viewer_payload_error_code=MALFORMED_JSON` 후보
- stage2 report 자체는 invalid 처리하지 않는다.
- payload route는 fallback-safe하게 error를 표시한다.

### 7.7 schema incomplete viewer_payload fallback

목적:

- viewer_payload root object 또는 핵심 key 누락 시 fallback 정책을 고정한다.

필요 fixture:

- 후순위 `run_dir_missing_optional_fields`

기대 assertion:

- root object가 dict이면 가능한 범위에서 summary를 만든다.
- 핵심 list field 누락은 empty list로 처리한다.
- missing scalar는 `unknown`, `N/A`, `-` fallback을 사용한다.
- schema가 너무 불완전하면 `viewer_payload_error_code=SCHEMA_INCOMPLETE` 후보를 검토한다.
- report 자체는 invalid 처리하지 않는다.

### 7.8 route contract 유지

목적:

- run_dir scan으로 바뀌어도 기존 Web UI route contract가 유지되는지 확인한다.

필요 fixture:

- `run_dir_valid_basic`
- `run_dir_missing_viewer_payload`

기대 assertion:

- list에서 얻은 `report_id`로 `/report/{report_id}` 접근 가능
- list에서 얻은 `report_id`로 `/report/{report_id}/payload` 접근 가능
- payload unavailable report도 payload route에서 500이 나지 않음
- `timeframe_id`로 `/compare/{timeframe_id}` 접근 가능하거나, 비교 대상 부족 시 기존 partial compare 정책을 유지
- `report_id`는 `loader.get_report_by_id(report_id)`로 역참조 가능

주의:

- `run_id` 전용 route는 이번 테스트 범위가 아니다.
- 기존 route를 변경하지 않는다.

### 7.9 metadata preservation

목적:

- run_dir source metadata가 normalized report에 보존되는지 확인한다.

필요 fixture:

- `run_dir_valid_basic`

기대 assertion:

- `storage_type=run_dir`
- `run_id`가 manifest 또는 directory name과 일치
- `manifest_path`가 존재
- `run_dir` 또는 repo-relative display path가 보존
- `viewer_payload_path`가 존재하는 경우 repo-relative path로 표시 가능
- `canonical_report_key`는 구현 전 후보이며 필수 assertion으로 두지 않는다.

### 7.10 read-only invariant

목적:

- loader 전환이 Web UI의 역할을 execution console로 확장하지 않도록 방지한다.

테스트 후보:

- template 문자열 또는 route table 검사
- HTML 응답 내 action keyword 검사
- app route path 검사

금지 항목:

- pipeline run button
- delete button
- rewrite/regenerate report action
- DB control action
- scheduling/live progress action
- severity/category/verdict recalculation action
- context-only promotion action

기대 assertion:

- 기본 list/detail/payload HTML에 실행/삭제/재작성 액션이 없다.
- loader/UI에 새 보안 판정을 만드는 endpoint가 없다.
- read-only 안내 또는 guardrail 문구는 유지된다.

### 7.11 source IP display-only 유지

목적:

- 기존 source IP masking/display-only 회귀를 유지한다.

기존 테스트 참조:

- `tests/test_web_payload_src_ip_mode.py`

기대 assertion:

- raw `src_ip`는 sanitize 단계에서 보존된다.
- masking은 display copy에만 적용된다.
- 원본 rows는 변경되지 않는다.
- Related Contexts matching은 raw data 기준을 유지한다.
- UI가 새 관계를 추론해 보정하지 않는다.

## 8. 최소 테스트 세트 제안

Phase 2D 구현 전에 최소로 고정할 테스트는 아래 5개다.

1. `test_run_dir_scan_includes_valid_run_only`
   - valid run_dir는 포함
   - malformed manifest/missing stage2는 제외

2. `test_default_scan_excludes_legacy_archive_outputs`
   - archive flat/lab/data fixture는 기본 scan에서 제외

3. `test_missing_viewer_payload_keeps_report_valid`
   - report valid 유지
   - payload unavailable 표시

4. `test_malformed_viewer_payload_is_fallback_safe`
   - report valid 유지
   - payload error code 후보 확인

5. `test_run_dir_report_id_resolves_detail_and_payload`
   - list report_id가 detail/payload route로 역참조 가능

후순위 테스트:

- huge text layout smoke
- archive opt-in duplicate dedupe
- canonical_report_key fallback
- read-only invariant HTML keyword 검사

## 9. xfail/pending 운영 기준

Phase 2C 테스트는 Phase 2D 구현 전에 작성될 수 있으므로 일부 테스트는 초기에는 실패할 수 있다.

권장 기준:

- 아직 구현되지 않은 run_dir scan 테스트는 `xfail` 또는 별도 marker로 둘 수 있다.
- 기존 flat-only 동작을 깨지 않는 테스트는 즉시 pass 상태로 둔다.
- Phase 2D 구현 PR/커밋에서 xfail을 pass로 전환한다.
- xfail 사유에는 `run_dir manifest scan not implemented yet`처럼 명시적 이유를 남긴다.

## 10. 테스트 데이터 작성 원칙

- fixture 문구는 Apache logs-only evidence boundary를 유지한다.
- `status_code=200`, `text/html`, `response_body_bytes`, route name, UA, IP만으로 성공/침해/유출을 단정하지 않는다.
- raw POST body, response body 원문, DB 결과, 브라우저 실행 여부를 fixture 근거로 만들지 않는다.
- context-only item은 finding/incident로 승격하지 않는다.
- long text fixture는 layout 압박 검증용이며 공격 성공 근거가 아니다.
- lab 전용 UA나 특정 IP를 공격 성공 근거로 일반화하지 않는다.

## 11. Phase 2D 진입 조건 충족 결과

Phase 2D `runs/*/manifest.json` scan 구현 진입 전 조건은 아래와 같이 충족됐다.

- 최소 fixture case 6개 확정: 충족
- pytest `tmp_path` 기반 runtime fixture root 방식 확정: 충족
- `tests/helpers/web_loader_phase2_fixtures.py` helper 방식 확정: 충족
- 최소 테스트 5개 작성 또는 xfail로 고정: 충족(초기 xfail 5개 작성 후 단계 전환)
- legacy flat/lab/data 기본 제외 기대값 고정: 충족
- missing/malformed viewer_payload fallback 기대값 고정: 충족
- malformed manifest/missing stage2 report skip 정책 고정: 충족
- read-only invariant 위반 금지 항목 확인: 충족

## 12. 결정 사항 요약

- Phase 2C는 fixture 생성 직후 바로 구현으로 가지 않고, 테스트 축을 먼저 고정하는 단계다.
- 최소 fixture case는 6개로 고정한다.
- 필수 run_dir fixture는 5개, 필수 archive exclusion fixture는 1개다.
- 초기 fixture root는 커밋된 정적 JSON 디렉터리가 아니라 pytest `tmp_path` 기반 runtime root로 생성한다.
- helper는 `tests/helpers/web_loader_phase2_fixtures.py` 후보로 둔다.
- 기본 테스트 방향은 run_dir-only scan과 legacy exclusion이다.
- viewer_payload 문제는 report invalid와 분리한다.
- manifest 문제는 해당 run skip을 우선 정책으로 둔다.
- route contract는 기존 `/report/{report_id}`, `/report/{report_id}/payload`, `/compare/{timeframe_id}`를 유지한다.
- archive opt-in과 duplicate dedupe는 후순위 테스트다.
- Phase 2D 구현 전 최소 테스트 5개를 먼저 고정하는 것을 권장한다.

## 13. 다음 단계

1. 실제 run_dir smoke로 Web UI 목록/detail/payload 화면 확인
2. list/detail에서 `run_id`/`storage_type` 표시 필요성 검토
3. archive opt-in 정책/구현 필요성 판단
4. archive opt-in 필요가 확인될 때 flat/run_dir dedupe와 canonical_report_key 검토
