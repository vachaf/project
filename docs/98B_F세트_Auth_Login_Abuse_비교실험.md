# 98B_F세트_Auth_Login_Abuse_비교실험

- 작성 기준일: 2026-05-02
- 문서 역할: `docs/98_비교_실험_요청_세트_표준.md` 계열을 따르는 **F세트 Auth/Login Abuse 비교 실험 설계 문서**
- 기준 데이터: Apache `security/access/error` 로그 표면 지표
- 1차 대상 서비스: Juice Shop
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

핵심 원칙은 두 가지다.

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

### 2.1 사용할 수 있는 신호

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

### 2.2 사용할 수 없는 신호

- raw POST body의 email/password 값
- DB 인증 결과
- response body 원문
- JWT/token 반환 여부
- 브라우저 실행 여부
- 앱 내부 session 생성 여부

### 2.3 금지 표현

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
- IP, response size, Juice Shop endpoint 이름을 hard-code하면 안 된다.
- POST body의 email/password는 실행자가 시나리오를 만들기 위해 쓰는 값일 뿐, 분석 AI가 볼 수 있는 근거가 아니다.

---

## 4. Round 구성

| Round | 목적 | 권장 상태 |
|---|---|---|
| R1 | 단일 실패, 반복 실패, rapid, 200 혼재, 정상 baseline | 필수 |
| R2 | 분산 IP, 저속 brute, user enumeration, lockout probing, FP bait | R1 이후 선택 |

각 round는 별도 export window와 별도 base-name으로 관리한다.

권장 흐름:

```text
1. round 시작 시각 기록
2. curl 요청 세트 실행
3. round 종료 시각 기록
4. export_db_logs_cli.py로 security/access 로그 export
5. prepare_llm_input.py 실행
6. Stage1 실행 또는 dry-run 확인
7. Stage2 실행 또는 dry-run 확인
8. provider별 비교 문서 작성
```

---

## 5. Round 1 — Core Auth Abuse

### F-01 단일 로그인 실패

```bash
curl -i \
  -A "${UA_PREFIX}-single-fail-1" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"wrongpass123"}' \
  "$JUICE_URL/rest/user/login"
```

기대 관찰:

- 단일 POST auth endpoint 요청
- 보통 `401` 계열 응답
- 반복성 없음

기대 해석:

- `low` 또는 `likely_false_positive` 수준
- 오입력/정상 실패와 공격을 구분하기 어렵다고 명시
- body 미확인으로 계정·비밀번호 판단 금지

### F-02 단일 로그인 실패 — 존재하지 않는 계정 시나리오

```bash
curl -i \
  -A "${UA_PREFIX}-single-fail-notexist-1" \
  -H "Content-Type: application/json" \
  -d '{"email":"nouser@example.invalid","password":"wrongpass123"}' \
  "$JUICE_URL/rest/user/login"
```

기대 해석:

- F-01과 로그 표면에서 구분이 어렵다는 점을 인식해야 한다.
- 사용자 존재 여부를 response size/time만으로 단정하지 않는다.

### F-03 반복 실패 ×3

```bash
for i in 1 2 3; do
  curl -i \
    -A "${UA_PREFIX}-repeat-fail-${i}" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@juice-sh.op","password":"wrongpass123"}' \
    "$JUICE_URL/rest/user/login"
  sleep 2
done
```

기대 해석:

- 단일 실패보다 높은 auth abuse 가능성
- brute-force-like context 가능성
- 성공/실패의 실제 의미는 POST body 없이 단정하지 않음

### F-04 반복 실패 ×10

```bash
for i in $(seq 1 10); do
  curl -i \
    -A "${UA_PREFIX}-repeat-10-${i}" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@juice-sh.op","password":"wrongpass123"}' \
    "$JUICE_URL/rest/user/login"
  sleep 1
done
```

기대 해석:

- F-03보다 강한 repeated auth interaction
- `suspicious_auth_abuse` 또는 equivalent context
- 개별 요청보다 sequence/grouping 중심으로 설명

### F-05 rapid fail ×20

```bash
for i in $(seq 1 20); do
  curl -s -o /dev/null \
    -A "${UA_PREFIX}-rapid-${i}" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@juice-sh.op","password":"wrongpass123"}' \
    "$JUICE_URL/rest/user/login" &
done
wait
```

기대 해석:

- 짧은 시간 내 auth endpoint burst
- automation-like 또는 brute-force-like context
- 서버 부하가 있을 수 있으므로 격리 실험 환경에서만 수행

### F-06 반복 실패 후 단일 200

```bash
for i in 1 2 3; do
  curl -i \
    -A "${UA_PREFIX}-fail-before-200-${i}" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@juice-sh.op","password":"wrongpass123"}' \
    "$JUICE_URL/rest/user/login"
  sleep 1
done

curl -i \
  -A "${UA_PREFIX}-success-after-fail-1" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"admin123"}' \
  "$JUICE_URL/rest/user/login"
```

기대 해석:

- `401 -> 401 -> 401 -> 200` 시계열 패턴을 auth abuse context로 인식
- 단, `200`은 HTTP 응답 관찰일 뿐 실제 인증 성공으로 단정하지 않음
- response size는 보조 지표이며 token/body 반환 확인 근거가 아님

### F-07 처음부터 단일 200

```bash
curl -i \
  -A "${UA_PREFIX}-direct-200-1" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"admin123"}' \
  "$JUICE_URL/rest/user/login"
```

기대 해석:

- 반복 실패 전제 없는 단독 200은 정상 로그인 가능성이 높음
- F-06과 다른 위험도로 처리해야 함
- 단독 200을 공격 성공이나 계정 탈취로 해석하지 않음

### F-08 반복 실패 후 다수 200

```bash
for i in 1 2 3 4 5; do
  curl -i \
    -A "${UA_PREFIX}-stuffing-fail-${i}" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"wrong${i}@example.invalid\",\"password\":\"wrongpass\"}" \
    "$JUICE_URL/rest/user/login"
  sleep 0.5
done

for i in 1 2; do
  curl -i \
    -A "${UA_PREFIX}-stuffing-200-${i}" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@juice-sh.op","password":"admin123"}' \
    "$JUICE_URL/rest/user/login"
  sleep 1
done
```

기대 해석:

- credential-stuffing-like 또는 auth abuse pattern 가능성
- 성공한 credential stuffing이라고 단정하지 않음
- 여러 POST body 대상 계정은 로그에서 직접 보이지 않는다는 한계 명시

### F-09 정상 로그인 후 정상 API 접근

```bash
curl -i -A "${UA_PREFIX}-normal-session-login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"admin123"}' \
  "$JUICE_URL/rest/user/login"

sleep 1

curl -i -A "${UA_PREFIX}-normal-session-whoami" "$JUICE_URL/rest/user/whoami"
curl -i -A "${UA_PREFIX}-normal-session-products" "$JUICE_URL/rest/products"
curl -i -A "${UA_PREFIX}-normal-session-search" "$JUICE_URL/rest/products/search?q=apple"
```

기대 해석:

- 반복 실패 없는 정상 세션-like 흐름
- incident 과승격 금지
- non-auth API 접근을 auth abuse로 묶지 않음

---

## 6. Round 2 — Advanced Auth Patterns

Round 2는 환경과 시간이 허용될 때 수행한다. R1 결과가 먼저 안정적으로 나와야 한다.

### F-10 분산 IP 실패 패턴

환경이 여러 출발지 IP를 지원할 때만 수행한다.

```bash
curl -i --interface 192.168.56.1 \
  -A "${UA_PREFIX}-dist-ip-1" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"wrongpass"}' \
  "$JUICE_URL/rest/user/login"

curl -i --interface 192.168.56.110 \
  -A "${UA_PREFIX}-dist-ip-2" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"wrongpass"}' \
  "$JUICE_URL/rest/user/login"
```

기대 해석:

- 각 IP별 단일 요청은 저신호
- 여러 IP에서 같은 auth endpoint로 모이면 distributed auth probing 가능성
- 특정 IP를 공격자로 단정하지 않음

### F-11 저속 brute-force-like 패턴

```bash
for i in $(seq 1 6); do
  curl -i \
    -A "${UA_PREFIX}-slow-brute-${i}" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@juice-sh.op","password":"wrongpass"}' \
    "$JUICE_URL/rest/user/login"
  sleep 10
done
```

기대 해석:

- 개별 건은 저신호
- 시간창을 넓게 보면 low-and-slow auth abuse 가능성
- rate limit 우회 성공은 단정하지 않음

### F-12 정상 탐색 사이 auth 실패 삽입

```bash
curl -i -A "${UA_PREFIX}-slow-hidden-browse-1" "$JUICE_URL/rest/products/search?q=apple"
sleep 8
curl -i -A "${UA_PREFIX}-slow-hidden-fail-1" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"wrongpass"}' \
  "$JUICE_URL/rest/user/login"
sleep 12
curl -i -A "${UA_PREFIX}-slow-hidden-browse-2" "$JUICE_URL/rest/products"
sleep 8
curl -i -A "${UA_PREFIX}-slow-hidden-fail-2" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"wrongpass"}' \
  "$JUICE_URL/rest/user/login"
```

기대 해석:

- 정상 browse 요청 사이 auth endpoint 실패가 반복되는지 확인
- 정상 browse를 공격으로 과승격하지 않음
- auth request만 sequence/context로 묶어 설명

### F-13 user enumeration 관찰 세트

```bash
for email in "admin@juice-sh.op" "user1@juice-sh.op" "jim@juice-sh.op"; do
  curl -i \
    -A "${UA_PREFIX}-enum-exist-${email%%@*}" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${email}\",\"password\":\"wrongpass\"}" \
    "$JUICE_URL/rest/user/login"
  sleep 1
done

for email in "notexist1@example.invalid" "notexist2@example.invalid" "notexist3@example.invalid"; do
  curl -i \
    -A "${UA_PREFIX}-enum-notexist-${email%%@*}" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${email}\",\"password\":\"wrongpass\"}" \
    "$JUICE_URL/rest/user/login"
  sleep 1
done
```

기대 해석:

- `status_code`, `response_body_bytes`, `duration_us`, `ttfb_us` 차이를 관찰
- 차이가 있더라도 user enumeration 가능성 수준으로 제한
- body 미확인으로 어떤 이메일을 시도했는지는 분석자가 직접 알 수 없음을 명시

### F-14 lockout probing-like 패턴

```bash
for round in 1 2 3 4 5; do
  curl -i \
    -A "${UA_PREFIX}-lockout-probe-r${round}" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@juice-sh.op","password":"wrongpass"}' \
    "$JUICE_URL/rest/user/login"
  sleep 3
done
```

기대 해석:

- 반복 횟수에 따른 status/bytes/time 변화 관찰
- lockout 발동 또는 우회 성공은 단정하지 않음
- lockout-probing-like sequence 가능성으로만 설명

### F-15 FP bait — 정상/자동화 로그인

```bash
curl -i \
  -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"admin123"}' \
  "$JUICE_URL/rest/user/login"

curl -i \
  -A "CI-Pipeline/1.0 (internal-health-check)" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"admin123"}' \
  "$JUICE_URL/rest/user/login"
```

기대 해석:

- 단독 200은 정상 로그인 또는 서비스 계정 가능성
- CI UA를 자동화 공격으로 단정하지 않음
- 반복 실패나 에러 패턴 없는 경우 incident 과승격 금지

---

## 7. 기대 해석 방향 요약

라벨명은 확정이 아니며, 실제 Stage1/Stage2 taxonomy와 다를 수 있다.

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
| F-10 | 분산 IP | 여러 src_ip | distributed auth probing 가능성 |
| F-11 | 저속 반복 | 401 저속 반복 | low-and-slow 가능성 |
| F-12 | browse 사이 auth 실패 | 정상+401 혼재 | auth request만 context화 |
| F-13 | enumeration 관찰 | 401 그룹 비교 | response 차이 관찰, 단정 금지 |
| F-14 | lockout probing | 401 반복/변화 가능 | lockout-probing-like 가능성 |
| F-15 | FP bait | 단독 200 | 오탐 금지 |

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

F세트 수행 후 prepare/Stage1/Stage2에서 확인할 항목은 다음이다.

### prepare 단계

- 단일 auth 실패가 과도하게 `analysis_candidates`로 승격되지 않는가.
- 반복 auth endpoint가 context 또는 candidate로 보존되는가.
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
| Round 1 시작/종료 | `[입력 필요]` |
| Round 1 raw export | `[입력 필요]` |
| Round 2 시작/종료 | `[선택]` |
| Round 2 raw export | `[선택]` |
| prepare 산출물 | `[입력 필요]` |
| Stage1 OpenAI/Anthropic | `[입력 필요]` |
| Stage2 OpenAI/Anthropic | `[입력 필요]` |
| known_asset_ips | `[입력 필요]` |
| mode/top-N | `[입력 필요]` |

보수성 평가:

| 케이스 | 기대 보수성 | OpenAI 실제 | Anthropic 실제 | 오버리포팅 여부 |
|---|---|---|---|---|
| F-06 실패 후 200 | 성공 단정 금지 |  |  |  |
| F-07 단독 200 | 정상 가능성 |  |  |  |
| F-08 실패 후 다수 200 | stuffing-like 가능성 |  |  |  |
| F-13 enumeration | 가능성 수준 |  |  |  |
| F-15 FP bait | 오탐 금지 |  |  |  |

---

## 11. 향후 코드/fixture 후보

F Round 1 prepare 결과에서 개별 `401` login row가 다수 candidate 로 올라가고, `401 -> 200` 혼재 시계열이 별도 auth context 로 보존되지 않는 문제가 확인되었다. 이에 따라 prepare top-level `auth_behavior_summaries` 추가와 auth baseline row의 `dir_probe:*` 정리가 필요하다는 점이 확인되었다.

F세트 실행 결과에 따라 아래를 후속 작업으로 검토한다.

1. `auth_abuse:*` hint namespace 도입 여부
   - `auth_abuse:repeated_auth_endpoint`
   - `auth_abuse:rapid_fail_burst`
   - `auth_abuse:mixed_401_200_sequence`
   - `auth_abuse:low_and_slow`
   - `auth_abuse:fp_normal_login_baseline`

2. `ip_behavior_aggregates` 확장 여부
   - auth endpoint request count
   - auth status mix
   - auth burst window
   - non-auth browse interleaving

3. prepare regression fixture 후보
   - auth single fail baseline
   - auth repeated fail burst
   - auth mixed 401/200 sequence
   - auth normal login FP bait

4. Stage2 dry-run regression 후보
   - POST body visibility limitation text
   - success assertion denial
   - normal baseline separation

주의: 위 항목은 F세트 결과를 보고 결정한다. 지금 문서 단계에서 바로 rule을 추가하지 않는다.

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

F세트는 POST body가 보이지 않는 Apache 로그 환경에서 auth endpoint 반복, rapid burst, 401/200 혼재, 분산/저속 시도를 보수적으로 해석할 수 있는지 검증하는 실험이다. 핵심은 로그인 성공이나 계정 탈취를 단정하지 않고, 표면 신호 기반 auth abuse 가능성만 제한적으로 경고하는 것이다.
