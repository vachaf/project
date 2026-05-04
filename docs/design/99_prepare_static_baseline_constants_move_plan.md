# 99_prepare_static_baseline_constants_move_plan

- 문서 상태: static baseline constants mini-move plan
- 기준 시점: 2026-05-04
- 목적: `STATIC_BASELINE_*`, `STATIC_EXTENSIONS`, `STATIC_PREFIXES`, `STATIC_BASELINE_IMAGE_EXTENSIONS`, `HEALTH_LIKE_PATHS` grep 결과를 바탕으로, 실제 module-local constants 이동 가능 범위와 보류 범위, 금지사항, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_protocol_anomaly_constants_move_plan.md](./99_prepare_protocol_anomaly_constants_move_plan.md)
- [99_prepare_ip_behavior_constants_move_plan.md](./99_prepare_ip_behavior_constants_move_plan.md)
- [99_prepare_method_behavior_constants_move_plan.md](./99_prepare_method_behavior_constants_move_plan.md)
- [99_prepare_static_baseline_split_plan.md](./99_prepare_static_baseline_split_plan.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

static baseline constants는 **부분 이동 후보**로 검토한다.

이동 후보:

```text
STATIC_BASELINE_WINDOW_SEC
STATIC_BASELINE_MIN_STATIC_PATHS
STATIC_BASELINE_SAMPLE_REQUEST_LIMIT
```

권장 owner module:

```text
src/prepare/static_baseline.py
```

보류할 constants:

```text
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
```

보류 이유:

```text
- `STATIC_EXTENSIONS` / `STATIC_PREFIXES`는 일반 static row 판별과 다른 baseline/context summary 경계에 걸릴 수 있다.
- `STATIC_BASELINE_IMAGE_EXTENSIONS`는 image/static classification 의미와 연결되어 static file 존재/노출 과해석 방지와 함께 관리해야 한다.
- `HEALTH_LIKE_PATHS`는 health 정상 여부 단정 금지와 연결된다.
- static/crawler/mixed scanner 경계가 아직 남아 있으므로 path/classification constants는 이번 mini-move에서 제외한다.
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
```

## 2. grep 확인 결과

확인 명령:

```bash
grep -n "STATIC_BASELINE_\|STATIC_EXTENSIONS\|STATIC_PREFIXES\|HEALTH_LIKE_PATHS" src/prepare_llm_input.py src/prepare/*.py
```

확인 결과:

```text
src/prepare_llm_input.py:392:STATIC_EXTENSIONS = (
src/prepare_llm_input.py:396:STATIC_PREFIXES = (
src/prepare_llm_input.py:413:STATIC_BASELINE_WINDOW_SEC = 300
src/prepare_llm_input.py:414:STATIC_BASELINE_MIN_STATIC_PATHS = 3
src/prepare_llm_input.py:415:STATIC_BASELINE_SAMPLE_REQUEST_LIMIT = 10
src/prepare_llm_input.py:439:STATIC_BASELINE_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp")
src/prepare_llm_input.py:440:HEALTH_LIKE_PATHS = {
src/prepare_llm_input.py:1350:        min_static_paths=STATIC_BASELINE_MIN_STATIC_PATHS,
src/prepare_llm_input.py:1351:        sample_request_limit=STATIC_BASELINE_SAMPLE_REQUEST_LIMIT,
src/prepare_llm_input.py:1357:    window_sec: int = STATIC_BASELINE_WINDOW_SEC,
src/prepare_llm_input.py:1362:        min_static_paths=STATIC_BASELINE_MIN_STATIC_PATHS,
src/prepare_llm_input.py:1363:        sample_request_limit=STATIC_BASELINE_SAMPLE_REQUEST_LIMIT,
src/prepare_llm_input.py:2280:    return uri_lower.endswith(STATIC_EXTENSIONS) or any(uri_lower.startswith(p) for p in STATIC_PREFIXES)
src/prepare_llm_input.py:2284:    return normalize_text(path).lower() in HEALTH_LIKE_PATHS
src/prepare_llm_input.py:2307:    if normalized_path.endswith(STATIC_BASELINE_IMAGE_EXTENSIONS):
src/prepare_llm_input.py:4165:                "static_baseline_window_sec": STATIC_BASELINE_WINDOW_SEC,
```

해석:

```text
- `STATIC_BASELINE_WINDOW_SEC`, `STATIC_BASELINE_MIN_STATIC_PATHS`, `STATIC_BASELINE_SAMPLE_REQUEST_LIMIT`는 static baseline wrapper/summary 호출과 policy note에 가까운 constants다.
- `STATIC_EXTENSIONS`, `STATIC_PREFIXES`, `STATIC_BASELINE_IMAGE_EXTENSIONS`, `HEALTH_LIKE_PATHS`는 path classification 또는 health-like 판단에 연결되어 있다.
- path/classification constants는 crawler baseline, mixed scanner, health-like path 해석과 경계가 있을 수 있다.
- 따라서 이번 mini-move는 `STATIC_BASELINE_*` 3개로 제한한다.
```

## 3. 현재 구조 추정

현재 `src/prepare_llm_input.py`에는 static baseline wrapper 계열이 남아 있고, 실제 구현 함수는 이미 `src/prepare/static_baseline.py`로 분리되어 있다.

사용 지점 유형:

```text
- static baseline summary builder 기본 window
- static baseline summary builder 호출 인자
- static baseline minimum static path count
- static baseline sample request limit
- policy_notes 메타 값
- 일반 static path 판단
- health-like path 판단
- image/static path classification
```

이동 후에도 아래 값 의미는 유지해야 한다.

```text
static_baseline_window_sec = 300
static_baseline_min_static_paths = 3
static_baseline_sample_request_limit = 10
```

이번 이동에서 아래 constants는 유지한다.

```text
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
```

## 4. 이동 방식

권장 방식:

```text
1. `src/prepare/static_baseline.py`에 이동 후보 constants 3개를 정의한다.
2. `src/prepare_llm_input.py`의 동일 constants 정의 3개를 제거한다.
3. `src/prepare_llm_input.py` import 블록에서 이동한 constants 3개를 함께 import한다.
4. `STATIC_EXTENSIONS`, `STATIC_PREFIXES`, `STATIC_BASELINE_IMAGE_EXTENSIONS`, `HEALTH_LIKE_PATHS`는 `src/prepare_llm_input.py`에 그대로 둔다.
5. 기존 wrapper 기본값과 policy_notes 참조는 동일한 constant 이름을 사용하게 한다.
6. 함수 호출 인자, output key, policy_notes key는 변경하지 않는다.
```

권장 import 예시:

```python
try:
    from src.prepare.static_baseline import (
        STATIC_BASELINE_MIN_STATIC_PATHS,
        STATIC_BASELINE_SAMPLE_REQUEST_LIMIT,
        STATIC_BASELINE_WINDOW_SEC,
        build_static_baseline_reason_hints_for_row as _build_static_baseline_reason_hints_for_row,
        build_static_baseline_summaries as _build_static_baseline_summaries,
        build_static_baseline_summary_contexts as _build_static_baseline_summary_contexts,
        finalize_static_baseline_bucket as _finalize_static_baseline_bucket,
    )
except ImportError:
    from prepare.static_baseline import (
        STATIC_BASELINE_MIN_STATIC_PATHS,
        STATIC_BASELINE_SAMPLE_REQUEST_LIMIT,
        STATIC_BASELINE_WINDOW_SEC,
        build_static_baseline_reason_hints_for_row as _build_static_baseline_reason_hints_for_row,
        build_static_baseline_summaries as _build_static_baseline_summaries,
        build_static_baseline_summary_contexts as _build_static_baseline_summary_contexts,
        finalize_static_baseline_bucket as _finalize_static_baseline_bucket,
    )
```

주의:

```text
- import alias를 새로 만들 필요는 없다.
- 기존 코드에서 `STATIC_BASELINE_*` 이름을 그대로 참조할 수 있게 import한다.
- `STATIC_EXTENSIONS`, `STATIC_PREFIXES`, `STATIC_BASELINE_IMAGE_EXTENSIONS`, `HEALTH_LIKE_PATHS`는 import하지 않는다.
- path/classification constants 정의와 참조는 `src/prepare_llm_input.py`에 유지한다.
```

## 5. 허용 범위

허용되는 변경:

```text
- `src/prepare/static_baseline.py`에 static baseline constants 3개 추가
- `src/prepare_llm_input.py`에서 동일 constants 정의 3개 제거
- `src/prepare_llm_input.py` import 블록에 constants 3개 import 추가
- `STATIC_EXTENSIONS`, `STATIC_PREFIXES`, `STATIC_BASELINE_IMAGE_EXTENSIONS`, `HEALTH_LIKE_PATHS`는 `src/prepare_llm_input.py`에 유지
- py_compile / regression 통과를 위한 import 정렬 수준의 최소 수정
```

허용되지 않는 변경:

```text
- `STATIC_EXTENSIONS` 이동
- `STATIC_PREFIXES` 이동
- `STATIC_BASELINE_IMAGE_EXTENSIONS` 이동
- `HEALTH_LIKE_PATHS` 이동
- static baseline helper/function 추가 이동
- static path classification 로직 변경
- health-like path 판단 로직 변경
- image/static classification 로직 변경
- sample request limit 값 변경
- min static path count 값 변경
- window sec 값 변경
- output key 변경
- policy_notes key 또는 wording 변경
- expected/test fixture 수정
- Stage2 reporter 수정
- candidate/scoring/filtering 변경
- supporting_events 생성/연결 로직 변경
- crawler baseline 로직 변경
- mixed scanner 로직 변경
- constants.py 생성
- 다른 constants group 이동
```

## 6. Apache logs-only 해석 원칙

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
crawler baseline behavior 변화 없음
mixed scanner behavior 변화 없음
```

## 8. 실패 시 롤백 기준

아래 중 하나라도 발생하면 constants 이동 커밋을 수정하거나 롤백한다.

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

## 9. 완료 후 문서 반영

이동 완료 후 아래 문서를 갱신한다.

```text
docs/design/99_prepare_static_baseline_constants_move_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```

완료 기록에 포함할 항목:

```text
- 이동한 constants 3개
- 보류한 path/classification constants
- 기준 커밋
- `src/prepare/static_baseline.py`에 constants 정의 추가
- `src/prepare_llm_input.py`에서 constants import 사용
- helper/function 추가 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- py_compile / prepare regression / stage dry-run regression 결과
```

## 10. 다음 작업

문서 작성 후 다음 작업은 Codex에 static baseline constants 3개 이동을 맡기는 것이다.

권장 커밋 순서:

```text
1. docs: plan static baseline constants move
2. refactor: move static baseline constants
3. docs: record static baseline constants move
```

코드 이동 커밋 후보 메시지:

```text
refactor: move static baseline constants
```
