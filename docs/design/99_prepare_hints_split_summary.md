# 99_prepare_hints_split_summary

- 문서 상태: prepare hints split 완료 요약
- 기준 시점: 2026-05-04
- 목적: SQLi, XSS, file disclosure, traversal/CMDI hint 계열 1차 분리 결과를 정리하고, 계속 보류할 shared logic과 다음 후보를 고정한다.

관련 문서:

- hints split candidate review 내용은 [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)에 흡수
- [99_prepare_attack_hints_shared_policy_candidate_review.md](./99_prepare_attack_hints_shared_policy_candidate_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

prepare hints split 1차는 완료 상태로 본다.

완료 모듈:

```text
src/prepare/sqli_hints.py
src/prepare/xss_hints.py
src/prepare/file_disclosure_hints.py
src/prepare/traversal_cmdi_hints.py
```

이번 1차 hints split의 공통 원칙:

```text
- mechanical refactor만 수행
- behavior 변경 없음
- candidate/scoring/filtering 변경 없음
- false positive suppression 의미 변경 없음
- supporting_events 생성/연결 로직 변경 없음
- Stage2 reporter 수정 없음
- expected/test fixture 수정 없음
- output key 변경 없음
- policy wording 변경 없음
- Apache logs-only evidence boundary 유지
```

현재 시점에서는 바로 automation UA, shared attack/search policy, decoded attack hint logic을 코드 분리하지 않는다. 남은 영역은 candidate preservation, false positive suppression, Stage1/Stage2 wording guard와 직접 맞물릴 수 있으므로 별도 boundary 검토가 필요하다.

권장 다음 문서:

```text
docs/design/99_prepare_automation_shared_policy_split_candidate_review.md
```

또는 기존 후보 검토 문서인 아래 문서를 갱신한다.

```text
docs/design/99_prepare_attack_hints_shared_policy_candidate_review.md
```

## 2. 완료 모듈 요약

### 2.1 SQLi hints

기준 커밋:

```text
4bf7ee08f9bc47aac4dfe905609f4b251ca6e9bd
refactor: extract SQLi hint patterns
```

생성 파일:

```text
src/prepare/sqli_hints.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이동한 pattern/constants:

```text
SQLI_PATTERNS
SQLI_BOOLEAN_CONDITION_PATTERN
SQLI_BOOLEAN_TRUE_CONDITION_PATTERN
SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN
SQLI_PAREN_TERMINATION_PATTERN
SQLI_XCLOSE_PATTERN
SQLI_UNION_COLUMN_ENUM_PATTERN
SQLI_SCHEMA_ACCESS_PATTERN
SQLI_FROM_USERS_PATTERN
SQLI_COMMENT_PATTERN
REPEATED_QUOTE_PATTERN
EDUCATIONAL_SQL_SEARCH_TERMS
SUPPORTING_SQL_KEYWORDS
```

이동한 helper:

```text
detect_educational_sql_search_context
```

유지한 wrapper:

```text
detect_educational_sql_search_context
```

보류한 영역:

```text
detect_decoded_attack_hints
decoded variants helper/decoder 계열
candidate scoring/filtering 전반
possible_false_positive_sql_keyword_search verdict 결정 로직
strong_sqli_structure 판단 로직
supporting_events 생성/연결 로직
shared attack/search policy constants
XSS/file disclosure/traversal/CMDI patterns
```

유지한 evidence boundary:

```text
- DB query 결과 단정 금지
- SQL injection 성공 단정 금지
- Boolean blind true/false가 실제 DB 조건 결과라는 단정 금지
- Time-based delay가 DB sleep 성공이라는 단정 금지
- DB schema 노출, row 반환, 인증 우회 성공, 데이터 탈취 단정 금지
- status_code, response_body_bytes, duration_us, ttfb_us는 관찰 신호이지 DB 결과가 아님
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

### 2.2 XSS hints

기준 커밋:

```text
de89a90df2e4f6bdecc21a06c62f0dfaf284b7f7
refactor: extract XSS hint patterns
```

생성 파일:

```text
src/prepare/xss_hints.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이동한 pattern/constants:

```text
XSS_PATTERNS
SCRIPT_TAG_PATTERN
SCRIPT_TAG_CAPTURE_RE
EVENT_HANDLER_ASSIGNMENT_RE
JAVASCRIPT_PROTOCOL_RE
BROWSER_DATA_ACCESS_RE
EXTERNAL_NAVIGATION_RE
EXTERNAL_URL_RE
XSS_QUOTE_BREAKOUT_PATTERN
XSS_TAG_INJECTION_PATTERN
EDUCATIONAL_XSS_SEARCH_TERMS
EDUCATIONAL_XSS_KEYWORDS
```

보류한 영역:

```text
HTML_ENTITY_RE
detect_decoded_attack_hints
decoded variants helper/decoder 계열
append_html_entity_variants
build_html_entity_variants
build_html_entity_decoded_variant
candidate scoring/filtering 로직
browser execution / impact verdict logic
supporting_events 생성/연결 로직
shared attack/search policy constants
SQLi/file disclosure/traversal/CMDI patterns
```

특이사항:

```text
- `HTML_ENTITY_RE`는 `src/prepare_llm_input.py`에 유지
- `src/prepare/decoders.py`의 `HTML_ENTITY_RE`도 변경 없음
- HTML entity handling 통합 없음
```

유지한 evidence boundary:

```text
- 브라우저 실행 여부 단정 금지
- alert/document.cookie/localStorage/sessionStorage 접근 코드 실행 단정 금지
- 쿠키 탈취, 세션 탈취, 외부 전송, exfiltration 성공 단정 금지
- URL decoding이나 HTML entity decoding은 payload reconstruction이지 execution proof가 아님
- script tag, event handler, javascript: protocol, external URL은 payload structure 신호이지 impact confirmation이 아님
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

### 2.3 file disclosure hints

기준 커밋:

```text
2981dd11d96bd93e0973f0c0b8fa228092c2f0f4
refactor: extract file disclosure hint patterns
```

생성 파일:

```text
src/prepare/file_disclosure_hints.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이동한 pattern/constants:

```text
FILE_DISCLOSURE_PATTERNS
PHP_FILTER_CANONICAL_PATTERN
```

이동한 helper:

```text
detect_file_disclosure_hints
```

유지한 wrapper:

```text
detect_file_disclosure_hints
```

보류한 영역:

```text
suspicious_file_disclosure verdict 결정 로직
php_filter_wrapper_detected 기반 verdict 선택 로직
candidate scoring/filtering 로직
supporting_events 생성/연결 로직
Stage2 reporter
expected/test fixture
sensitive path probe 로직
DIR_PROBE_* constants
SENSITIVE_PATH_PROBE_* constants
shared attack/search policy constants
SQLi/XSS/traversal/CMDI patterns
```

유지한 Stage2/expected 계약:

```text
file_disclosure:php_filter_wrapper
file_disclosure:base64_source_intent
file_disclosure:resource_parameter
suspicious_file_disclosure
policy_notes.file_disclosure_policy
```

유지한 evidence boundary:

```text
- 파일 내용 노출 단정 금지
- response body 원문 추정 금지
- .env 노출 단정 금지
- phpinfo 노출 단정 금지
- server-status 노출 또는 차단 성공 단정 금지
- backup/config 파일 노출 단정 금지
- PHP source/config disclosure 성공 단정 금지
- status_code=200, content-type, response_body_bytes만으로 file exposure 확정 금지
- suspicious_file_disclosure는 의심 verdict이지 confirmed disclosure가 아님
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

### 2.4 traversal/CMDI hints

기준 커밋:

```text
fdedb2ec1627cb9ef0a6d5feb115c6d6fc965a95
refactor: extract traversal CMDI hint patterns
```

생성 파일:

```text
src/prepare/traversal_cmdi_hints.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이동한 pattern/constants:

```text
TRAVERSAL_PATTERNS
CMDI_PATTERNS
```

보류한 영역:

```text
AUTOMATION_UA_PATTERNS
detect_decoded_attack_hints
decoded variants helper/decoder 계열
candidate scoring/filtering 로직
normal search false-positive handling
attack category extraction 로직
reason_hints category normalization 로직
supporting_events 생성/연결 로직
Stage1/Stage2 reporter
expected/test fixture
shared attack/search policy constants
SQLi/XSS/file disclosure patterns
```

유지한 evidence boundary:

```text
- path traversal 성공 단정 금지
- 파일 읽기 성공 단정 금지
- /etc/passwd 또는 win.ini 내용 노출 단정 금지
- filesystem 존재 여부 단정 금지
- response body 원문 추정 금지
- command execution 성공 단정 금지
- whoami/id/cat/uname/curl/wget/bash/sh 실행 단정 금지
- shell access 또는 server compromise 단정 금지
- status_code=200, content-type, response_body_bytes만으로 file exposure 또는 command execution success 확정 금지
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

## 3. 공통으로 보류한 shared logic

아래 영역은 hint split 전반에서 공통으로 보류했다.

```text
detect_decoded_attack_hints
decoded variants helper/decoder 계열
candidate scoring/filtering 로직
false positive verdict 결정 로직
normal search false-positive handling
attack category extraction 로직
reason_hints category normalization 로직
supporting_events 생성/연결 로직
Stage1/Stage2 reporter
expected/test fixture
shared attack/search policy constants
AUTOMATION_UA_PATTERNS
```

보류 이유:

```text
- 여러 hint 계열이 공유한다.
- false positive suppression과 candidate preservation의 경계에 있다.
- candidate scoring/filtering과 supporting_events는 behavior 변경 위험이 크다.
- Stage1/Stage2 reporter와 expected fixture는 policy wording과 결과 계약을 고정한다.
- automation/tool UA는 lab-* / experiment-like UA guard와 직접 연결된다.
- shared module을 만들기 전에 import 방향과 ownership을 먼저 검토해야 한다.
```

## 4. 계속 보류할 constants/patterns

### 4.1 shared attack/search policy constants

```text
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
STRONG_ATTACK_HINT_PREFIXES
STRONG_ATTACK_HINTS
ATTACK_ENCODED_PAYLOAD_RE
```

현재 판단:

```text
DO_NOT_MOVE_YET
```

이유:

```text
- SQLi/XSS/file disclosure/traversal/CMDI 등 여러 hint 계열이 공유할 수 있음
- false positive suppression과 candidate preservation의 경계에 있음
- shared policy module을 별도로 검토하기 전에는 이동하지 않음
```

### 4.2 automation UA patterns

```text
AUTOMATION_UA_PATTERNS
```

현재 판단:

```text
KEEP_FOR_NOW
```

이유:

```text
- tool/lab UA 과해석 금지와 직접 연결됨
- sqlmap/nikto/nmap/curl/wget/python-requests UA는 trace aid일 수 있지만 성공 증거가 아님
- Stage1/Stage2 wording guard와 함께 관리해야 함
```

### 4.3 decoded attack hints

```text
detect_decoded_attack_hints
```

현재 판단:

```text
DO_NOT_MOVE_YET
```

이유:

```text
- SQLi, XSS, file disclosure, traversal, CMDI와 모두 연결됨
- decoders.py의 decoded variants와도 연결됨
- encoding descriptors와 hint generation을 동시에 다룸
- topic-specific module로 옮기면 경계가 흐려짐
```

## 5. 현재 상태 평가

현재까지의 hint split은 여기서 한 번 멈추는 것이 적절하다.

이유:

```text
- 주요 topic-specific pattern 모듈은 분리 완료됨
- 남은 항목은 shared policy, decoded reconstruction, automation UA wording guard처럼 behavior boundary가 더 민감함
- 추가 코드 분리는 새 shared module 설계나 Stage1/Stage2 wording guard 검토를 요구할 수 있음
```

바로 진행하지 않을 것:

```text
- AUTOMATION_UA_PATTERNS 코드 분리
- shared attack/search policy constants 이동
- detect_decoded_attack_hints 이동
- candidate scoring/filtering 이동
- false positive verdict 결정 로직 이동
- supporting_events 생성/연결 로직 이동
- Stage1/Stage2 reporter 변경
- expected/test fixture 변경
```

## 6. 권장 다음 작업

다음 작업은 추가 코드 분리가 아니라 shared boundary를 정리하는 후보 검토다.

권장 신규 문서:

```text
docs/design/99_prepare_shared_attack_policy_boundary_review.md
```

검토 대상:

```text
AUTOMATION_UA_PATTERNS
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
STRONG_ATTACK_HINT_PREFIXES
STRONG_ATTACK_HINTS
ATTACK_ENCODED_PAYLOAD_RE
detect_decoded_attack_hints
normal search false-positive handling
candidate preservation logic
```

검토할 항목:

```text
- shared module을 만들 필요가 있는지
- shared module 없이 prepare_llm_input.py에 유지하는 편이 나은지
- Stage1/Stage2 lab-* / tool UA wording guard와 연결되는지
- candidate scoring/filtering과 분리 가능한지
- false positive suppression과 분리 가능한지
- decoded variants와의 의존 방향
- Apache logs-only evidence boundary
```

## 7. 커밋/검증 메모

이 문서는 hints split summary 갱신용이다.

문서 작성 시 기대 변경 범위:

```text
docs/design/99_prepare_hints_split_summary.md
```

코드 변경은 없다.

문서 전용 커밋 후보:

```text
docs: update prepare hint split summary
```
