# 99_prepare_static_baseline_constants_move_plan

- 문서 상태: static baseline constants mini-move 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `f97164b8e5be89aa354c9ef575e1d7b45a56cf2e`
- 목적: static baseline constants 3개를 `src/prepare/static_baseline.py`로 이동하고, path/classification constants를 보류한 완료 범위와 검증 결과를 기록한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_protocol_anomaly_constants_move_plan.md](./99_prepare_protocol_anomaly_constants_move_plan.md)
- [99_prepare_ip_behavior_constants_move_plan.md](./99_prepare_ip_behavior_constants_move_plan.md)
- [99_prepare_method_behavior_constants_move_plan.md](./99_prepare_method_behavior_constants_move_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

static baseline constants의 부분 이동은 완료했다.

이동한 constants:

```text
STATIC_BASELINE_WINDOW_SEC = 300
STATIC_BASELINE_MIN_STATIC_PATHS = 3
STATIC_BASELINE_SAMPLE_REQUEST_LIMIT = 10
```

owner module:

```text
src/prepare/static_baseline.py
```

보류한 constants:

```text
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
```

보류 위치:

```text
src/prepare_llm_input.py
```

수정 파일:

```text
src/prepare/static_baseline.py
src/prepare_llm_input.py
```

이번 작업의 성격:

```text
- constants mini-move only
- behavior 변경 없음
- helper/function 추가 이동 없음
- output key 변경 없음
- policy wording 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 생성/연결 로직 변경 없음
- crawler baseline 로직 변경 없음
- mixed scanner 로직 변경 없음
- constants.py 생성 없음
- 다른 constants group 이동 없음
```

## 2. 적용 내용

적용한 변경:

```text
- `src/prepare/static_baseline.py`에 static baseline constants 3개 추가
- `src/prepare_llm_input.py`의 동일 constants 정의 3개 제거
- `src/prepare_llm_input.py`의 `static_baseline` try/except import 블록 양쪽에 constants 3개 import 추가
- 내부 참조 이름 `STATIC_BASELINE_*`는 그대로 유지
- `STATIC_EXTENSIONS`, `STATIC_PREFIXES`, `STATIC_BASELINE_IMAGE_EXTENSIONS`, `HEALTH_LIKE_PATHS`는 `src/prepare_llm_input.py`에 그대로 유지
```

유지한 값:

```text
static_baseline_window_sec = 300
static_baseline_min_static_paths = 3
static_baseline_sample_request_limit = 10
```

보류 constants 유지 이유:

```text
- `STATIC_EXTENSIONS` / `STATIC_PREFIXES`는 일반 static row 판별과 다른 baseline/context summary 경계에 걸릴 수 있다.
- `STATIC_BASELINE_IMAGE_EXTENSIONS`는 image/static classification 의미와 연결되어 static file 존재/노출 과해석 방지와 함께 관리해야 한다.
- `HEALTH_LIKE_PATHS`는 health 정상 여부 단정 금지와 연결된다.
- static/crawler/mixed scanner 경계가 아직 남아 있으므로 path/classification constants는 이번 mini-move에서 제외했다.
```

## 3. 이동하지 않은 것

이번 커밋에서 아래 항목은 이동하거나 수정하지 않았다.

```text
- STATIC_EXTENSIONS
- STATIC_PREFIXES
- STATIC_BASELINE_IMAGE_EXTENSIONS
- HEALTH_LIKE_PATHS
- build_static_baseline_reason_hints_for_row
- build_static_baseline_summaries
- build_static_baseline_summary_contexts
- finalize_static_baseline_bucket
- static path classification 로직
- health-like path 판단 로직
- image/static classification 로직
- crawler baseline 로직
- mixed scanner 로직
- candidate/scoring/filtering 로직
- supporting_events 생성/연결 로직
- Stage2 reporter
- expected/test fixture
- policy wording
- output key
- 다른 constants group
```

## 4. Apache logs-only 해석 원칙

이번 constants 이동 이후에도 아래 해석 제한은 유지한다.

```text
- static file 존재를 단정하지 않는다.
- JS 실행을 단정하지 않는다.
- robots/sitemap 내용이나 site structure를 단정하지 않는다.
- health 정상 여부를 단정하지 않는다.
- response bytes/content-type만으로 file exposure를 단정하지 않는다.
- static baseline은 context이지 파일 존재나 노출 성공 증거가 아니다.
```

금지 표현:

```text
- static asset exists
- JavaScript executed
- health endpoint is healthy
- site structure confirmed
- file exposure confirmed
```

## 5. 검증 결과

기준 커밋 `f97164b8e5be89aa354c9ef575e1d7b45a56cf2e`에서 아래 검증을 통과했다.

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

수정하지 않은 영역:

```text
- tests/fixtures
- tests/expected
- src/llm_stage2_reporter.py
- src/llm_stage1_classifier.py
- src/run_analysis_pipeline.py
```

## 6. 롤백 기준

향후 관련 추가 이동에서 아래 중 하나라도 발생하면 해당 커밋을 수정하거나 롤백한다.

```text
- import cycle 발생
- py_compile fail
- prepare regression fail
- stage dry-run regression fail
- static_baseline_* policy_notes 값 변화
- static baseline summary count 변화
- crawler baseline summary 변화
- mixed scanner summary 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- static path classification 변화
- health-like path classification 변화
- static file 존재 / JS 실행 / health 정상 / file exposure 단정 문구 발생
```

## 7. 다음 작업

static baseline constants 부분 이동은 완료했다.

`99_prepare_constants_mini_move_candidate_review.md`에서 상대적으로 안전한 mini-move 후보로 잡았던 항목은 현재까지 모두 처리했다.

완료된 mini-move:

```text
PROTOCOL_ANOMALY_* constants
IP_BEHAVIOR_* constants
METHOD_BEHAVIOR_* / method family constants 일부
STATIC_BASELINE_* constants 일부
```

계속 보류:

```text
STANDARD_HTTP_METHODS
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
PROBING_SEQUENCE_*
SENSITIVE_PATH_PROBE_* / DIR_PROBE_*
MIXED_BASELINE_SCANNER_*
SQLi/XSS/file_disclosure hint patterns
```

다음 작업은 constants를 더 이동하기보다 mini-move summary를 먼저 작성한다.

권장 다음 문서:

```text
docs/design/99_prepare_constants_mini_move_summary.md
```

문서 전용 커밋 후보:

```text
docs: record static baseline constants move
```
