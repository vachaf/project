# 99_prepare_static_baseline_split_plan

- 문서 상태: static baseline split plan
- 기준 시점: 2026-05-04
- 목적: `static_baseline_summaries` 계열을 실제 코드 분리 후보로 좁히기 전에 함수명, 호출 위치, 출력 key, 사용 상수, fixture 기준을 정리한다.

관련 문서:

- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md)
- [99_prepare_auth_behavior_split_plan.md](./99_prepare_auth_behavior_split_plan.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 현재 결론

`static_baseline_summaries`는 `method_behavior_summaries`, `protocol_anomaly_summaries`, `auth_behavior_summaries` 이후의 다음 코드 분리 후보로 볼 수 있다.

다만 바로 분리하지 않고, 1차 분리 범위를 아래로 제한한다.

```text
- static_baseline_summaries builder 함수
- static baseline 전용 helper
- static baseline summary context builder
```

1차 분리에서 하지 않을 것:

```text
- static/crawler 관련 constants 이동
- crawler baseline summary 이동
- sensitive path / mixed baseline scanner summary 이동
- candidate/scoring/filtering 변경
- Stage2 policy 문구 변경
- expected fixture 수정
```

권장 신규 모듈 후보:

```text
src/prepare/static_baseline.py
```

`prepare/context_summaries.py` 전체를 바로 만들지 않는 이유:

- static baseline은 baseline/context 계열이지만 crawler baseline, sensitive path, mixed scanner와 경계가 일부 겹친다.
- fallback HTML, health-like path, static file 존재/내용 정상 여부 단정 금지가 핵심이다.
- 첫 단계는 static baseline 계열만 좁게 검증하는 편이 안전하다.

## 2. 현재 함수/호출 위치 후보

현재 `static_baseline_summaries` 관련 로직은 `src/prepare_llm_input.py` 안에 있다.

실제 분리 전 확인해야 할 후보 함수명:

```text
build_static_baseline_summaries
build_static_baseline_summary_contexts
finalize_static_baseline_bucket
```

실제 코드 작업 전에는 아래를 확인한다.

```bash
grep -n "static_baseline_summaries\|build_static_baseline\|finalize_static_baseline\|STATIC_BASELINE" src/prepare_llm_input.py
```

확인할 항목:

```text
- builder 함수명
- finalize 함수명
- summary context 함수명
- builder 호출 위치
- builder가 받는 rows/candidates/filtered 구조
- main payload에 static_baseline_summaries를 넣는 위치
- pipeline_counts.static_baseline_summary_count를 계산하는 위치
- static baseline policy_notes와 Stage2 입력 연결 위치
```

주의:

- 이 문서는 함수명이 위 후보와 같을 가능성을 기준으로 한다.
- 실제 코드에서 이름이 다르면 코드 이름을 우선한다.
- 이름 변경을 위한 refactor는 이번 분리와 섞지 않는다.

## 3. 입력 계약

static baseline summary builder가 소비하는 입력 범주는 아래로 제한한다.

```text
- normalized rows 또는 source rows
- src_ip
- method
- uri / raw_request_target
- status_code
- response_body_bytes
- resp_content_type
- log_time
- request_id
- user_agent
- referer
```

해석 원칙:

```text
- response body 원문은 보지 않는다.
- static file 내용은 보지 않는다.
- robots.txt / sitemap.xml 내용은 보지 않는다.
- JS 실행 여부는 보지 않는다.
- health endpoint의 실제 정상 상태는 보지 않는다.
- 200 OK와 content-type만으로 static file 존재, site structure, file exposure, health success를 단정하지 않는다.
- User-Agent는 trace aid 또는 운영 문맥 보조 정보일 뿐, 공격 근거가 아니다.
```

입력에서 직접 사용하면 안 되는 것:

```text
- response body 원문
- static asset 실제 파일 내용
- robots/sitemap body 내용
- browser JS execution result
- backend health check result
- filesystem 존재 여부
```

## 4. 출력 계약

Stage2 report input에서 유지되어야 하는 핵심 output key는 아래다.

```text
static_baseline_summaries
pipeline_counts.static_baseline_summary_count
policy_notes.static_baseline_summary_policy
policy_notes.behavior_scope_separation_policy
```

`static_baseline_summaries[0]`에서 expected가 고정하는 핵심 key:

```text
context_role = static_baseline_context
should_promote_to_candidate = false
interpretation_limit = static_content_not_visible_no_attack_inference
```

Stage2 policy 쪽 핵심 문구:

```text
static file 내용, crawler policy, site structure, JS 실행, file exposure, health 상태를 단정하지 않음
```

출력에 포함될 수 있는 정보:

```text
- asset_categories
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
- static_baseline_summary_count 의미 변경 금지
- context_role 변경 금지
- should_promote_to_candidate=true 변경 금지
- interpretation_limit 변경 금지
- candidate_rows 증가 금지
- static baseline summary를 incident로 승격 금지
- crawler baseline과 static baseline 경계 변경 금지
```

## 5. 사용하는 constants

static baseline summary와 연결된 주요 상수 후보:

```text
STATIC_BASELINE_WINDOW_SEC
STATIC_BASELINE_MIN_STATIC_PATHS
STATIC_BASELINE_SAMPLE_REQUEST_LIMIT
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
BROWSER_UA_HINTS
```

1차 분리 원칙:

```text
- 위 constants는 1차 분리에서 이동하지 않는다.
- static_baseline.py가 필요하면 prepare_llm_input.py wrapper에서 값을 인자로 넘긴다.
- constants 이동은 별도 커밋에서 검토한다.
```

이유:

- static/crawler baseline은 일부 상수와 해석 경계가 겹칠 수 있다.
- health-like path와 static path 판단은 output에 직접 영향을 줄 수 있다.
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
choose_best_time
get_effective_request_path 또는 path normalization helper
static extension / prefix classifier
health-like path classifier
status distribution helper
sample request formatting helper
```

1차 분리 원칙:

```text
- static baseline 전용 helper만 함께 이동한다.
- crawler baseline, sensitive path, mixed scanner와 공유되는 helper는 이동하지 않는다.
- shared helper module을 새로 만들지 않는다.
- helper behavior 변경 금지
- helper 이름 변경 금지
```

## 7. 회귀 fixture 기준

### 7.1 prepare fixture

fixture:

```text
tests/fixtures/prepare_regression/h_r1_static_baseline_context.json
```

구성:

```text
- GET /favicon.ico 404 image/x-icon
- GET /robots.txt 200 text/plain
- GET /sitemap.xml 200 application/xml
- GET /assets/app.js 200 application/javascript
- GET /assets/style.css 200 text/css
- GET /images/logo.png 200 image/png
- GET /api/health 500 application/json
- GET / 200 text/html
```

해석 기준:

```text
- static/baseline context는 보존한다.
- robots/sitemap 내용은 확인하지 않는다.
- JS 실행, file exposure, static file 존재를 단정하지 않는다.
- health endpoint 500을 health 정상/비정상 확정으로 단정하지 않는다.
- baseline GET/asset traffic을 공격 incident로 과승격하지 않는다.
```

### 7.2 stage dry-run expected

expected:

```text
tests/expected/stage_dryrun_regression/h_r1_static_baseline_context.expected.json
```

MUST 기준:

```text
pipeline_counts.static_baseline_summary_count exists
pipeline_counts.static_baseline_summary_count == 1
policy_notes.static_baseline_summary_policy exists
policy_notes.static_baseline_summary_policy.success_rule contains conservative success rule
policy_notes.behavior_scope_separation_policy.non_merge_rule contains static_baseline_summaries
static_baseline_summaries.0.context_role == static_baseline_context
static_baseline_summaries.0.should_promote_to_candidate == false
static_baseline_summaries.0.interpretation_limit == static_content_not_visible_no_attack_inference
pipeline_counts.candidate_rows == 0
stage2 prompt includes static baseline context-only rule
stage2 report markdown includes Static baseline context
stage2 report markdown includes static baseline 해석 제한
stage2 report markdown includes asset_categories=
```

MUST_NOT 기준:

```text
- static file 존재 단정 금지
- robots/sitemap 내용 단정 금지
- JS 실행 단정 금지
- file exposure 단정 금지
- health 정상 여부 단정 금지
```

## 8. 분리 가능 범위

1차 코드 분리에서 허용되는 변경:

```text
- src/prepare/static_baseline.py 생성
- static baseline summary builder 함수 이동
- static baseline 전용 helper 이동
- src/prepare_llm_input.py에서 import / wrapper 추가
```

1차 코드 분리에서 금지되는 변경:

```text
- constants 이동
- crawler baseline summary 이동
- sensitive path summary 이동
- mixed baseline scanner summary 이동
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
static_baseline_summary_count == 1 유지
candidate_rows == 0 유지
h_r1_static_baseline_context expected 수정 없음
```

## 10. 실패 시 롤백 기준

아래 중 하나라도 발생하면 분리 커밋을 수정하거나 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- static_baseline_summary_count 변화
- candidate_rows 변화
- context_role 변화
- should_promote_to_candidate 변화
- interpretation_limit 변화
- asset_categories 출력 누락
- static file 존재 / robots-sitemap 내용 / JS 실행 / file exposure / health 정상 여부 단정 문구 발생
- crawler baseline과 static baseline 경계 변화
- import cycle 발생
```

## 11. 현재 결론

`static_baseline_summaries`는 auth behavior 이후의 다음 실제 코드 분리 후보로 검토 가능하다.

다만 실제 코드 분리 전에 아래 명령으로 함수명과 호출 위치를 먼저 확정한다.

```bash
grep -n "static_baseline_summaries\|build_static_baseline\|finalize_static_baseline\|STATIC_BASELINE" src/prepare_llm_input.py
```

그 결과가 명확하면 다음 코드는 아래 범위로 진행한다.

```text
src/prepare/static_baseline.py 생성
static baseline summary builder만 이동
constants는 이동하지 않음
crawler baseline summary는 이동하지 않음
expected는 수정하지 않음
```
