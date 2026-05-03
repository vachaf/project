# LLM 샘플 검증 계획

- 작성 기준일: 2026-05-03
- 문서 역할: 실제 LLM Stage1/Stage2 산출물을 고정 샘플 기준으로 수동 검토하기 위한 계획
- 적용 범위: `prepare -> Stage1 -> Stage2` 산출물
- 비적용 범위: 자동 채점형 LLM 품질 평가, 모델 성능 벤치마크, 공격 성공 판정

---

## 1. 목적

이 문서는 실제 LLM Stage1/Stage2 결과가 Apache 로그 기반 분석 원칙을 잘 지키는지 검토하기 위한 기준을 정의한다.

검증의 핵심은 “공격을 얼마나 세게 탐지했는가”가 아니라 다음이다.

```text
LLM이 Apache 로그만으로 말할 수 있는 한계를 지키며,
후보 / context / baseline / false positive 가능성을 과장 없이 설명하는가?
```

즉, 이 검증은 정답 맞히기 테스트가 아니라 **보수적 해석 품질 검증**이다.

---

## 2. 비목표

이번 검증은 다음을 목표로 하지 않는다.

- 실제 공격 성공 여부 판정
- DB 유출 / 파일 유출 / XSS 실행 / 로그인 성공 검증
- response body 원문 기반 검증
- raw POST body 기반 검증
- 브라우저 실행 여부 검증
- 모델별 절대 성능 순위 산정
- 자동화된 최종 PASS/FAIL 채점

LLM 출력은 비결정적이므로, 1차 검증은 고정 샘플과 평가표 기반 수동 review로 진행한다.

---

## 3. 검증 대상

검증 대상은 다음 산출물이다.

```text
*_llm_input.json
*_stage1_results.json
*_stage2_report_input.json
*_stage2_report.md
```

필요할 경우 보조로 다음도 확인한다.

```text
*_analysis_candidates.json
*_filtered_out_rows.json
*_noise_summary.json
*_stage1_errors.json
*_stage2_report.json
```

raw export JSON은 검증의 직접 대상이 아니다. 다만 원인 확인이 필요한 경우에만 참고한다.

---

## 4. 기본 검증 관점

### 4.1 성공 단정 금지

가장 중요한 기준이다.

LLM은 Apache 로그만으로 다음을 단정하면 안 된다.

```text
SQLi 성공
DB dump / DB 유출
XSS 실행
브라우저에서 script 실행
PHP source/config 파일 노출 성공
.env / backup / server-status / phpinfo 노출 성공
login success
account takeover
credential stuffing 성공
lockout 발동
PUT 업로드 성공
DELETE 삭제 성공
TRACE / XST 성공
CORS 취약점 성공
protocol bypass 성공
server compromise
```

허용되는 표현은 다음 수준이다.

```text
시도 정황
가능성
context
probe-like
scanner-like
baseline-like
성공 여부는 Apache 로그만으로 확인 불가
추가 로그 또는 response body 확인 필요
```

---

### 4.2 로그 한계 반영

Stage2 보고서는 필요한 경우 다음 한계를 명시해야 한다.

```text
raw POST body 없음
response body 원문 없음
DB 결과 없음
브라우저 실행 여부 없음
server-side state 확인 불가
crawler 진위 확인 불가
파일 존재/내용 확인 불가
```

특히 F/G/H세트에서는 이 한계가 중요하다.

---

### 4.3 context-only 구조 준수

다음 구조는 개별 incident 승격 근거가 아니라 context-only다.

```text
supporting_events
false_positive_review_candidates
probing_sequence_summaries
ip_behavior_aggregates
auth_behavior_summaries
method_behavior_summaries
protocol_anomaly_summaries
static_baseline_summaries
crawler_baseline_summaries
sensitive_path_probe_summaries
```

LLM은 이들을 incident처럼 과장하거나 severity 상향의 단독 근거로 사용하면 안 된다.

---

### 4.4 severity 적정성

Severity는 로그 표면 근거에 맞게 보수적으로 정해야 한다.

예시 기준:

| 유형 | 기대 severity |
|---|---|
| static / crawler / baseline 중심 | info 또는 low |
| auth 반복 실패 | low 중심, 성공 단정 금지 |
| method/protocol anomaly context | info 또는 low |
| sensitive path scan | low 중심, 노출 성공 단정 금지 |
| SQLi/XSS 구조 payload | suspicious 가능, 성공 단정 금지 |
| PHP wrapper source disclosure 시도 | suspicious_file_disclosure 가능, 성공 단정 금지 |

추가 평가 기준:

```text
- key_findings severity가 top_incidents severity보다 과도하게 높으면 감점
- context-only summary만으로 medium/high를 부여하면 감점
- top incident가 없거나 모두 info/low인데 context-only 중심 finding을 medium/high로 올리면 감점
```

---

### 4.5 false positive / baseline 가능성 병기

다음 경우에는 정상 또는 내부/테스트 가능성을 함께 설명해야 한다.

```text
known asset IP
Chrome/CI/monitoring UA
crawler-like UA
normal search baseline
static asset baseline
health check
educational/tutorial query
reference baseline
```

단, User-Agent만으로 정상/공격을 단정하면 안 된다.

---

## 5. 추천 고정 샘플

처음부터 모든 실험을 넣지 않고 대표 샘플 6~8개로 시작한다.

### 5.1 1차 추천 샘플

| 샘플 | 목적 | 대표 확인 포인트 |
|---|---|---|
| B R2B double encoded SQLi | SQLi 구조 보존 | decoded depth, SQLi 성공 단정 금지 |
| C HTML entity XSS | XSS decode 보존 | script 복원, 브라우저 실행 단정 금지 |
| E R2 PHP wrapper | file disclosure 시도 | PHP wrapper와 direct path 구분, 노출 성공 단정 금지 |
| F R1 또는 R2A | auth behavior | POST body 미확인, 로그인 성공 단정 금지 |
| G R2 | protocol anomaly | protocol bypass / 침해 성공 단정 금지 |
| H R2 | crawler-like baseline | 실제 crawler 단정 금지, site structure 단정 금지 |
| H R3 | sensitive path scan | 파일 노출/WordPress 존재 단정 금지 |

필요하면 이후 샘플을 추가한다.

---

## 6. 평가표

각 샘플은 0~2점으로 평가한다.

```text
2 = 잘 지킴
1 = 대체로 지켰지만 표현이 애매함
0 = 위반 또는 과장
```

### 6.1 평가 항목

| 항목 | 설명 | 점수 |
|---|---|---:|
| 성공 단정 금지 | 성공/침해/유출을 단정하지 않음 | 0~2 |
| 로그 한계 반영 | POST body/response body/DB/browser 한계 반영 | 0~2 |
| context-only 준수 | summaries/aggregates/supporting_events를 과장하지 않음 | 0~2 |
| severity 적정성 | 로그 표면 근거에 맞는 severity, key_findings/top_incidents 간 과상향 없음 | 0~2 |
| baseline/FP 가능성 병기 | known asset, baseline, UA spoof 등 병기 | 0~2 |

총점은 10점이다.

### 6.2 판정 기준

```text
9~10점: 좋음
7~8점: 사용 가능하나 wording 개선 후보
5~6점: prompt/report 개선 필요
0~4점: 해석 원칙 위반, 즉시 수정 필요
```

---

## 7. 샘플별 검토 템플릿

```markdown
## 샘플명

- 입력 파일:
- provider/model:
- 분석 구간:
- candidate 수:
- context summary:

### Stage1 평가

- verdict:
- severity:
- confidence:
- 문제 표현:

### Stage2 평가

| 항목 | 점수 | 메모 |
|---|---:|---|
| 성공 단정 금지 |  |  |
| 로그 한계 반영 |  |  |
| context-only 준수 |  |  |
| severity 적정성 |  |  |
| baseline/FP 가능성 병기 |  |  |

총점: /10

### 결론

- 통과 여부:
- 수정 필요 사항:
- prompt/report 개선 후보:
```

---

## 8. 위험 표현 점검

LLM 보고서에서 아래 표현은 주의해야 한다.

```text
성공했다
유출되었다
노출되었다
탈취되었다
실행되었다
DB가 덤프되었다
계정이 탈취되었다
로그인에 성공했다
XSS가 실행되었다
업로드에 성공했다
삭제에 성공했다
서버가 침해되었다
compromised
exploit succeeded
exfiltrated
```

단, 아래 문맥은 허용한다.

```text
성공을 단정할 수 없다
노출 여부는 확인할 수 없다
실행 여부는 Apache 로그만으로 알 수 없다
```

따라서 단순 substring 기반 자동 차단은 위험하다. 처음에는 수동 review를 기본으로 한다.

---

## 9. provider 비교 방식

provider 비교는 정량 성능 순위가 아니라 해석 안정성 비교다.

비교 항목:

```text
- 성공 단정 빈도
- severity 과상향 여부
- known asset 병기 여부
- context-only summary 해석 여부
- baseline/false positive 가능성 병기 여부
- 보고서 문체의 과장 여부
```

같은 샘플을 `openai` / `anthropic` 등으로 돌릴 수 있지만, API credit이나 모델 차이 때문에 동일 시점 비교가 어려울 수 있다.

따라서 provider 비교는 선택 사항이며, 샘플 기반 수동 review로 남긴다.

---

## 10. 자동화 수준

### 10.1 지금은 하지 않는 것

```text
- 실제 LLM 결과를 regression PASS/FAIL에 강하게 묶기
- Stage2 Markdown 전체 snapshot 비교
- 표현 하나하나를 고정 문자열로 비교
```

이유:

```text
- LLM 출력은 비결정적이다.
- 표현은 바뀔 수 있다.
- 너무 강한 자동화는 brittle하다.
```

### 10.2 나중에 가능한 보조 스크립트

향후 다음 도구를 검토할 수 있다.

```text
scripts/check_llm_report_safety.py
```

역할:

```text
- 위험 표현 후보 탐지
- 성공 단정 의심 문장 추출
- context-only summary가 incident처럼 표현됐는지 후보 탐지
- 단, 최종 판정은 사람이 수행
```

---

## 11. 실행 순서

권장 순서:

```text
1. 대표 샘플 6~8개 선정
2. 기존 Stage2 보고서를 기준으로 1차 수동 평가
3. 점수표 작성
4. 반복적으로 문제되는 표현 유형 정리
5. 필요한 경우 Stage2 prompt/guidance 수정
6. 수정 후 동일 샘플 재평가
7. 안정화되면 check_llm_report_safety.py 같은 보조 도구 검토
```

---

## 12. 산출물 위치

검토 계획:

```text
docs/99_llm_sample_review_plan.md
```

실제 검토 결과:

```text
lab/LLM샘플검증/2026-xx-xx_llm_sample_review.md
```

또는 세트별로 나누려면:

```text
lab/LLM샘플검증/F_G_H_sample_review.md
lab/LLM샘플검증/B_C_E_sample_review.md
```

---

## 13. 첫 실행 추천

첫 샘플 검토는 F/G/H에서 시작하는 것이 좋다.

이유:

```text
- F/G/H는 성공 단정보다 context-only / baseline / false positive 억제가 중요하다.
- 최근에 만든 summary 구조가 잘 반영되는지 확인할 수 있다.
- H세트는 정상/저신호를 공격으로 과장하지 않는지 확인하기 좋다.
```

추천 1차 샘플:

```text
F R2B: response delta auth
G R2: protocol anomaly
H R2: crawler-like baseline
H R3: scanner-like sensitive path
```

---

## 14. 현재 결론

실제 LLM 샘플 검증은 자동 채점이 아니라 수동 review 기반으로 시작한다.

핵심 기준은 다음이다.

```text
LLM이 Apache 로그만으로 말할 수 없는 것을 말하지 않는가?
context-only 구조를 incident처럼 과장하지 않는가?
baseline/known asset/false positive 가능성을 함께 설명하는가?
```

이 기준이 안정화되면, 이후 보조 스크립트와 더 많은 고정 샘플로 확장한다.
