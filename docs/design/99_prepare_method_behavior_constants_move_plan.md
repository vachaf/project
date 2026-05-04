# 99_prepare_method_behavior_constants_move_plan

- 문서 상태: method behavior constants mini-move 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `6bfa68e599501b27154181b8048f0362ce059e6b`
- 목적: method behavior constants 5개를 `src/prepare/method_summaries.py`로 이동하고, `STANDARD_HTTP_METHODS`를 보류한 완료 범위와 검증 결과를 기록한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_protocol_anomaly_constants_move_plan.md](./99_prepare_protocol_anomaly_constants_move_plan.md)
- [99_prepare_ip_behavior_constants_move_plan.md](./99_prepare_ip_behavior_constants_move_plan.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

method behavior constants의 부분 이동은 완료했다.

이동한 constants:

```text
METHOD_BEHAVIOR_WINDOW_SEC = 300
METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT = 10
METHOD_RISKY_FAMILIES = ("OPTIONS", "TRACE", "PUT", "DELETE", "PATCH")
METHOD_BASELINE_FAMILIES = ("GET", "HEAD")
METHOD_DESTRUCTIVE_FAMILIES = {"PUT", "DELETE", "PATCH"}
```

owner module:

```text
src/prepare/method_summaries.py
```

보류한 constant:

```text
STANDARD_HTTP_METHODS
```

보류 위치:

```text
src/prepare_llm_input.py
```

수정 파일:

```text
src/prepare/method_summaries.py
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
- protocol anomaly 로직 변경 없음
- constants.py 생성 없음
- 다른 constants group 이동 없음
```

## 2. 적용 내용

적용한 변경:

```text
- `src/prepare/method_summaries.py`에 method behavior constants 5개 추가
- `src/prepare_llm_input.py`의 동일 constants 정의 5개 제거
- `src/prepare_llm_input.py`의 `method_summaries` try/except import 블록 양쪽에 constants 5개 import 추가
- 내부 참조 이름 `METHOD_*`는 그대로 유지
- `STANDARD_HTTP_METHODS`는 `src/prepare_llm_input.py`에 그대로 유지
```

유지한 값:

```text
method_behavior_window_sec = 300
method_behavior_sample_request_limit = 10
method_risky_families = ("OPTIONS", "TRACE", "PUT", "DELETE", "PATCH")
method_baseline_families = ("GET", "HEAD")
method_destructive_families = {"PUT", "DELETE", "PATCH"}
```

`STANDARD_HTTP_METHODS` 보류 이유:

```text
- method behavior뿐 아니라 protocol anomaly / malformed method 판단에도 사용된다.
- `src/prepare/method_summaries.py` 단독 owner로 보기 어렵다.
- method_summaries.py와 protocol_anomalies.py 사이의 공유 경계를 흐리지 않기 위해 이번 mini-move에서 제외했다.
```

## 3. 이동하지 않은 것

이번 커밋에서 아래 항목은 이동하거나 수정하지 않았다.

```text
- STANDARD_HTTP_METHODS
- build_method_behavior_reason_hints_for_row
- build_method_behavior_summaries
- build_method_behavior_summary_contexts
- method classification 로직
- protocol anomaly 로직
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

## 5. 검증 결과

기준 커밋 `6bfa68e599501b27154181b8048f0362ce059e6b`에서 아래 검증을 통과했다.

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
- method_behavior_* policy_notes 값 변화
- method behavior summary count 변화
- protocol anomaly summary 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- method family 값 변경
- STANDARD_HTTP_METHODS 이동 또는 의미 변경
- PUT/DELETE/TRACE/OPTIONS 성공 단정 문구 발생
```

## 7. 다음 작업

method behavior constants 부분 이동은 완료했다.

`99_prepare_constants_mini_move_candidate_review.md` 기준 다음 후보는 static baseline constants다. 다만 static constants는 crawler baseline, mixed scanner, health-like path 해석과 경계가 있을 수 있으므로, 먼저 grep 확인과 move plan 작성 여부를 판단한다.

권장 확인 명령:

```bash
grep -n "STATIC_BASELINE_\|STATIC_EXTENSIONS\|STATIC_PREFIXES\|HEALTH_LIKE_PATHS" src/prepare_llm_input.py src/prepare/*.py
```

다음 후보 문서:

```text
docs/design/99_prepare_static_baseline_constants_move_plan.md
```

문서 전용 커밋 후보:

```text
docs: record method behavior constants move
```
