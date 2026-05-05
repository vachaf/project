# 99_prepare_attack_hints_shared_policy_candidate_review

- 문서 상태: prepare attack hints / shared policy 후보 검토
- 기준 시점: 2026-05-04
- 목적: SQLi/XSS/file disclosure hint 1차 분리 이후 남은 traversal/CMDI/automation hints와 shared attack/search policy constants, decoded attack hint logic을 실제 코드 분리 후보로 볼 수 있는지 비교하고, 다음 진행 순서를 정한다.

관련 문서:

- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_sqli_hints_split_plan.md](./99_prepare_sqli_hints_split_plan.md)
- [99_prepare_xss_hints_split_plan.md](./99_prepare_xss_hints_split_plan.md)
- [99_prepare_file_disclosure_hints_split_plan.md](./99_prepare_file_disclosure_hints_split_plan.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

남은 attack hint / shared policy 영역은 바로 코드 분리하지 않는다.

현재 권장 순서:

```text
1. traversal/CMDI/automation patterns의 실제 사용 위치를 grep으로 확인
2. shared attack/search policy constants의 사용 위치를 grep으로 확인
3. detect_decoded_attack_hints가 SQLi/XSS/file_disclosure/traversal/CMDI와 어떻게 결합되는지 확인
4. 그 결과를 바탕으로 topic-specific split plan 또는 shared policy 보류 여부를 결정
```

현재 판단:

```text
- traversal/CMDI/automation hints: 후보 검토 가능, 단 scoring/supporting 연결 확인 전 코드 분리 금지
- shared attack/search policy constants: 계속 보류
- detect_decoded_attack_hints: 계속 보류
```

다음에 바로 쓸 수 있는 split plan 후보는 아직 확정하지 않는다. 먼저 grep 결과를 확인해야 한다.

## 2. 검토 대상

이번 후보 검토 대상:

```text
TRAVERSAL_PATTERNS
CMDI_PATTERNS
AUTOMATION_UA_PATTERNS
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
STRONG_ATTACK_HINT_PREFIXES
STRONG_ATTACK_HINTS
ATTACK_ENCODED_PAYLOAD_RE
detect_decoded_attack_hints
```

관련될 수 있는 추가 shared logic:

```text
get_matching_pattern_names
has_encoded_payload_marker
normal search false-positive handling
candidate score accumulation
supporting_events 생성/연결 로직
reason_hints category extraction
```

## 3. 공통 원칙

이 영역의 분리 원칙:

```text
- mechanical refactor only
- behavior 변경 금지
- candidate/scoring/filtering 변경 금지
- false positive suppression 의미 변경 금지
- supporting_events 생성/연결 로직 변경 금지
- decoded variants 의미 변경 금지
- output key 변경 금지
- policy wording 변경 금지
- expected/test fixture 수정 금지
- Stage2 reporter 수정 금지
- constants.py 생성 금지
- shared module 신설은 grep/의존성 확인 전 금지
```

## 4. Apache logs-only evidence boundary

남은 attack hint 계열은 아래 한계를 계속 지켜야 한다.

```text
- path traversal 성공 단정 금지
- 파일 읽기 성공 단정 금지
- command execution 성공 단정 금지
- shell/webshell 실행 성공 단정 금지
- automation/tool User-Agent만으로 공격 확정 금지
- lab-* UA를 공격 근거로 일반화하지 않음
- decoded payload reconstruction을 execution proof로 사용하지 않음
- status_code=200, content-type, response_body_bytes만으로 성공/침해/유출 확정 금지
```

특히 아래 표현은 금지한다.

```text
- traversal succeeded
- file was read
- command executed
- shell access obtained
- server compromised
- sqlmap/nikto/nmap UA proves attack success
- decoded payload executed
```

허용되는 표현:

```text
- traversal-like pattern observed
- command-injection-like token observed
- automation/tool-like user agent observed
- encoded payload structure observed
- scanner-like request context, not success evidence
```

## 5. 후보 1: traversal hints

### 5.1 대상 후보

```text
TRAVERSAL_PATTERNS
```

예상 owner 후보:

```text
src/prepare/traversal_hints.py
```

또는 CMDI/automation과 함께:

```text
src/prepare/attack_hints.py
```

### 5.2 현재 판단

```text
GREP_FIRST
```

이유:

```text
- traversal patterns는 candidate scoring과 직접 연결될 가능성이 높다.
- file disclosure와 경계가 일부 겹칠 수 있다.
- path traversal-like 구조는 파일 읽기 성공과 다르므로 evidence boundary가 중요하다.
```

### 5.3 분리 전 확인할 것

권장 grep:

```bash
grep -n "TRAVERSAL_PATTERNS\|traversal:" src/prepare_llm_input.py src/prepare/*.py
```

확인 항목:

```text
- traversal pattern 사용 위치
- candidate scoring과의 연결
- reason_hints 이름
- file disclosure 또는 sensitive path probe와의 경계
- decoded variants와의 연결
- expected fixture에서 traversal hint를 고정하는지 여부
```

### 5.4 evidence boundary

유지할 제한:

```text
- path traversal 성공 단정 금지
- 파일 읽기 성공 단정 금지
- /etc/passwd 또는 win.ini 내용 노출 단정 금지
- decoded ../ 구조는 request text 관찰이지 filesystem access proof가 아님
```

## 6. 후보 2: CMDI hints

### 6.1 대상 후보

```text
CMDI_PATTERNS
```

예상 owner 후보:

```text
src/prepare/cmdi_hints.py
```

또는 traversal/automation과 함께:

```text
src/prepare/attack_hints.py
```

### 6.2 현재 판단

```text
GREP_FIRST
```

이유:

```text
- CMDI patterns는 command execution 성공 단정 위험이 크다.
- candidate scoring과 직접 연결될 가능성이 높다.
- decoded payload와 연결될 수 있다.
```

### 6.3 분리 전 확인할 것

권장 grep:

```bash
grep -n "CMDI_PATTERNS\|cmdi:" src/prepare_llm_input.py src/prepare/*.py
```

확인 항목:

```text
- CMDI pattern 사용 위치
- candidate scoring과의 연결
- reason_hints 이름
- decoded variants와의 연결
- supporting_events와의 연결 여부
```

### 6.4 evidence boundary

유지할 제한:

```text
- command execution 성공 단정 금지
- whoami/id/cat/uname 등이 실행되었다고 단정하지 않음
- shell access 또는 server compromise 단정 금지
- command-like token은 request text 구조 관찰일 뿐임
```

## 7. 후보 3: automation UA hints

### 7.1 대상 후보

```text
AUTOMATION_UA_PATTERNS
```

예상 owner 후보:

```text
src/prepare/automation_hints.py
```

또는 shared attack hints:

```text
src/prepare/attack_hints.py
```

### 7.2 현재 판단

```text
KEEP_FOR_NOW
```

이유:

```text
- automation UA는 lab-* / tool UA 과해석 금지와 직접 연결된다.
- sqlmap/nikto/nmap/curl/wget UA는 trace aid일 수 있지만 성공 증거가 아니다.
- User-Agent 기반 판단은 Stage1/Stage2 wording guard와 함께 관리해야 한다.
```

### 7.3 분리 전 확인할 것

권장 grep:

```bash
grep -n "AUTOMATION_UA_PATTERNS\|automation:ua\|sqlmap\|nikto\|nmap\|python-requests" src/prepare_llm_input.py src/prepare/*.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py
```

확인 항목:

```text
- UA pattern 사용 위치
- lab-* / experiment-like UA guard와의 경계
- candidate scoring에 반영되는지 여부
- Stage1/Stage2 wording과 연결되는지 여부
```

### 7.4 evidence boundary

유지할 제한:

```text
- tool UA만으로 공격 확정 금지
- tool UA만으로 공격 성공 확정 금지
- lab-* UA를 공격 근거로 일반화하지 않음
- UA는 trace aid 또는 context signal일 뿐임
```

## 8. 후보 4: shared attack/search policy constants

### 8.1 대상 후보

```text
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
STRONG_ATTACK_HINT_PREFIXES
STRONG_ATTACK_HINTS
ATTACK_ENCODED_PAYLOAD_RE
```

예상 owner 후보는 아직 정하지 않는다.

가능한 후보:

```text
src/prepare/attack_policy.py
src/prepare/search_false_positive_policy.py
src/prepare/shared_attack_hints.py
```

### 8.2 현재 판단

```text
DO_NOT_MOVE_YET
```

이유:

```text
- SQLi/XSS/file disclosure/traversal/CMDI 등 여러 hint 계열이 공유할 수 있다.
- normal search false-positive suppression과 strong attack preservation의 경계에 있다.
- candidate preservation과 false positive filtering 의미를 바꾸기 쉽다.
- shared module을 만들면 import 방향과 ownership 문제가 커질 수 있다.
```

### 8.3 분리 전 확인할 것

권장 grep:

```bash
grep -n "SEARCH_PARAM_NAMES\|NORMAL_SEARCH_VALUE_RE\|NORMAL_SEARCH_ATTACK_TEXT_RE\|STRONG_ATTACK_HINT_PREFIXES\|STRONG_ATTACK_HINTS\|ATTACK_ENCODED_PAYLOAD_RE" src/prepare_llm_input.py src/prepare/*.py
```

확인 항목:

```text
- normal search false-positive 처리와의 연결
- strong attack hint preservation과의 연결
- SQLi/XSS/file disclosure/traversal/CMDI 중 어느 계열이 참조하는지
- candidate filtering에 직접 영향을 주는지
```

## 9. 후보 5: detect_decoded_attack_hints

### 9.1 대상 후보

```text
detect_decoded_attack_hints
```

### 9.2 현재 판단

```text
DO_NOT_MOVE_YET
```

이유:

```text
- SQLi, XSS, traversal, file disclosure, CMDI와 모두 연결될 수 있다.
- decoders.py의 decoded variants와도 연결된다.
- encoding descriptors와 hint generation을 동시에 다룬다.
- 한 topic module로 옮기면 경계가 흐려진다.
```

### 9.3 분리 전 확인할 것

권장 grep:

```bash
grep -n "def detect_decoded_attack_hints\|detect_decoded_attack_hints\|encoding:double_decoded\|encoding:html_entity" src/prepare_llm_input.py src/prepare/*.py tests/expected -R
```

확인 항목:

```text
- SQLi/XSS/file_disclosure/traversal/CMDI pattern 의존성
- decoders.py와의 의존 방향
- expected fixture에서 encoding hint를 고정하는지 여부
- candidate scoring과 연결되는지 여부
```

## 10. 후보 비교 결론

현재 우선순위:

```text
1. traversal/CMDI patterns를 함께 grep으로 확인
2. automation UA는 Stage1/Stage2 wording guard와 함께 보류
3. shared attack/search policy constants는 보류
4. detect_decoded_attack_hints는 보류
```

다음에 바로 코드 분리를 할 후보는 아직 확정하지 않는다.

먼저 해야 할 확인:

```bash
grep -n "TRAVERSAL_PATTERNS\|CMDI_PATTERNS\|traversal:\|cmdi:" src/prepare_llm_input.py src/prepare/*.py

grep -n "AUTOMATION_UA_PATTERNS\|automation:ua\|sqlmap\|nikto\|nmap\|python-requests" src/prepare_llm_input.py src/prepare/*.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py

grep -n "SEARCH_PARAM_NAMES\|NORMAL_SEARCH_VALUE_RE\|NORMAL_SEARCH_ATTACK_TEXT_RE\|STRONG_ATTACK_HINT_PREFIXES\|STRONG_ATTACK_HINTS\|ATTACK_ENCODED_PAYLOAD_RE" src/prepare_llm_input.py src/prepare/*.py

grep -n "def detect_decoded_attack_hints\|detect_decoded_attack_hints\|encoding:double_decoded\|encoding:html_entity" src/prepare_llm_input.py src/prepare/*.py tests/expected -R
```

## 11. 권장 다음 작업

이 문서 작성 후 다음 작업은 grep 확인이다.

그 결과에 따라 아래 중 하나를 선택한다.

```text
A. docs/design/99_prepare_traversal_cmdi_hints_split_plan.md 작성
B. docs/design/99_prepare_automation_ua_hints_split_plan.md 작성
C. shared attack/search policy는 보류 유지
D. detect_decoded_attack_hints는 보류 유지
```

현재 예비 추천은 A다.

이유:

```text
- traversal/CMDI patterns는 topic-specific hint module로 분리할 가능성이 automation/shared policy보다 높다.
- 단, candidate scoring과 직접 연결되면 pattern/constants만 이동하고 scoring은 유지해야 한다.
```

문서 전용 커밋 후보:

```text
docs: review attack hints shared policy candidates
```
