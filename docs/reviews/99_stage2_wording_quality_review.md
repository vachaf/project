# Stage2 wording 품질 검토

- 작성 기준일: 2026-05-03
- 문서 역할: Stage2 Markdown 보고서의 자연어 표현 품질 문제를 별도 관리하기 위한 검토 문서
- 적용 범위: `src/llm_stage2_reporter.py`가 생성하는 Stage2 report JSON/Markdown
- 비적용 범위: prepare 탐지 로직, Stage1 verdict schema, 후보 선정 로직

---

## 1. 배경

A~H세트 실험을 진행하면서 Stage2 보고서는 전반적으로 Apache 로그 기반 보수적 해석 원칙을 잘 지켰다.

특히 다음 원칙은 대체로 유지됐다.

```text
- 성공/침해/노출 단정 금지
- context-only summary를 incident로 과장하지 않음
- known asset / 내부 테스트 가능성 병기
- baseline / false positive 가능성 설명
- severity를 low/info 중심으로 유지
```

다만 일부 보고서에서 작은 wording 품질 문제가 관찰됐다.

대표 사례:

```text
crawller-like -> crawler-like
```

이 문제는 탐지 실패나 해석 원칙 위반은 아니지만, 보고서 품질과 신뢰도 측면에서는 정리할 필요가 있다.

---

## 2. 발견된 문제 유형

### 2.1 단순 오타

대표 사례:

```text
crawller-like
```

의도된 표현:

```text
crawler-like
```

성격:

```text
- LLM 자연어 생성 과정에서 생긴 spelling 오류
- 탐지 로직 문제 아님
- 성공 단정 문제 아님
- 보고서 품질 문제
```

---

### 2.2 용어 흔들림

현재 보고서에는 한영 혼합 용어가 많다.

예:

```text
context-only
known asset
baseline
crawler-like
scanner-like
sensitive path probe
method behavior
protocol anomaly
후보 밖 탐색성 요청
정상 비교군
```

이런 용어가 많을수록 LLM이 표현을 조금씩 다르게 쓰거나 철자를 틀릴 가능성이 있다.

---

### 2.3 넓은 category 표현

일부 결과에서는 의미가 더 구체적인데도 넓은 category가 남는다.

예:

```text
low_signal_fuzzing
low_signal_dir_probe
```

실제 문맥은 더 구체적일 수 있다.

```text
crawler_like_baseline
static_asset_baseline
sensitive_path_probe_context
health_check_error_context
```

다만 현재는 top-level summary가 별도 문맥을 제공하므로 기능상 큰 문제는 아니다.

---

### 2.4 row-level / summary-level 표현 혼동 가능성

H R3에서 한때 supporting event가 summary 전체 힌트를 많이 포함했다.

예:

```text
supporting row = /server-status
reason_hints = wp_login, env_file, backup_artifact 등 summary-level hint 포함
```

이는 이미 row-specific hint 중심으로 개선했다.

남은 교훈:

```text
- summary-level context는 top-level summary에 둔다.
- row-level event에는 해당 row에 직접 관련된 hint를 우선 둔다.
```

---

### 2.5 key finding severity와 top incident severity 불일치

H R4 mixed benign + scanner-like dry-run/실제 보고서 검토에서 다음 사례가 관찰됐다.

대표 incident:

```text
verdict=suspicious_scan
severity=low
uri=/server-status
status=403
```

그런데 Stage2 `key_findings` 중 하나가 다음처럼 표현됐다.

```text
"민감 경로 정찰과 /server-status 탐색이 같은 출발지에서 관찰됨" [medium]
```

이 사례의 성격은 다음과 같다.

```text
- 성공/침해/노출 단정은 없었다.
- 따라서 치명적 오판은 아니다.
- 그러나 top incident가 low인데 key finding이 medium으로 올라가 report consistency 관점에서 과장으로 보일 수 있다.
- 특히 H R4는 static/crawler/sensitive-path/mixed/ip aggregate 같은 context-only summary가 함께 많아 전체 중요도를 높게 표현하기 쉬운 조건이었다.
```

---

## 3. 원인 분석

### 3.1 LLM 자연어 생성 특성

Stage2 Markdown은 LLM이 생성한다. 따라서 철자, 문장 구조, 표현 방식은 매번 약간 달라질 수 있다.

이 문제는 JSON schema나 candidate selection 문제와 구분해야 한다.

```text
탐지 로직 문제: candidate/hint/context가 잘못 생성됨
보고서 wording 문제: 산출된 정보를 자연어로 표현하는 과정에서 오타/표현 흔들림 발생
```

`crawller-like`는 후자다.

---

### 3.2 표준 용어 사전 부족

현재 Stage2 prompt에는 정책과 해석 제한이 많지만, 표준 용어 사전이 충분히 명시되어 있지는 않다.

예를 들어 다음 용어는 표준 표기를 고정하는 것이 좋다.

```text
crawler-like
scanner-like
context-only
known asset
baseline
reference baseline
method behavior
protocol anomaly
static baseline
sensitive path probe
no success inference
```

---

### 3.3 한영 혼합 표현

보고서는 한국어 문장에 영어 기술 용어가 섞인다.

예:

```text
crawler-like User-Agent와 baseline context가 함께 관찰됨
```

이 방식은 기술적으로는 자연스럽지만, LLM의 철자 오류 가능성을 높인다.

---

### 3.4 후처리 lint 부재

현재 회귀 검증은 구조 중심이다.

```text
- report_input에 summary가 들어갔는지
- policy_notes가 있는지
- 성공 단정 표현이 없는지
- dry-run Markdown에 필요한 섹션이 있는지
```

하지만 다음 항목은 아직 체계적으로 검사하지 않는다.

```text
- 오타
- 용어 통일성
- 문장 반복
- 표현의 어색함
- 과도한 완곡/과장 표현
```

---

### 3.5 key finding severity와 top incident severity가 별도 생성됨

현재 Stage2는 `top_incidents`와 `key_findings`를 같은 입력으로 생성하지만, severity 문구는 LLM이 별도로 서술한다.

이때 다음 현상이 생길 수 있다.

```text
- top incident severity는 low
- context-only summary 수는 많음
- LLM이 전체 관찰 중요도를 강조하면서 key finding severity만 medium으로 올림
```

즉, 이 문제는 prepare 탐지 로직이나 candidate 선정 로직의 오류라기보다 **Stage2 wording/guidance 부족**에 가깝다.

---

## 4. 표준 용어 후보

Stage2 보고서에서 아래 용어는 가능한 한 표준 표기로 유지한다.

| 개념 | 표준 표현 | 피할 표현 |
|---|---|---|
| crawler 유사 접근 | `crawler-like` | `crawller-like`, `crawler like` |
| scanner 유사 접근 | `scanner-like` | `scannerlike` |
| 문맥 전용 | `context-only` | `context only`, `incident-like` |
| 알려진 내부 자산 | `known asset` | `known attacker`, `trusted attacker` |
| 기준선 | `baseline` | `normal proof`, `safe proof` |
| 정상 비교군 | `reference baseline` | `confirmed normal` |
| 민감 경로 탐색 | `sensitive path probe` | `file exposure success` |
| method 문맥 | `method behavior context` | `method exploit success` |
| protocol 문맥 | `protocol anomaly context` | `protocol bypass success` |
| static 문맥 | `static baseline context` | `static file confirmed` |
| crawler 문맥 | `crawler baseline context` | `real crawler confirmed` |
| 성공 단정 금지 | `no success inference` | `success confirmed` |

---

## 5. 대응 원칙

### 5.1 탐지 로직과 wording 문제 분리

오타나 표현 흔들림이 있더라도 아래가 유지되면 탐지 로직 문제로 보지 않는다.

```text
- 후보 선정이 적절함
- reason_hints가 적절함
- context-only summary가 유지됨
- 성공/침해/노출을 단정하지 않음
- severity가 적절함
```

---

### 5.2 바로 코드 수정하지 않는 기준

다음 정도는 즉시 코드 수정 대상이 아니다.

```text
- 단발성 오타
- 의미가 명확한 경미한 표현 흔들림
- 보고서 전체 판단에 영향 없는 문장 품질 문제
```

단, 반복되면 Stage2 prompt/guidance 보강을 검토한다.

---

### 5.3 코드 수정이 필요한 기준

다음은 수정 대상이다.

```text
- 성공/침해/노출 단정 표현
- context-only summary를 incident처럼 표현
- baseline을 공격으로 과승격하는 표현
- known asset을 공격자로 단정
- static/crawler/sensitive path의 내용을 확인한 것처럼 표현
- 같은 오타/용어 흔들림이 반복적으로 발생
```

---

## 6. 가능한 개선 방향

### 6.1 Stage2 prompt에 표준 용어 목록 추가

`src/llm_stage2_reporter.py`의 prompt/guidance에 표준 용어를 추가할 수 있다.

예:

```text
Use these exact terms when applicable:
- crawler-like
- scanner-like
- context-only
- known asset
- baseline
- reference baseline
- sensitive path probe
- no success inference
```

효과:

```text
- 오타 감소
- 표현 일관성 증가
```

위험:

```text
- prompt가 더 길어짐
- 용어 목록이 계속 커질 수 있음
```

현재는 선택 사항이다.

---

### 6.2 Markdown 후처리 lint 추가

나중에 보조 스크립트를 둘 수 있다.

```text
scripts/check_llm_report_safety.py
```

역할:

```text
- 위험 표현 후보 탐지
- 오타 후보 탐지
- 성공 단정 의심 문장 추출
- context-only 관련 문장 점검
```

단, 자동 판정기는 아니다. 최종 판단은 사람이 한다.

---

### 6.3 간단한 typo denylist

초기에는 아주 좁게 시작할 수 있다.

예:

```text
crawller-like -> crawler-like
sucess -> success
compromized -> compromised
```

하지만 오타 치환이 의미를 바꿀 수 있으므로 자동 수정보다는 lint warning이 안전하다.

---

### 6.4 key finding severity ceiling guidance 추가

이번 작업에서는 탐지 로직을 바꾸지 않고 `src/llm_stage2_reporter.py`의 Stage2 guidance를 보강한다.

핵심 규칙:

```text
- 명시적인 non-context-only 근거가 없으면 key_findings severity를 top_incidents 최대 severity보다 높이지 않는다.
- context-only summary는 severity 상향의 단독 근거가 아니다.
- top incident가 없거나 모두 info/low이고 관찰 근거가 context-only summary 중심이면 key_findings severity는 info 또는 low를 사용한다.
- medium/high는 medium/high top incident, 반복적인 고신뢰 candidate, 또는 다른 명시적 non-context-only candidate evidence가 있을 때만 허용한다.
```

이 대응은 다음 성격을 가진다.

```text
- prepare 수정 아님
- Stage1 schema/logic 수정 아님
- candidate 선정 로직 수정 아님
- H R4 prepare 결과 수정 아님
- Stage2 wording/guidance 수정
```

---

## 7. 현재 판단

현재 판단은 다음과 같다.

```text
- 단순 오타/용어 흔들림은 계속 관찰 대상으로 둔다.
- H R4 severity consistency 문제는 실제 prompt/guidance 보강 대상으로 본다.
- 이번 대응은 탐지 로직 수정이 아니라 wording/guidance 수정으로 한정한다.
```

즉, 오타 계열은 문서화와 관찰 중심으로 두되, severity 과상향 가능성은 Stage2 prompt/report input policy 강화로 바로 관리한다.

---

## 8. 후속 조건

아래 조건 중 하나라도 발생하면 실제 개선을 진행한다.

```text
- 동일 오타가 2회 이상 반복
- crawler-like / scanner-like / context-only 같은 핵심 용어 흔들림이 반복
- 보고서에서 성공 단정 표현이 다시 나타남
- known asset을 공격자로 단정하는 표현 발생
- baseline/context가 incident처럼 설명됨
- 발표/보고서 제출 전 문서 품질 정리가 필요함
```

---

## 9. 다음 우선순위

현재는 아래 순서를 권장한다.

```text
1. H R4 mixed benign + scanner-like 실험 여부 결정
2. 실제 LLM 샘플 검증을 몇 개 더 수행할지 결정
3. 발표/보고용 요약이 필요해지는 시점에 Stage2 wording 표준화 반영
4. 반복 문제가 확인되면 check_llm_report_safety.py 작성
```

---

## 10. 결론

Stage2 wording 품질 문제는 현재까지는 경미하다.

```text
탐지/해석 원칙은 유지되고 있다.
단발 오타와 표현 흔들림은 문서화하고 관찰한다.
H R4 같은 severity consistency 문제는 Stage2 guidance 보강으로 대응한다.
이번 조정은 탐지 로직이 아니라 wording/guidance 범위의 수정이다.
```
