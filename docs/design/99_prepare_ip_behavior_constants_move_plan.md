# 99_prepare_ip_behavior_constants_move_plan

- 문서 상태: IP behavior constants mini-move 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `66d46f419b88b01e69144be93edd59b60afd9dc0`
- 목적: `IP_BEHAVIOR_*` constants 3개를 `src/prepare/ip_behavior.py`로 이동한 완료 범위, 유지한 계약, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_protocol_anomaly_constants_move_plan.md](./99_prepare_protocol_anomaly_constants_move_plan.md)
- [99_prepare_ip_behavior_aggregates_split_plan.md](./99_prepare_ip_behavior_aggregates_split_plan.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

`IP_BEHAVIOR_*` constants 3개의 module-local 이동은 완료했다.

이동한 constants:

```text
IP_BEHAVIOR_WINDOW_SEC = 300
IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT = 10
IP_BEHAVIOR_SENSITIVE_PATH_LIMIT = 10
```

owner module:

```text
src/prepare/ip_behavior.py
```

수정 파일:

```text
src/prepare/ip_behavior.py
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

`IP_BEHAVIOR_SENSITIVE_PATH_LIMIT`는 sensitive path/probing 계열과 의미 경계가 있을 수 있으므로 값과 의미를 그대로 유지했다.

## 2. 적용 내용

적용한 변경:

```text
- `src/prepare/ip_behavior.py`에 `IP_BEHAVIOR_*` constants 3개 추가
- `src/prepare_llm_input.py`의 동일 constants 정의 3개 제거
- `src/prepare_llm_input.py`의 `ip_behavior` try/except import 블록 양쪽에 constants 3개 import 추가
- 내부 참조 이름 `IP_BEHAVIOR_*`는 그대로 유지
```

유지한 값:

```text
ip_behavior_window_sec = 300
ip_behavior_sample_request_limit = 10
ip_behavior_sensitive_path_limit = 10
```

유지한 사용 지점 유형:

```text
- IP behavior aggregate sample request limit
- IP behavior aggregate sensitive path sample limit
- build_ip_behavior_aggregates 기본 window
- policy_notes 메타 값
```

## 3. 이동하지 않은 것

이번 커밋에서 아래 항목은 이동하거나 수정하지 않았다.

```text
- is_sensitive_ip_behavior_path
- finalize_ip_behavior_bucket
- build_ip_behavior_aggregates
- IP behavior aggregate 로직
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
- 특정 IP를 attacker identity로 단정하지 않는다.
- source IP만으로 공격 의도, 공격 성공, 침해 성공을 단정하지 않는다.
- IP 단위 집계는 관찰된 요청 묶음이지 신원 식별 결과가 아니다.
- lab/source IP를 공격 근거로 사용하지 않는다.
- sensitive path sample은 민감 경로 관찰 context이지 파일 노출 또는 앱 존재 증거가 아니다.
```

금지 표현:

```text
- attacker IP confirmed
- compromised host confirmed
- account takeover source confirmed
- lab IP proves attack
- sensitive path hit proves file exposure
```

## 5. 검증 결과

기준 커밋 `66d46f419b88b01e69144be93edd59b60afd9dc0`에서 아래 검증을 통과했다.

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
- ip_behavior_* policy_notes 값 변화
- ip_behavior_aggregates count 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- sensitive path limit 의미 변경
- IP identity / attacker identity 단정 문구 발생
- sensitive path sample을 노출/성공으로 단정하는 문구 발생
```

## 7. 다음 작업

`IP_BEHAVIOR_*` constants 이동은 완료했다.

`99_prepare_constants_mini_move_candidate_review.md` 기준 다음 후보는 method behavior constants다. 다만 `STANDARD_HTTP_METHODS`는 protocol anomaly와 공유될 수 있으므로, 먼저 grep 확인과 move plan 작성 여부를 판단한다.

권장 확인 명령:

```bash
grep -n "METHOD_BEHAVIOR_\|METHOD_RISKY_FAMILIES\|METHOD_BASELINE_FAMILIES\|METHOD_DESTRUCTIVE_FAMILIES\|STANDARD_HTTP_METHODS" src/prepare_llm_input.py src/prepare/*.py
```

다음 후보 문서:

```text
docs/design/99_prepare_method_behavior_constants_move_plan.md
```

문서 전용 커밋 후보:

```text
docs: record ip behavior constants move
```
