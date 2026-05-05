# 99_stage2_prompt_compaction_plan

- 문서 상태: Stage2 prompt compaction plan
- 기준 시점: 2026-05-05
- 목적: `llm_stage2_reporter.py`의 `build_messages()` system prompt가 길고 반복이 많은 상태이므로, Apache logs-only guard를 약화하지 않으면서 섹션화·중복 제거·self-check 추가 방향을 정리한다.

관련 문서:

- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md)
- [../reviews/99_post_refactor_dry_run_spot_check.md](../reviews/99_post_refactor_dry_run_spot_check.md)
- [../reviews/99_post_refactor_LLM_output_spot_check.md](../reviews/99_post_refactor_LLM_output_spot_check.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

Stage2 prompt는 보강이 필요하지만, 방향은 단순 추가가 아니다.

현재 prompt는 이미 많은 Apache logs-only guard를 포함한다. 문제는 규칙 부족보다는 아래에 가깝다.

```text
- 중복 문장이 많음
- context-only summary별 guard가 길게 나열됨
- 새로운 summary/hint가 추가될 때마다 prompt가 계속 비대해짐
- 모델이 긴 prompt 중 일부 규칙을 놓칠 가능성이 있음
- 유지보수 시 어느 문장이 최종 authoritative rule인지 파악하기 어려움
```

따라서 권장 방향은 아래다.

```text
1. 기존 guard 의미를 유지한 채 섹션화
2. 중복 문구를 공통 rule로 끌어올림
3. evidence type별 금지/허용 표현을 압축
4. context-only summary 규칙을 공통 schema + 예외 규칙 형태로 정리
5. 마지막에 짧은 self-check 추가
6. 반복 문제가 실제 출력에서 확인될 때만 report lint 검토
```

## 2. non-goals

이번 계획에서 하지 않을 것:

```text
- Apache logs-only guard 약화
- Stage2 output schema 변경
- Stage2 reporter 정책 의미 변경
- expected/stage dry-run fixture 수정
- 실제 LLM 결과에 맞춘 과적합 wording 추가
- 특정 lab-* UA, 특정 IP, 특정 route, 특정 response size 기반 rule 추가
- report lint를 바로 fail 조건으로 도입
```

## 3. 현재 prompt의 유지해야 할 핵심 계약

Stage2 system prompt에서 반드시 유지할 계약:

```text
- raw POST body 원문을 본 것처럼 단정하지 않음
- response body 원문을 본 것처럼 단정하지 않음
- DB query 결과를 단정하지 않음
- 브라우저 실행 여부를 단정하지 않음
- status_code / response_body_bytes / content-type만으로 성공·침해·유출을 단정하지 않음
- known asset IP는 내부 테스트/자체 호출/운영 점검 가능성을 함께 고려
- lab-* UA나 tool-like UA를 공격 근거로 일반화하지 않음
- context-only summary는 incident 승격 또는 severity 상승의 단독 근거가 아님
- count scope가 다른 summary들을 하나의 사건 수처럼 합산하지 않음
- output은 schema-valid JSON이어야 함
- 자유서술은 한국어로 작성
```

## 4. 권장 prompt 구조

현재 긴 system prompt를 아래 구조로 재배치한다.

```text
A. Role and input boundary
B. Global Apache logs-only invariants
C. Evidence-specific interpretation rules
   - SQLi
   - XSS
   - file disclosure / PHP wrapper
   - traversal / CMDI
   - auth behavior
   - method behavior
   - protocol anomaly
D. Context-only summary rules
   - common context-only rule
   - static baseline
   - crawler baseline
   - sensitive path probe
   - mixed baseline scanner
   - probing sequence
   - ip behavior
   - auth/method/protocol summaries
E. Known asset / User-Agent / lab-* guard
F. Severity and key findings policy
G. Filtered-out / supporting events policy
H. Output schema and language policy
I. Final self-check
```

## 5. 압축 원칙

### 5.1 공통 invariant로 묶기

현재 여러 문단에 반복되는 아래 표현은 하나의 공통 rule로 묶는다.

```text
status_code, response_body_bytes, resp_content_type, text/html, application/json, 200/403/404/500 alone do not prove success, exposure, compromise, browser execution, DB result, or file content.
```

한국어 prompt에서는 아래처럼 압축 가능하다.

```text
status_code, response_body_bytes, resp_content_type, 200/403/404/500, text/html/application/json 응답은 모두 관찰 신호일 뿐이며, 단독으로 성공·침해·노출·브라우저 실행·DB 결과·파일 내용 반환을 증명하지 않는다.
```

### 5.2 context-only 공통 rule 만들기

현재 summary별로 반복되는 `context-only`, `should_promote_to_candidate=false`, `severity 상향 금지` 문구는 공통 rule로 올린다.

공통 rule 예시:

```text
모든 *_summaries 및 ip_behavior_aggregates는 context-only collection이다. should_promote_to_candidate=false 이면 해당 summary 안의 어떤 row도 summary 때문에 analysis_candidate 또는 incident로 승격된 것으로 해석하지 않는다. context-only collection은 key_findings severity를 올리는 단독 근거가 아니다.
```

그 다음 summary별로는 고유 금지만 짧게 둔다.

```text
- static: static file 존재, JS 실행, robots/sitemap 내용, health 정상 단정 금지
- crawler: 실제 crawler identity, robots/sitemap 내용, site structure, product/category page existence 단정 금지
- sensitive: WordPress 존재, admin access, .env/phpinfo/server-status/backup 노출 단정 금지
- mixed: baseline/static/crawler-like와 scanner-like를 하나의 성공 공격 체인으로 합치지 않음
- auth: login success/account takeover/credential stuffing/lockout 단정 금지
- method: upload/delete/XST/CORS success 단정 금지
- protocol: bypass/exploit/compromise success 단정 금지
```

### 5.3 evidence-specific rules는 금지/허용 쌍으로 정리

각 공격군은 아래 포맷으로 압축한다.

```text
SQLi:
- Allowed: SQLi-like structure, quote termination, boolean condition, comment marker, timing/byte delta observed.
- Forbidden: DB rows/schema/result, auth bypass, data exfiltration, sleep executed.
```

```text
XSS:
- Allowed: script-like/event-handler/javascript: pattern, browser-executable payload structure, possible exfil intent in text.
- Forbidden: browser execution, cookie theft, session hijack, external exfil success.
```

```text
File disclosure:
- Allowed: php://filter/source/config disclosure attempt pattern.
- Forbidden: file contents exposed, source disclosed, .env/phpinfo/server-status/backup exposed.
```

```text
Traversal/CMDI:
- Allowed: traversal-like path or command-like token observed.
- Forbidden: file read, command executed, shell access, server compromised.
```

## 6. 권장 self-check

prompt 마지막에는 짧은 self-check를 추가한다.

권장 문구:

```text
반환 전 최종 점검:
- SQLi 성공, DB 결과, 인증 우회, 데이터 탈취를 단정했는가?
- XSS 실행, 브라우저 실행, 쿠키/세션 탈취, 외부 전송 성공을 단정했는가?
- file/source disclosure 성공 또는 파일 내용 노출을 단정했는가?
- static file 존재, crawler authenticity, site structure, WordPress/admin access를 단정했는가?
- compromise, attack success, upload/delete success, CORS/XST success를 단정했는가?
- IP, User-Agent, lab-* UA, route, response size, status, content-type만으로 공격자/성공/침해를 단정했는가?

위 항목 중 하나라도 있으면 observed request pattern, attempt, context, inconclusive finding으로 바꿔라.
```

이 self-check는 길지 않으면서 실제 LLM 출력에서 반복되는 위험 표현을 마지막에 한 번 더 걸러준다.

## 7. 현재 prompt에서 특히 보존할 문구

현재 실제 LLM spot check에서 효과가 확인된 계열은 유지한다.

보존할 핵심:

```text
- known_asset IP는 내부 테스트/자체 호출/운영 점검 가능성 병기
- suspicious_file_disclosure는 시도 정황이지 confirmed disclosure가 아님
- php://filter는 PHP wrapper 기반 source/config disclosure attempt로 설명
- context-only summary는 severity 상승 단독 근거가 아님
- count scope가 다른 summary들을 합산하지 않음
- low_signal_fuzzing / low_signal_dir_probe는 후보 밖 탐색성 요청으로 유지
```

## 8. 현재 prompt에서 정리할 후보

중복 또는 정리 후보:

```text
- static/crawler/sensitive/mixed summary별 status_code/bytes/content-type 금지 문구 반복
- context-only / should_promote_to_candidate=false 반복
- count scope 설명의 긴 단일 문장
- file disclosure guard의 중복 문장
- XSS browser execution guard의 중복 문장
- auth/method/protocol context-only guard의 반복 구조
```

정리 방식:

```text
- 공통 rule로 승격
- summary별 예외/고유 금지만 유지
- 긴 문장은 bullet 또는 짧은 문장으로 분할
```

## 9. report lint와의 관계

prompt compaction과 report lint는 별개다.

현재 권장:

```text
- prompt compaction 먼저 검토
- 실제 LLM 출력에서 반복 문제가 확인될 때만 report lint 후보 검토
- report lint는 처음부터 fail이 아니라 warning-only로 시작
```

report lint 후보 문서:

```text
docs/design/99_stage2_report_lint_candidate_review.md
```

warning 후보 표현:

```text
성공했다
노출됐다
유출됐다
탈취됐다
실행됐다
침해됐다
우회 성공
파일 내용이 반환
WordPress가 존재
실제 crawler
공격자 IP
```

주의:

```text
단순 문자열만으로 fail 처리하면 정상적인 부정 문장도 잡힐 수 있으므로 처음에는 warning-only가 적절하다.
```

## 10. 구현 계획

권장 작업 순서:

```text
1. 현재 build_messages() system_prompt를 별도 섹션 단위로 재구성
2. 기존 금지 규칙을 삭제하지 말고 공통 rule로 병합
3. evidence-specific rule을 SQLi/XSS/file disclosure/traversal-CMDI/auth/method/protocol로 압축
4. context-only summary rule을 공통 rule + summary-specific rule로 압축
5. final self-check 추가
6. py_compile 실행
7. stage dry-run regression strict 실행
8. 실제 H R4 또는 E R2B spot check 1개로 wording 변화 확인
```

최소 검증:

```bash
python3 -m py_compile src/llm_stage2_reporter.py
python3 scripts/check_stage_dryrun_regression.py --strict
```

권장 검증:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

## 11. 금지 범위

이번 compaction에서 하지 않을 것:

```text
- output schema 변경
- report_input 구조 변경
- Stage1 결과 구조 변경
- severity policy 변경
- context-only policy 의미 변경
- expected fixture 수정
- candidate/scoring/filtering 변경
- prepare logic 변경
- provider/model 설정 변경
```

## 12. 성공 기준

성공 기준:

```text
- Stage2 prompt 길이와 중복이 줄어듦
- Apache logs-only guard 의미가 약화되지 않음
- stage dry-run regression 통과
- H R4 또는 E R2B 실제/드라이런 spot check에서 conservative wording 유지
- schema-valid JSON 반환 요구 유지
```

## 13. 다음 작업

이 문서 작성 후 다음 작업은 Codex에 Stage2 prompt compaction을 맡기는 것이다.

문서 전용 커밋 후보:

```text
docs: plan Stage2 prompt compaction
```

코드 작업 커밋 후보:

```text
refactor: compact Stage2 report prompt
```
