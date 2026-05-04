# file disclosure verdict taxonomy 검토

- 작성 기준일: 2026-05-04
- 문서 역할: `suspicious_file_disclosure` verdict/taxonomy 상태와 남은 검증 조건 정리
- 관련 세트: E세트 R2/R2B PHP wrapper / file disclosure
- 관련 구조: `file_disclosure:*` reason hints, Stage1 verdict schema, Stage2 file disclosure policy, stage dry-run regression

---

## 1. 배경

B/C/E 실제 LLM 샘플 검증에서 E R2B PHP wrapper 샘플은 8/10으로 평가됐다.

핵심 평가는 다음이다.

```text
- php://filter variant 보존은 성공
- config/admin config disclosure intent 설명은 성공
- direct /config.php, /admin/config.php control 과승격 억제는 성공
- 실제 파일/source/config 노출 성공 단정은 없음
- 다만 Stage1 verdict taxonomy와 일부 wording은 개선 후보
```

특히 기존 E R2B 산출물에서는 `verdict_hint=suspicious_file_disclosure`와 Stage2 설명은 file/source/config disclosure에 가까웠지만, Stage1 최종 verdict가 `suspicious_path_traversal`로 수렴한 사례가 있었다.

이 문서는 그 문제를 기준으로 다음을 정리한다.

```text
1. 현재 코드에서 suspicious_file_disclosure taxonomy가 이미 존재하는지
2. 기존 산출물에서 보인 gap이 현재도 남은 문제인지
3. path traversal / file disclosure / direct config probe를 어떻게 구분할지
4. 바로 코드 수정이 필요한지, 아니면 재검증과 wording 관리가 우선인지
```

---

## 2. 현재 구현 상태

현재 `src/llm_stage1_classifier.py` 기준으로 `suspicious_file_disclosure`는 이미 Stage1 verdict schema에 포함되어 있다.

또한 Stage1 prompt/guidance에는 다음 원칙이 들어가 있다.

```text
- php://filter, convert.base64-encode, resource= 정황은 단순 ../ path traversal과 구분한다.
- file_disclosure:php_filter_wrapper, file_disclosure:base64_source_intent, file_disclosure:resource_parameter 힌트가 함께 있으면 suspicious_file_disclosure를 우선 고려한다.
- PHP wrapper 관련 verdict는 실제 파일 노출 성공이 아니라 source/config disclosure 시도로 표현한다.
- wrapper 구조 없이 /config.php 또는 /admin/config.php만 직접 접근한 단발 요청은 high-confidence file disclosure로 과승격하지 않는다.
```

추가로 현재 코드에는 LLM이 `suspicious_path_traversal`로 응답하더라도, PHP wrapper 핵심 hint 조합이 있으면 `suspicious_file_disclosure`로 보수 정규화하는 후처리도 존재한다.

```text
FILE_DISCLOSURE_WRAPPER_HINTS:
- file_disclosure:php_filter_wrapper
- file_disclosure:base64_source_intent
- file_disclosure:resource_parameter
```

따라서 현재 기준의 문제는 “verdict enum이 없다”가 아니라, 다음에 가깝다.

```text
- 과거 실제 E R2B 산출물에는 suspicious_path_traversal로 수렴한 흔적이 있다.
- 현재 코드 기준으로 같은 샘플을 다시 dry-run/실행하면 suspicious_file_disclosure가 안정적으로 반영되는지 확인해야 한다.
- Stage1/Stage2 자연어에서 lab-* UA를 공격 근거처럼 쓰지 않도록 wording guard가 필요했고, 1차 보강이 완료됐다.
```

---

## 3. Stage dry-run regression 상태

현재 `e_r2_php_wrapper.expected.json`은 다음을 고정한다.

```text
- Stage1 schema에 suspicious_file_disclosure verdict 포함
- Stage1 request payload가 php_filter_wrapper, base64_source_intent, resource_parameter hint를 보존
- Stage1 prompt가 php://filter marker를 언급
- suspicious_file_disclosure label guidance가 실제 파일 내용 반환 성공을 단정하지 않도록 제한
- Stage2 report input에 file_disclosure_policy 포함
- dry-run Markdown에 PHP wrapper 문맥과 보수적 파일 노출 설명 포함
- config.php 내용 노출, DB credential 유출, 공격 성공 단정 표현 금지
```

즉 구조적 회귀 기준은 이미 상당 부분 존재한다.

현재 남은 것은 실제 LLM 출력 또는 기존 산출물에서 다음이 재발하는지 확인하는 것이다.

```text
- wrapper 기반 source/config disclosure를 suspicious_path_traversal로만 설명
- 200/text/html 또는 큰 response_body_bytes를 실제 파일 노출 성공처럼 표현
- lab-* UA를 실험 식별자가 아니라 공격 근거처럼 사용
- direct /config.php 접근을 wrapper 기반 file disclosure와 같은 수준으로 과승격
```

추가로 현재 main 기준의 guard 반영 상태는 다음과 같다.

```text
- Stage1: llm_stage1_classifier.py 에서 User-Agent 를 요청 식별/trace aid 로만 사용하고, lab-* 또는 실험용 UA 를 공격 근거/탐지 근거로 쓰지 않도록 prompt guard 추가
- Stage2: llm_stage2_reporter.py 에서 User-Agent 를 보조 evidence 로만 사용하고, policy_notes.user_agent_interpretation_policy.stage1_carryover_rule 로 Stage1 evidence_fields/reasoning_summary 의 lab-* / 실험용 UA 자유서술 carry-over 재해석을 금지
- expected: e_r2_php_wrapper.expected.json 에 Stage1/Stage2 guard 존재 여부 확인 rule 추가
- regression: python3 scripts/check_stage_dryrun_regression.py --strict -> pass=12 warn=0 fail=0, python3 scripts/check_prepare_regression.py --strict -> pass=18 warn=0 fail=0 fixtures=18
```

---

## 4. taxonomy 구분 기준

### 4.1 suspicious_path_traversal

다음 구조가 중심이면 path traversal로 본다.

```text
../
..%2f
..\\
path escape
encoded traversal
/etc/passwd 직접 경로 이탈
```

해석 원칙:

```text
- 경로 이탈 시도 정황으로 설명한다.
- status_code=200 또는 text/html만으로 파일 노출 성공을 단정하지 않는다.
- fallback HTML 가능성을 병기한다.
```

### 4.2 suspicious_file_disclosure

다음 구조가 중심이면 file/source/config disclosure로 본다.

```text
php://filter
convert.base64-encode
resource=config.php
resource=admin/config.php
file=php://filter/...
path=php://filter/...
route=php://filter/...
```

해석 원칙:

```text
- source/config disclosure 시도로 설명한다.
- 단순 path traversal보다 더 구체적인 PHP wrapper/file-read primitive로 본다.
- 실제 config/source 내용 반환 성공은 Apache 로그만으로 단정하지 않는다.
- 200/text/html, 큰 response_body_bytes, 404는 모두 보조 지표일 뿐 성공/실패 확정 근거가 아니다.
```

### 4.3 direct config path control

다음 구조는 wrapper 기반 file disclosure와 구분한다.

```text
/config.php
/admin/config.php
/.env
/backup.zip
/phpinfo.php
```

해석 원칙:

```text
- direct sensitive path probe 또는 probing context로 우선 본다.
- response_body_bytes=0이면 파일 내용 노출 근거가 없다.
- PHP 파일은 실행되더라도 출력이 없을 수 있으므로 안전/성공 어느 쪽도 단정하지 않는다.
- 반복·sequence·sensitive path 문맥은 context-only summary로 보존한다.
```

---

## 5. E R2B 기준 재해석

E R2B의 요청 구성은 다음과 같다.

```text
E-14: file=php://filter/convert.base64-encode/resource=config.php
E-15: path=php://filter/convert.base64-encode/resource=admin/config.php
E-16: route=php://filter/resource=config.php
E-17a: /config.php
E-17b: /admin/config.php
```

현재 기준으로 기대되는 분류는 다음이다.

| 요청 | 기대 분류 | 이유 |
|---|---|---|
| E-14 | `suspicious_file_disclosure` | php wrapper + base64 source intent + resource=config.php |
| E-15 | `suspicious_file_disclosure` | php wrapper + base64 source intent + resource=admin/config.php |
| E-16 | `suspicious_file_disclosure` 또는 file disclosure 시도 문맥 | base64는 없지만 php wrapper + resource=config.php |
| E-17a | context-only / low-signal sensitive path probe | direct config path, wrapper 없음 |
| E-17b | context-only / low-signal sensitive path probe | direct admin config path, wrapper 없음 |

주의할 점:

```text
- E-14/E-15/E-16은 실제 파일 노출 성공이 아니라 source/config disclosure 시도다.
- E-17a/E-17b는 file disclosure candidate로 과승격하지 않는 현재 정책이 적절하다.
- Stage2는 wrapper candidate와 direct config control을 분리해서 설명해야 한다.
```

---

## 6. lab-* UA wording 문제

B/C/E 샘플 검증에서 E R2B의 일부 Stage1 evidence/reasoning은 `lab-*` User-Agent를 보조 근거처럼 소비한 점이 개선 후보로 남았다.

원칙은 다음이다.

```text
- lab-* UA는 실험 식별자 또는 trace aid로만 사용한다.
- lab-* UA 자체를 공격 근거, 악성 근거, 탐지 근거로 쓰지 않는다.
- 일반화 가능한 근거는 query_string, decoded payload, reason_hints, path, status_code, response_body_bytes, resp_content_type, sequence/context다.
```

권장 wording guard:

```text
User-Agent values may be used as request labels or trace aids.
Do not treat lab-* or experiment-like User-Agent values as attack evidence.
Prefer payload structure, decoded query, path, status, bytes, content-type, timing, and sequence context.
```

이 guard는 Stage1 prompt와 Stage2 prompt/policy 양쪽에 1차 반영 완료됐다.

현재 반영 상태 요약:

```text
- Stage1: user_agent 는 trace aid 로만 사용하고, lab-* / 실험용 UA 를 공격 근거나 탐지 근거로 쓰지 않도록 system prompt + instructions 보강
- Stage2: User-Agent 원문뿐 아니라 Stage1 evidence_fields/reasoning_summary 에 남은 lab-* / 실험용 UA 표현도 공격 증거나 severity 상향 근거로 재해석하지 않도록 policy + prompt carry-over guard 보강
```

---

## 7. 바로 코드 수정이 필요한가?

현재 판단은 다음이다.

```text
suspicious_file_disclosure verdict 자체는 이미 존재한다.
Stage1 schema, prompt, dry-run regression에도 반영되어 있다.
따라서 새 verdict taxonomy 도입 작업은 현재 필요하지 않다.
```

다만 아래 두 가지는 후속 검증 또는 소규모 wording 보강 후보로 남는다.

```text
1. 현재 main 기준으로 E R2B stage dry-run 또는 실제 Stage1 재실행 시 suspicious_file_disclosure가 안정적으로 나오는지 확인
2. Stage1/Stage2 lab-* UA guard는 1차 보강 완료 상태이므로, 이후에는 실제 LLM 출력에서 carry-over wording 재발 여부를 점검
```

---

## 8. 권장 다음 작업

### 8.1 우선 확인

```text
python3 scripts/check_stage_dryrun_regression.py --strict
```

확인할 항목:

```text
- e_r2_php_wrapper fixture 통과 여부
- suspicious_file_disclosure enum/guidance 유지
- file_disclosure_policy 유지
- Stage1/Stage2 lab-* UA guard 및 carry-over guard 유지
- dry-run Markdown에서 파일 노출 성공 단정 없음
```

### 8.2 선택 확인

기존 E R2B input을 현재 main 코드로 다시 Stage1 dry-run 또는 제한 실행한다.

목적:

```text
- 과거 E R2B 산출물의 suspicious_path_traversal 수렴 문제가 현재 코드에서도 재현되는지 확인
- 현재 코드의 normalization이 실제 결과에 반영되는지 확인
```

### 8.3 보강 후보

필요하면 다음만 소규모로 보강한다.

```text
- Stage1 prompt: lab-* UA는 trace aid일 뿐 attack evidence가 아니라고 명시
- Stage2 prompt/policy: experiment-like UA를 탐지 근거로 일반화하지 말라고 명시
- regression: lab-* UA가 evidence_fields에 공격 근거로 들어가지 않는지 dry-run 수준에서 검토 가능 여부 확인
```

---

## 9. 보류할 작업

현재는 하지 않는다.

```text
- 새로운 file disclosure verdict 추가
- suspicious_file_disclosure를 더 세분화한 suspicious_source_disclosure / suspicious_lfi 즉시 도입
- direct /config.php 접근을 candidate로 일괄 승격
- status_code=200 또는 response_body_bytes 대형 응답 기반 파일 노출 성공 판단
```

이유:

```text
- 현재 taxonomy는 suspicious_file_disclosure 하나로 충분하다.
- 세분화는 regression 영향과 Stage2 wording 부담이 크다.
- Apache logs-only 조건에서는 파일 내용 반환 성공을 확정할 수 없다.
```

---

## 10. 결론

현재 기준 결론은 다음이다.

```text
suspicious_file_disclosure verdict/taxonomy는 이미 현재 코드에 존재한다.
E R2B 샘플에서 확인된 문제는 새 taxonomy 부재라기보다 과거 산출물/wording/검증 상태의 문제에 가깝다.
따라서 지금은 새 verdict를 추가하지 말고, 현재 code + regression 기준으로 E R2B를 재확인한 뒤 lab-* UA wording guard만 소규모로 보강할지 판단한다.
```

권장 우선순위:

```text
1. stage dry-run regression strict 확인
2. 필요 시 E R2B 현재 코드 기준 재검증
3. lab-* UA wording guard 보강 여부 결정
4. 그 이후에만 Stage1/Stage2 prompt 소규모 수정
```
