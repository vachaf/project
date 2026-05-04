# 99_prepare_sensitive_path_probe_split_plan

- 문서 상태: sensitive path probe split plan
- 기준 시점: 2026-05-04
- 목적: `sensitive_path_probe_summaries` 계열을 실제 코드 분리 후보로 볼 수 있는지 판단하기 전에 함수명, 호출 위치, 출력 key, 사용 상수, fixture 기준을 정리한다.

관련 문서:

- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md)
- [99_prepare_static_baseline_split_plan.md](./99_prepare_static_baseline_split_plan.md)
- [99_prepare_crawler_baseline_split_plan.md](./99_prepare_crawler_baseline_split_plan.md)
- [99_sensitive_path_probe_context_category_검토.md](./99_sensitive_path_probe_context_category_검토.md)
- [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 현재 결론

`sensitive_path_probe_summaries`는 `crawler_baseline_summaries` 이후의 다음 검토 후보로 볼 수 있다.

다만 method/protocol/auth/static/crawler보다 위험도가 높다. 바로 코드 분리하지 않고, 먼저 함수와 supporting event 결합도를 확인한다.

1차 분리 가능 범위는 아래로 제한한다.

```text
- sensitive_path_probe_summaries builder 함수
- sensitive path probe 전용 helper
- sensitive path probe summary context builder
```

1차 분리에서 하지 않을 것:

```text
- sensitive path 관련 constants 이동
- sensitive_path_probe_support supporting event 전체 로직 이동
- probing_sequence_summaries 이동
- mixed_baseline_scanner_summaries 이동
- file disclosure hint/scoring 로직 이동
- candidate/scoring/filtering 변경
- Stage2 policy 문구 변경
- expected fixture 수정
```

권장 신규 모듈 후보:

```text
src/prepare/sensitive_path_probe.py
```

`prepare/context_summaries.py` 전체를 바로 만들지 않는 이유:

- sensitive path probe는 `.env`, `.git`, `phpinfo`, `server-status`, backup/config, admin/wp-login path와 연결된다.
- 200/text/html, text/plain, application/octet-stream, response_body_bytes를 파일 노출 성공으로 오해할 위험이 크다.
- `supporting_events` 안의 `sensitive_path_probe_support`와 연결된다.
- file disclosure taxonomy와 경계가 일부 겹친다.
- 첫 단계는 summary builder 계열만 좁게 검증하는 편이 안전하다.

## 2. 현재 함수/호출 위치 후보

현재 `sensitive_path_probe_summaries` 관련 로직은 `src/prepare_llm_input.py` 안에 있다.

실제 분리 전 확인해야 할 후보 함수명:

```text
classify_sensitive_path_probe_category
build_sensitive_path_probe_reason_hints_for_row
finalize_sensitive_path_probe_bucket
build_sensitive_path_probe_summaries
build_sensitive_path_probe_summary_contexts
build_sensitive_path_probe_support_reason_hints
build_sensitive_path_probe_supporting_event
```

주의:

```text
- build_sensitive_path_probe_support_reason_hints
- build_sensitive_path_probe_supporting_event
```

위 두 함수는 supporting event와 직접 연결될 가능성이 높으므로 1차 분리 대상에서 제외하는 것을 기본으로 한다.

실제 코드 작업 전에는 아래를 확인한다.

```bash
grep -n "sensitive_path_probe_summaries\|build_sensitive_path_probe\|finalize_sensitive_path_probe\|SENSITIVE_PATH_PROBE\|classify_sensitive_path" src/prepare_llm_input.py
```

확인할 항목:

```text
- builder 함수명
- finalize 함수명
- summary context 함수명
- path category classifier 함수명
- reason hint 함수명
- supporting event 함수명
- builder 호출 위치
- builder가 받는 rows/candidates/filtered/supporting 구조
- main payload에 sensitive_path_probe_summaries를 넣는 위치
- pipeline_counts.sensitive_path_probe_summary_count를 계산하는 위치
- supporting_events 중 sensitive_path_probe_support를 생성/보존하는 위치
- sensitive path probe policy_notes와 Stage2 입력 연결 위치
```

주의:

- 이 문서는 함수명이 위 후보와 같을 가능성을 기준으로 한다.
- 실제 코드에서 이름이 다르면 코드 이름을 우선한다.
- 이름 변경을 위한 refactor는 이번 분리와 섞지 않는다.

## 3. 입력 계약

sensitive path probe summary builder가 소비하는 입력 범주는 아래로 제한한다.

```text
- normalized rows 또는 source rows
- src_ip
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
```

해석 원칙:

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

## 4. 출력 계약

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

Stage2 policy 쪽 핵심 문구:

```text
WordPress 존재, admin access, .env 노출, phpinfo 노출, server-status 노출/차단, backup 노출, 공격 성공을 단정하지 않음
```

출력에 포함될 수 있는 정보:

```text
- path_categories
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

## 5. 사용하는 constants

sensitive path probe summary와 연결된 주요 상수 후보:

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

1차 분리 원칙:

```text
- 위 constants는 1차 분리에서 이동하지 않는다.
- sensitive_path_probe.py가 필요하면 prepare_llm_input.py wrapper에서 값을 인자로 넘긴다.
- constants 이동은 별도 커밋에서 검토한다.
```

이유:

- sensitive path, probing sequence, mixed scanner가 path category 판단을 공유할 수 있다.
- representative candidate limit은 supporting_events와 candidate rows에 영향을 줄 수 있다.
- constants 이동까지 같이 하면 regression 실패 시 원인 추적이 어려워진다.

## 6. 사용하는 helper 후보

분리 전 실제 사용 여부를 확인할 helper 후보:

```text
raw_text / normalize_text
safe_int
parse_flexible_iso_dt 또는 timestamp helper
get_src_ip
get_method
get_status_code
get_sample_request_id
get_effective_request_path 또는 path normalization helper
choose_best_time
sensitive path category classifier
status distribution helper
sample request formatting helper
```

1차 분리 원칙:

```text
- sensitive path probe 전용 helper만 함께 이동한다.
- supporting_events 전체 연결 로직은 이동하지 않는다.
- probing_sequence, mixed scanner, file disclosure와 공유되는 helper는 이동하지 않는다.
- shared helper module을 새로 만들지 않는다.
- helper behavior 변경 금지
- helper 이름 변경 금지
```

## 7. 회귀 fixture 기준

### 7.1 prepare fixture

fixture:

```text
tests/fixtures/prepare_regression/h_r3_sensitive_path_probe_context.json
```

구성:

```text
- GET /wp-login.php 200 text/html
- GET /wp-admin/ 200 text/html
- GET /.env 200 text/plain
- GET /phpinfo.php 200 text/html
- GET /server-status 403 text/html with error_link_id
- GET /backup.zip 200 application/octet-stream
- repeated /.env, /server-status, /backup.zip
```

해석 기준:

```text
- scanner-like sensitive path probing context는 보존한다.
- WordPress 존재를 단정하지 않는다.
- admin access 성공을 단정하지 않는다.
- .env 노출을 단정하지 않는다.
- phpinfo 노출을 단정하지 않는다.
- server-status 노출 또는 차단 성공을 단정하지 않는다.
- backup 노출을 단정하지 않는다.
- 공격 성공을 단정하지 않는다.
```

### 7.2 stage dry-run expected

expected:

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

## 8. 분리 가능 범위

1차 코드 분리에서 허용되는 변경:

```text
- src/prepare/sensitive_path_probe.py 생성
- sensitive path probe summary builder 함수 이동
- sensitive path probe 전용 helper 이동
- sensitive path probe reason hint builder 이동 여부는 supporting_event 의존성을 확인한 뒤 결정
- src/prepare_llm_input.py에서 import / wrapper 추가
```

1차 코드 분리에서 금지되는 변경:

```text
- constants 이동
- supporting_events 전체 로직 이동
- probing_sequence_summaries 이동
- mixed_baseline_scanner_summaries 이동
- file disclosure hint/scoring 이동
- output key 변경
- policy 문구 변경
- expected fixture 변경
- scoring/filtering/candidate logic 변경
```

## 9. 검증 계획

분리 전:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

분리 후:

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
sensitive_path_probe_summary_count == 1 유지
supporting_events의 sensitive_path_probe_support 유지
h_r3_sensitive_path_probe_context expected 수정 없음
```

## 10. 실패 시 롤백 기준

아래 중 하나라도 발생하면 분리 커밋을 수정하거나 롤백한다.

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

## 11. 현재 결론

`sensitive_path_probe_summaries`는 다음 실제 코드 분리 후보로 검토 가능하지만, 지금까지 분리한 baseline summary보다 위험도가 높다.

실제 코드 분리 전에 아래 명령으로 함수명과 호출 위치를 먼저 확정한다.

```bash
grep -n "sensitive_path_probe_summaries\|build_sensitive_path_probe\|finalize_sensitive_path_probe\|SENSITIVE_PATH_PROBE\|classify_sensitive_path" src/prepare_llm_input.py
```

그 결과가 명확하면 다음 코드는 아래 범위로 검토한다.

```text
src/prepare/sensitive_path_probe.py 생성
sensitive path probe summary builder만 이동
supporting_events 전체 로직은 이동하지 않음
constants는 이동하지 않음
probing_sequence/mixed/file_disclosure logic은 이동하지 않음
expected는 수정하지 않음
```
