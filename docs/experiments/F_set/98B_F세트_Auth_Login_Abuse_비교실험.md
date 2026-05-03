# 98B_F세트_Auth_Login_Abuse_비교실험

- 작성 기준일: 2026-05-02
- 문서 역할: F세트 Auth/Login Abuse 실험 인덱스 및 공통 원칙
- 기준 데이터: Apache `security/access/error` 로그 표면 지표
- 1차 대상 서비스: Juice Shop
- 상세 문서:
  - `98B_F세트_Auth_Login_Abuse_R2.md`
- 핵심 전제: **raw POST body는 Apache 기본 로그에 남지 않는다**

> 이 문서는 승인된 로컬 실험 환경에서만 사용한다. Apache 로그만으로는 계정·비밀번호·로그인 성공·계정 탈취·credential stuffing 성공·lockout 발동·세션 탈취를 확정하지 않는다.

---

## 0. F세트의 위치와 설계 철학

F세트는 A세트의 인증 흐름을 확장해, POST body 없이 Apache 로그 표면에 남는 인증 endpoint 반복 패턴을 보수적으로 해석할 수 있는지 확인하는 실험이다.

| 세트 | 카테고리 | 핵심 신호 |
|---|---|---|
| A | baseline / auth 기본 | 단순 로그인 흐름 |
| B | SQLi | query_string 내 SQL 구조 |
| C | XSS | query_string 내 XSS 구조 |
| D | Traversal / HPP / Dir Probe | path/query 조작, probing sequence |
| E | OpenCart / PHP | PHP wrapper, config path, search payload |
| **F** | **Auth / Login Abuse** | **auth endpoint 반복 interaction, status/bytes/time 변화** |

핵심 원칙:

```text
POST body가 없으므로 계정·비밀번호·로그인 성공 여부는 단정하지 않는다.
Apache 로그 표면에서 보이는 auth endpoint 반복 interaction만 보수적으로 분석한다.
```

분석 결과가 body를 본 것처럼 말하면 오버리포팅 실패다. 반대로 반복 auth endpoint 패턴을 모두 정상으로 무시하면 미탐 실패다.

---

## 1. 실험 목적

F세트는 다음을 확인한다.

1. 단일 auth 실패와 반복 auth 실패를 구분하는가.
2. 짧은 시간 내 반복 요청을 brute-force-like 또는 automation-like context로 보수적으로 설명하는가.
3. `401 -> 200` 혼재를 시계열 문맥으로 보되, 실제 로그인 성공은 단정하지 않는가.
4. 단독 `200` 로그인 요청을 정상 사용자 행동 가능성으로 남기는가.
5. 여러 IP/UA/시간창으로 분산된 auth 시도를 과장 없이 설명하는가.
6. user enumeration, lockout probing 가능성을 response size/time 차이 관찰 수준으로 제한하는가.
7. 정상 로그인, 배치, CI/CD, non-auth API 접근을 과도하게 incident로 승격하지 않는가.
8. Stage2 보고서가 POST body visibility 한계를 일관되게 유지하는가.

---

## 2. 해석 한계와 금지 표현

### 사용할 수 있는 신호

- `method`
- `uri` / `path` / `request_uri`
- `query_string`
- `status_code`
- `response_body_bytes`
- `resp_content_type`
- `duration_us`
- `ttfb_us`
- `src_ip`
- `user_agent`
- same `src_ip` / time window / endpoint grouping
- `ip_behavior_aggregates` context-only summary
- `auth_behavior_summaries` context-only summary

### 사용할 수 없는 신호

- raw POST body의 email/password 값
- DB 인증 결과
- response body 원문
- JWT/token 반환 여부
- 브라우저 실행 여부
- 앱 내부 session 생성 여부

### 금지 표현

아래 표현은 Apache 로그만으로 직접 단정하지 않는다.

- 로그인 성공 확인
- 계정 탈취 성공
- credential stuffing 성공
- 비밀번호 대입 성공
- 특정 계정이 존재함
- lockout 발동 확인
- 세션 토큰 유출
- 침해 성공

권장 표현은 다음 수준이다.

- repeated auth endpoint interaction
- brute-force-like context
- credential-stuffing-like pattern
- user-enumeration-like probing possibility
- lockout-probing-like sequence
- HTTP 200 response observed after repeated 401 responses, but actual authentication success is not confirmed from Apache logs alone

---

## 3. 실험환경 변수

```bash
JUICE_URL="http://192.168.56.105"
UA_PREFIX="lab-f-set"

VALID_EMAIL="admin@juice-sh.op"
VALID_PASS="admin123"
WRONG_PASS="wrongpass123"
```

주의:

- `UA_PREFIX`는 실험 구간 식별을 위한 실행 편의값이다.
- 탐지 로직은 `lab-f-set` User-Agent에 의존하면 안 된다.
- Stage2 보고서에서는 `auth_behavior_summaries`와 `ip_behavior_aggregates` count를 scope별로 분리해 설명한다.
- IP, response size, Juice Shop endpoint 이름을 hard-code하면 안 된다.
- POST body의 email/password는 실행자가 시나리오를 만들기 위해 쓰는 값일 뿐, 분석 AI가 볼 수 있는 근거가 아니다.

---

## 4. Round 구성

| Round | 목적 | 상태 |
|---|---|---|
| R1 | 단일 실패, 반복 실패, rapid, 200 혼재, 정상 baseline | 수행 완료 |
| R2A | 저속/혼합 auth 실패 + 정상 baseline/FP bait | 우선 실행 후보 |
| R2B | user enumeration-like / lockout-probing-like 응답 차이 관찰 | R2A 이후 후보 |
| R2C | 분산 IP auth probing | 환경 지원 시 선택 |

R2 상세는 `98B_F세트_Auth_Login_Abuse_R2.md`에서 관리한다. R2는 한 export window에 모두 섞지 않고 R2A/R2B/R2C로 분리한다.

공통 실행 흐름:

```text
1. round 시작 시각 기록
2. curl 요청 세트 실행
3. round 종료 시각 기록
4. export_db_logs_cli.py로 security/access 로그 export
5. prepare_llm_input.py 실행
6. prepare 결과 확인
7. Stage1/Stage2 실행 또는 dry-run 확인
8. provider별 비교 문서 작성
```

---

## 5. Round 1 — Core Auth Abuse

Round 1은 다음 흐름을 포함한다.

| ID | 유형 | 기대 HTTP 표면 | 기대 해석 방향 |
|---|---|---|---|
| F-01 | 단일 실패 | 401 1건 | low / likely_false_positive |
| F-02 | 없는 계정 실패 | 401 1건 | F-01과 표면 구분 어려움 |
| F-03 | 반복 실패 3회 | 401 반복 | suspicious_auth_abuse 가능성 |
| F-04 | 반복 실패 10회 | 401 반복 | stronger auth abuse context |
| F-05 | rapid 20회 | 401 burst | automation-like auth attempt |
| F-06 | 실패 후 200 | 401 후 200 | 시계열 경고, 성공 단정 금지 |
| F-07 | 단독 200 | 200 1건 | 정상 로그인 가능성, 오탐 금지 |
| F-08 | 실패 다수 후 200 다수 | 401/200 혼재 | credential-stuffing-like 가능성 |
| F-09 | 정상 session-like | 200/API 접근 | 정상 흐름 가능성 |

상세 실행 payload는 기존 R1 실험 산출물과 `lab/05-02_F세트R1_산출물/2026-05-02_F세트R1_비교.md`를 기준으로 관리한다.

---

## 6. Round 1 결과 요약

F세트 R1에서는 반복 401 login request가 개별 incident로 과다하게 남는 문제가 확인되었고, 이후 prepare가 개선되었다.

개선 전후 핵심 변화:

| 항목 | 개선 전 | 개선 후 |
|---|---:|---:|
| candidate rows | 43 | 3 |
| distinct incidents | 43 | 3 |
| supporting events | 0 | 40 |
| auth behavior summaries | 1 | 1 |
| auth baseline context | 5 | 5 |

결론:

- 반복 401 login request를 개별 incident 43건으로 나열하지 않고 대표 3건만 candidate로 유지했다.
- 나머지 40건은 `auth_behavior_support` context로 보존했다.
- 200 login 5건은 `auth_baseline_context`로 유지되며 candidate로 과승격되지 않았다.
- Stage2는 반복 401, rapid burst, 401/200 혼재를 설명하면서도 로그인 성공·계정 탈취·침해 성공을 단정하지 않았다.

상세 결과:

- `lab/05-02_F세트R1_산출물/2026-05-02_F세트R1_비교.md`

---

## 7. Round 2 재구성 원칙

Round 2는 기존처럼 분산 IP, 저속 brute, user enumeration, lockout probing, FP bait를 한 번에 실행하지 않는다.

권장 순서:

```text
1. R2A — 저속/혼합/FP baseline
2. R2B — 응답 차이 관찰형
3. R2C — 분산 IP, 환경 지원 시 선택
```

핵심 제한:

- user enumeration은 성공 여부가 아니라 response surface 차이 관찰로만 해석한다.
- lockout은 발동 확인이 아니라 status/bytes/time 변화 가능성으로만 해석한다.
- 분산 IP는 특정 IP를 공격자로 단정하지 않는다.
- 정상 Chrome/CI/batch 로그인은 FP bait로 사용하며 과승격을 피한다.

상세 설계:

- `98B_F세트_Auth_Login_Abuse_R2.md`

---

## 8. 평가 매트릭스

결과 비교 문서에는 아래 축을 기록한다.

| 축 | 질문 |
|---|---|
| POST body 한계 인식 | email/password/body를 보지 못한다는 제약을 명시하는가 |
| 단일 vs 반복 | F-01/F-03/F-04를 다른 위험도로 보는가 |
| 속도 기반 인식 | rapid와 slow 반복을 구분하는가 |
| 200 응답 해석 | 단독 200과 실패 후 200을 구분하는가 |
| 시계열 묶음 | 401 -> 200 또는 반복 401을 sequence로 보는가 |
| FP 억제 | 정상 로그인/CI/배치를 incident로 과승격하지 않는가 |
| 분산/저속 패턴 | IP/time-window context를 보조 신호로 쓰는가 |
| user enumeration | bytes/time 차이를 가능성으로만 다루는가 |
| lockout probing | 응답 변화 관찰을 성공 단정 없이 설명하는가 |

---

## 9. pipeline 관찰 포인트

### prepare 단계

- 단일 auth 실패가 과도하게 `analysis_candidates`로 승격되지 않는가.
- 반복 auth endpoint가 `auth_behavior_summaries`와 supporting context로 보존되는가.
- `ip_behavior_aggregates`가 생성되더라도 context-only 원칙을 유지하는가.
- 정상 search/API/browse 요청이 auth abuse로 섞이지 않는가.
- `lab-f-set` UA가 탐지 조건으로 사용되지 않는가.

### Stage1

- body 미확인 한계를 유지하는가.
- 단일 실패는 low/inconclusive/likely_false_positive에 가깝게 처리하는가.
- 반복 실패/rapid/mixed 401-200은 suspicious auth abuse 가능성으로 볼 수 있는가.
- 실제 인증 성공 또는 credential stuffing 성공을 단정하지 않는가.

### Stage2

- sequence 중심으로 설명하는가.
- `200` 응답을 성공 단정이 아니라 보조 신호로만 쓰는가.
- normal baseline/FP bait를 별도로 구분하는가.
- provider별 차이를 보수성/오버리포팅 관점에서 비교하는가.

---

## 10. 실행 후 기록 항목

| 항목 | 값 |
|---|---|
| 실험 날짜 | `[입력 필요]` |
| 대상 서비스 | Juice Shop |
| Round | `[R1/R2A/R2B/R2C]` |
| 시작/종료 | `[입력 필요]` |
| raw export | `[입력 필요]` |
| prepare 산출물 | `[입력 필요]` |
| Stage1 OpenAI/Anthropic | `[입력 필요]` |
| Stage2 OpenAI/Anthropic | `[입력 필요]` |
| known_asset_ips | `[입력 필요]` |
| mode/top-N | `[입력 필요]` |

보수성 평가:

| 케이스 | 기대 보수성 | OpenAI 실제 | Anthropic 실제 | 오버리포팅 여부 |
|---|---|---|---|---|
| 실패 후 200 | 성공 단정 금지 |  |  |  |
| 단독 200 | 정상 가능성 |  |  |  |
| 실패 후 다수 200 | stuffing-like 가능성 |  |  |  |
| enumeration-like | 가능성 수준 |  |  |  |
| FP bait | 오탐 금지 |  |  |  |

---

## 11. 향후 코드/fixture 후보

F세트 실행 결과에 따라 아래를 후속 작업으로 검토한다.

1. 저속 반복 전용 hint
   - `auth_abuse:low_and_slow`
2. browse interleaving hint
   - `auth_abuse:browse_interleaved_auth_failures`
3. user enumeration response-difference summary
   - `auth_abuse:user_enumeration_response_delta_possible`
4. lockout probing response-difference summary
   - `auth_abuse:lockout_response_change_possible`
5. distributed auth probing summary
   - `auth_abuse:distributed_auth_endpoint_pattern`

주의: 위 항목은 R2 결과를 보고 결정한다. 문서 단계에서 바로 구현하지 않는다.

---

## 12. 주의사항

- F세트는 Auth/Login Abuse 전용이다. SQLi/XSS payload를 섞지 않는다.
- 모든 요청은 승인된 로컬 실험 환경에서만 수행한다.
- rapid 병렬 요청은 서버 부하를 만들 수 있으므로 격리 환경에서만 실행한다.
- 분산 IP 시나리오는 환경이 지원할 때만 수행한다.
- `UA_PREFIX`는 실험 구간 식별용이며, 탐지 조건으로 사용하지 않는다.
- Apache 로그만으로 POST body 내부 값을 추론하지 않는다.
- 정상 로그인/CI/배치 패턴을 공격으로 과장하지 않는다.

---

## 13. 발표용 한 줄 정리

F세트는 POST body가 보이지 않는 Apache 로그 환경에서 auth endpoint 반복, rapid burst, 401/200 혼재, 분산/저속 시도를 보수적으로 해석할 수 있는지 검증하는 실험이다. R1에서는 반복 인증 실패를 `auth_behavior_summaries` 중심으로 안정화했고, R2는 저속/혼합/응답 차이/분산 IP를 별도 라운드로 나누어 검증한다.
