# 99_prepare_shared_attack_policy_boundary_review

- 문서 상태: shared attack/search policy boundary review
- 기준 시점: 2026-05-04
- 목적: prepare hint split 이후에도 `src/prepare_llm_input.py`에 남겨둔 automation UA, shared attack/search policy, decoded attack hint logic의 ownership과 분리 가능성을 검토하고, 다음 작업 방향을 정한다.

관련 문서:

- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_attack_hints_shared_policy_candidate_review.md](./99_prepare_attack_hints_shared_policy_candidate_review.md)
- hints split candidate review 기준은 [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)로 정리됐다
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)

## 1. 결론

남은 shared attack/search policy 영역은 당장 코드 분리하지 않는다.

현재 판단:

```text
AUTOMATION_UA_PATTERNS: KEEP_FOR_NOW
detect_decoded_attack_hints: KEEP_FOR_NOW
shared attack/search policy constants: KEEP_FOR_NOW
normal search false-positive handling: KEEP_FOR_NOW
candidate preservation logic: KEEP_FOR_NOW
```

이유:

```text
- 여러 hint 계열이 공유한다.
- candidate preservation과 false positive suppression 경계에 있다.
- Stage1/Stage2 lab-* / experiment-like / tool UA wording guard와 연결된다.
- decoded attack hint logic은 SQLi/XSS/file disclosure/traversal/CMDI 모두와 연결된다.
- shared module을 만들면 import 방향과 ownership 문제가 커질 수 있다.
```

따라서 현재 권장 다음 작업은 코드 분리가 아니라 문서 정리다.

권장 다음 작업:

```text
1. docs/planning/99_비교실험_후속개선_TODO.md에 hints split summary / shared policy boundary review 완료 반영
2. 필요하면 docs/design/99_prepare_module_split_round3_candidate_review.md 작성
3. 그 후 다음 코드 후보를 결정
```

## 2. 검토 대상

이번 문서의 검토 대상은 아래다.

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

이미 분리 완료된 topic-specific hint modules:

```text
src/prepare/sqli_hints.py
src/prepare/xss_hints.py
src/prepare/file_disclosure_hints.py
src/prepare/traversal_cmdi_hints.py
```

## 3. 공통 판단 기준

shared policy 후보는 아래 기준을 모두 만족하기 전까지 이동하지 않는다.

```text
- 한 owner module이 명확함
- SQLi/XSS/file disclosure/traversal/CMDI 중 특정 한 계열에 치우치지 않음
- false positive suppression 의미를 바꾸지 않음
- candidate preservation 의미를 바꾸지 않음
- decoded variant reconstruction 의미를 바꾸지 않음
- Stage1/Stage2 wording guard를 흔들지 않음
- import cycle이 발생하지 않음
- regression 실패 시 원인 추적이 쉬움
```

현재는 이 조건을 만족한다고 보기 어렵다.

## 4. Apache logs-only evidence boundary

shared attack/search policy는 아래 한계를 계속 유지해야 한다.

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

## 5. 후보 1: AUTOMATION_UA_PATTERNS

### 5.1 현재 판단

```text
KEEP_FOR_NOW
```

### 5.2 이유

```text
- automation/tool User-Agent는 trace aid 또는 weak context signal일 수 있다.
- sqlmap/nikto/nmap/curl/wget/python-requests UA만으로 공격 의도나 성공을 단정하면 안 된다.
- lab-* / experiment-like User-Agent guard와 직접 연결된다.
- Stage1/Stage2 carryover wording과 함께 관리해야 한다.
```

### 5.3 이동을 보류하는 이유

```text
- 단순 pattern module로 옮기면 tool UA가 공격 근거처럼 보일 위험이 있다.
- UA는 공격 성공 근거가 아니라 request metadata context다.
- Stage1/Stage2 prompt/report guard와 문서 기준이 먼저 고정되어야 한다.
```

### 5.4 향후 가능 조건

아래 조건을 만족하면 별도 문서로 검토한다.

```text
- automation UA가 scoring에 어떻게 반영되는지 grep으로 확인
- lab-* / experiment-like guard와 충돌하지 않음
- output wording이 tool identity/success를 단정하지 않음
- UA pattern 이동만으로 behavior가 바뀌지 않음
```

후보 문서:

```text
docs/design/99_prepare_automation_ua_hints_split_plan.md
```

현재는 작성하지 않는다.

## 6. 후보 2: shared attack/search policy constants

### 6.1 대상

```text
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
STRONG_ATTACK_HINT_PREFIXES
STRONG_ATTACK_HINTS
ATTACK_ENCODED_PAYLOAD_RE
```

### 6.2 현재 판단

```text
KEEP_FOR_NOW
```

### 6.3 이유

```text
- SQLi/XSS/file disclosure/traversal/CMDI 등 여러 hint 계열이 공유할 수 있다.
- normal search false-positive suppression과 strong attack preservation의 경계에 있다.
- shared policy module을 만들면 import 방향과 ownership 문제가 커질 수 있다.
- false positive suppression이 조금만 바뀌어도 candidate_rows / filtered_out 변화가 날 수 있다.
```

### 6.4 특히 보존해야 할 의미

```text
- normal search value는 과잉탐지를 줄이는 context일 뿐이다.
- strong attack hints는 false positive suppression 중에도 보존해야 할 수 있다.
- encoded payload marker는 decoding/reconstruction 관찰이지 execution proof가 아니다.
```

### 6.5 향후 가능 조건

아래 조건을 만족하면 별도 검토한다.

```text
- SEARCH_PARAM_NAMES 계열과 STRONG_ATTACK_* 계열의 사용처가 명확히 분리됨
- false positive suppression과 candidate preservation의 계약이 문서화됨
- shared module import 방향이 단방향으로 유지됨
- prepare/stage dry-run regression에서 candidate_rows / filtered_out 변화가 없음
```

후보 문서:

```text
docs/design/99_prepare_shared_attack_policy_split_plan.md
```

현재는 작성하지 않는다.

## 7. 후보 3: detect_decoded_attack_hints

### 7.1 현재 판단

```text
KEEP_FOR_NOW
```

### 7.2 이유

```text
- SQLi, XSS, file disclosure, traversal, CMDI와 모두 연결된다.
- decoders.py의 decoded variants와도 연결된다.
- encoding descriptors와 hint generation을 동시에 다룬다.
- topic-specific module로 옮기면 경계가 흐려진다.
```

### 7.3 이동을 보류하는 이유

```text
- decoded payload reconstruction은 exploit success 증거가 아니다.
- double-decoded SQLi, HTML entity decoded XSS, encoded payload trace는 여러 evidence boundary와 연결된다.
- expected fixture에서 encoding:* hint가 고정될 수 있다.
- decoding helper와 hint detector를 한꺼번에 움직이면 회귀 원인 추적이 어려워진다.
```

### 7.4 향후 가능 조건

아래 조건을 만족하면 별도 검토한다.

```text
- decoders.py와 detect_decoded_attack_hints의 역할 경계가 명확함
- SQLi/XSS/file disclosure/traversal/CMDI pattern dependencies를 안전하게 import할 수 있음
- encoding:* reason_hints 의미가 유지됨
- expected fixture에서 encoding hints 변화가 없음
```

후보 문서:

```text
docs/design/99_prepare_decoded_attack_hints_split_plan.md
```

현재는 작성하지 않는다.

## 8. 후보 4: normal search false-positive handling

### 8.1 현재 판단

```text
KEEP_FOR_NOW
```

### 8.2 이유

```text
- false positive suppression은 candidate_rows / filtered_out에 직접 영향을 준다.
- SQLi/XSS/file disclosure/traversal/CMDI 모든 hint 계열과 연결될 수 있다.
- normal search value와 strong attack preservation의 균형이 중요하다.
```

### 8.3 향후 가능 조건

아래 조건을 만족하면 별도 검토한다.

```text
- normal search false-positive 판단이 별도 함수/블록으로 안정적으로 분리되어 있음
- strong hint preservation rule이 문서화되어 있음
- candidate_rows / filtered_out 의미가 regression으로 고정되어 있음
```

후보 문서:

```text
docs/design/99_prepare_search_false_positive_policy_split_plan.md
```

현재는 작성하지 않는다.

## 9. 후보 5: candidate preservation logic

### 9.1 현재 판단

```text
KEEP_FOR_NOW
```

### 9.2 이유

```text
- candidate preservation은 scoring/filtering 결과와 직접 연결된다.
- shared attack hints와 false positive suppression 사이의 경계에 있다.
- behavior 변경 없이 분리하기 어렵다.
```

### 9.3 향후 가능 조건

아래 조건을 만족하면 별도 검토한다.

```text
- candidate preservation 조건이 함수 단위로 독립되어 있음
- scoring/filtering과 분리해도 output이 동일함
- expected fixture 또는 regression이 candidate preservation 의미를 충분히 고정함
```

현재는 작성하지 않는다.

## 10. 현 시점의 권장 결론

현 시점에서 추가 코드 분리는 보류한다.

권장 이유:

```text
- topic-specific hint pattern split은 충분히 진행됨
- 남은 후보는 policy/false-positive/decoded/candidate 경계가 강함
- 다음 작업은 코드 분리보다 TODO 정리와 전체 summary 갱신이 더 안전함
```

바로 하지 않을 것:

```text
- AUTOMATION_UA_PATTERNS 이동
- shared attack/search policy constants 이동
- detect_decoded_attack_hints 이동
- normal search false-positive handling 이동
- candidate preservation logic 이동
- Stage1/Stage2 reporter 변경
- expected/test fixture 변경
```

## 11. 권장 다음 작업

다음 작업은 planning TODO를 갱신해 현재 상태를 고정하는 것이다.

수정 대상:

```text
docs/planning/99_비교실험_후속개선_TODO.md
```

반영할 내용:

```text
- SQLi/XSS/file disclosure/traversal/CMDI hint split 완료
- shared attack/search policy boundary review 작성 완료
- automation UA / shared policy / decoded attack hints / false-positive handling은 보류
- 다음은 추가 코드 분리가 아니라 상태 정리 또는 필요 시 실제 LLM 샘플 관찰로 전환
```

문서 전용 커밋 후보:

```text
docs: review shared attack policy boundary
```
