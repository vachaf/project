# 2026-05-03 F/G/H LLM 샘플 검증

- 작성 기준일: 2026-05-03
- 문서 역할: 실제 LLM Stage1/Stage2 결과를 고정 샘플 기준으로 수동 평가
- 기준 문서: `docs/99_llm_sample_review_plan.md`
- 검증 방식: 기존 Stage1/Stage2 산출물 수동 review
- 실제 LLM 재호출: 없음

---

## 1. 검증 목적

이번 검증은 모델이 공격을 더 강하게 말하는지 보는 테스트가 아니다.

목적은 다음이다.

```text
LLM이 Apache 로그만으로 말할 수 없는 것을 말하지 않는가?
context-only 구조를 incident처럼 과장하지 않는가?
baseline/known asset/false positive 가능성을 함께 설명하는가?
```

평가 항목은 5개이며, 각 항목은 0~2점이다.

| 항목 | 설명 | 점수 |
|---|---|---:|
| 성공 단정 금지 | 성공/침해/유출을 단정하지 않음 | 0~2 |
| 로그 한계 반영 | POST body/response body/DB/browser 한계 반영 | 0~2 |
| context-only 준수 | summaries/aggregates/supporting_events를 과장하지 않음 | 0~2 |
| severity 적정성 | 로그 표면 근거에 맞는 severity | 0~2 |
| baseline/FP 가능성 병기 | known asset, baseline, UA spoof 등 병기 | 0~2 |

판정 기준:

```text
9~10점: 좋음
7~8점: 사용 가능하나 wording 개선 후보
5~6점: prompt/report 개선 필요
0~4점: 해석 원칙 위반, 즉시 수정 필요
```

---

## 2. 샘플 목록

1차 검증은 최근 산출물이 안정적인 F/G/H 4개 샘플로 시작했다.

| 샘플 | 목적 | 사용 산출물 |
|---|---|---|
| F R2B | Auth response delta | `openai-f_r2b_response_delta_*` |
| G R2 | Protocol anomaly | `openai-g_r2_protocol_anomaly_*` |
| H R2 | Crawler-like baseline | `openai-h_r2_crawler_baseline_*` |
| H R3 | Scanner-like sensitive path | `openai-h_r3_scanner_low_signal_*` |

---

## 3. F R2B — Auth response delta

### 3.1 입력 요약

F R2B는 existing/nonexistent/lockout-probe 의도 그룹이 Apache 로그 표면에서 어떻게 보이는지 확인한 샘플이다.

주요 prepare / Stage2 input 요약:

```text
total_exported_rows=11
candidate_rows=3
supporting_events=8
auth_behavior_summaries=1
status surface: 401 / 26B 중심
```

핵심 해석 대상:

```text
- existing/nonexistent 의도 그룹 간 response surface 차이
- lockout-probing-like 반복 실패
- POST body 미확인 상태에서 계정 존재/lockout 발동을 단정하지 않는지
```

### 3.2 Stage1 평가

Stage1은 대표 candidate 3건만 처리했다.

```text
suspicious_auth_abuse=2
likely_false_positive=1
severity=low 중심
```

평가:

```text
- 반복 401을 auth abuse context로 보되 low severity 유지
- 계정 존재 여부 또는 lockout 발동 단정 없음
- POST body 내용이 보이는 것처럼 해석하지 않음
```

### 3.3 Stage2 평가

| 항목 | 점수 | 메모 |
|---|---:|---|
| 성공 단정 금지 | 2 | user enumeration 성공, lockout 발동, login success 단정 없음 |
| 로그 한계 반영 | 2 | POST body 미확인과 response surface 한계를 유지 |
| context-only 준수 | 2 | auth_behavior_summaries/supporting_events를 문맥으로 해석 |
| severity 적정성 | 2 | low 중심으로 적절 |
| baseline/FP 가능성 병기 | 1 | known asset / 내부 테스트 가능성은 반영되나 더 명시적이어도 좋음 |

총점: **9/10**

### 3.4 결론

F R2B는 통과로 본다.

```text
계정 존재 여부, lockout 발동, credential stuffing 성공을 단정하지 않았고,
반복 auth 실패를 response surface context로 보수적으로 설명했다.
```

---

## 4. G R2 — Protocol anomaly

### 4.1 입력 요약

G R2는 raw socket runner로 malformed/protocol-like 요청을 만든 샘플이다.

주요 prepare / Stage2 input 요약:

```text
total_exported_rows=12
candidate_rows=0
filtered_out_rows=6
ip_behavior_aggregates=1
method_behavior_summaries=1
protocol_anomaly_summaries=1
```

관찰된 context:

```text
FAKEMETHOD
HTTP/1.0 request
bad protocol version
missing Host
odd Host
long path
```

### 4.2 Stage1 평가

Stage1 처리 candidate는 없다.

```text
processed_candidate_count=0
success_count=0
error_count=0
```

이는 실패가 아니다. G R2는 개별 incident가 아니라 protocol anomaly context 보존이 목적이다.

### 4.3 Stage2 평가

| 항목 | 점수 | 메모 |
|---|---:|---|
| 성공 단정 금지 | 2 | protocol bypass, malformed request 우회, 침해 성공 단정 없음 |
| 로그 한계 반영 | 2 | Apache 로그 표면 한계와 response/request body 부재를 반영 |
| context-only 준수 | 2 | protocol_anomaly_summaries를 context-only로 설명 |
| severity 적정성 | 2 | candidate 없음, info/low 중심으로 적절 |
| baseline/FP 가능성 병기 | 2 | known asset / 내부 점검 가능성 병기 |

총점: **10/10**

### 4.4 결론

G R2는 매우 양호하다.

```text
protocol anomaly context를 잘 설명했고,
우회/침해/서버 취약점 성공을 단정하지 않았다.
```

---

## 5. H R2 — Crawler-like baseline

### 5.1 입력 요약

H R2는 crawler-like UA와 robots/sitemap/product/category browse가 공격으로 과승격되지 않는지 확인한 샘플이다.

주요 prepare / Stage2 input 요약:

```text
total_exported_rows=16
candidate_rows=0
filtered_out_rows=8
static_baseline_summaries=1
crawler_baseline_summaries=1
ip_behavior_aggregates=1
```

관찰된 context:

```text
Googlebot-like /robots.txt
Googlebot-like /sitemap.xml
GenericCrawler /products/
GenericCrawler /category/
Browser-like GET /
GenericCrawler repeated crawl sequence
```

### 5.2 Stage1 평가

Stage1 처리 candidate는 없다.

```text
processed_candidate_count=0
success_count=0
error_count=0
```

H R2는 baseline/FP bait 성격이므로 candidate가 없는 것이 정상에 가깝다.

### 5.3 Stage2 평가

| 항목 | 점수 | 메모 |
|---|---:|---|
| 성공 단정 금지 | 2 | crawler authenticity, site structure, page existence, attack success 단정 없음 |
| 로그 한계 반영 | 2 | Apache 로그만으로 crawler 진위/내용 확인 불가를 반영 |
| context-only 준수 | 2 | crawler_baseline_summaries/static_baseline_summaries를 context로 설명 |
| severity 적정성 | 2 | candidate 없음, info/low 중심으로 적절 |
| baseline/FP 가능성 병기 | 1 | known asset/내부 점검 가능성은 반영. 단, 보고서에 `crawller-like` 오타가 있음 |

총점: **9/10**

### 5.4 결론

H R2는 통과로 본다.

```text
crawler-like UA를 실제 crawler로 단정하지 않았고,
robots/sitemap/page existence를 과장하지 않았다.
```

개선 후보:

```text
- Stage2 wording에서 `crawller-like` 오타 수정
- low_signal_fuzzing category를 crawler_like_baseline 계열로 세분화할지 장기 검토
```

---

## 6. H R3 — Scanner-like sensitive path

### 6.1 입력 요약

H R3는 scanner-like sensitive path가 노출/성공 단정 없이 context로 보존되는지 확인한 샘플이다.

주요 prepare / Stage2 input 요약:

```text
total_exported_rows=20
candidate_rows=1
supporting_events=1
filtered_out_rows=7
probing_sequence_summaries=1
ip_behavior_aggregates=1
sensitive_path_probe_summaries=1
```

대표 candidate:

```text
GET /server-status -> 403
verdict=suspicious_scan
severity=low
```

### 6.2 Stage1 평가

Stage1은 `/server-status` 대표 candidate 1건을 처리했다.

```text
verdict=suspicious_scan
severity=low
confidence=high
false_positive_possible=true
```

평가:

```text
- /server-status를 정찰성 요청으로 설명
- 실제 server-status 노출이나 침해 성공 단정 없음
- false positive 가능성 병기
```

### 6.3 Stage2 평가

| 항목 | 점수 | 메모 |
|---|---:|---|
| 성공 단정 금지 | 2 | WordPress 존재, .env/phpinfo/backup/server-status 노출, 침해 성공 단정 없음 |
| 로그 한계 반영 | 2 | Apache 로그만으로 노출/차단/성공 확인 불가를 유지 |
| context-only 준수 | 2 | sensitive_path_probe_summaries/supporting_events/probing_sequence를 문맥으로 설명 |
| severity 적정성 | 2 | representative candidate를 low severity로 유지 |
| baseline/FP 가능성 병기 | 2 | known asset 및 내부 테스트/운영 점검 가능성 병기 |

총점: **10/10**

### 6.4 결론

H R3는 매우 양호하다.

```text
scanner-like sensitive path를 low severity context로 설명했고,
파일 노출·WordPress 존재·admin access·server-status 노출을 단정하지 않았다.
```

개선 후보:

```text
- supporting_event reason_hints를 row-specific하게 줄이는 개선은 이미 반영됨
- 필요 시 low_signal_dir_probe category를 sensitive_path_probe_context로 세분화할지 장기 검토
```

---

## 7. 종합 평가

| 샘플 | 점수 | 판정 |
|---|---:|---|
| F R2B | 9/10 | 통과 |
| G R2 | 10/10 | 통과 |
| H R2 | 9/10 | 통과 |
| H R3 | 10/10 | 통과 |

평균 점수:

```text
38 / 40 = 95%
```

1차 F/G/H 실제 LLM 샘플 검증은 성공적으로 본다.

---

## 8. 반복적으로 확인된 좋은 점

```text
- 성공/침해/유출 단정을 피함
- context-only summary를 incident로 과장하지 않음
- known asset 가능성을 병기함
- baseline/low-signal 요청을 고신호로 과승격하지 않음
- severity가 대체로 low/info 중심으로 유지됨
```

---

## 9. 발견된 개선 후보

### 9.1 Stage2 오타

H R2 보고서에서 `crawller-like` 오타가 있었다.

```text
crawller-like -> crawler-like
```

기능 문제는 아니지만, Stage2 wording 개선 후보로 남긴다.

### 9.2 category 표현 세분화

아래 category는 장기적으로 세분화할 수 있다.

```text
low_signal_fuzzing
low_signal_dir_probe
```

후보:

```text
crawler_like_baseline
sensitive_path_probe_context
static_asset_baseline
health_check_error_context
```

현재는 top-level summaries가 문맥을 보존하므로 급한 문제는 아니다.

### 9.3 실제 LLM 자동 검증은 아직 보류

이번 수동 검증 결과는 좋지만, 자동화는 아직 이르다.

```text
- LLM 출력 비결정성
- 표현 변화 가능성
- 성공 단정 금지 문맥과 위험 표현의 구분 어려움
```

따라서 당분간은 샘플 기반 수동 review를 유지한다.

---

## 10. 결론

F/G/H 실제 LLM 샘플 1차 검증 결과, 현재 Stage1/Stage2는 Apache 로그 기반 보수적 해석 원칙을 대체로 잘 지킨다.

핵심 결론:

```text
- 실제 성공/침해/노출 단정을 하지 않음
- context-only 구조를 적절히 설명함
- baseline/FP 가능성을 병기함
- severity가 과도하지 않음
```

따라서 현재 Stage2 prompt/guidance는 F/G/H 범위에서는 사용 가능한 수준으로 평가한다.

추가 조치는 오타/wording 정리와 장기적인 category 세분화 검토 정도로 충분하다.
