# 99_prepare_method_behavior_constants_move_plan

- 문서 상태: method behavior constants mini-move plan
- 기준 시점: 2026-05-04
- 목적: `METHOD_BEHAVIOR_*` 및 method family constants grep 결과를 바탕으로, 실제 module-local constants 이동 가능 범위와 보류 범위, 금지사항, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_protocol_anomaly_constants_move_plan.md](./99_prepare_protocol_anomaly_constants_move_plan.md)
- [99_prepare_ip_behavior_constants_move_plan.md](./99_prepare_ip_behavior_constants_move_plan.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

method behavior constants는 **부분 이동 후보**로 검토한다.

이동 후보:

```text
METHOD_BEHAVIOR_WINDOW_SEC
METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT
METHOD_RISKY_FAMILIES
METHOD_BASELINE_FAMILIES
METHOD_DESTRUCTIVE_FAMILIES
```

권장 owner module:

```text
src/prepare/method_summaries.py
```

보류할 constant:

```text
STANDARD_HTTP_METHODS
```

보류 이유:

```text
- `STANDARD_HTTP_METHODS`는 method behavior뿐 아니라 protocol anomaly / malformed method 판단에도 사용된다.
- `src/prepare/method_summaries.py` 단독 owner로 보기 어렵다.
- 이번 mini-move에서 이동하면 `method_summaries.py`와 `protocol_anomalies.py` 사이의 공유 경계를 흐릴 수 있다.
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
grep -n "METHOD_BEHAVIOR_\|METHOD_RISKY_FAMILIES\|METHOD_BASELINE_FAMILIES\|METHOD_DESTRUCTIVE_FAMILIES\|STANDARD_HTTP_METHODS" src/prepare_llm_input.py src/prepare/*.py
```

확인 결과:

```text
src/prepare_llm_input.py:418:METHOD_BEHAVIOR_WINDOW_SEC = 300
src/prepare_llm_input.py:419:METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT = 10
src/prepare_llm_input.py:420:METHOD_RISKY_FAMILIES = ("OPTIONS", "TRACE", "PUT", "DELETE", "PATCH")
src/prepare_llm_input.py:421:METHOD_BASELINE_FAMILIES = ("GET", "HEAD")
src/prepare_llm_input.py:422:METHOD_DESTRUCTIVE_FAMILIES = {"PUT", "DELETE", "PATCH"}
src/prepare_llm_input.py:423:STANDARD_HTTP_METHODS = {
src/prepare_llm_input.py:1647:    if normalized in METHOD_RISKY_FAMILIES:
src/prepare_llm_input.py:1649:    if normalized in METHOD_BASELINE_FAMILIES:
src/prepare_llm_input.py:1651:    if normalized not in STANDARD_HTTP_METHODS:
src/prepare_llm_input.py:1716:    if not method or method == "-" or method not in STANDARD_HTTP_METHODS or not re.fullmatch(r"[A-Z!#$%&'*+.^_`|~-]{1,32}", method):
src/prepare_llm_input.py:1757:        standard_http_methods=STANDARD_HTTP_METHODS,
src/prepare_llm_input.py:1769:        method_destructive_families=METHOD_DESTRUCTIVE_FAMILIES,
src/prepare_llm_input.py:1770:        method_risky_families=METHOD_RISKY_FAMILIES,
src/prepare_llm_input.py:1771:        method_baseline_families=METHOD_BASELINE_FAMILIES,
src/prepare_llm_input.py:1772:        standard_http_methods=STANDARD_HTTP_METHODS,
src/prepare_llm_input.py:1778:    window_sec: int = METHOD_BEHAVIOR_WINDOW_SEC,
src/prepare_llm_input.py:1783:        sample_request_limit=METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
src/prepare_llm_input.py:1784:        method_risky_families=METHOD_RISKY_FAMILIES,
src/prepare_llm_input.py:1785:        method_baseline_families=METHOD_BASELINE_FAMILIES,
src/prepare_llm_input.py:1786:        method_destructive_families=METHOD_DESTRUCTIVE_FAMILIES,
src/prepare_llm_input.py:1787:        standard_http_methods=STANDARD_HTTP_METHODS,
src/prepare_llm_input.py:1800:        standard_http_methods=STANDARD_HTTP_METHODS,
src/prepare_llm_input.py:1813:        standard_http_methods=STANDARD_HTTP_METHODS,
src/prepare_llm_input.py:4167:                "method_behavior_window_sec": METHOD_BEHAVIOR_WINDOW_SEC,
```

해석:

```text
- method behavior 전용 window/sample/family constants는 `method_summaries.py` owner 후보로 볼 수 있다.
- `STANDARD_HTTP_METHODS`는 method behavior wrapper뿐 아니라 protocol anomaly 성격의 malformed method 판단에도 사용된다.
- 따라서 이번 mini-move는 `STANDARD_HTTP_METHODS`를 제외한 partial move로 제한한다.
```

## 3. 현재 구조 추정

현재 `src/prepare_llm_input.py`에는 method behavior wrapper 계열이 남아 있고, 실제 구현 함수는 이미 `src/prepare/method_summaries.py`로 분리되어 있다.

사용 지점 유형:

```text
- method family classification
- method behavior summary builder 기본 window
- method behavior summary builder 호출 인자
- policy_notes 메타 값
- protocol anomaly / malformed method 판단에서 standard method set 사용
```

이동 후에도 아래 값 의미는 유지해야 한다.

```text
method_behavior_window_sec = 300
method_behavior_sample_request_limit = 10
method_risky_families = ("OPTIONS", "TRACE", "PUT", "DELETE", "PATCH")
method_baseline_families = ("GET", "HEAD")
method_destructive_families = {"PUT", "DELETE", "PATCH"}
```

`STANDARD_HTTP_METHODS`는 이번 이동에서 유지한다.

## 4. 이동 방식

권장 방식:

```text
1. `src/prepare/method_summaries.py`에 이동 후보 constants 5개를 정의한다.
2. `src/prepare_llm_input.py`의 동일 constants 정의 5개를 제거한다.
3. `src/prepare_llm_input.py` import 블록에서 이동한 constants 5개를 함께 import한다.
4. `STANDARD_HTTP_METHODS`는 `src/prepare_llm_input.py`에 그대로 둔다.
5. 기존 wrapper 기본값과 policy_notes 참조는 동일한 constant 이름을 사용하게 한다.
6. 함수 호출 인자, output key, policy_notes key는 변경하지 않는다.
```

권장 import 예시:

```python
try:
    from src.prepare.method_summaries import (
        METHOD_BASELINE_FAMILIES,
        METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        METHOD_BEHAVIOR_WINDOW_SEC,
        METHOD_DESTRUCTIVE_FAMILIES,
        METHOD_RISKY_FAMILIES,
        build_method_behavior_reason_hints_for_row as _build_method_behavior_reason_hints_for_row,
        build_method_behavior_summaries as _build_method_behavior_summaries,
        build_method_behavior_summary_contexts as _build_method_behavior_summary_contexts,
    )
except ImportError:
    from prepare.method_summaries import (
        METHOD_BASELINE_FAMILIES,
        METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        METHOD_BEHAVIOR_WINDOW_SEC,
        METHOD_DESTRUCTIVE_FAMILIES,
        METHOD_RISKY_FAMILIES,
        build_method_behavior_reason_hints_for_row as _build_method_behavior_reason_hints_for_row,
        build_method_behavior_summaries as _build_method_behavior_summaries,
        build_method_behavior_summary_contexts as _build_method_behavior_summary_contexts,
    )
```

주의:

```text
- import alias를 새로 만들 필요는 없다.
- 기존 코드에서 `METHOD_*` 이름을 그대로 참조할 수 있게 import한다.
- `STANDARD_HTTP_METHODS`는 import하지 않는다.
- `STANDARD_HTTP_METHODS` 정의와 참조는 `src/prepare_llm_input.py`에 유지한다.
```

## 5. 허용 범위

허용되는 변경:

```text
- `src/prepare/method_summaries.py`에 method behavior constants 5개 추가
- `src/prepare_llm_input.py`에서 동일 constants 정의 5개 제거
- `src/prepare_llm_input.py` import 블록에 constants 5개 import 추가
- `STANDARD_HTTP_METHODS`는 `src/prepare_llm_input.py`에 유지
- py_compile / regression 통과를 위한 import 정렬 수준의 최소 수정
```

허용되지 않는 변경:

```text
- `STANDARD_HTTP_METHODS` 이동
- method behavior helper/function 추가 이동
- method classification 로직 변경
- sample request limit 값 변경
- window sec 값 변경
- risky/baseline/destructive family 값 변경
- output key 변경
- policy_notes key 또는 wording 변경
- expected/test fixture 수정
- Stage2 reporter 수정
- candidate/scoring/filtering 변경
- supporting_events 생성/연결 로직 변경
- protocol anomaly 로직 변경
- constants.py 생성
- 다른 constants group 이동
```

## 6. Apache logs-only 해석 원칙

이번 constants 이동 이후에도 아래 해석 제한은 유지한다.

```text
- PUT 업로드 성공을 단정하지 않는다.
- DELETE 삭제 성공을 단정하지 않는다.
- TRACE/XST 성공을 단정하지 않는다.
- OPTIONS/CORS 취약점 성공을 단정하지 않는다.
- method 관찰은 Apache access log 표면 신호로만 해석한다.
- method family classification은 context이지 exploit success 증거가 아니다.
```

금지 표현:

```text
- PUT upload succeeded
- DELETE removed data
- TRACE/XST succeeded
- CORS vulnerability confirmed
- destructive method caused state change
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
protocol anomaly behavior 변화 없음
```

## 8. 실패 시 롤백 기준

아래 중 하나라도 발생하면 constants 이동 커밋을 수정하거나 롤백한다.

```text
- import cycle 발생
- py_compile fail
- prepare regression fail
- stage dry-run regression fail
- method_behavior_* policy_notes 값 변화
- method behavior summary count 변화
- protocol anomaly summary 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- method family 값 변경
- PUT/DELETE/TRACE/OPTIONS 성공 단정 문구 발생
```

## 9. 완료 후 문서 반영

이동 완료 후 아래 문서를 갱신한다.

```text
docs/design/99_prepare_method_behavior_constants_move_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```

완료 기록에 포함할 항목:

```text
- 이동한 constants 5개
- 보류한 `STANDARD_HTTP_METHODS`
- 기준 커밋
- `src/prepare/method_summaries.py`에 constants 정의 추가
- `src/prepare_llm_input.py`에서 constants import 사용
- helper/function 추가 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- py_compile / prepare regression / stage dry-run regression 결과
```

## 10. 다음 작업

문서 작성 후 다음 작업은 Codex에 method behavior constants 5개 이동을 맡기는 것이다.

권장 커밋 순서:

```text
1. docs: plan method behavior constants move
2. refactor: move method behavior constants
3. docs: record method behavior constants move
```

코드 이동 커밋 후보 메시지:

```text
refactor: move method behavior constants
```
