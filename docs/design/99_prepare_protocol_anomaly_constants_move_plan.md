# 99_prepare_protocol_anomaly_constants_move_plan

- 문서 상태: protocol anomaly constants mini-move plan
- 기준 시점: 2026-05-04
- 목적: `99_prepare_constants_mini_move_candidate_review.md`에서 다음 후보로 잡은 `PROTOCOL_ANOMALY_*` constants 3개를 실제로 module-local constants로 이동할 수 있는지 범위, 금지사항, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

`PROTOCOL_ANOMALY_*` constants는 소규모 이동 후보로 적합하다.

이동 후보:

```text
PROTOCOL_ANOMALY_WINDOW_SEC
PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT
PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN
```

권장 owner module:

```text
src/prepare/protocol_anomalies.py
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
grep -n "PROTOCOL_ANOMALY_" src/prepare_llm_input.py src/prepare/*.py
```

확인 결과:

```text
src/prepare_llm_input.py:411:PROTOCOL_ANOMALY_WINDOW_SEC = 300
src/prepare_llm_input.py:412:PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT = 10
src/prepare_llm_input.py:413:PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN = 512
src/prepare_llm_input.py:1736:    if len(request_path) >= PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN:
src/prepare_llm_input.py:1750:        long_path_min_len=PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
src/prepare_llm_input.py:1792:        sample_request_limit=PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT,
src/prepare_llm_input.py:1793:        long_path_min_len=PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
src/prepare_llm_input.py:1800:    window_sec: int = PROTOCOL_ANOMALY_WINDOW_SEC,
src/prepare_llm_input.py:1805:        sample_request_limit=PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT,
src/prepare_llm_input.py:1806:        long_path_min_len=PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
src/prepare_llm_input.py:4162:                "protocol_anomaly_window_sec": PROTOCOL_ANOMALY_WINDOW_SEC,
src/prepare_llm_input.py:4163:                "protocol_anomaly_long_path_min_len": PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
```

해석:

```text
- `PROTOCOL_ANOMALY_*` 참조는 현재 `src/prepare_llm_input.py` 안에만 있다.
- `src/prepare/protocol_anomalies.py` 또는 다른 `src/prepare/*.py`에서 직접 참조하는 결과는 보이지 않는다.
- 따라서 module-local constants 이동은 비교적 단순할 가능성이 높다.
```

## 3. 현재 구조 추정

현재 `src/prepare_llm_input.py`에는 protocol anomaly wrapper 계열이 남아 있고, 실제 구현 함수는 이미 `src/prepare/protocol_anomalies.py`로 분리되어 있다.

현재 constants는 wrapper 기본값과 wrapper 호출 인자로 사용된다.

사용 지점 유형:

```text
- long path 판단 기준
- protocol anomaly row reason hint 호출 인자
- protocol anomaly summary context/finalize 호출 인자
- build_protocol_anomaly_summaries 기본 window
- policy_notes 메타 값
```

따라서 이동 후에도 아래 값 의미는 유지해야 한다.

```text
protocol_anomaly_window_sec = 300
protocol_anomaly_sample_request_limit = 10
protocol_anomaly_long_path_min_len = 512
```

## 4. 이동 방식

권장 방식:

```text
1. `src/prepare/protocol_anomalies.py`에 constants 3개를 정의한다.
2. `src/prepare_llm_input.py`의 constants 정의 3개를 제거한다.
3. `src/prepare_llm_input.py` import 블록에서 constants도 함께 import한다.
4. 기존 wrapper 기본값과 policy_notes 참조는 동일한 constant 이름을 사용하게 한다.
5. 함수 호출 인자, output key, policy_notes key는 변경하지 않는다.
```

권장 import 예시:

```python
try:
    from src.prepare.protocol_anomalies import (
        PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
        PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT,
        PROTOCOL_ANOMALY_WINDOW_SEC,
        build_protocol_anomaly_reason_hints_for_row as _build_protocol_anomaly_reason_hints_for_row,
        build_protocol_anomaly_summaries as _build_protocol_anomaly_summaries,
        build_protocol_anomaly_summary_contexts as _build_protocol_anomaly_summary_contexts,
        finalize_protocol_anomaly_bucket as _finalize_protocol_anomaly_bucket,
    )
except ImportError:
    from prepare.protocol_anomalies import (
        PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN,
        PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT,
        PROTOCOL_ANOMALY_WINDOW_SEC,
        build_protocol_anomaly_reason_hints_for_row as _build_protocol_anomaly_reason_hints_for_row,
        build_protocol_anomaly_summaries as _build_protocol_anomaly_summaries,
        build_protocol_anomaly_summary_contexts as _build_protocol_anomaly_summary_contexts,
        finalize_protocol_anomaly_bucket as _finalize_protocol_anomaly_bucket,
    )
```

주의:

```text
- import alias를 새로 만들 필요는 없다.
- 기존 코드에서 `PROTOCOL_ANOMALY_*` 이름을 그대로 참조할 수 있게 import한다.
- wrapper 기본 인자와 policy_notes 값이 같은 constant 이름을 쓰게 유지한다.
```

## 5. 허용 범위

허용되는 변경:

```text
- `src/prepare/protocol_anomalies.py`에 `PROTOCOL_ANOMALY_*` constants 3개 추가
- `src/prepare_llm_input.py`에서 동일 constants 정의 제거
- `src/prepare_llm_input.py` import 블록에 constants import 추가
- py_compile / regression 통과를 위한 import 정렬 수준의 최소 수정
```

허용되지 않는 변경:

```text
- protocol anomaly helper/function 추가 이동
- protocol anomaly detection 로직 변경
- long path threshold 값 변경
- sample request limit 값 변경
- window sec 값 변경
- output key 변경
- policy_notes key 또는 wording 변경
- expected/test fixture 수정
- Stage2 reporter 수정
- candidate/scoring/filtering 변경
- supporting_events 생성/연결 로직 변경
- constants.py 생성
- 다른 constants group 이동
```

## 6. Apache logs-only 해석 원칙

이번 constants 이동 이후에도 아래 해석 제한은 유지한다.

```text
- protocol bypass 성공을 단정하지 않는다.
- malformed request exploit success를 단정하지 않는다.
- 서버 침해 성공을 단정하지 않는다.
- status_code나 error log 존재만으로 exploit 성공을 판단하지 않는다.
- long path 또는 protocol anomaly 관찰은 context이지 성공 증거가 아니다.
```

금지 표현:

```text
- protocol bypass succeeded
- malformed request exploit succeeded
- server compromise confirmed
- exploit success confirmed by status code
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
```

## 8. 실패 시 롤백 기준

아래 중 하나라도 발생하면 constants 이동 커밋을 수정하거나 롤백한다.

```text
- import cycle 발생
- py_compile fail
- prepare regression fail
- stage dry-run regression fail
- protocol_anomaly_* policy_notes 값 변화
- protocol anomaly summary count 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- long path threshold 의미 변경
- protocol bypass / malformed exploit / server compromise 성공 단정 문구 발생
```

## 9. 완료 후 문서 반영

이동 완료 후 아래 문서를 갱신한다.

```text
docs/design/99_prepare_protocol_anomaly_constants_move_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```

완료 기록에 포함할 항목:

```text
- 이동한 constants 3개
- 기준 커밋
- `src/prepare/protocol_anomalies.py`에 constants 정의 추가
- `src/prepare_llm_input.py`에서 constants import 사용
- helper/function 추가 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- py_compile / prepare regression / stage dry-run regression 결과
```

## 10. 다음 작업

문서 작성 후 다음 작업은 Codex에 constants 3개 이동을 맡기는 것이다.

권장 커밋 순서:

```text
1. docs: plan protocol anomaly constants move
2. refactor: move protocol anomaly constants
3. docs: record protocol anomaly constants move
```

코드 이동 커밋 후보 메시지:

```text
refactor: move protocol anomaly constants
```
