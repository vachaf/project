# 99_prepare_auth_behavior_split_plan

- 문서 상태: auth behavior split plan / 1차 분리 완료
- 기준 시점: 2026-05-04
- 목적: `auth_behavior_summaries` 계열의 분리 범위, 출력 key, 사용 상수, fixture 기준을 정리한다.

관련 문서:

- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md)
- [99_prepare_method_summary_split_plan.md](./99_prepare_method_summary_split_plan.md)
- [99_prepare_protocol_anomaly_split_plan.md](./99_prepare_protocol_anomaly_split_plan.md)
- [99_POST_body_visibility_한계와_해석_기준.md](./99_POST_body_visibility_한계와_해석_기준.md)

## 1. 현재 결론

`auth_behavior_summaries` 계열 1차 분리는 완료됐다.

완료된 신규 모듈:

```text
src/prepare/auth_behavior.py
```

이동된 실제 구현 함수:

```text
finalize_auth_behavior_bucket
build_auth_behavior_summaries
build_auth_behavior_summary_contexts
```

`src/prepare_llm_input.py`에는 기존 함수명과 기본값 의미를 유지하는 wrapper를 남겼다.

유지한 원칙:

```text
- auth 관련 constants 이동 없음
- supporting_events 로직 이동 없음
- ip_behavior_aggregates 이동 없음
- method/protocol/static/crawler/sensitive/mixed summary 이동 없음
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
grep -n "auth_behavior_summaries\|build_auth_behavior\|finalize_auth_behavior\|AUTH_BEHAVIOR" src/prepare_llm_input.py
```

확인된 주요 위치:

```text
AUTH_BEHAVIOR_WINDOW_SEC
AUTH_BEHAVIOR_RAPID_WINDOW_SEC
AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT
AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT
finalize_auth_behavior_bucket wrapper
build_auth_behavior_summaries wrapper
build_auth_behavior_summary_contexts wrapper
supporting event 관련 함수 유지
main pipeline의 auth_behavior_summaries 생성/연결 위치
pipeline_counts / payload wiring 위치
```

최종 구조:

```text
src/prepare/auth_behavior.py
  - 실제 auth behavior summary 구현

src/prepare_llm_input.py
  - AUTH_BEHAVIOR_* constants 유지
  - auth endpoint 관련 constants 유지
  - supporting_events 관련 함수 유지
  - 기존 함수명 wrapper 유지
  - payload wiring 유지
```

## 3. 입력 계약

auth behavior summary builder가 소비하는 입력 범주는 아래로 제한한다.

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
- req_content_type
```

해석 원칙:

```text
- raw POST body는 보지 않는다.
- 계정명, password, credential 내용은 보지 않는다.
- response body 원문은 보지 않는다.
- HTTP 200 observed after repeated 401은 처리/응답 변화 정황일 뿐 로그인 성공 확정이 아니다.
- 401 반복은 credential stuffing 성공, brute force 성공, account lockout 발동의 증거가 아니다.
- User-Agent는 trace aid 또는 운영 문맥 보조 정보일 뿐, 공격 근거가 아니다.
```

입력에서 직접 사용하면 안 되는 것:

```text
- POST body 원문
- password / credential 값
- DB 계정 존재 여부
- JWT/token 발급 여부
- response body 원문
- 실제 account lockout 상태
- 실제 로그인 세션 생성 여부
```

## 4. 출력 계약

Stage2 report input에서 유지되어야 하는 핵심 output key는 아래다.

```text
auth_behavior_summaries
pipeline_counts.auth_behavior_summary_count
policy_notes.auth_behavior_summary_policy
policy_notes.supporting_events_policy.auth_behavior_rule
policy_notes.behavior_scope_separation_policy
policy_notes.user_agent_interpretation_policy
supporting_events
```

`auth_behavior_summaries[0]`에서 expected가 고정하는 핵심 key:

```text
context_role = auth_behavior_context
should_promote_to_candidate = false
interpretation_limit = post_body_not_visible_no_auth_success_inference
```

Stage2 policy 쪽 핵심 문구:

```text
HTTP 200 observed after repeated 401
raw POST body 미확인
count scope 를 분리하라
lab-* 같은 실험 prefix 자체를 탐지 근거로 삼지 마라
```

출력에 포함될 수 있는 정보:

```text
- auth_requests 또는 request_count
- status_counts
- representative_requests
- sample_request_ids
- window_start / window_end
- context_role
- should_promote_to_candidate
- interpretation_limit
- reason_hints
```

출력 불변조건:

```text
- auth_behavior_summary_count 의미 변경 금지
- context_role 변경 금지
- should_promote_to_candidate=true 변경 금지
- interpretation_limit 변경 금지
- candidate_rows 의미 변경 금지
- supporting_event_count 의미 변경 금지
- auth behavior summary를 incident로 승격 금지
- auth count와 ip behavior window count를 range 표현으로 병합 금지
```

## 5. 사용하는 constants

auth behavior summary와 연결된 주요 상수:

```text
AUTH_BEHAVIOR_WINDOW_SEC
AUTH_BEHAVIOR_RAPID_WINDOW_SEC
AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT
AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT
LOGIN_URI_HINTS
AUTH_ENDPOINT_FAMILY_PATTERNS
AUTH_SUCCESS_ATTACK_HINT_PATTERN
```

1차 분리 결과:

```text
- 위 constants는 이동하지 않았다.
- src/prepare_llm_input.py wrapper가 constants를 새 모듈 함수 인자로 넘긴다.
- constants 이동은 별도 커밋으로 보류한다.
```

이유:

- auth endpoint family 판단은 candidate/supporting_events와 연결될 수 있다.
- representative candidate limit은 candidate_rows와 supporting_event_count에 영향을 준다.
- constants 이동까지 같이 하면 regression 실패 시 원인 추적이 어려워진다.

## 6. helper 처리 결과

`src/prepare/auth_behavior.py`에는 auth behavior summary 전용 helper가 함께 들어갔다.

대표 helper:

```text
normalize/raw text helper
safe int helper
flexible datetime parse helper
src_ip / method / status / request_id 추출 helper
auth endpoint family helper
bucket finalize helper
```

판단:

```text
- helper 일부는 prepare_llm_input.py 기존 helper와 유사할 수 있지만 auth 전용 복제로 유지한다.
- supporting_events 또는 ip_behavior와 공유될 수 있는 로직은 이번 분리에서 제외했다.
- shared helper를 새로 만들지 않아 import cycle 위험을 줄였다.
- 향후 shared utils 분리는 별도 판단으로 둔다.
```

## 7. 회귀 fixture 기준

### 7.1 prepare fixture

fixture:

```text
tests/fixtures/prepare_regression/f_r1_auth_behavior_context.json
```

구성:

```text
- POST /api/login 401 4건
- POST /api/login 200 2건
- GET /api/products 200 baseline 1건
```

해석 기준:

```text
- repeated auth endpoint interaction은 context로 보존한다.
- HTTP 200 observed after repeated 401은 mixed-status caution으로만 다룬다.
- 로그인 성공, 계정 탈취, credential stuffing 성공, lockout 발동을 단정하지 않는다.
- GET /api/products baseline은 auth behavior로 과승격하지 않는다.
```

### 7.2 stage dry-run expected

expected:

```text
tests/expected/stage_dryrun_regression/f_r1_auth_behavior_context.expected.json
```

MUST 기준:

```text
pipeline_counts.auth_behavior_summary_count exists
pipeline_counts.auth_behavior_summary_count == 1
policy_notes.auth_behavior_summary_policy exists
policy_notes.behavior_scope_separation_policy exists
behavior_scope_separation_policy.non_merge_rule forbids range wording
auth_behavior_summaries.0.context_role == auth_behavior_context
auth_behavior_summaries.0.should_promote_to_candidate == false
auth_behavior_summaries.0.interpretation_limit == post_body_not_visible_no_auth_success_inference
pipeline_counts.candidate_rows == 3
pipeline_counts.supporting_event_count == 1
policy_notes.auth_behavior_summary_policy.mixed_status_rule contains HTTP 200 observed after repeated 401
stage2 prompt keeps mixed 401/200 caution
stage2 prompt separates auth and ip behavior count scope
stage2 prompt avoids lab prefix as attack rationale
stage2 report markdown includes context-only auth behavior summaries
stage2 report markdown includes raw POST body 미확인
stage2 report markdown includes scope 구분
stage2 report markdown labels window_requests= and auth_requests=
401 auth request remains in top_incidents
supporting_events keeps auth_behavior_support / covered_by_auth_behavior_summary
```

MUST_NOT 기준:

```text
- 48~51 같은 auth/ip count range 병합 금지
- 로그인 성공 confirmed 단정 금지
- credential stuffing 성공 단정 금지
- lab-f-set prefix 자체를 공격 근거로 사용 금지
```

## 8. 완료된 분리 범위

1차 코드 분리에서 수행한 변경:

```text
- src/prepare/auth_behavior.py 생성
- auth behavior summary builder 함수 이동
- auth behavior 전용 helper 이동
- src/prepare_llm_input.py에서 import / wrapper 추가
```

1차 코드 분리에서 하지 않은 변경:

```text
- constants 이동 없음
- supporting_events 전체 로직 이동 없음
- ip_behavior_aggregates 이동 없음
- method/protocol/static/crawler/sensitive/mixed summary 이동 없음
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
auth_behavior_summary_count == 1 유지
candidate_rows == 3 유지
supporting_event_count == 1 유지
f_r1_auth_behavior_context expected 수정 없음
```

## 10. 실패 시 롤백 기준

아래 중 하나라도 발생하면 분리 커밋을 수정하거나 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- auth_behavior_summary_count 변화
- candidate_rows 변화
- supporting_event_count 변화
- context_role 변화
- should_promote_to_candidate 변화
- interpretation_limit 변화
- top_incidents에서 401 auth request 누락
- auth_behavior_support supporting_event 누락
- raw POST body 한계 문구 누락
- login success / credential stuffing success / lockout 단정 문구 발생
- lab-* UA를 공격 근거로 쓰는 표현 발생
- import cycle 발생
```

## 11. 현재 결론

`auth_behavior_summaries` 1차 분리는 완료됐다.

현재 상태:

```text
src/prepare/auth_behavior.py 생성 완료
prepare_llm_input.py wrapper 유지
supporting_events 관련 함수는 prepare_llm_input.py에 유지
constants 이동 없음
expected 수정 없음
strict regression 통과
```

다음 후보:

```text
static_baseline_summaries 계열 검토
```

단, static baseline은 fallback HTML, health-like path, static file 존재/내용 정상 여부 단정 금지와 연결되므로 바로 코드 분리하지 않는다. 먼저 `docs/design/99_prepare_static_baseline_split_plan.md` 같은 좁은 계획 문서를 작성한 뒤 실제 분리 여부를 판단한다.
