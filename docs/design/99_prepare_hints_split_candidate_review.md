# 99_prepare_hints_split_candidate_review

- 문서 상태: prepare hint split 후보 검토
- 기준 시점: 2026-05-04
- 목적: context summary와 safe constants mini-move 이후 남은 hint 계열(SQLi, XSS, file disclosure, traversal/CMDI/automation, shared attack/search policy)을 실제 코드 분리 후보로 볼 수 있는지 비교하고, 다음 단계의 안전한 진행 순서를 정한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md)
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)

## 1. 결론

hint 계열은 바로 코드 분리하지 않는다.

이유:

```text
- SQLi/XSS/file disclosure/traversal/CMDI/automation hints는 candidate selection, false positive suppression, supporting context와 직접 연결될 수 있다.
- hint pattern 이동은 단순 mechanical refactor처럼 보이지만 evidence boundary와 wording guard를 흔들 수 있다.
- Apache logs-only 원칙상 DB 결과, 브라우저 실행, response body 원문, file exposure 성공을 볼 수 없으므로 각 hint별 해석 제한을 먼저 고정해야 한다.
```

현재 권장 순서:

```text
1. SQLi hints 후보를 가장 먼저 별도 split plan으로 검토
2. XSS hints는 decoded reconstruction과 browser execution 경계를 문서화한 뒤 검토
3. file disclosure hints는 suspicious_file_disclosure taxonomy와 sensitive path probe 경계를 재확인한 뒤 검토
4. traversal/CMDI/automation hints는 topic별 후보가 아니라 attack_hints/shared policy 경계 검토 후 결정
5. shared attack/search policy constants는 마지막까지 보류
```

다음 권장 문서:

```text
docs/design/99_prepare_sqli_hints_split_plan.md
```

단, 이 문서 작성 전 실제 grep으로 SQLi 관련 함수/패턴/호출 위치를 확인한다.

## 2. 공통 원칙

hint 계열 분리의 공통 원칙:

```text
- mechanical refactor만 수행
- behavior 변경 금지
- candidate/scoring/filtering 기준 변경 금지
- false positive suppression 의미 변경 금지
- supporting_events 생성/연결 로직 변경 금지
- output key 변경 금지
- policy wording 변경 금지
- expected/test fixture 수정 금지
- Stage2 reporter 수정 금지
- constants.py 생성 금지
- shared hint policy module을 무리하게 만들지 않음
- Apache logs-only 해석 원칙 유지
```

hint split 전 반드시 확인할 항목:

```text
- pattern/constants 이름
- detector/helper 함수명
- candidate scoring과 연결되는지
- likely_false_positive 또는 supporting context와 연결되는지
- Stage1/Stage2 prompt/report wording과 연결되는지
- expected fixture가 고정하는 key/hint가 있는지
- decoded variants와 결합되는지
- raw POST body, response body, DB result, browser execution을 추정하지 않는지
```

## 3. Apache logs-only evidence boundary

hint 계열은 아래 한계를 흔들면 안 된다.

```text
- raw POST body 내용 추정 금지
- response body 원문 추정 금지
- DB query 결과 추정 금지
- 브라우저 실행 여부 추정 금지
- 로그인 성공 / 계정 탈취 / credential stuffing 성공 / lockout 발동 단정 금지
- PUT 업로드 성공 / DELETE 삭제 성공 / TRACE/XST 성공 / CORS 취약점 성공 단정 금지
- protocol bypass / malformed request exploit success / 서버 침해 성공 단정 금지
- static file 존재 / robots/sitemap 내용 / JS 실행 / file exposure / health 정상 여부 단정 금지
- 실제 crawler 여부 / site structure / product/category page existence 단정 금지
- WordPress 존재 / admin access / .env/phpinfo/server-status/backup 노출 단정 금지
- status_code=200, text/html, response_body_bytes만으로 성공·침해·유출 확정 금지
```

실험환경 특화 rule도 계속 금지한다.

```text
- lab-* UA를 공격 근거로 쓰지 않음
- 특정 IP에 과적합하지 않음
- 특정 response size에 과적합하지 않음
- 특정 제품명에 과적합하지 않음
- 특정 route에 과적합하지 않음
```

## 4. 후보 비교 요약

| 후보 | 현재 판단 | 위험도 | 다음 문서 |
|---|---|---:|---|
| SQLi hints | 1순위 split plan 후보 | 높음 | `99_prepare_sqli_hints_split_plan.md` |
| XSS hints | 보류 후 검토 | 높음 | `99_prepare_xss_hints_split_plan.md` 또는 통합 plan 이후 |
| file disclosure hints | 보류 후 검토 | 높음 | `99_prepare_file_disclosure_hints_split_plan.md` |
| traversal/CMDI/automation hints | 보류 | 중간~높음 | topic boundary review 이후 |
| shared attack/search policy constants | 유지 | 높음 | shared policy module 검토 전 이동 금지 |

현재 추천은 SQLi부터다. 이유는 SQLi 관련 false positive suppression과 Round2 실험 기준이 이미 여러 문서에서 관리되고 있고, `educational SQL search` 같은 보수적 처리 기준이 구체화되어 있기 때문이다.

## 5. 후보 1: SQLi hints

### 5.1 관련 pattern/constants 후보

예상 후보:

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

### 5.2 예상 owner 후보

```text
src/prepare/sqli_hints.py
```

단, shared policy나 decoded variant helper까지 같이 이동하지 않는다.

### 5.3 현재 판단

```text
NEXT_SPLIT_PLAN_CANDIDATE
```

이유:

```text
- SQLi hint는 B세트/Round2에서 이미 evidence boundary가 비교적 구체화되어 있음
- xclose, boolean/time-based, educational SQL search FP 처리 기준이 문서화되어 있음
- 단, candidate scoring/false positive suppression과 연결될 가능성이 높으므로 바로 코드 분리하지 않고 split plan을 먼저 작성해야 함
```

### 5.4 SQLi evidence boundary

유지할 제한:

```text
- DB query 결과를 단정하지 않는다.
- SQL injection 성공을 단정하지 않는다.
- Boolean blind true/false가 실제 DB 조건 결과라고 단정하지 않는다.
- Time-based delay가 DB sleep 성공이라고 단정하지 않는다.
- status_code, response_body_bytes, duration_us, ttfb_us는 관찰 신호이지 DB 결과가 아니다.
- educational SQL search는 구조적 공격 신호가 약하면 false positive로 보수 처리한다.
```

허용되는 표현:

```text
- SQLi-like structure observed
- quote termination / boolean condition / comment marker observed
- possible SQLi candidate based on Apache log surface
- timing/byte delta observed, not DB result
- educational SQL search likely false positive, if applicable
```

금지 표현:

```text
- SQL injection succeeded
- DB returned rows
- authentication bypass succeeded
- data exfiltration confirmed
- database schema was exposed
- sleep() executed in database
```

### 5.5 split plan 작성 전 grep

권장 grep:

```bash
grep -n "SQLI_\|EDUCATIONAL_SQL_SEARCH_TERMS\|SUPPORTING_SQL_KEYWORDS\|REPEATED_QUOTE_PATTERN" src/prepare_llm_input.py src/prepare/*.py
```

추가 grep:

```bash
grep -n "detect_decoded_attack_hints\|educational.*sql\|sqli:\|possible_false_positive_sql_keyword_search" src/prepare_llm_input.py src/prepare/*.py
```

확인할 항목:

```text
- SQLi pattern 사용 위치
- decoded variants와 결합 여부
- false positive suppression 조건
- supporting_events와 연결 여부
- candidate scoring에 직접 영향을 주는지
- Stage1/Stage2 carryover와 연결되는지
```

## 6. 후보 2: XSS hints

### 6.1 관련 pattern/constants 후보

예상 후보:

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
HTML_ENTITY_RE
```

### 6.2 예상 owner 후보

```text
src/prepare/xss_hints.py
```

단, decoders.py 또는 shared attack policy와 강하게 엮이면 보류한다.

### 6.3 현재 판단

```text
PLAN_AFTER_SQLI
```

이유:

```text
- XSS는 URL/HTML/entity decoding과 결합된다.
- payload reconstruction과 browser execution success를 엄격히 분리해야 한다.
- false positive educational XSS query 처리와 연결될 수 있다.
```

### 6.4 XSS evidence boundary

유지할 제한:

```text
- 브라우저 실행 여부를 단정하지 않는다.
- alert/document.cookie/exfil 코드가 실제 실행되었다고 단정하지 않는다.
- 쿠키 탈취, 세션 탈취, 외부 전송 성공을 단정하지 않는다.
- URL/HTML entity decoding은 reconstruction이지 execution proof가 아니다.
```

허용되는 표현:

```text
- XSS-like payload structure observed
- decoded script-like payload candidate
- browser-executable pattern, not browser execution evidence
- possible exfil intent in payload text, not exfil success
```

금지 표현:

```text
- XSS executed
- cookie was stolen
- session was hijacked
- browser ran the script
- exfiltration succeeded
```

### 6.5 split plan 작성 전 grep

권장 grep:

```bash
grep -n "XSS_\|SCRIPT_TAG\|EVENT_HANDLER\|JAVASCRIPT_PROTOCOL\|BROWSER_DATA_ACCESS\|EXTERNAL_NAVIGATION\|EXTERNAL_URL\|EDUCATIONAL_XSS\|HTML_ENTITY_RE" src/prepare_llm_input.py src/prepare/*.py
```

확인할 항목:

```text
- decoders.py와 의존 경계
- decoded variants 사용 위치
- educational query FP 처리
- impact wording과 연결되는지
- Stage2 report wording guard와 연결되는지
```

## 7. 후보 3: file disclosure hints

### 7.1 관련 pattern/constants 후보

예상 후보:

```text
FILE_DISCLOSURE_PATTERNS
PHP_FILTER_CANONICAL_PATTERN
```

관련 경계:

```text
suspicious_file_disclosure verdict
sensitive_path_probe_summaries
DIR_PROBE_* constants
response_body_bytes / content-type / status_code interpretation
```

### 7.2 예상 owner 후보

```text
src/prepare/file_disclosure_hints.py
```

단, sensitive path probe와 분리 기준이 명확해야 한다.

### 7.3 현재 판단

```text
PLAN_AFTER_SQLI_OR_XSS
```

이유:

```text
- suspicious_file_disclosure verdict와 연결됨
- file disclosure는 response body 원문/파일 내용/실제 노출 여부를 Apache 로그만으로 볼 수 없음
- sensitive path probe와 경계가 겹침
```

### 7.4 file disclosure evidence boundary

유지할 제한:

```text
- 파일 내용 노출을 단정하지 않는다.
- response body 원문을 추정하지 않는다.
- .env/phpinfo/server-status/backup 노출을 단정하지 않는다.
- status_code=200, content-type, response_body_bytes만으로 file exposure를 확정하지 않는다.
- suspicious_file_disclosure는 의심 verdict이지 confirmed disclosure가 아니다.
```

허용되는 표현:

```text
- file disclosure-like request pattern observed
- php://filter-style wrapper observed
- suspicious_file_disclosure candidate
- possible sensitive file access attempt, not confirmed exposure
```

금지 표현:

```text
- file was disclosed
- .env contents leaked
- phpinfo was exposed
- backup archive was downloaded
- server-status data was exposed
```

### 7.5 split plan 작성 전 grep

권장 grep:

```bash
grep -n "FILE_DISCLOSURE_\|PHP_FILTER_CANONICAL_PATTERN\|suspicious_file_disclosure\|file_disclosure" src/prepare_llm_input.py src/prepare/*.py src/llm_stage2_reporter.py tests/expected -R
```

확인할 항목:

```text
- suspicious_file_disclosure verdict와 연결 여부
- sensitive path probe와의 경계
- response bytes/content-type/status 사용 방식
- expected fixture가 고정하는 wording/key
- Stage2 reporter 출력 문구
```

## 8. 후보 4: traversal/CMDI/automation hints

### 8.1 관련 pattern/constants 후보

```text
TRAVERSAL_PATTERNS
CMDI_PATTERNS
AUTOMATION_UA_PATTERNS
```

### 8.2 현재 판단

```text
KEEP_FOR_NOW
```

이유:

```text
- traversal/CMDI는 candidate scoring과 직접 연결될 가능성이 높음
- command execution 성공이나 filesystem read 성공을 단정하면 안 됨
- automation UA는 lab-* / tool UA 과해석 금지와 연결됨
- topic별 module로 나눌지 shared attack_hints.py로 둘지 먼저 결정해야 함
```

### 8.3 evidence boundary

유지할 제한:

```text
- path traversal 성공 단정 금지
- 파일 읽기 성공 단정 금지
- command execution 성공 단정 금지
- automation UA만으로 공격 확정 금지
- lab-* UA 또는 tool UA를 공격 근거로 일반화하지 않음
```

## 9. shared attack/search policy constants

관련 후보:

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
- 여러 hint 계열이 공유한다.
- false positive suppression과 candidate preservation의 경계에 있다.
- shared policy module을 만들면 import 방향과 ownership 문제가 커질 수 있다.
- SQLi/XSS/file_disclosure split plan 이후에 재검토한다.
```

## 10. 다음 작업

다음 작업은 SQLi hints split plan 작성이다.

권장 문서:

```text
docs/design/99_prepare_sqli_hints_split_plan.md
```

작성 전 확인 명령:

```bash
grep -n "SQLI_\|EDUCATIONAL_SQL_SEARCH_TERMS\|SUPPORTING_SQL_KEYWORDS\|REPEATED_QUOTE_PATTERN" src/prepare_llm_input.py src/prepare/*.py

grep -n "detect_decoded_attack_hints\|educational.*sql\|sqli:\|possible_false_positive_sql_keyword_search" src/prepare_llm_input.py src/prepare/*.py
```

SQLi split plan에서 결정할 것:

```text
- 이동 대상 pattern/constants
- 이동 대상 helper 함수
- false positive suppression과 분리 가능한지
- decoded variants와의 의존 방향
- supporting_events와의 결합 여부
- candidate/scoring/filtering 변경 없이 이동 가능한지
- Apache logs-only SQLi evidence boundary
```

문서 전용 커밋 후보:

```text
docs: review prepare hint split candidates
```
