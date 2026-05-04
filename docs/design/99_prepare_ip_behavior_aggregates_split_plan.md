# 99_prepare_ip_behavior_aggregates_split_plan

- 문서 상태: `ip_behavior_aggregates` split plan
- 기준 시점: 2026-05-04
- 목적: round2 후보 비교 결과에 따라 `ip_behavior_aggregates` 계열을 다음 코드 분리 대상으로 삼을 수 있는지, 분리 범위와 금지 범위, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_candidate_review.md](./99_prepare_module_split_round2_candidate_review.md)
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)

## 1. 결론

`ip_behavior_aggregates` 계열은 round2의 다음 코드 분리 후보로 진행 가능하다.

권장 신규 모듈:

```text
src/prepare/ip_behavior.py
```

분리 방식:

```text
- mechanical refactor only
- `src/prepare_llm_input.py`에는 기존 공개 함수명 wrapper 유지
- constants 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- output key 의미 변경 없음
```

이번 분리는 IP 단위 집계/요약 builder만 좁게 이동한다. IP 기반 판단 의미를 바꾸거나 IP를 공격자 신원으로 해석하는 변경은 하지 않는다.

## 2. 실제 코드 확인 대상

코드 작업 전 아래 grep으로 실제 함수명과 호출 위치를 확정한다.

```bash
grep -n "build_ip_behavior_aggregates\|ip_behavior_aggregates\|IP_BEHAVIOR" src/prepare_llm_input.py
```

확인할 항목:

```text
- builder 함수명
- helper 함수명
- 호출 위치
- main payload에 `ip_behavior_aggregates`를 넣는 위치
- `pipeline_counts`에 IP behavior count를 넣는지 여부
- Stage2 input / report에서 해당 key를 소비하는지 여부
- candidates, filtered_out, supporting_events와 직접 연결되는지 여부
- IP behavior가 sensitive path sample limit과 연결되는지 여부
```

현재 예상 후보:

```text
build_ip_behavior_aggregates
ip_behavior_aggregates
IP_BEHAVIOR_WINDOW_SEC
IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT
IP_BEHAVIOR_SENSITIVE_PATH_LIMIT
```

실제 코드에서 이름이 다르면 코드 이름을 우선한다. 이름 변경 refactor는 이번 분리와 섞지 않는다.

## 3. 입력 계약

`ip_behavior_aggregates` builder가 소비할 수 있는 입력은 Apache log에서 이미 정규화된 표면 정보로 제한한다.

허용 입력 범주:

```text
- normalized rows 또는 source rows
- src_ip
- peer_ip, if already present as log metadata
- method
- uri / raw_request_target
- query_string
- status_code
- response_body_bytes
- resp_content_type
- log_time
- request_id
- error_link_id
- user_agent
- referer
- source_table
- already prepared candidate/supporting context, if currently used
```

사용하면 안 되는 입력:

```text
- raw POST body 내용
- response body 원문
- DB query 결과
- 계정 상태
- 세션 상태
- filesystem 존재 여부
- browser execution 결과
- external threat intelligence identity
```

## 4. 출력 계약

유지해야 할 output key 후보:

```text
ip_behavior_aggregates
pipeline_counts.ip_behavior_aggregate_count, if currently present
```

출력에 포함될 수 있는 정보:

```text
- src_ip 또는 source IP group key
- request_count
- distinct_path_count
- method_counts
- status_counts
- sample_request_ids
- sample_paths
- sensitive_path_sample 또는 sensitive_path_count, if currently present
- time window metadata, if currently present
- context_role, if currently present
- interpretation_limit, if currently present
```

출력 불변조건:

```text
- output key 이름 변경 금지
- count 의미 변경 금지
- sample limit 의미 변경 금지
- candidate_rows 의미 변경 금지
- supporting_events 의미 변경 금지
- IP behavior aggregate를 incident로 승격 금지
- IP를 attacker identity로 단정하는 필드/문구 추가 금지
```

## 5. Apache logs-only 해석 원칙

IP behavior aggregate는 과해석 위험이 크다. 아래 제한을 반드시 유지한다.

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

## 6. constants 사용 방침

관련 constants 후보:

```text
IP_BEHAVIOR_WINDOW_SEC
IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT
IP_BEHAVIOR_SENSITIVE_PATH_LIMIT
```

1차 코드 분리 원칙:

```text
- 위 constants는 이동하지 않는다.
- 새 모듈이 필요로 하는 값은 `prepare_llm_input.py` wrapper에서 인자로 넘긴다.
- constants.py 대량 분리와 섞지 않는다.
```

보류 이유:

```text
- constants 이동까지 함께 하면 regression 실패 시 원인 추적이 어려워진다.
- IP behavior sensitive path limit은 sensitive path/probing 계열과 의미 경계가 겹칠 수 있다.
- constants ownership map은 별도 문서에서 다룬다.
```

## 7. helper 이동 방침

이동 가능 범위:

```text
- IP behavior aggregate builder
- IP behavior aggregate 전용 bucket/helper
- IP behavior aggregate 전용 sample formatting helper
```

이동 금지 또는 보류:

```text
- generic row normalization helper
- generic timestamp parser
- generic path normalization helper
- candidate selection/scoring helper
- supporting_events 생성/연결 helper
- sensitive path probe helper
- probing sequence helper
- mixed baseline scanner helper
```

공용 helper가 필요하면 새 shared module을 만들지 않고, 이번 round에서는 기존 위치에서 import하거나 wrapper 인자로 전달하는 방식을 우선한다.

## 8. 예상 구현 단계

권장 코드 작업 순서:

```text
1. grep으로 `build_ip_behavior_aggregates` 계열 함수와 호출 위치 확인
2. `src/prepare/ip_behavior.py` 생성
3. IP behavior aggregate builder와 전용 helper만 이동
4. `src/prepare_llm_input.py`에 import 추가
5. 기존 공개 함수명 wrapper 유지
6. constants는 이동하지 않고 wrapper에서 전달
7. output key, pipeline_counts, supporting_events 의미가 바뀌지 않았는지 확인
8. py_compile, prepare regression, stage dry-run regression 실행
```

권장 import 패턴:

```text
try:
    from src.prepare.ip_behavior import ... as _...
except ImportError:
    from prepare.ip_behavior import ... as _...
```

기존 round1 모듈 분리와 같은 형태를 유지한다.

## 9. 금지 범위

이번 코드 분리에서 하지 않을 것:

```text
- constants 이동
- constants.py 생성 또는 대량 분리
- candidate/scoring/filtering 변경
- supporting_events 생성/연결 로직 변경
- Stage2 reporter 수정
- expected/test fixture 수정
- policy wording 변경
- output key 변경
- IP behavior aggregate를 incident로 승격
- source IP 기반 attacker identity 단정 문구 추가
- lab-* UA 또는 특정 IP를 공격 근거로 일반화
```

## 10. 검증 계획

코드 분리 전:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

코드 분리 후:

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
candidate_rows 의미 변경 없음
filtered_out 의미 변경 없음
supporting_events 의미 변경 없음
pipeline_counts 의미 변경 없음
ip_behavior_aggregates output key 유지
IP를 attacker identity로 단정하는 문구 없음
```

## 11. 실패 시 롤백 기준

아래 중 하나라도 발생하면 분리 커밋을 수정하거나 롤백한다.

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

## 12. 다음 작업

이 문서 작성 후 다음 작업은 실제 코드 분리다.

권장 커밋 순서:

```text
1. docs: plan ip behavior aggregate split
2. refactor: extract ip behavior aggregate helpers
3. docs: record ip behavior aggregate split
```

코드 분리 커밋 후보 메시지:

```text
refactor: extract ip behavior aggregate helpers
```

완료 후 문서 반영 대상:

```text
docs/design/99_prepare_ip_behavior_aggregates_split_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```
