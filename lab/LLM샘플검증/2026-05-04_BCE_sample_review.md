# 2026-05-04 B/C/E LLM 샘플 검증

- 작성 기준일: 2026-05-04
- 문서 역할: 실제 LLM Stage1/Stage2 산출물을 B/C/E 대표 샘플 기준으로 수동 평가
- 기준 문서: `docs/reviews/99_llm_sample_review_plan.md`
- 검증 방식: 기존 Stage1/Stage2 산출물 수동 review
- 실제 LLM 재호출: 없음

---

## 1. 검증 목적

이번 검증의 목적은 탐지 강도를 높게 평가하는 것이 아니다.

핵심 질문은 다음이다.

```text
LLM이 Apache 로그만으로 말할 수 없는 성공/유출/실행을 단정하지 않는가?
candidate / supporting_events / false_positive_review_candidates / probing summaries를 과장하지 않는가?
known asset, 내부 테스트, false positive 가능성을 함께 적절히 병기하는가?
```

평가 항목은 5개이며 각 항목은 0~2점이다.

| 항목 | 설명 | 점수 |
|---|---|---:|
| 성공 단정 금지 | 성공/침해/유출을 단정하지 않음 | 0~2 |
| 로그 한계 반영 | POST body/response body/DB/browser 한계 반영 | 0~2 |
| context-only 준수 | summaries/aggregates/supporting_events를 과장하지 않음 | 0~2 |
| severity 적정성 | 로그 표면 근거에 맞는 severity | 0~2 |
| baseline/FP 가능성 병기 | known asset, baseline, UA spoof, tutorial/FP 가능성 병기 | 0~2 |

판정 기준:

```text
9~10점: 좋음
7~8점: 사용 가능하나 wording 개선 후보
5~6점: prompt/report 개선 필요
0~4점: 해석 원칙 위반, 즉시 수정 필요
```

---

## 2. 샘플 목록

이번 문서는 B/C/E 대표 샘플 3개를 본다.

| 샘플 | 목적 | 사용 산출물 |
|---|---|---|
| B R2B double encoded SQLi | double decode, temporal chain, educational SQL FP 분리 확인 | `op-security_2026-04-25_18-23-00_to_2026-04-25_18-29-00_kst_*` |
| C HTML entity XSS | HTML entity decode, XSS hint, tutorial/onerror FP 보존 확인 | `op-security_2026-04-25_21-30-00_to_2026-04-25_21-33-00_kst_*` |
| E R2B PHP wrapper / file disclosure | php://filter variant 일반화, direct config control 분리 확인 | `opencart_e_r2b_*` |

---

## 3. B R2B — Double Encoded SQLi

### 3.1 입력 요약

B R2B는 SQLi evasion, chain, educational SQL false-positive bait를 함께 확인하는 샘플이다.

주요 prepare / Stage1 input 요약:

```text
total_exported_rows=17
candidate_rows=15
supporting_events=2
filtered_out_rows=2
stage1 success/error=15/0
verdicts=suspicious_sqli 14, likely_false_positive 1
```

핵심 해석 대상:

```text
- double encoded payload가 candidate로 보존되었는가
- decoded_depth_2, double_decoded_sqli 같은 encoding hint가 실제 reasoning에 반영되었는가
- chain-step-02 같은 저신호 step이 supporting_events로 남아 context-only로 소비되는가
- educational SQL search가 candidate 과승격 없이 supporting context 또는 likely_false_positive로 분리되는가
```

### 3.2 Stage1 평가

OpenAI Stage1은 15개 candidate를 모두 처리했다.

평가:

```text
- SQLi candidate 14건과 likely_false_positive 1건으로 분리됐다.
- double encoded payload는 filtered out 되지 않고 candidate로 유지됐다.
- SQLi 성공, DB schema 유출, DB dump, 데이터 유출은 단정하지 않았다.
- Apache 로그 표면에서는 payload 구조와 오류 유발 정황만 말하고 결과 성공은 열어 두었다.
```

### 3.3 Stage2 평가

Stage2 보고서는 `/rest/products/search`에 집중된 반복 SQLi 시도, 인코딩/주석/대소문자 변형, known asset 가능성을 함께 적었다. 특히 “실제 침해 성공이나 데이터 유출은 확인되지 않았다”, “교육용 SQL 검색 문구는 공격으로 단정하지 않았다”는 점은 기준에 부합한다.

다만 `supporting_events` 자체를 본문에서 직접 길게 풀어 쓰기보다는 `filtered_out_breakdown` 중심으로 설명해, double decode / chain context의 구조적 강점을 Stage2가 더 적극적으로 언급하지는 못했다.

| 항목 | 점수 | 메모 |
|---|---:|---|
| 성공 단정 금지 | 2 | SQLi 성공, DB schema 유출, DB dump, 데이터 유출 단정 없음 |
| 로그 한계 반영 | 2 | 200/JSON, 500/text/html을 성공 근거로 쓰지 않고 추가 확인 필요로 제한 |
| context-only 준수 | 2 | chain 저신호 step과 educational search를 incident로 과승격하지 않음 |
| severity 적정성 | 2 | top incident high, supporting context는 info/보조 문맥으로 유지 |
| baseline/FP 가능성 병기 | 1 | known asset와 educational SQL 가능성은 적었지만 supporting_events 활용 설명은 더 명시적일 수 있음 |

총점: **9/10**

### 3.4 결론

B R2B는 통과로 본다.

```text
double encoded SQLi payload 보존,
decoded depth hint 반영,
educational SQL search 분리,
SQLi 성공 미단정
```

위 네 가지가 모두 유지됐다. Apache 로그 표면에서는 SQLi 시도와 payload 구조만 말할 수 있다는 정리도 적절하다.

### 3.5 개선 후보

```text
- Stage2가 decoded_depth_2, double_decoded_sqli, supporting_events를 더 직접적으로 설명하면 좋다.
- educational SQL search 중 supporting_events로 남은 항목은 false_positive_review_candidates와의 경계 설명을 더 분명히 할 수 있다.
- provider 비교 관점에서는 OpenAI보다 Anthropic이 chain/evasion 구조를 더 잘 드러냈다는 점을 후속 리뷰에 반영할 수 있다.
```

---

## 4. C HTML Entity XSS

### 4.1 입력 요약

C 샘플은 HTML entity encoded XSS 복원과 tutorial/onerror 검색의 false-positive 보존을 같이 보는 샘플이다.

주요 prepare / Stage1 input 요약:

```text
total_exported_rows=10
candidate_rows=9
supporting_events=0
false_positive_review_candidates=1
filtered_out_rows=1
stage1 success/error=9/0
verdicts=suspicious_xss 8, likely_false_positive 1
```

핵심 해석 대상:

```text
- HTML entity encoded XSS가 실제 XSS 구조로 복원되었는가
- entity 내부 # 문자가 SQL comment로 오탐되지 않았는가
- onerror, javascript:, document.cookie, external navigation/exfil intent가 구분되었는가
- C-10 tutorial/onerror 검색이 candidate로 과승격되지 않고 false positive review context로 남았는가
```

### 4.2 Stage1 평가

OpenAI Stage1은 9개 candidate를 모두 처리했다.

평가:

```text
- suspicious_xss 8건, likely_false_positive 1건으로 안정적으로 수렴했다.
- HTML entity payload를 XSS로 읽었고 SQL comment 오탐 정황은 보이지 않는다.
- document.cookie, javascript:, onerror, external navigation/exfil intent가 reasoning/evidence에 반영됐다.
- 브라우저 실행 성공, 쿠키 탈취 성공, 외부 전송 성공은 단정하지 않았다.
```

### 4.3 Stage2 평가

Stage2 보고서는 XSS 시도, 쿠키 접근 및 외부 전송 의도, known asset 가능성, 교육용 검색 질의를 함께 적었다. 특히 “Apache 로그만으로 브라우저 실행 성공, 쿠키 탈취, 외부 전송 성공은 확인되지 않았다”는 문장은 이번 샘플의 핵심 기준을 잘 지킨다.

또한 HTML entity encoded XSS를 별도 top incident로 과장하지 않고 XSS 계열의 우회성 payload로 설명했다. response body 원문이나 브라우저 실행 검증이 없다는 한계를 더 직접적으로 쓰면 더 좋았겠지만, 실제 wording은 충분히 보수적이다.

| 항목 | 점수 | 메모 |
|---|---:|---|
| 성공 단정 금지 | 2 | 브라우저 실행, 쿠키 탈취, 외부 전송 성공 단정 없음 |
| 로그 한계 반영 | 2 | 500/text/html, 200/application/json만으로 반사/실행 성공을 단정하지 않음 |
| context-only 준수 | 2 | tutorial/onerror 검색을 false positive review context로 남기고 과승격하지 않음 |
| severity 적정성 | 2 | script/document.cookie 계열 high~medium, tutorial 계열 low로 적절 |
| baseline/FP 가능성 병기 | 1 | known asset와 교육용 검색 가능성은 적절하나 false_positive_review_candidates 구조를 Stage2가 더 직접 인용하면 좋음 |

총점: **9/10**

### 4.4 결론

C 샘플도 통과로 본다.

```text
HTML entity XSS 복원,
SQL comment 오탐 억제,
XSS 의도 세분화,
tutorial/onerror 질의의 FP 보존,
실행 성공 미단정
```

위 항목이 모두 유지됐다. response body 원문과 브라우저 실행 검증이 없다는 한계를 더 명시하면 더 좋아질 수 있지만, 현재도 해석 원칙 위반은 없다.

### 4.5 개선 후보

```text
- Stage2가 false_positive_review_candidates=1을 더 직접적으로 언급하면 FP 보존 구조가 더 분명해진다.
- response body 원문 없음, browser execution 없음 한계를 신뢰도/한계 섹션에서 더 명시적으로 적을 수 있다.
- provider 비교 시 Anthropic은 campaign/test-flow 서술이 더 강하므로, 표현 강도 보정 기준을 후속 리뷰에 남길 수 있다.
```

---

## 5. E R2B — PHP Wrapper / File Disclosure

### 5.1 입력 요약

E R2B는 `php://filter` 기반 file disclosure intent와 direct config probing 분리를 확인하는 샘플이다.

주요 prepare / Stage1 input 요약:

```text
total_exported_rows=6
candidate_rows=4
supporting_events=0
probing_sequence_summaries=1
filtered_out_rows=2
stage1 success/error=4/0
verdicts=suspicious_path_traversal 4
```

핵심 해석 대상:

```text
- file=, path=, route= 기반 php://filter variant가 모두 candidate로 보존되었는가
- convert.base64-encode/resource=config.php, resource=admin/config.php가 source/config disclosure intent로 읽혔는가
- direct /config.php, /admin/config.php가 candidate로 과승격되지 않고 filtered/context로 남았는가
- 200/text/html, 큰 response_body_bytes를 성공 근거로 쓰지 않았는가
- Stage1 verdict taxonomy가 suspicious_file_disclosure가 아니라 suspicious_path_traversal로 수렴한 한계를 드러내는가
```

### 5.2 Stage1 평가

OpenAI Stage1은 4개 candidate를 모두 처리했다.

평가:

```text
- php://filter, resource=config.php, resource=admin/config.php, convert.base64-encode 의미를 인식했다.
- 실제 config/source 내용 노출 성공은 단정하지 않았다.
- direct /config.php, /admin/config.php는 candidate로 올리지 않았다.
- 다만 최종 verdict가 모두 suspicious_path_traversal로 수렴해 file disclosure taxonomy가 정식화되지 않았다.
- 일부 evidence_fields에 “user_agent가 실험용으로 보이는 문자열”이 들어가 있어, lab-* UA를 보조 근거로 소비한 표현은 개선 필요하다.
```

### 5.3 Stage2 평가

Stage2 보고서는 PHP 래퍼를 이용한 파일 노출 시도 정황, known asset IP, 200/text/html과 큰 body size의 한계, direct config path의 low_signal_dir_probe 분리를 비교적 잘 적었다. “실제 파일 내용 노출 성공은 확인되지 않는다”는 문구도 유지됐다.

강점은 wrapper variant 4건을 모두 file disclosure intent로 설명한 점이고, 약점은 top incident label이 `suspicious_path_traversal`이라 기법 분류가 덜 정확하다는 점이다. 또 Anthropic provider가 미실행이라 provider 비교는 불완전하다.

| 항목 | 점수 | 메모 |
|---|---:|---|
| 성공 단정 금지 | 2 | config/source 노출 성공, 유출 성공 단정 없음 |
| 로그 한계 반영 | 2 | 200/text/html, response_body_bytes 대형 응답을 성공 근거로 쓰지 않음 |
| context-only 준수 | 2 | `/config.php`, `/admin/config.php` direct access를 low_signal_dir_probe와 probing sequence context로 유지 |
| severity 적정성 | 1 | medium 유지 자체는 적절하지만 verdict taxonomy가 suspicious_path_traversal로 흡수되어 기법 적합성이 떨어짐 |
| baseline/FP 가능성 병기 | 1 | known asset 가능성은 적절하나 일부 Stage1 evidence에서 실험용 UA를 보조 근거로 삼은 표현은 감점 요소 |

총점: **8/10**

### 5.4 결론

E R2B는 사용 가능하지만 개선 후보로 본다.

```text
php://filter variant 보존,
config/admin config disclosure intent 설명,
direct config control의 과승격 억제,
성공 미단정
```

은 잘 지켰다. 반면 Stage1 verdict taxonomy가 아직 `suspicious_file_disclosure`를 표현하지 못하고, 일부 evidence에서 실험용 UA를 끌어온 점은 후속 수정 필요가 있다.

### 5.5 개선 후보

```text
- Stage1 verdict에 suspicious_file_disclosure 또는 suspicious_source_disclosure 계열을 정식화할 필요가 있다.
- Stage1 evidence/reasoning에서 lab-* UA를 탐지 근거처럼 쓰지 않도록 wording을 더 엄격히 제한해야 한다.
- probing_sequence_summaries는 유지하되 direct config probe를 file disclosure candidate로 과승격하지 않는 현재 정책은 유지하는 편이 맞다.
- Anthropic provider가 미실행이므로 provider 비교 문서는 아직 불완전하다고 명시해야 한다.
```

---

## 6. 전체 종합 평가

| 샘플 | 점수 | 판정 |
|---|---:|---|
| B R2B | 9/10 | 통과 |
| C HTML entity XSS | 9/10 | 통과 |
| E R2B PHP wrapper | 8/10 | wording 개선 후보 |

종합 판단:

```text
B/C/E 세 샘플 모두 Apache logs-only 원칙은 전반적으로 잘 지켰다.
B와 C는 표현 보강 여지는 있어도 실제 해석 위반은 크지 않다.
E는 file disclosure intent 자체는 잘 읽었지만 taxonomy와 일부 evidence wording이 아직 거칠다.
```

---

## 7. 후속 반영 후보

아래 문서에는 이번 턴에서 직접 반영하지 않는다. 후속 반영 후보만 정리한다.

### 7.1 `docs/reviews/99_A-H세트_중간정리.md`

```text
- 실제 LLM 샘플 검증 범위를 F/G/H 5개에서 B/C/E까지 확장
- B 9/10, C 9/10, E 8/10 추가
- E의 suspicious_file_disclosure taxonomy 한계와 lab-* UA wording 이슈를 실제 샘플 개선 후보로 기록
```

### 7.2 `docs/진행상황.md`

```text
- 실제 LLM 샘플 검증 상태에 B/C/E 3개 샘플 추가
- 현재 누적 샘플 검증 범위와 점수 요약 반영
```

### 7.3 `docs/planning/99_비교실험_후속개선_TODO.md`

```text
- P1/P2 후보로 suspicious_file_disclosure verdict 정식화
- Stage1/Stage2 wording에서 lab-* UA 근거 사용 억제
- supporting_events / false_positive_review_candidates / probing_sequence_summaries 설명 명확화
```
