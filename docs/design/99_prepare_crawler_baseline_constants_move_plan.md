# 99_prepare_crawler_baseline_constants_move_plan

- 문서 상태: crawler baseline constants mini-move plan
- 기준 시점: 2026-05-04
- 목적: `CRAWLER_BASELINE_*`, `BROWSER_UA_HINTS`, `CRAWLER_BROWSE_*` grep 결과를 바탕으로, crawler baseline 관련 constants/patterns의 module-local 이동 가능 범위와 금지사항, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_crawler_baseline_split_plan.md](./99_prepare_crawler_baseline_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

Crawler baseline constants/patterns는 소규모 이동 후보로 검토 가능하다.

이동 후보:

```text
BROWSER_UA_HINTS
CRAWLER_BASELINE_WINDOW_SEC
CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT
CRAWLER_BROWSE_PRODUCT_SEGMENTS
CRAWLER_BROWSE_CATEGORY_SEGMENTS
CRAWLER_BROWSE_GENERIC_SEGMENTS
```

권장 owner module:

```text
src/prepare/crawler_baseline.py
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
```

주의:

```text
BROWSER_UA_HINTS와 CRAWLER_BROWSE_*는 crawler-like / browse-like context를 위한 보조 신호다.
실제 crawler identity, robots/sitemap 내용, site structure, product/category page existence를 단정하는 근거가 아니다.
```

## 2. grep 확인 결과

확인 명령:

```bash
grep -n "CRAWLER_BASELINE_\|BROWSER_UA_HINTS\|CRAWLER_BROWSE_PRODUCT_SEGMENTS\|CRAWLER_BROWSE_CATEGORY_SEGMENTS\|CRAWLER_BROWSE_GENERIC_SEGMENTS" src/prepare_llm_input.py src/prepare/*.py
```

확인 결과:

```text
src/prepare_llm_input.py:425:BROWSER_UA_HINTS = (
src/prepare_llm_input.py:438:CRAWLER_BASELINE_WINDOW_SEC = 300
src/prepare_llm_input.py:439:CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT = 10
src/prepare_llm_input.py:464:CRAWLER_BROWSE_PRODUCT_SEGMENTS = {"product", "products"}
src/prepare_llm_input.py:465:CRAWLER_BROWSE_CATEGORY_SEGMENTS = {"category", "categories"}
src/prepare_llm_input.py:466:CRAWLER_BROWSE_GENERIC_SEGMENTS = {"list", "browse"}
src/prepare_llm_input.py:2098:    return any(hint in ua_lower for hint in BROWSER_UA_HINTS)
src/prepare_llm_input.py:2195:        product_segments=CRAWLER_BROWSE_PRODUCT_SEGMENTS,
src/prepare_llm_input.py:2196:        category_segments=CRAWLER_BROWSE_CATEGORY_SEGMENTS,
src/prepare_llm_input.py:2197:        generic_segments=CRAWLER_BROWSE_GENERIC_SEGMENTS,
src/prepare_llm_input.py:2215:        product_segments=CRAWLER_BROWSE_PRODUCT_SEGMENTS,
src/prepare_llm_input.py:2216:        category_segments=CRAWLER_BROWSE_CATEGORY_SEGMENTS,
src/prepare_llm_input.py:2217:        generic_segments=CRAWLER_BROWSE_GENERIC_SEGMENTS,
src/prepare_llm_input.py:2228:        sample_request_limit=CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT,
src/prepare_llm_input.py:2234:    window_sec: int = CRAWLER_BASELINE_WINDOW_SEC,
src/prepare_llm_input.py:2239:        sample_request_limit=CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT,
src/prepare_llm_input.py:2250:        product_segments=CRAWLER_BROWSE_PRODUCT_SEGMENTS,
src/prepare_llm_input.py:2251:        category_segments=CRAWLER_BROWSE_CATEGORY_SEGMENTS,
src/prepare_llm_input.py:2252:        generic_segments=CRAWLER_BROWSE_GENERIC_SEGMENTS,
src/prepare_llm_input.py:4027:                "crawler_baseline_window_sec": CRAWLER_BASELINE_WINDOW_SEC,
```

해석:

```text
- Crawler baseline constants/patterns는 현재 `src/prepare_llm_input.py`에 남아 있다.
- `src/prepare/crawler_baseline.py` 또는 다른 `src/prepare/*.py`에서 직접 참조하는 결과는 보이지 않는다.
- owner module은 `src/prepare/crawler_baseline.py`로 비교적 명확하다.
- 다만 User-Agent와 browse path 판단은 crawler identity/site structure/page existence 과해석과 연결될 수 있으므로 값과 의미를 바꾸지 않는 조건에서만 이동한다.
```

## 3. 현재 구조 추정

현재 `src/prepare_llm_input.py`에는 crawler baseline wrapper 계열과 crawler-like / browse path classifier helper가 남아 있고, 실제 crawler baseline summary builder는 이미 `src/prepare/crawler_baseline.py`로 분리되어 있다.

사용 지점 유형:

```text
- browser-like UA 판단
- crawler browse path category 판단
- crawler baseline reason hint 생성 호출 인자
- crawler baseline summary context 호출 인자
- crawler baseline summary builder 기본 window
- crawler baseline summary builder sample limit
- policy_notes 메타 값
```

이동 후에도 아래 값 의미는 유지해야 한다.

```text
crawler_baseline_window_sec = 300
crawler_baseline_sample_request_limit = 10
browser_ua_hints = ("mozilla/", "chrome/", "safari/", "firefox/", "edg/", "applewebkit/")
crawler_browse_product_segments = {"product", "products"}
crawler_browse_category_segments = {"category", "categories"}
crawler_browse_generic_segments = {"list", "browse"}
```

## 4. 이동 방식

권장 방식:

```text
1. `src/prepare/crawler_baseline.py`에 이동 후보 constants/patterns를 정의한다.
2. `src/prepare_llm_input.py`의 동일 constants/patterns 정의를 제거한다.
3. `src/prepare_llm_input.py` import 블록에서 이동한 constants/patterns를 함께 import한다.
4. 기존 wrapper 기본값과 policy_notes 참조는 동일한 constant 이름을 사용하게 한다.
5. 함수 호출 인자, output key, policy_notes key는 변경하지 않는다.
```

권장 import 예시:

```python
try:
    from src.prepare.crawler_baseline import (
        BROWSER_UA_HINTS,
        CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT,
        CRAWLER_BASELINE_WINDOW_SEC,
        CRAWLER_BROWSE_CATEGORY_SEGMENTS,
        CRAWLER_BROWSE_GENERIC_SEGMENTS,
        CRAWLER_BROWSE_PRODUCT_SEGMENTS,
        build_crawler_baseline_reason_hints_for_row as _build_crawler_baseline_reason_hints_for_row,
        build_crawler_baseline_summaries as _build_crawler_baseline_summaries,
        build_crawler_baseline_summary_contexts as _build_crawler_baseline_summary_contexts,
        classify_crawler_baseline_path_category as _classify_crawler_baseline_path_category,
        classify_crawler_like_user_agent_family as _classify_crawler_like_user_agent_family,
        finalize_crawler_baseline_bucket as _finalize_crawler_baseline_bucket,
    )
except ImportError:
    from prepare.crawler_baseline import (
        BROWSER_UA_HINTS,
        CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT,
        CRAWLER_BASELINE_WINDOW_SEC,
        CRAWLER_BROWSE_CATEGORY_SEGMENTS,
        CRAWLER_BROWSE_GENERIC_SEGMENTS,
        CRAWLER_BROWSE_PRODUCT_SEGMENTS,
        build_crawler_baseline_reason_hints_for_row as _build_crawler_baseline_reason_hints_for_row,
        build_crawler_baseline_summaries as _build_crawler_baseline_summaries,
        build_crawler_baseline_summary_contexts as _build_crawler_baseline_summary_contexts,
        classify_crawler_baseline_path_category as _classify_crawler_baseline_path_category,
        classify_crawler_like_user_agent_family as _classify_crawler_like_user_agent_family,
        finalize_crawler_baseline_bucket as _finalize_crawler_baseline_bucket,
    )
```

주의:

```text
- import alias를 새로 만들 필요는 없다.
- 기존 코드에서 `BROWSER_UA_HINTS`, `CRAWLER_BASELINE_*`, `CRAWLER_BROWSE_*` 이름을 그대로 참조할 수 있게 import한다.
- crawler baseline helper/function을 추가 이동하지 않는다.
```

## 5. 허용 범위

허용되는 변경:

```text
- `src/prepare/crawler_baseline.py`에 crawler baseline constants/patterns 추가
- `src/prepare_llm_input.py`에서 동일 constants/patterns 정의 제거
- `src/prepare_llm_input.py` import 블록에 constants/patterns import 추가
- py_compile / regression 통과를 위한 import 정렬 수준의 최소 수정
```

허용되지 않는 변경:

```text
- crawler baseline helper/function 추가 이동
- crawler-like UA classifier 로직 변경
- crawler browse path classifier 로직 변경
- crawler baseline summary output key 변경
- policy_notes key 또는 wording 변경
- expected/test fixture 수정
- Stage2 reporter 수정
- candidate/scoring/filtering 변경
- supporting_events 생성/연결 로직 변경
- constants.py 생성
- 다른 constants group 이동
```

## 6. Apache logs-only 해석 원칙

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

## 7. 검증 계획

이동 전:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

이동 후:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

성공 기준:

```text
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
output key 의미 변경 없음
policy_notes 의미 변경 없음
expected/test fixture 수정 없음
Stage2 reporter 수정 없음
candidate/scoring/filtering 변경 없음
crawler baseline summary count 변화 없음
crawler-like UA family 이름 변화 없음
path category 이름 변화 없음
crawler authenticity / site structure / page existence 단정 문구 없음
```

## 8. 실패 시 롤백 기준

아래 중 하나라도 발생하면 constants/patterns 이동 커밋을 수정하거나 롤백한다.

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

## 9. 완료 후 문서 반영

이동 완료 후 아래 문서를 갱신한다.

```text
docs/design/99_prepare_crawler_baseline_constants_move_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```

완료 기록에 포함할 항목:

```text
- 이동한 constants/patterns 목록
- 기준 커밋
- `src/prepare/crawler_baseline.py`에 constants/patterns 정의 추가
- `src/prepare_llm_input.py`에서 constants/patterns import 사용
- helper/function 추가 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- py_compile / prepare regression / stage dry-run regression 결과
```

## 10. 다음 작업

문서 작성 후 다음 작업은 Codex에 crawler baseline constants/patterns 이동을 맡기는 것이다.

권장 커밋 순서:

```text
1. docs: plan crawler baseline constants move
2. refactor: move crawler baseline constants
3. docs: record crawler baseline constants move
```

코드 이동 커밋 후보 메시지:

```text
refactor: move crawler baseline constants
```
