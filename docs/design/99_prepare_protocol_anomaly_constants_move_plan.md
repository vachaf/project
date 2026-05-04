# 99_prepare_protocol_anomaly_constants_move_plan

- 문서 상태: protocol anomaly constants mini-move 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `b81db3f449b06fccd7815dae30c7c4db6f30aa57`
- 목적: `PROTOCOL_ANOMALY_*` constants 3개를 `src/prepare/protocol_anomalies.py`로 이동한 완료 범위, 유지한 계약, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

`PROTOCOL_ANOMALY_*` constants 3개의 module-local 이동은 완료했다.

이동한 constants:

```text
PROTOCOL_ANOMALY_WINDOW_SEC = 300
PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT = 10
PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN = 512
```

owner module:

```text
src/prepare/protocol_anomalies.py
```

수정 파일:

```text
src/prepare/protocol_anomalies.py
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
- constants.py 생성 없음
- 다른 constants group 이동 없음
```

## 2. 적용 내용

적용한 변경:

```text
- `src/prepare/protocol_anomalies.py`에 `PROTOCOL_ANOMALY_*` constants 3개 추가
- `src/prepare_llm_input.py`의 동일 constants 정의 3개 제거
- `src/prepare_llm_input.py`의 `protocol_anomalies` try/except import 블록 양쪽에 constants 3개 import 추가
- 내부 참조 이름 `PROTOCOL_ANOMALY_*`는 그대로 유지
```

유지한 값:

```text
protocol_anomaly_window_sec = 300
protocol_anomaly_sample_request_limit = 10
protocol_anomaly_long_path_min_len = 512
```

유지한 사용 지점 유형:

```text
- long path 판단 기준
- protocol anomaly row reason hint 호출 인자
- protocol anomaly summary context/finalize 호출 인자
- build_protocol_anomaly_summaries 기본 window
- policy_notes 메타 값
```

## 3. 이동하지 않은 것

이번 커밋에서 아래 항목은 이동하거나 수정하지 않았다.

```text
- build_protocol_anomaly_reason_hints_for_row
- build_protocol_anomaly_summaries
- build_protocol_anomaly_summary_contexts
- finalize_protocol_anomaly_bucket
- protocol anomaly detection 로직
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

## 5. 검증 결과

기준 커밋 `b81db3f449b06fccd7815dae30c7c4db6f30aa57`에서 아래 검증을 통과했다.

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
- protocol_anomaly_* policy_notes 값 변화
- protocol anomaly summary count 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- long path threshold 의미 변경
- protocol bypass / malformed exploit / server compromise 성공 단정 문구 발생
```

## 7. 다음 작업

`PROTOCOL_ANOMALY_*` constants 이동은 완료했다.

`99_prepare_constants_mini_move_candidate_review.md` 기준 다음 후보는 `IP_BEHAVIOR_*` constants다. 다만 `IP_BEHAVIOR_SENSITIVE_PATH_LIMIT`는 sensitive path/probing 계열과 의미 경계가 겹칠 수 있으므로, 먼저 grep 확인과 move plan 문서 작성 여부를 판단한다.

권장 확인 명령:

```bash
grep -n "IP_BEHAVIOR_" src/prepare_llm_input.py src/prepare/*.py
```

다음 후보 문서:

```text
docs/design/99_prepare_ip_behavior_constants_move_plan.md
```

문서 전용 커밋 후보:

```text
docs: record protocol anomaly constants move
```
