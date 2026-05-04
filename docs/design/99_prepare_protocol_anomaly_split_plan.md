# 99_prepare_protocol_anomaly_split_plan

- 문서 상태: protocol anomaly split plan / 1차 분리 완료
- 기준 시점: 2026-05-04
- 목적: `protocol_anomaly_summaries` 계열의 분리 범위, 출력 key, 사용 상수, fixture 기준을 정리한다.

관련 문서:

- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md)
- [99_prepare_method_summary_split_plan.md](./99_prepare_method_summary_split_plan.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 현재 결론

`protocol_anomaly_summaries` 계열 1차 분리는 완료됐다.

완료된 신규 모듈:

```text
src/prepare/protocol_anomalies.py
```

이동된 실제 구현 함수:

```text
build_protocol_anomaly_reason_hints_for_row
finalize_protocol_anomaly_bucket
build_protocol_anomaly_summaries
build_protocol_anomaly_summary_contexts
```

`src/prepare_llm_input.py`에는 기존 함수명과 기본값 의미를 유지하는 wrapper를 남겼다.

유지한 원칙:

```text
- protocol/method 관련 constants 이동 없음
- method summary 이동 없음
- auth/static/crawler/sensitive/mixed summary 이동 없음
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
grep -n "protocol_anomaly_summaries\|build_protocol_anomaly\|finalize_protocol_anomaly\|PROTOCOL_ANOMALY" src/prepare_llm_input.py
```

확인된 주요 위치:

```text
PROTOCOL_ANOMALY_WINDOW_SEC
PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT
PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN
build_protocol_anomaly_reason_hints_for_row wrapper
finalize_protocol_anomaly_bucket wrapper 또는 import 연결
build_protocol_anomaly_summaries wrapper
build_protocol_anomaly_summary_contexts wrapper
protocol_anomaly_summaries 생성 위치
protocol_anomaly_contexts 생성 위치
pipeline_counts / payload wiring 위치
```

최종 구조:

```text
src/prepare/protocol_anomalies.py
  - 실제 protocol anomaly summary 구현

src/prepare_llm_input.py
  - PROTOCOL_ANOMALY_* constants 유지
  - STANDARD_HTTP_METHODS 등 공유 상수 유지
  - 기존 함수명 wrapper 유지
  - payload wiring 유지
```

## 3. 입력 계약

protocol anomaly summary builder가 소비하는 입력 범주는 아래로 제한한다.

```text
- normalized rows 또는 source rows
- src_ip
- method
- uri / raw_request_target
- raw_request
- protocol
- host / vhost
- status_code
- response_body_bytes
- resp_content_type
- log_time
- request_id
- user_agent
```

해석 원칙:

```text
- raw POST body는 보지 않는다.
- response body 원문은 보지 않는다.
- malformed request 또는 unusual protocol surface와 exploit success를 분리한다.
- HTTP status, bytes, content-type만으로 protocol bypass, virtual host bypass, 침해 성공을 단정하지 않는다.
- error/access/security source table 차이를 혼동하지 않는다.
- User-Agent는 trace aid 또는 운영 문맥 보조 정보일 뿐, 공격 근거가 아니다.
```

입력에서 직접 사용하면 안 되는 것:

```text
- 서버 내부 parser 결과
- response body 원문
- 브라우저 실행 결과
- 실제 virtual host routing 결과
- backend exploit success 여부
```

## 4. 출력 계약

Stage2 report input에서 유지되어야 하는 핵심 output key는 아래다.

```text
protocol_anomaly_summaries
pipeline_counts.protocol_anomaly_summary_count
policy_notes.protocol_anomaly_summary_policy
policy_notes.behavior_scope_separation_policy
```

`protocol_anomaly_summaries[0]`에서 expected가 고정하는 핵심 key:

```text
context_role = protocol_anomaly_context
should_promote_to_candidate = false
interpretation_limit = protocol_anomaly_context_only_no_success_inference
reason_hints contains protocol_anomaly:unsupported_method
reason_hints contains protocol_anomaly:no_success_inference
```

Stage2 policy 쪽 핵심 문구:

```text
우회 성공, 침해 성공, 서버 취약점 성공을 단정하지 않음
```

출력에 포함될 수 있는 정보:

```text
- anomaly_types
- method_counts
- status_counts
- sample_request_ids
- request_count
- context_role
- should_promote_to_candidate
- interpretation_limit
- reason_hints
```

출력 불변조건:

```text
- protocol_anomaly_summary_count 의미 변경 금지
- context_role 변경 금지
- should_promote_to_candidate=true 변경 금지
- interpretation_limit 변경 금지
- reason_hints 이름 변경 금지
- candidate_rows 증가 금지
- protocol anomaly summary를 incident로 승격 금지
```

## 5. 사용하는 constants

protocol anomaly summary와 연결된 주요 상수:

```text
PROTOCOL_ANOMALY_WINDOW_SEC
PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT
PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN
STANDARD_HTTP_METHODS
```

1차 분리 결과:

```text
- 위 constants는 이동하지 않았다.
- src/prepare_llm_input.py wrapper가 constants를 새 모듈 함수 인자로 넘긴다.
- constants 이동은 별도 커밋으로 보류한다.
```

이유:

- `STANDARD_HTTP_METHODS`는 method behavior summary와 공유될 수 있다.
- long path threshold는 output에 직접 영향을 줄 수 있다.
- constants 이동까지 같이 하면 regression 실패 시 원인 추적이 어려워진다.

## 6. helper 처리 결과

`src/prepare/protocol_anomalies.py`에는 protocol anomaly 전용 helper가 함께 들어갔다.

대표 helper:

```text
normalize/raw text helper
safe int helper
flexible datetime parse helper
src_ip / method / status / request_id 추출 helper
protocol/host/path anomaly 판정 helper
bucket finalize helper
```

판단:

```text
- helper 일부는 prepare_llm_input.py 또는 method_summaries.py와 유사할 수 있지만 protocol 전용 복제로 유지한다.
- shared helper를 새로 만들지 않아 import cycle 위험을 줄였다.
- 향후 shared utils 분리는 별도 판단으로 둔다.
```

## 7. 회귀 fixture 기준

### 7.1 prepare fixture

fixture:

```text
tests/fixtures/prepare_regression/g_r2_protocol_anomaly_context.json
```

구성:

```text
- FAKEMETHOD / 400 / unsupported method
- GET / HTTP/1.0 / missing host-like baseline
- GET / HTTP/9.9 / bad protocol version
- GET /host-check HTTP/1.1 / missing host
- GET /odd-host-check HTTP/1.1 / odd host
- GET very long path / 414 / long path
```

해석 기준:

```text
- malformed 또는 unusual protocol surface는 context로 보존한다.
- unsupported method는 protocol anomaly hint로 보존한다.
- bad protocol / missing host / odd host / long path는 protocol anomaly context로 보존한다.
- protocol bypass 성공, virtual host bypass 성공, 침해 성공, 서버 취약점 성공을 단정하지 않는다.
```

### 7.2 stage dry-run expected

expected:

```text
tests/expected/stage_dryrun_regression/g_r2_protocol_anomaly_context.expected.json
```

MUST 기준:

```text
pipeline_counts.protocol_anomaly_summary_count exists
pipeline_counts.protocol_anomaly_summary_count == 1
policy_notes.protocol_anomaly_summary_policy exists
policy_notes.protocol_anomaly_summary_policy.success_rule contains no-success-inference rule
policy_notes.behavior_scope_separation_policy.non_merge_rule contains protocol_anomaly_summaries
protocol_anomaly_summaries.0.context_role == protocol_anomaly_context
protocol_anomaly_summaries.0.should_promote_to_candidate == false
protocol_anomaly_summaries.0.interpretation_limit == protocol_anomaly_context_only_no_success_inference
protocol_anomaly_summaries.0.reason_hints contains protocol_anomaly:unsupported_method
protocol_anomaly_summaries.0.reason_hints contains protocol_anomaly:no_success_inference
pipeline_counts.candidate_rows == 0
stage2 prompt includes protocol anomaly context-only rule
stage2 report markdown includes protocol anomaly context section
stage2 report markdown includes anomaly_types=
```

MUST_NOT 기준:

```text
- 우회 성공 단정 금지
- 침해 성공 단정 금지
- virtual host bypass 성공 단정 금지
```

## 8. 완료된 분리 범위

1차 코드 분리에서 수행한 변경:

```text
- src/prepare/protocol_anomalies.py 생성
- protocol anomaly summary builder 함수 이동
- protocol anomaly 전용 helper 이동
- src/prepare_llm_input.py에서 import / wrapper 추가
```

1차 코드 분리에서 하지 않은 변경:

```text
- constants 이동 없음
- method behavior summary 이동 없음
- auth/static/crawler/sensitive/mixed summary 이동 없음
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
protocol_anomaly_summary_count == 1 유지
candidate_rows == 0 유지
g_r2_protocol_anomaly_context expected 수정 없음
```

## 10. 실패 시 롤백 기준

아래 중 하나라도 발생하면 분리 커밋을 수정하거나 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- protocol_anomaly_summary_count 변화
- candidate_rows 변화
- context_role 변화
- should_promote_to_candidate 변화
- interpretation_limit 변화
- reason_hints 누락
- anomaly_types 출력 누락
- 우회/침해/virtual host bypass 성공 단정 문구 발생
- import cycle 발생
```

## 11. 현재 결론

`protocol_anomaly_summaries` 1차 분리는 완료됐다.

현재 상태:

```text
src/prepare/protocol_anomalies.py 생성 완료
prepare_llm_input.py wrapper 유지
constants 이동 없음
expected 수정 없음
strict regression 통과
```

다음 후보:

```text
auth_behavior_summaries 계열 검토
```

단, auth behavior는 POST body visibility, account existence, lockout, credential stuffing success 단정 금지와 연결되므로 바로 코드 분리하지 않는다. 먼저 `docs/design/99_prepare_auth_behavior_split_plan.md` 같은 좁은 계획 문서를 작성한 뒤 실제 분리 여부를 판단한다.
