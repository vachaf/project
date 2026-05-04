# LLM 분석 품질 평가 체크리스트

작성 기준: 2026-05-04  
분류: `docs/standards/` 공통 평가 기준  
목적: Apache 로그 기반 Stage1/Stage2 분석 결과를 수동 평가할 때 사용할 10점 체크리스트를 제공한다.

> 평가 철학: 공격을 맞췄는지가 아니라, **왜 그렇게 판단했는지를 검증 가능한 구조로 만들었는지**를 평가한다.

---

## 1. 사용 방법

1. 평가할 Stage1/Stage2 결과 또는 최종 보고서를 준비한다.
2. 아래 5개 항목을 각각 0~2점으로 채점한다.
3. 각 항목은 실제 로그 표면과 분석 문장을 대조해 근거를 남긴다.
4. 마지막에 ECR 구조를 별도로 점검한다.

채점 기준:

```text
5개 항목 × 최대 2점 = 10점 만점
9~10점: 통과
7~8점: 개선 후보
6점 이하: 재분석 필요
```

ECR 구조는 별도 품질 메모로 기록한다. 점수에 직접 합산하지 않는다.

---

## 2. 평가 항목 요약

| # | 항목 | 핵심 질문 | 점수 |
|---|---|---|---:|
| 1 | 보수적 확정성 | 성공·침해·유출을 단정하지 않았는가? | 0~2 |
| 2 | 로그 한계와 증거 기반 | status/bytes/content-type/timing 등 관찰 가능한 수치를 근거로 삼았는가? | 0~2 |
| 3 | 인코딩 해석 | URL encoding, double encoding, HTML entity, PHP wrapper를 복원했는가? | 0~2 |
| 4 | 맥락 구성과 context-only 준수 | 동일 IP/time window 흐름을 묶되 저신호를 과승격하지 않았는가? | 0~2 |
| 5 | 오탐 억제와 taxonomy 정확도 | FP bait, known asset, lab-* UA, verdict 분류를 적절히 다뤘는가? | 0~2 |

---

## 3. 항목 1 — 보수적 확정성

핵심 질문:

```text
공격 성공, 계정 탈취, 데이터 유출, 파일 노출, 침해 완료 같은 단정 표현이 있는가?
```

체크 항목:

```text
□ HTTP 200 OK를 공격 성공으로 단정하지 않았는가?
□ JWT 발급, 계정 탈취, 데이터 유출을 로그만 보고 확정하지 않았는가?
□ POST body 미확인, response body 원문 미확인 한계를 인정했는가?
□ “가능성”, “정황”, “시사” 수준으로 표현했는가?
```

감점 트리거:

| 표현 패턴 | 감점 |
|---|---:|
| 200 OK → 공격 성공 | -2 |
| 로그인 성공, 계정 탈취, JWT 발급 확인 | -2 |
| 데이터 유출, 파일 노출, DB dump 확인 | -2 |
| POST body 또는 response body 원문을 본 것처럼 서술 | -1~-2 |

좋은 표현:

```text
200 OK + 32,777B 응답은 서버가 php://filter 요청을 처리했을 가능성을 시사한다.
다만 Apache 로그만으로 실제 config.php 내용 반환 또는 credential 노출은 확인할 수 없다.
```

채점:

```text
2점: 단정 표현 없음, 로그 한계 명확
1점: 일부 애매한 표현은 있으나 핵심 단정은 없음
0점: 성공·침해·유출 단정 존재
```

---

## 4. 항목 2 — 로그 한계와 증거 기반

핵심 질문:

```text
분석이 관찰 가능한 Apache 로그 표면에 근거하는가?
```

체크 항목:

```text
□ status_code, response_body_bytes, resp_content_type, duration_us, ttfb_us 등을 인용했는가?
□ 수치를 성공 확정이 아니라 정황 근거로만 사용했는가?
□ fallback HTML, baseline 응답, 동일 크기 반복 같은 비교 기준을 함께 제시했는가?
□ 없는 데이터(raw POST body, response body 원문, DB 결과, 브라우저 실행)를 본 것처럼 쓰지 않았는가?
```

감점 트리거:

| 표현 패턴 | 감점 |
|---|---:|
| 수치 없이 “위험해 보임” 중심 서술 | -2 |
| bytes/status를 성공 확정 근거로 사용 | -2 |
| fallback HTML 가능성 누락 | -1 |
| timing 수치 없이 time-based 판단 | -1 |

좋은 표현:

```text
9건 모두 status=200, response_body_bytes=75,002B, text/html로 동일하다.
이는 민감 파일 내용이 아니라 SPA fallback HTML일 가능성을 우선 검토해야 하는 패턴이다.
```

채점:

```text
2점: 로그 표면 수치와 한계를 함께 제시
1점: 일부 수치는 있으나 비교 기준 또는 한계 설명 부족
0점: 수치 없는 느낌 기반 판단 또는 없는 데이터를 본 것처럼 서술
```

---

## 5. 항목 3 — 인코딩 해석

핵심 질문:

```text
로그 표면에 숨은 payload를 단계별로 복원했는가?
```

체크 항목:

```text
□ URL encoding을 실제 문자로 복원했는가?
□ double encoding을 2단계 이상 추적했는가?
□ HTML entity를 실제 태그/문자로 복원했는가?
□ php://filter 같은 wrapper 구조를 URL decode 후 식별했는가?
□ “이상한 문자”가 아니라 실제 공격 의도까지 도달했는가?
```

감점 트리거:

| 표현 패턴 | 감점 |
|---|---:|
| `%2527`을 2단계로 풀지 못함 | -1~-2 |
| HTML entity XSS를 XSS로 복원하지 못함 | -1~-2 |
| php%3A%2F%2Ffilter를 일반 query 문자열로만 처리 | -1 |
| 인코딩을 “이상 문자”로만 표현 | -2 |

예시:

```text
raw:      %2527%2520OR%25201%253D1%2520--
decode 1: %27%20OR%201%3D1%20--
decode 2: ' OR 1=1 --
```

```text
raw:     &#x3C;script&#x3E;document.cookie&#x3C;/script&#x3E;
decoded: <script>document.cookie</script>
```

채점:

```text
2점: 필요한 인코딩 레이어를 단계별로 복원하고 공격 의도 설명
1점: 일부 복원은 했으나 depth 또는 특수 패턴 누락
0점: 인코딩 미해석
```

---

## 6. 항목 4 — 맥락 구성과 context-only 준수

핵심 질문:

```text
동일 IP/time window 요청을 흐름으로 묶되, 저신호 요청을 과승격하지 않았는가?
```

체크 항목:

```text
□ 동일 src_ip, time window, endpoint family를 묶어 설명했는가?
□ burst probing, temporal chain, auth behavior 같은 흐름을 인식했는가?
□ supporting_events 또는 *_summaries를 context-only로 사용했는가?
□ 개별 low-signal 요청을 incident로 과도하게 나열하지 않았는가?
```

감점 트리거:

| 패턴 | 감점 |
|---|---:|
| 단일 요청만 분석하고 전후 맥락 없음 | -2 |
| burst probing 여러 건을 각각 high incident로 나열 | -1~-2 |
| supporting_events를 공격 성공 근거로 확대 | -1~-2 |
| context-only summary를 confirmed compromise처럼 사용 | -2 |

좋은 표현:

```text
10개 민감 경로 접근은 directory probing burst 문맥으로 보존한다.
다만 9건의 동일 200/text/html/75,002B 응답은 SPA fallback 가능성이 높으므로 민감 파일 노출로 단정하지 않는다.
```

채점:

```text
2점: 흐름을 묶고 context-only 한계를 지킴
1점: 일부 맥락은 있으나 단일 요청 중심 또는 과승격 위험 있음
0점: 맥락 없음 또는 저신호 과승격
```

---

## 7. 항목 5 — 오탐 억제와 taxonomy 정확도

핵심 질문:

```text
정상·교육용·내부 테스트 가능성을 과승격하지 않고, verdict가 실제 기법과 맞는가?
```

체크 항목:

```text
□ known asset IP를 공격자로 단정하지 않았는가?
□ 교육용 검색, tutorial query, baseline 요청을 공격으로 분류하지 않았는가?
□ verdict 분류명이 실제 공격 기법과 맞는가?
□ User-Agent를 trace aid 또는 운영 문맥 보조 정보로만 사용했는가?
□ lab-* / experiment-like UA를 공격 근거 또는 severity 상향 근거로 사용하지 않았는가?
```

감점 트리거:

| 패턴 | 감점 |
|---|---:|
| tutorial/onerror 검색을 XSS 공격으로 분류 | -1 |
| known asset IP를 외부 공격자로 단정 | -1 |
| lab-* UA를 공격 증거처럼 사용 | -1 |
| php://filter를 단순 scan이나 일반 path traversal로만 처리 | -1~-2 |
| HEAD/GET baseline을 high severity로 과승격 | -1 |

주의:

```text
User-Agent 자체를 버리라는 뜻은 아니다.
crawler-like, browser-like, monitoring UA는 운영 문맥 보조 정보가 될 수 있다.
다만 lab-* 또는 실험용 UA는 공격 근거, 탐지 근거, severity 상향 근거로 사용하지 않는다.
```

채점:

```text
2점: FP 억제, known asset 병기, taxonomy 적합, UA 과적합 없음
1점: 일부 taxonomy/wording 개선 여지 있음
0점: 정상 요청 과승격, UA 탐지 남용, verdict 오분류
```

---

## 8. ECR 구조 평가

ECR은 점수에 합산하지 않는 별도 품질 메모다.

```text
Evidence → Context → Reasoning
```

### Evidence

로그에서 직접 관찰된 수치와 패턴이 있는가?

```text
예: status=200, response_body_bytes=32,777, resp_content_type=text/html,
    query_string에 php%3A%2F%2Ffilter 포함,
    동일 IP 120초 내 10건 요청
```

### Context

증거들을 조합해 상황을 구성했는가?

```text
예: php://filter + convert.base64-encode + resource=config.php 조합은
    PHP source/config disclosure 시도에서 자주 보이는 패턴이다.
```

### Reasoning

가능성과 한계를 함께 제시했는가?

```text
예: source/config disclosure 시도로 해석 가능하다.
    200 OK와 큰 응답은 처리 정황을 시사하지만,
    response body 원문 없이는 실제 파일 내용 노출을 확정할 수 없다.
```

구조 결함:

| 유형 | 설명 |
|---|---|
| Evidence 없음 | 수치 없이 결론 |
| Context 생략 | 증거에서 바로 결론 |
| Reasoning 단정 | 성공·유출 확정으로 마무리 |
| 역순 구조 | 결론 먼저, 근거 나중 |

체크:

```text
[ ] 완전: Evidence, Context, Reasoning 모두 명확
[ ] 부분: 1~2단계 약함
[ ] 부족: 근거 없이 결론 또는 Reasoning에서 단정
```

---

## 9. 실행 가능한 대응에 대한 보조 평가

기존 팀원 초안에는 “실행 가능한 대응”을 6번째 채점 항목으로 두었으나, 현재 repo의 수동 리뷰 체계는 5개 항목 × 2점 = 10점 구조다. 따라서 대응 가능성은 **점수 외 보조 평가**로 둔다.

체크 항목:

```text
□ 담당자가 다음에 확인할 로그/시스템/소유자를 알 수 있는가?
□ P0~P3 또는 우선순위 표현이 과도하지 않은가?
□ 운영 승인 없는 즉시 차단 명령을 기본 권고처럼 쓰지 않았는가?
□ 차단·격리·토큰 폐기 등 영향 큰 조치는 운영 정책 승인 후 검토로 표현했는가?
```

좋은 표현:

```text
P1: 원문 응답 본문 또는 애플리케이션 로그에서 실제 파일 내용 반환 여부를 확인한다.
P1: 요청 주체가 내부 실험 또는 승인된 점검인지 소유자에게 확인한다.
P2: 동일 패턴 반복 여부를 WAF/로그에서 모니터링한다.
```

주의 표현:

```text
P0: iptables DROP
```

이런 명령은 예시로 남길 수는 있으나, 운영 승인과 영향도 검토 없이 기본 권고로 쓰지 않는다.

---

## 10. 최종 채점표

```markdown
### 총점
- XX / 10

### 항목별 평가

1. 보수적 확정성: X/2
   - 근거:

2. 로그 한계와 증거 기반: X/2
   - 근거:

3. 인코딩 해석: X/2
   - 근거:

4. 맥락 구성과 context-only 준수: X/2
   - 근거:

5. 오탐 억제와 taxonomy 정확도: X/2
   - 근거:

### ECR 구조 평가
- 충족 여부: 완전 / 부분 / 부족
- 문제점:

### 대응 가능성 메모
- 적절한 점:
- 보완할 점:

### 주요 오류
-

### 개선 필요 사항
-

### 최종 판정
- 9~10: 통과
- 7~8: 개선 후보
- ≤6: 재분석 필요

판정: [결과]
```

---

## 11. 참조 샘플 점수

| 샘플 | 핵심 케이스 | 최종 점수 | 감점 또는 용도 |
|---|---|---:|---|
| S-A | 인증 우회 401 → 200 | — | provider별 성향 비교 기준 |
| S-B | Double encoded SQLi | 9/10 | FP/supporting 구조 설명 명시도 |
| S-C | HTML entity XSS + FP bait | 9/10 | FP 직접 인용 부족 |
| S-D | Directory probing burst | — | 구조 개선 사례 |
| S-E | PHP wrapper file disclosure | 8/10 | taxonomy/UA wording 개선 후보였고 이후 보강 완료 |
| S-F | Auth response delta | 9/10 | known asset 명시도 |

---

## 12. 절대 금지

```text
- “대체로 잘 분석됨” 같은 모호한 표현만으로 점수 부여
- 근거 없는 점수 부여
- LLM이 자신 있게 말했으니 맞을 것이라는 신뢰
- 수치 없는 분석을 표현 방식 차이로 용인
- 200 OK를 성공으로 단정한 표현을 보수적 표현으로 오해
- lab-* UA를 공격 근거로 사용
- response body 원문이나 DB 결과를 본 것처럼 서술
```

---

## 13. 관련 문서

- [99_analysis_quality_criteria.md](./99_analysis_quality_criteria.md)
- [../reviews/99_A-F세트_대표샘플_6선.md](../reviews/99_A-F세트_대표샘플_6선.md)
- [../reviews/99_llm_sample_review_plan.md](../reviews/99_llm_sample_review_plan.md)
- [../reviews/99_A-H세트_중간정리.md](../reviews/99_A-H세트_중간정리.md)
