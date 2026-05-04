# 99_prepare_ip_behavior_aggregates_split_plan

- 문서 상태: `ip_behavior_aggregates` split 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `30ac7d6e3fec31c6777dc124f295780b52bdb321`
- 목적: `ip_behavior_aggregates` 계열의 코드 분리 완료 범위, 유지한 계약, 보류한 영역, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_candidate_review.md](./99_prepare_module_split_round2_candidate_review.md)
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)

## 1. 완료 결론

`ip_behavior_aggregates` 계열의 코드 분리는 완료했다.

신규 모듈:

```text
src/prepare/ip_behavior.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이번 작업은 mechanical refactor로 제한했다.

```text
- `src/prepare_llm_input.py`에는 기존 공개 함수명 wrapper 유지
- constants 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- output key 의미 변경 없음
- policy wording 변경 없음
```

IP behavior aggregate는 계속 context-only 성격의 집계다. IP 기반 판단 의미를 바꾸거나 IP를 공격자 신원으로 해석하는 변경은 하지 않았다.

## 2. 이동 완료 함수

아래 함수 3개를 `src/prepare/ip_behavior.py`로 이동했다.

```text
is_sensitive_ip_behavior_path
finalize_ip_behavior_bucket
build_ip_behavior_aggregates
```

`src/prepare_llm_input.py`에는 기존 함수명을 유지하는 wrapper를 남겼다.

유지한 import 패턴:

```text
try:
    from src.prepare.ip_behavior import ... as _...
except ImportError:
    from prepare.ip_behavior import ... as _...
```

이 분리는 IP behavior aggregate builder와 전용 helper만 좁게 옮긴 것이다. main payload 구성, counts 계산, policy notes, Stage2 reporter는 바꾸지 않았다.

## 3. 이동하지 않은 constants

아래 constants는 이동하지 않았다.

```text
IP_BEHAVIOR_WINDOW_SEC
IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT
IP_BEHAVIOR_SENSITIVE_PATH_LIMIT
```

유지 이유:

```text
- constants 이동까지 함께 하면 regression 실패 시 원인 추적이 어려워진다.
- IP behavior sensitive path limit은 sensitive path/probing 계열과 의미 경계가 겹칠 수 있다.
- constants.py 대량 분리는 별도 ownership map 이후에 검토한다.
```

## 4. 유지한 output 계약

아래 output/policy/count 위치는 유지했다.

```text
ip_behavior_aggregates
counts.ip_behavior_aggregates
policy_notes.ip_behavior_aggregates_are_context_only
policy_notes.ip_behavior_window_sec
```

출력 불변조건:

```text
- output key 이름 변경 없음
- count 의미 변경 없음
- sample limit 의미 변경 없음
- candidate_rows 의미 변경 없음
- filtered_out 의미 변경 없음
- supporting_events 의미 변경 없음
- IP behavior aggregate를 incident로 승격하지 않음
- IP를 attacker identity로 단정하는 필드/문구 추가 없음
```

## 5. Apache logs-only 해석 원칙

이번 분리 이후에도 아래 제한을 유지한다.

```text
- 특정 IP를 attacker identity로 단정하지 않는다.
- 특정 IP를 실험환경 공격 주체로 일반화하지 않는다.
- source IP만으로 공격 의도, 공격 성공, 침해 성공을 단정하지 않는다.
- 요청량이 많다는 이유만으로 compromise를 단정하지 않는다.
- 경로 다양성이 높다는 이유만으로 scanner 성공을 단정하지 않는다.
- lab/source IP를 공격 근거로 사용하지 않는다.
- IP 단위 집계는 관찰된 요청 묶음이지 신원 식별 결과가 아니다.
```

허용되는 표현:

```text
- observed requests grouped by source IP
- IP-level request concentration
- source-IP-scoped context summary
- repeated request context
- scanner-like behavior context, if supported by request patterns
```

금지 표현:

```text
- attacker IP 확정
- compromised host 확정
- 동일 공격자 확정
- botnet node 확정
- account takeover source 확정
- lab IP이므로 공격 확정
- source IP가 곧 실제 사용자/공격자 신원이라는 단정
```

## 6. 검증 결과

기준 커밋 `30ac7d6e3fec31c6777dc124f295780b52bdb321`에서 아래 검증을 통과했다.

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

## 7. 롤백 기준

향후 관련 추가 분리에서 아래 중 하나라도 발생하면 해당 분리 커밋을 수정하거나 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- import cycle 발생
- ip_behavior_aggregates 누락
- pipeline_counts 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- sample request limit 의미 변경
- sensitive path count 의미 변경
- IP를 공격자 신원으로 단정하는 문구 발생
- 특정 IP, lab-* UA, response size, product/route에 과적합하는 문구 발생
```

## 8. 다음 작업

`ip_behavior_aggregates` 분리는 완료했다.

round2 후보 비교 기준상 다음 후보는 `probing_sequence_summaries`다. 다만 바로 코드 분리하지 않고 split plan 문서를 먼저 작성한다.

권장 다음 문서:

```text
docs/design/99_prepare_probing_sequence_split_plan.md
```

다음 후보에서 특히 주의할 점:

```text
- PROBING_SEQUENCE_* constants는 sensitive path probe와 경계가 겹칠 수 있음
- 여러 경로 순회만으로 침해/노출/성공을 단정하지 않음
- scanner-like sequence를 candidate로 과승격하지 않음
- constants 이동 없이 wrapper 전달 방식을 우선 검토
```

문서 전용 커밋 후보:

```text
docs: record ip behavior aggregate split
```
