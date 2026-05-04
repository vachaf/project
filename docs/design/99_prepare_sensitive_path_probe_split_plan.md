# 99_prepare_sensitive_path_probe_split_plan

- 문서 상태: sensitive path probe split 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `113c97f24843d0d044e5e1eed3785fac83d43071`
- 목적: `sensitive_path_probe_summaries` 계열의 1차 분리 완료 범위, 유지한 계약, 보류한 영역, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md)
- [99_prepare_static_baseline_split_plan.md](./99_prepare_static_baseline_split_plan.md)
- [99_prepare_crawler_baseline_split_plan.md](./99_prepare_crawler_baseline_split_plan.md)
- [99_sensitive_path_probe_context_category_검토.md](./99_sensitive_path_probe_context_category_검토.md)
- [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

`sensitive_path_probe_summaries` 계열의 1차 코드 분리는 완료했다.

신규 모듈:

```text
src/prepare/sensitive_path_probe.py
```

`src/prepare_llm_input.py`에는 기존 함수명을 유지하는 wrapper를 남겼다. 따라서 외부 호출부, expected fixture, Stage2 reporter 계약을 변경하지 않았다.

이번 작업은 mechanical refactor로 제한했다.

```text
- candidate/scoring/filtering 변경 없음
- output key 변경 없음
- policy 문구 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
```

## 2. 이동 완료 함수

아래 함수 4개를 `src/prepare/sensitive_path_probe.py`로 이동했다.

```text
classify_sensitive_path_probe_category
finalize_sensitive_path_probe_bucket
build_sensitive_path_probe_summaries
build_sensitive_path_probe_summary_contexts
```

`src/prepare_llm_input.py`에는 동일한 공개 함수명을 유지하는 wrapper를 남겼다.

이 분리는 summary builder 계열만 좁게 옮긴 것이다. sensitive path probe의 의미, 출력 key, 지원 이벤트 연결 방식은 바꾸지 않았다.

## 3. 이동하지 않은 함수와 로직

아래 함수와 로직은 1차 분리에서 이동하지 않았다.

```text
build_sensitive_path_probe_support_reason_hints
build_sensitive_path_probe_supporting_event
sensitive_path_probe_supporting_events 생성/연결 로직 전체
```

보류 이유:

- `supporting_events`의 row-specific reason hint 오염을 피해야 한다.
- `sensitive_path_probe_support`는 Stage2 입력과 expected가 직접 확인하는 구조다.
- summary context와 supporting event 생성/연결 로직을 한 커밋에서 같이 이동하면 regression 실패 시 원인 추적이 어려워진다.

## 4. 이동하지 않은 constants

아래 constants는 1차 분리에서 이동하지 않았다.

```text
SENSITIVE_PATH_PROBE_WINDOW_SEC
SENSITIVE_PATH_PROBE_SAMPLE_REQUEST_LIMIT
SENSITIVE_PATH_PROBE_REPRESENTATIVE_CANDIDATE_LIMIT
DIR_PROBE_PATH_HINTS
DIR_PROBE_FILE_HINTS
PROBING_SEQUENCE_PATH_PREFIX_HINTS
PROBING_SEQUENCE_PATH_SEGMENT_HINTS
PROBING_SEQUENCE_SUFFIX_HINTS
```

보류 이유:

- sensitive path, probing sequence, mixed scanner가 path category 판단을 공유할 수 있다.
- representative candidate limit은 supporting_events와 candidate rows에 영향을 줄 수 있다.
- constants 이동까지 같이 하면 regression 실패 시 원인 추적이 어려워진다.
- constants.py 대량 분리는 별도 round에서 검토한다.

## 5. Apache logs-only 해석 원칙

이번 분리 이후에도 아래 해석 제한은 그대로 유지한다.

```text
- response body 원문은 보지 않는다.
- 파일 내용은 보지 않는다.
- WordPress 존재 여부는 보지 않는다.
- admin access 성공 여부는 보지 않는다.
- .env / phpinfo / server-status / backup 노출 여부는 보지 않는다.
- 200/text/html, 200/text/plain, application/octet-stream, response bytes만으로 파일 노출을 단정하지 않는다.
- 403 server-status는 차단 성공이나 노출 실패를 단정하는 근거가 아니다.
- User-Agent는 trace aid 또는 운영 문맥 보조 정보일 뿐, 공격 근거가 아니다.
```

입력에서 직접 사용하면 안 되는 것:

```text
- response body 원문
- filesystem 존재 여부
- WordPress 설치 여부
- admin login 가능 여부
- .env 내용
- phpinfo output
- server-status body
- backup archive 실제 내용
- DB 결과
```

## 6. 출력 계약

Stage2 report input에서 유지되어야 하는 핵심 output key는 아래다.

```text
sensitive_path_probe_summaries
pipeline_counts.sensitive_path_probe_summary_count
policy_notes.sensitive_path_probe_summary_policy
policy_notes.behavior_scope_separation_policy
supporting_events
```

`sensitive_path_probe_summaries[0]`에서 expected가 고정하는 핵심 key:

```text
context_role = sensitive_path_probe_context
should_promote_to_candidate = false
interpretation_limit = sensitive_path_probe_no_file_or_app_exposure_inference
```

supporting event 쪽 expected가 고정하는 핵심 구조:

```text
supporting_events contains supporting_role = sensitive_path_probe_support
request_id = h-r3-server-status-1
reason_hints contains sensitive_path:server_status
reason_hints contains sensitive_path:covered_by_sensitive_path_probe_summary
reason_hints must not contain unrelated sensitive_path:wp_login for server-status row
```

출력 불변조건:

```text
- sensitive_path_probe_summary_count 의미 변경 금지
- context_role 변경 금지
- should_promote_to_candidate=true 변경 금지
- interpretation_limit 변경 금지
- reason_hints 이름 변경 금지
- candidate_rows 의미 변경 금지
- supporting_event_count 의미 변경 금지
- sensitive path probe summary를 incident로 승격 금지
- sensitive_path_probe_support의 row-specific reason_hints 오염 금지
```

## 7. 회귀 fixture 기준

prepare fixture:

```text
tests/fixtures/prepare_regression/h_r3_sensitive_path_probe_context.json
```

stage dry-run expected:

```text
tests/expected/stage_dryrun_regression/h_r3_sensitive_path_probe_context.expected.json
```

MUST 기준:

```text
pipeline_counts.sensitive_path_probe_summary_count exists
pipeline_counts.sensitive_path_probe_summary_count == 1
policy_notes.sensitive_path_probe_summary_policy exists
policy_notes.sensitive_path_probe_summary_policy.success_rule contains conservative success rule
policy_notes.behavior_scope_separation_policy.non_merge_rule contains sensitive_path_probe_summaries
sensitive_path_probe_summaries.0.context_role == sensitive_path_probe_context
sensitive_path_probe_summaries.0.should_promote_to_candidate == false
sensitive_path_probe_summaries.0.interpretation_limit == sensitive_path_probe_no_file_or_app_exposure_inference
supporting_events keeps sensitive_path_probe_support / h-r3-server-status-1
supporting_events reason_hints contains sensitive_path:server_status
supporting_events reason_hints contains sensitive_path:covered_by_sensitive_path_probe_summary
stage2 prompt includes sensitive path probe context-only rule
stage2 report markdown includes Sensitive path probe context
stage2 report markdown includes sensitive path probe 해석 제한
stage2 report markdown includes path_categories=
```

MUST_NOT 기준:

```text
- WordPress 존재 단정 금지
- admin access 단정 금지
- .env 노출 단정 금지
- phpinfo 노출 단정 금지
- server-status 노출 단정 금지
- backup 노출 단정 금지
- attack success 단정 금지
- server-status support event가 unrelated wp_login hint를 carry하지 않음
```

## 8. 검증 결과

기준 커밋 `113c97f24843d0d044e5e1eed3785fac83d43071`에서 아래 검증을 통과했다.

```text
py_compile: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
import check: sensitive path probe imports ok
```

이번 문서 반영 커밋은 코드, fixture, expected, Stage2 reporter를 수정하지 않는다.

## 9. 롤백 기준

향후 추가 분리에서 아래 중 하나라도 발생하면 해당 분리 커밋을 수정하거나 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- sensitive_path_probe_summary_count 변화
- candidate_rows 변화
- supporting_event_count 변화
- context_role 변화
- should_promote_to_candidate 변화
- interpretation_limit 변화
- path_categories 출력 누락
- sensitive_path_probe_support 누락
- row-specific reason_hints 오염
- WordPress 존재 / admin access / .env 노출 / phpinfo 노출 / server-status 노출 / backup 노출 / attack success 단정 문구 발생
- probing_sequence 또는 mixed scanner 경계 변화
- import cycle 발생
```

## 10. 다음 단계

sensitive path probe 1차 분리는 완료했다.

다음 작업은 바로 추가 코드 분리를 진행하기보다, P4 1차 분리 전체를 정리하는 summary 문서를 작성한다.

```text
docs/design/99_prepare_module_split_round1_summary.md
```

summary에서 완료 모듈, regression 결과, 보류 영역을 정리한 뒤 다음 후보를 다시 결정한다.

보류 후보:

```text
mixed_baseline_scanner_summaries
probing_sequence_summaries
ip_behavior_aggregates
constants.py 대량 분리
SQLi hints
XSS hints
file_disclosure hints
```
