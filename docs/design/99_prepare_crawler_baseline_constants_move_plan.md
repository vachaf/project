# 99_prepare_crawler_baseline_constants_move_plan

- 문서 상태: crawler baseline constants mini-move 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `0787a859088c90160d54510fcc7a29f33070dcea`
- 목적: crawler baseline 관련 constants/patterns를 `src/prepare/crawler_baseline.py`로 이동한 완료 범위, 유지한 계약, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

Crawler baseline constants/patterns의 module-local 이동은 완료했다.

이동한 constants/patterns:

```text
BROWSER_UA_HINTS
CRAWLER_BASELINE_WINDOW_SEC = 300
CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT = 10
CRAWLER_BROWSE_PRODUCT_SEGMENTS = {"product", "products"}
CRAWLER_BROWSE_CATEGORY_SEGMENTS = {"category", "categories"}
CRAWLER_BROWSE_GENERIC_SEGMENTS = {"list", "browse"}
```

owner module:

```text
src/prepare/crawler_baseline.py
```

수정 파일:

```text
src/prepare/crawler_baseline.py
src/prepare_llm_input.py
```

이번 작업의 성격:

```text
- constants/patterns mini-move only
- behavior 변경 없음
- helper/function 추가 이동 없음
- output key 변경 없음
- policy wording 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 생성/연결 로직 변경 없음
- constants.py 생성 없음
- 다른 constants group 이동 없음
```

## 2. 적용 내용

적용한 변경:

```text
- `src/prepare/crawler_baseline.py`에 crawler baseline constants/patterns 6개 추가
- `src/prepare_llm_input.py`의 동일 constants/patterns 정의 6개 제거
- `src/prepare_llm_input.py`의 `crawler_baseline` try/except import 블록 양쪽에 constants/patterns 6개 import 추가
- 내부 참조 이름 `BROWSER_UA_HINTS`, `CRAWLER_BASELINE_*`, `CRAWLER_BROWSE_*`는 그대로 유지
```

유지한 값:

```text
crawler_baseline_window_sec = 300
crawler_baseline_sample_request_limit = 10
browser_ua_hints = ("mozilla/", "chrome/", "safari/", "firefox/", "edg/", "applewebkit/")
crawler_browse_product_segments = {"product", "products"}
crawler_browse_category_segments = {"category", "categories"}
crawler_browse_generic_segments = {"list", "browse"}
```

## 3. 이동하지 않은 것

이번 커밋에서 아래 항목은 이동하거나 수정하지 않았다.

```text
build_crawler_baseline_reason_hints_for_row
build_crawler_baseline_summaries
build_crawler_baseline_summary_contexts
classify_crawler_baseline_path_category
classify_crawler_like_user_agent_family
finalize_crawler_baseline_bucket
crawler-like UA classifier 로직
crawler browse path classifier 로직
candidate/scoring/filtering 로직
supporting_events 생성/연결 로직
Stage2 reporter
expected/test fixture
policy wording
output key
다른 constants group
```

## 4. Apache logs-only 해석 원칙

이번 constants/patterns 이동 이후에도 아래 해석 제한은 유지한다.

```text
- 실제 crawler identity를 단정하지 않는다.
- User-Agent가 Googlebot-like여도 실제 Googlebot 여부를 단정하지 않는다.
- robots.txt 또는 sitemap.xml 내용은 Apache 로그만으로 알 수 없다.
- site structure를 단정하지 않는다.
- product/category page existence를 단정하지 않는다.
- crawler baseline summary는 context이지 crawler authenticity 또는 site mapping proof가 아니다.
```

금지 표현:

```text
- real crawler confirmed
- Googlebot verified
- robots policy confirmed
- sitemap contents confirmed
- site structure mapped
- product/category page exists
- crawler successfully indexed the site
```

## 5. 검증 결과

기준 커밋 `0787a859088c90160d54510fcc7a29f33070dcea`에서 아래 검증을 통과했다.

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
- crawler_baseline_* policy_notes 값 변화
- crawler baseline summary count 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- crawler-like UA family 이름 변화
- crawler browse path category 이름 변화
- crawler identity / robots policy / sitemap contents / site structure / page existence 단정 문구 발생
```

## 7. 다음 작업

Crawler baseline constants/patterns 이동은 완료했다.

상대적으로 owner가 명확한 constants mini-move 후보는 대부분 완료 상태다.

완료된 mini-move:

```text
PROTOCOL_ANOMALY_* constants
IP_BEHAVIOR_* constants
METHOD_BEHAVIOR_* / method family constants 일부
STATIC_BASELINE_* constants 일부
AUTH_* / LOGIN_URI / AUTH_ENDPOINT family constants
CRAWLER_BASELINE_* / BROWSER_UA / CRAWLER_BROWSE constants
```

계속 보류:

```text
STANDARD_HTTP_METHODS
STATIC_EXTENSIONS / STATIC_PREFIXES / STATIC_BASELINE_IMAGE_EXTENSIONS / HEALTH_LIKE_PATHS
PROBING_SEQUENCE_*
SENSITIVE_PATH_PROBE_* / DIR_PROBE_*
MIXED_BASELINE_SCANNER_*
AUTOMATION_UA_PATTERNS
shared attack/search policy constants
detect_decoded_attack_hints
candidate/scoring/filtering
supporting_events 생성/연결 로직
```

다음 작업은 추가 constants 이동보다 constants mini-move summary와 TODO 상태를 갱신하는 것이다.

문서 전용 커밋 후보:

```text
docs: record crawler baseline constants move
```
