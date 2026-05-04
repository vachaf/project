# 분석 신뢰성 평가 기준

## Apache 로그 기반 침입 분석에서 “좋은 분석”이란 무엇인가

> **핵심 명제:**  
> 우리는 공격을 “맞췄는지”가 아니라, **왜 그렇게 판단했는지를 검증 가능한 구조로 만들었는지**를 평가한다.

---

## 1. 문서 목적

이 문서는 Apache 로그 기반 LLM 침입 분석 파이프라인에서 분석 품질을 평가하기 위한 공통 기준이다.

적용 대상:

```text
- 비교 실험 결과 문서
- Stage1 / Stage2 실제 LLM 샘플 리뷰
- Stage2 Markdown 보고서 품질 검토
- 발표/보고용 요약 작성 전 품질 점검
```

비목표:

```text
- 실제 공격 성공 여부 확정
- 자동 차단 정책 정의
- 모델 성능 순위 산정
- response body / DB 결과 / 브라우저 실행 검증을 대체
```

---

## 2. “좋은 분석”의 정의

> **좋은 분석이란:** Apache 로그의 가시성 한계를 인정하면서, 로그 표면에서 직접 관찰 가능한 수치와 구조적 증거를 출발점으로 삼아 **Evidence → Context → Reasoning** 흐름으로 판단 근거를 설명하고, 공격 가능성과 확인 한계를 함께 제시하는 분석이다.

이 정의는 세 가지 요소를 동시에 요구한다.

| 요소 | 내용 |
|---|---|
| 보수적 해석 | 가능성을 말하되 성공·침해·유출을 단정하지 않는다. |
| 증거 기반 | status, bytes, duration/ttfb, query/path, 인코딩 패턴, 반복 건수 같은 로그 표면 근거를 명시한다. |
| 설명 가능성 | 로그를 모르는 사람도 왜 위험할 수 있는지와 무엇을 추가 확인해야 하는지 추적할 수 있어야 한다. |

핵심 원칙:

```text
LLM이 말했다는 것은 근거가 아니다.
Apache 로그에서 관찰된 수치와 구조가 근거다.
```

---

## 3. 기본 가시성 한계

Apache 로그 기반 분석은 다음을 직접 볼 수 없다.

```text
- raw POST body
- response body 원문
- DB query 결과
- 브라우저 실행 여부
- 서버 내부 state 변화
- 실제 파일 내용 반환 여부
- 실제 crawler 진위
```

따라서 다음 표현은 피한다.

```text
- 공격 성공
- 유출 확인
- 침해 완료
- DB dump 확인
- XSS 실행 확인
- 파일 내용 노출 확인
- 계정 탈취 확인
```

허용되는 표현은 다음 수준이다.

```text
- 시도 정황
- 가능성
- 의심 신호
- probe-like / scanner-like / crawler-like context
- 추가 확인 필요
- Apache 로그만으로는 성공 여부 확인 불가
```

---

## 4. Evidence → Context → Reasoning 구조

### 4.1 Evidence

로그에서 직접 관찰된 수치와 구조를 적는다.

예:

```text
- status_code=200
- response_body_bytes=32777
- resp_content_type=text/html
- query_string에 php%3A%2F%2Ffilter 포함
- URL decode 후 php://filter/convert.base64-encode/resource=config.php 복원
- 동일 src_ip가 120초 내 민감 경로 여러 개에 순차 접근
```

주의:

```text
response_body_bytes는 보조 지표다.
응답 크기만으로 실제 파일 내용 반환이나 데이터 유출을 확정하지 않는다.
```

### 4.2 Context

증거들을 같은 src_ip, endpoint, time window, sequence, baseline과 묶어 해석한다.

예:

```text
동일 src_ip가 짧은 시간 안에 /config.php, /admin/config.php, php://filter 요청을 순차 수행했다.
이는 단일 요청보다 source/config disclosure 또는 sensitive path probing 맥락으로 볼 수 있다.
```

주의:

```text
context-only summary는 개별 incident 승격 근거가 아니다.
severity 상향의 단독 근거로 쓰지 않는다.
```

### 4.3 Reasoning

가능성과 한계를 함께 제시한다.

예:

```text
php://filter + convert.base64-encode + resource=config.php 조합은 PHP source/config disclosure 시도로 해석 가능하다.
200 OK와 큰 응답 크기는 서버가 요청을 처리했을 가능성을 시사하지만,
response body 원문이 없으므로 실제 config.php 내용 반환이나 DB credential 노출은 확정할 수 없다.
```

---

## 5. 평가 기준 테이블

| # | 항목 | 정의 | 왜 중요한가 | Good | Bad |
|---|---|---|---|---|---|
| 1 | 보수적 해석 원칙 | Apache 로그 가시성 밖의 성공·침해·유출을 확정하지 않는다. | 한계를 무시한 단정은 오탐과 과대 대응을 유발한다. | “200 OK + 32KB 응답은 처리 정황이다. 파일 노출 여부는 response body 확인 필요.” | “200 OK이므로 공격 성공.” |
| 2 | 증거 기반 판단 | status, bytes, duration/ttfb, query/path, 인코딩 패턴, 건수를 명시한다. | 느낌 기반 판단은 재현·검증이 어렵다. | “status=404, bytes=19832, query에 php://filter/resource=config.php 복원.” | “뭔가 수상하다.” |
| 3 | 인코딩 해석 | URL encoding, double encoding, HTML entity, PHP wrapper 등을 복원한다. | 인코딩을 보지 않으면 공격 의도가 로그 표면에 숨어 있을 수 있다. | “php%3A%2F%2Ffilter → php://filter 복원.” | “이상한 문자열 포함.” |
| 4 | 행동 맥락 | 동일 src_ip / endpoint / time window 내 요청 패턴을 묶어 해석한다. | 단일 요청만 보면 정찰·burst·chain 맥락을 놓칠 수 있다. | “120초 내 민감 경로 10건 순차 접근.” | “/server-status 1건 접근.” |
| 5 | 전처리 신뢰도 | 후보, supporting_events, filtered_out, summary가 어떤 기준으로 나뉘었는지 점검한다. | 필터링 과정이 불투명하면 중요 신호 누락을 알 수 없다. | “low_signal_dir_probe로 분리됐지만 sensitive_path_probe_summaries로 보존됨.” | “노이즈는 모두 제거.” |
| 6 | 오탐 억제 | known asset, baseline, crawler-like, monitoring, educational query를 과승격하지 않는다. | 오탐이 많으면 보고서 신뢰도가 떨어진다. | “known asset IP라 내부 테스트 가능성 병기.” | “HEAD 요청도 high severity.” |
| 7 | LLM 출력 교차 검증 | LLM verdict와 reasoning이 로그 수치·기법 분류와 맞는지 확인한다. | LLM은 확신 있게 틀릴 수 있다. | “php://filter는 scan보다 file disclosure 시도로 재검토.” | “모델이 말했으므로 사실.” |
| 8 | 실행 가능한 후속 확인 | 분석 결과가 구체적 확인 절차로 이어진다. | “위험함”만으로는 행동할 수 없다. | “P1: request_id 기준 raw/error/app log 대조, 필요 시 response body 확인.” | “즉시 대응 필요.” |

---

## 6. 내부 검증 기준 — Internal Validation

전문가 또는 파이프라인 관리자는 다음을 본다.

```text
전처리 단계
  ├── 어떤 row가 candidate가 되었는가?
  ├── 어떤 row가 supporting_events / false_positive_review_candidates / filtered_out으로 갔는가?
  ├── filtered_out 중 중요한 공격 신호가 누락됐을 가능성은 없는가?
  └── context-only summary가 필요한 문맥을 보존했는가?

LLM 입력 품질
  ├── query_string, raw_request_target, reason_hints, status/bytes/content-type이 보존됐는가?
  ├── 인코딩 복원 정보가 전달됐는가?
  ├── known asset / baseline / FP 가능성 문맥이 포함됐는가?
  └── lab-* / experiment-like UA가 공격 근거처럼 전달되지 않도록 guard가 있는가?

LLM 출력 교차 검증
  ├── verdict가 기법에 맞는가?
  │     예: php://filter → suspicious_file_disclosure 계열
  ├── reasoning이 로그 수치를 실제로 인용하는가?
  ├── 성공·침해·노출 단정 표현이 없는가?
  └── context-only summary를 incident처럼 과장하지 않는가?
```

---

## 7. 비전문가 검증 기준 — External Validation

보고서를 받는 사람은 다음 질문으로 품질을 판단할 수 있다.

| # | 질문 | YES이면 | NO이면 |
|---|---|---|---|
| 1 | 분석이 “공격 성공”이 아니라 “공격 가능성/시도 정황”으로 표현됐는가? | 신뢰 가능 | 과도한 단정 가능성 |
| 2 | 판단 근거에 숫자(status, bytes, 시간, 건수)가 포함됐는가? | 검증 가능 | 느낌 기반 판단 가능성 |
| 3 | 인코딩 문자열이 풀어서 설명됐는가? | 의도 추적 가능 | 공격 의도 누락 가능성 |
| 4 | 단일 요청이 아니라 같은 IP/time window 패턴을 봤는가? | 맥락 반영 | 맥락 누락 가능성 |
| 5 | “확인됨”, “성공”, “침해 완료” 같은 표현이 없는가? | 한계 준수 | 가시성 한계 위반 |
| 6 | known asset, baseline, FP 가능성이 병기됐는가? | 오탐 억제 | 과승격 가능성 |
| 7 | 무엇을 확인해야 하는지 구체적인가? | 행동 가능 | 보고서 활용 어려움 |
| 8 | LLM 판단을 수치와 기법 기준으로 다시 검토했는가? | 검증 구조 있음 | LLM 맹신 위험 |

---

## 8. Anti-Patterns

### 8.1 200 OK = 성공

Bad:

```text
HTTP 200 OK 응답이 반환되었으므로 공격이 성공했다.
```

왜 나쁜가:

```text
200 OK는 서버가 요청을 처리했다는 신호일 수 있지만,
공격자가 원하는 데이터가 반환됐다는 증거는 아니다.
fallback HTML, 빈 출력, 오류 페이지, 정상 로그인 페이지도 200으로 반환될 수 있다.
```

Good:

```text
200 OK + 32,777B 응답은 서버가 요청을 처리했을 가능성을 시사한다.
다만 response body 원문이 없으므로 파일 내용 반환이나 credential 노출 성공은 확정할 수 없다.
request_id 기준 원문 응답 또는 애플리케이션 로그 대조가 필요하다.
```

### 8.2 응답 크기 = 파일 노출 확정

Bad:

```text
응답이 32KB이므로 config.php가 base64로 노출됐다.
```

왜 나쁜가:

```text
Apache 로그에는 response body 원문이 없다.
응답 크기가 크다는 점은 보조 지표지만, 실제 내용이 config.php인지 확인할 수 없다.
```

Good:

```text
응답 크기 32,777B는 일반 baseline보다 큰 응답으로 file/source disclosure 가능성을 검토할 만한 신호다.
그러나 실제 config.php 내용 또는 base64 인코딩 결과와 일치하는지는 response body 원문 없이는 확인할 수 없다.
```

### 8.3 단일 로그만 분석

Bad:

```text
이 요청 1건에서 SQLi payload가 발견됐다.
```

Good:

```text
동일 src_ip가 같은 time window에서 여러 search 요청을 반복했고,
그중 일부 query_string에 SQLi payload와 encoding 변형이 관찰됐다.
단일 요청보다 evasion/chain 테스트 정황으로 해석할 수 있다.
```

### 8.4 인코딩 무시

Bad:

```text
query_string에 이상한 문자들이 포함됐다.
```

Good:

```text
%2e%2e%2f는 URL decode 후 ../ 로 복원되며 path traversal 시도 정황이다.
php%3A%2F%2Ffilter는 php://filter 로 복원되며 PHP wrapper 기반 source/config disclosure 시도 가능성을 시사한다.
```

### 8.5 LLM 결과 그대로 믿음

Bad:

```text
모델이 suspicious_scan으로 판정했으므로 scanner다.
```

Good:

```text
모델 verdict는 suspicious_scan이지만, query_string의 php://filter/convert.base64-encode/resource=config.php 구조는 scanner보다 PHP wrapper 기반 file/source disclosure 시도에 가깝다.
따라서 suspicious_file_disclosure taxonomy와 대조해 재검토한다.
```

### 8.6 실험용 UA를 공격 근거로 사용

Bad:

```text
User-Agent가 lab-* 형식이므로 공격 가능성이 높다.
```

Good:

```text
User-Agent는 실험 식별 또는 trace aid로만 사용한다.
공격 판단은 query_string, decoded payload, path, reason_hints, status/bytes/content-type, timing, sequence context 같은 일반화 가능한 Apache 로그 표면 신호를 우선한다.
```

---

## 9. 실행 가능한 후속 확인 기준

좋은 분석은 “위험하다”에서 끝나지 않고 다음 확인으로 이어져야 한다.

권장 표현:

```text
P0: 성공/침해 단정이 아니라 확인 우선순위를 지정한다.
P1: request_id 기준 raw log, error log, application log, reverse proxy log를 대조한다.
P2: 필요 시 response body 원문 또는 애플리케이션 재현 테스트로 실제 노출 여부를 확인한다.
P3: known asset / 내부 테스트 / scanner-like baseline 여부를 담당자에게 확인한다.
```

차단 관련 주의:

```text
자동 차단 또는 iptables/방화벽 적용은 현재 분석 보고서의 기본 결론이 아니다.
운영 정책, 영향 범위, 승인 절차를 확인한 뒤 별도 대응 단계에서 검토한다.
```

---

## 10. 시스템 구조와 평가 포인트

```text
Apache 로그 원시 데이터
        │
        ▼
┌─────────────────────────────────────────┐
│ 규칙 기반 전처리                         │ ← 평가 포인트 A
│ - candidate / supporting_events 분리      │
│ - filtered_out / noise summary 보존        │
│ - context-only summary 생성               │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ LLM 정밀 분석 Stage1 / Stage2             │ ← 평가 포인트 B
│ - verdict / severity / confidence 검토     │
│ - 증거 수치와 reasoning 연결 확인          │
│ - 단정 표현과 기법 taxonomy 점검           │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 최종 보고서                              │ ← 평가 포인트 C
│ - Evidence → Context → Reasoning 구조     │
│ - 비전문가도 이해 가능한 설명             │
│ - 실행 가능한 후속 확인 절차              │
└─────────────────────────────────────────┘
```

---

## 11. 발표용 핵심 요약

> 우리는 공격을 “맞췄는지”가 아니라, **왜 그렇게 판단했는지를 검증 가능한 구조로 만들었는지**를 평가한다.

이 기준이 의미하는 것:

```text
- 탐지율보다 판단 추적 가능성이 중요하다.
- 분석 결과가 틀릴 수는 있지만, 왜 그렇게 판단했는지 설명할 수 있어야 한다.
- Apache 로그의 가시성 한계를 인정하는 것이 신뢰성의 출발점이다.
- LLM 출력은 근거가 아니다. 로그 표면 수치와 구조가 근거다.
- 성공 단정보다 확인 가능한 다음 행동을 제시하는 것이 좋은 보고서다.
```

---

## 12. 관련 문서

- [98_비교_실험_요청_세트_표준.md](./98_비교_실험_요청_세트_표준.md)
- [99_비교_실험_결과_기록_템플릿.md](./99_비교_실험_결과_기록_템플릿.md)
- [../reviews/99_llm_sample_review_plan.md](../reviews/99_llm_sample_review_plan.md)
- [../reviews/99_stage2_wording_quality_review.md](../reviews/99_stage2_wording_quality_review.md)
- [../design/99_POST_body_visibility_한계와_해석_기준.md](../design/99_POST_body_visibility_한계와_해석_기준.md)
- [../design/99_file_disclosure_verdict_taxonomy_검토.md](../design/99_file_disclosure_verdict_taxonomy_검토.md)
