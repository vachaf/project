# 99_prepare_method_summary_split_plan

- 문서 상태: method summary split plan / 1차 분리 완료
- 기준 시점: 2026-05-04
- 목적: `method_behavior_summaries` 계열을 실제 코드 분리 후보로 좁히기 전에 함수명, 호출 위치, 출력 key, 사용 상수, fixture 기준을 정리한다.

관련 문서:

- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_llm_input_inventory.md](./99_prepare_llm_input_inventory.md)

## 1. 현재 결론

`method_behavior_summaries` 계열 1차 분리는 완료됐다.

완료된 신규 모듈:

```text
src/prepare/method_summaries.py
```

이동된 실제 구현 함수:

```text
build_method_behavior_reason_hints_for_row
build_method_behavior_summaries
build_method_behavior_summary_contexts
```

`src/prepare_llm_input.py`에는 기존 함수명과 기본값 의미를 유지하는 wrapper를 남겼다.

유지한 원칙:

```text
- method 관련 constants 이동 없음
- protocol anomaly summary 이동 없음
- auth/static/crawler summary 이동 없음
- candidate/scoring/filtering 변경 없음
- Stage2 policy 문구 변경 없음
- expected fixture 수정 없음
```

검증 상태:

```text
py_compile 통과
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
```

## 2. 최종 함수/호출 위치

분리 전 확인 명령:

```bash
grep -n "method_behavior_summaries\|build_method_behavior\|METHOD_BEHAVIOR" src/prepare_llm_input.py
```

확인된 주요 위치:

```text
METHOD_BEHAVIOR_WINDOW_SEC
METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT
build_method_behavior_reason_hints_for_row wrapper
build_method_behavior_summaries wrapper
build_method_behavior_summary_contexts wrapper
method_behavior_summaries 생성 위치
method_behavior_contexts 생성 위치
pipeline_counts / payload wiring 위치
```

최종 구조:

```text
src/prepare/method_summaries.py
  - 실제 method summary 구현

src/prepare_llm_input.py
  - METHOD_BEHAVIOR_* constants 유지
  - method family constants 유지
  - 기존 함수명 wrapper 유지
  - payload wiring 유지
```

## 3. 입력 계약

method summary builder가 소비하는 입력 범주는 아래로 제한한다.

```text
- normalized rows 또는 source rows
- src_ip
- method
- uri / raw_request_target
- status_code
- response_body_bytes
- resp_content_type
- duration_us / ttfb_us
- log_time
- request_id
- user_agent
- referer
```

해석 원칙:

```text
- raw POST body는 보지 않는다.
- response body 원문은 보지 않는다.
- PUT/DELETE/TRACE/OPTIONS가 있었다는 사실과 성공 여부를 분리한다.
- status/bytes/content-type만으로 method 허용, 업로드 성공, 삭제 성공, XST 성공, CORS 취약점을 단정하지 않는다.
- User-Agent는 trace aid 또는 운영 문맥 보조 정보일 뿐, 공격 근거가 아니다.
```

입력에서 직접 사용하면 안 되는 것:

```text
- DB 결과
- response body 원문
- 브라우저 실행 결과
- 파일 업로드 실제 성공 여부
- 서버 설정 원문
```

## 4. 출력 계약

Stage2 report input에서 유지되어야 하는 핵심 output key는 아래다.

```text
method_behavior_summaries
pipeline_counts.method_behavior_summary_count
policy_notes.method_behavior_summary_policy
policy_notes.behavior_scope_separation_policy
```

`method_behavior_summaries[0]`에서 expected가 고정하는 핵심 key:

```text
context_role = method_behavior_context
should_promote_to_candidate = false
interpretation_limit = no_method_success_inference_from_apache_logs
```

Stage2 policy 쪽 핵심 문구:

```text
method 허용, 업로드 성공, 삭제 성공, XST 성공, CORS 취약점을 단정하지 않음
```

출력에 포함될 수 있는 정보:

```text
- method_counts
- risky_methods
- baseline_methods
- representative_requests
- status_counts
- request_count
- context_role
- should_promote_to_candidate
- interpretation_limit
```

출력 불변조건:

```text
- method_behavior_summary_count 의미 변경 금지
- context_role 변경 금지
- should_promote_to_candidate=true 변경 금지
- interpretation_limit 변경 금지
- candidate_rows 증가 금지
- method summary를 incident로 승격 금지
```

## 5. 사용하는 constants

method summary와 연결된 주요 상수:

```text
METHOD_BEHAVIOR_WINDOW_SEC
METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT
METHOD_RISKY_FAMILIES
METHOD_BASELINE_FAMILIES
METHOD_DESTRUCTIVE_FAMILIES
STANDARD_HTTP_METHODS
```

1차 분리 결과:

```text
- 위 constants는 이동하지 않았다.
- src/prepare_llm_input.py wrapper가 constants를 새 모듈 함수 인자로 넘긴다.
- constants 이동은 별도 커밋으로 보류한다.
```

이유:

- constants에는 단순 문자열뿐 아니라 behavior 의미가 섞여 있다.
- method summary와 protocol anomaly가 일부 constants를 공유할 가능성이 있다.
- constants 이동까지 같이 하면 regression 실패 시 원인 추적이 어려워진다.

## 6. helper 처리 결과

`src/prepare/method_summaries.py`에는 method summary 전용 helper가 함께 들어갔다.

대표 helper:

```text
_normalize_text
_safe_int
_parse_flexible_iso_dt
_classify_method_behavior_family
_has_method_protocol_anomaly
_get_src_ip
_get_status_code
_get_method
_get_sample_request_id
_choose_best_time
```

판단:

```text
- helper 일부는 prepare_llm_input.py 기존 helper와 유사하지만 method 전용 복제로 유지한다.
- shared helper를 강제로 이동하지 않아 import cycle 위험을 줄였다.
- 향후 shared utils 분리는 별도 판단으로 둔다.
```

## 7. 회귀 fixture 기준

### 7.1 prepare fixture

fixture:

```text
tests/fixtures/prepare_regression/g_r1_method_behavior_context.json
```

구성:

```text
- OPTIONS / 204 / 0B
- TRACE / 405 / 96B
- PUT / 200 / 512B
- DELETE / 500 / 184B
- HEAD / 200 / 0B
- GET / 200 / 1240B
```

해석 기준:

```text
- risky method context는 보존한다.
- baseline GET/HEAD와 risky method를 구분한다.
- PUT 200을 업로드 성공으로 단정하지 않는다.
- DELETE 500을 삭제 성공 또는 실패 원인으로 단정하지 않는다.
- TRACE 405를 XST 성공으로 단정하지 않는다.
```

### 7.2 stage dry-run expected

expected:

```text
tests/expected/stage_dryrun_regression/g_r1_method_behavior_context.expected.json
```

MUST 기준:

```text
pipeline_counts.method_behavior_summary_count exists
pipeline_counts.method_behavior_summary_count == 1
policy_notes.method_behavior_summary_policy exists
policy_notes.method_behavior_summary_policy.success_rule contains no-success-inference rule
policy_notes.behavior_scope_separation_policy.non_merge_rule contains method_behavior_summaries
method_behavior_summaries.0.context_role == method_behavior_context
method_behavior_summaries.0.should_promote_to_candidate == false
method_behavior_summaries.0.interpretation_limit == no_method_success_inference_from_apache_logs
pipeline_counts.candidate_rows == 0
stage2 prompt includes method behavior context-only rule
stage2 report markdown includes method behavior context section
stage2 report markdown includes risky_methods= and baseline_methods=
```

MUST_NOT 기준:

```text
- 업로드 성공 단정 금지
- 삭제 성공 단정 금지
- XST 성공 단정 금지
- CORS 취약점 성공 단정 금지
```

## 8. 완료된 분리 범위

1차 코드 분리에서 수행한 변경:

```text
- src/prepare/method_summaries.py 생성
- method summary builder 함수 이동
- method 전용 helper 이동
- src/prepare_llm_input.py에서 import / wrapper 추가
```

1차 코드 분리에서 하지 않은 변경:

```text
- constants 이동 없음
- protocol anomaly summary 이동 없음
- auth/static/crawler summary 이동 없음
- output key 변경 없음
- policy 문구 변경 없음
- expected fixture 변경 없음
- scoring/filtering/candidate logic 변경 없음
```

## 9. 검증 계획과 결과

검증 명령:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

검증 결과:

```text
py_compile 통과
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
```

성공 기준 유지:

```text
method_behavior_summary_count == 1 유지
candidate_rows == 0 유지
g_r1_method_behavior_context expected 수정 없음
```

## 10. 실패 시 롤백 기준

아래 중 하나라도 발생하면 분리 커밋을 수정하거나 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- method_behavior_summary_count 변화
- candidate_rows 변화
- context_role 변화
- should_promote_to_candidate 변화
- interpretation_limit 변화
- risky_methods / baseline_methods 출력 누락
- upload/delete/XST/CORS 성공 단정 문구 발생
- import cycle 발생
```

## 11. 현재 결론

`method_behavior_summaries` 1차 분리는 완료됐다.

현재 상태:

```text
src/prepare/method_summaries.py 생성 완료
prepare_llm_input.py wrapper 유지
constants 이동 없음
expected 수정 없음
strict regression 통과
```

다음 후보:

```text
protocol_anomaly_summaries 계열 검토
```

단, protocol anomaly는 error/access/security surface 해석과 long path threshold가 연결되므로 바로 코드 분리하지 않는다. 먼저 `docs/design/99_prepare_protocol_anomaly_split_plan.md` 같은 좁은 계획 문서를 작성한 뒤 실제 분리 여부를 판단한다.
