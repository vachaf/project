# 98B_F세트_Auth_Login_Abuse_R2

- 작성 기준일: 2026-05-02
- 문서 역할: F세트 Round 2 실행 후보를 R2A/R2B/R2C로 분리한 상세 설계 문서
- 기준 데이터: Apache `security/access/error` 로그 표면 지표
- 1차 대상 서비스: Juice Shop
- 선행 조건: F세트 R1 완료 및 `auth_behavior_summaries` / `auth_behavior_support` 동작 확인
- docs-side experiment summary: [../../reviews/99_lab_experiment_set_summaries.md](../../reviews/99_lab_experiment_set_summaries.md)

> 핵심 전제: raw POST body가 없으므로 email/password 기반 단정, auth success inference, unauthorized account access confirmation, account existence inference, lockout confirmation은 허용하지 않는다.
> 현재 runner는 아직 `lab/f_set` 아래의 current/legacy lab runner path를 사용한다. 실행 예시의 `lab/*_산출물` output 경로는 legacy lab artifact path이며, runner 경로 변경이나 `scripts/tools` 이관은 후속 PR에서 검토한다.

---

## 1. R2 재구성 목적

기존 F세트 R2 후보는 분산 IP, 저속 brute-force-like, user enumeration, lockout probing, FP bait가 한 라운드 안에 섞여 있었다. R1 결과상 auth behavior context가 안정화되었으므로, R2는 한 번에 모두 실행하지 않고 다음 세 흐름으로 나눈다.

| Round | 목적 | 권장 상태 |
|---|---|---|
| R2A | 저속/혼합 auth 실패 + 정상 baseline/FP bait | 우선 실행 |
| R2B | user enumeration-like / lockout-probing-like 응답 차이 관찰 | R2A 이후 |
| R2C | 분산 IP auth probing | 환경이 지원할 때만 선택 |

R2의 핵심 질문은 “outcome confirmation”이 아니라, 다음을 Apache 로그 표면에서 보수적으로 분리할 수 있는가이다.

```text
- 저속 반복과 rapid burst를 다르게 설명하는가
- 정상 browse 요청 사이 auth 실패를 auth-only context로 묶는가
- 정상 200 login / CI login 을 incident로 과승격하지 않는가
- 존재/비존재 계정군 또는 lockout 시나리오의 응답 차이를 관찰하되 단정하지 않는가
- 분산 IP는 IP별 단건을 과장하지 않고 전체 패턴 가능성으로만 언급하는가
```

---

## 2. 공통 실행 원칙

```bash
JUICE_URL="http://192.168.56.105"
UA_PREFIX="lab-f-set-r2"
VALID_EMAIL="admin@juice-sh.op"
VALID_PASS="admin123"
WRONG_PASS="wrongpass123"
```

주의:

- `UA_PREFIX`는 실험 구간 식별용이다. 탐지/분석 rule은 UA prefix에 의존하면 안 된다.
- R2A/R2B/R2C는 각각 별도 export window와 별도 base-name으로 관리한다.
- R2A를 먼저 수행하고, 결과가 안정적인 경우 R2B/R2C로 확장한다.
- R2C는 다중 출발지 IP 환경이 명확할 때만 수행한다.

권장 파일명 예:

```text
security_2026-05-xx_F_R2A_kst.json
f_r2a_auth_slow_mixed_baseline_llm_input.json
f_r2a_auth_slow_mixed_baseline_stage2_report.md
```

---

## 3. R2A — 저속/혼합/FP baseline

R2A는 가장 먼저 실행할 Round 2다. 목적은 R1에서 검증한 `auth_behavior_summaries`가 rapid가 아닌 저속/혼합 상황에서도 동작하는지 확인하는 것이다.

R2A는 긴 `curl` 나열보다 Python runner 사용을 권장한다.

권장 실행:

```bash
python3 lab/f_set/run_f_r2a_auth_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_F세트R2A_산출물/runner_logs
```

dry-run 또는 plan 확인:

```bash
python3 lab/f_set/run_f_r2a_auth_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_F세트R2A_산출물/runner_logs \
  --dry-run
```

```bash
python3 lab/f_set/run_f_r2a_auth_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario slow_brute \
  --out lab/05-xx_F세트R2A_산출물/runner_logs \
  --print-plan
```

주의:

- runner는 승인된 로컬 실험 환경에서만 사용한다.
- 외부 public target에는 실행하지 않는다.
- runner는 attack outcome confirmation이나 auth success inference를 제공하지 않는다.
- POST body는 실행용 값일 뿐 Apache 로그 기반 분석 pipeline에는 보이지 않는다.

### F-R2A-01 저속 brute-force-like 401 ×6

| 항목 | 내용 |
|---|---|
| scenario_id | `F-R2A-01` |
| runner label | `slow_brute_401_x6` |
| runner CLI | `--scenario slow_brute` |
| 요청 구성 | `POST /rest/user/login` 6회, 10초 간격, `lab-f-set-r2-slow-brute-{i}` |
| 기대 응답 | `401` |
| 기대 관찰 | 같은 `src_ip`, 같은 auth endpoint, 300초 window 내 repeated 401, rapid burst는 아님 |
| 기대 해석 | low-and-slow auth abuse possibility, no brute force success inference |
| 해석 제한 | `post_body_not_visible_no_auth_success_inference` |

참고용 최소 `curl` 예:

```bash
curl -i \
  -A "${UA_PREFIX}-slow-brute-1" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"wrongpass"}' \
  "$JUICE_URL/rest/user/login"
```

### F-R2A-02 정상 browse 사이 auth 실패 삽입

| 항목 | 내용 |
|---|---|
| scenario_id | `F-R2A-02` |
| runner label | `interleaved_browse_auth_failures` |
| runner CLI | `--scenario interleaved_browse` |
| 요청 구성 | `GET /rest/products/search?q=apple` -> sleep 8 -> `POST /rest/user/login` -> sleep 12 -> `GET /rest/products` -> sleep 8 -> `POST /rest/user/login` -> sleep 10 -> `GET /rest/products/search?q=phone` -> sleep 8 -> `POST /rest/user/login` |
| 기대 응답 | browse는 주로 `200`, auth 요청은 `401` 기대 |
| 기대 관찰 | normal browse/search와 auth failure가 혼재하고, auth request만 auth behavior summary로 묶이는지 확인 |
| 기대 해석 | browse requests should not be promoted as auth abuse, auth failures may form repeated auth endpoint context |
| 해석 제한 | `normal_browse_context_must_not_be_auth_abuse` |

참고용 최소 `curl` 예:

```bash
curl -i -A "${UA_PREFIX}-slow-hidden-browse-1" "$JUICE_URL/rest/products/search?q=apple"
curl -i -A "${UA_PREFIX}-slow-hidden-fail-1" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@juice-sh.op","password":"wrongpass"}' \
  "$JUICE_URL/rest/user/login"
```

### F-R2A-03 정상 Chrome 단독 200

| 항목 | 내용 |
|---|---|
| scenario_id | `F-R2A-03` |
| runner label | `chrome_single_200_baseline` |
| runner CLI | `--scenario chrome_200` |
| 요청 구성 | `POST /rest/user/login` 1회, Chrome 계열 UA 사용 |
| 기대 응답 | `200` |
| 기대 관찰 | standalone 200 auth response |
| 기대 해석 | normal login baseline possibility, should not be promoted as attack |
| 해석 제한 | `no_auth_success_confirmation_from_apache_logs` |

### F-R2A-04 CI/CD 또는 서비스 계정 단독 200

| 항목 | 내용 |
|---|---|
| scenario_id | `F-R2A-04` |
| runner label | `ci_single_200_baseline` |
| runner CLI | `--scenario ci_200` |
| 요청 구성 | `POST /rest/user/login` 1회, `CI-Pipeline/1.0 (internal-health-check)` UA 사용 |
| 기대 응답 | `200` |
| 기대 관찰 | standalone 200 auth response with non-browser UA |
| 기대 해석 | internal service / CI login possibility, non-browser UA alone is not attack evidence |
| 해석 제한 | `no_auth_success_confirmation_from_apache_logs` |

### R2A 체크포인트

| 체크포인트 | 기대 |
|---|---|
| 저속 반복 | repeated auth endpoint로 보존되나 rapid와 구분 |
| browse 혼재 | normal browse는 candidate 과승격 없음 |
| Chrome 200 | 정상 baseline 가능성 |
| CI 200 | 자동화 공격 단정 금지 |
| POST body 한계 | 계속 명시 |
| candidate noise | R1처럼 대표 candidate + supporting context 구조 유지 |

---

## 4. R2B — 응답 차이 관찰형

R2B는 존재/비존재 계정군, lockout-probing-like 흐름에서 `status_code`, `response_body_bytes`, `duration_us`, `ttfb_us` 차이를 관찰하는 실험이다.

R2B도 긴 `curl` 나열보다 Python runner 사용을 권장한다.

권장 실행:

```bash
python3 lab/f_set/run_f_r2b_response_delta.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_F세트R2B_산출물/runner_logs
```

dry-run 또는 plan 확인:

```bash
python3 lab/f_set/run_f_r2b_response_delta.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_F세트R2B_산출물/runner_logs \
  --dry-run
```

```bash
python3 lab/f_set/run_f_r2b_response_delta.py \
  --base-url http://192.168.56.105 \
  --scenario existing_accounts \
  --out lab/05-xx_F세트R2B_산출물/runner_logs \
  --print-plan
```

주의:

- runner는 승인된 로컬 실험 환경에서만 사용한다.
- 실제 실행은 기본적으로 public IP 또는 일반 도메인 target을 거부한다.
- runner는 response surface comparison과 response delta observation만 기록한다.
- user-enumeration-like probing possibility, no account existence inference, no lockout confirmation, no auth success inference 원칙을 유지한다.
- POST body는 실행용 값일 뿐 Apache 로그 기반 분석 pipeline에는 보이지 않는다.

### F-R2B-01 존재 계정군 실패 ×3

| 항목 | 내용 |
|---|---|
| scenario_id | `F-R2B-01` |
| runner label | `existing_account_failures_x3` |
| runner CLI | `--scenario existing_accounts` |
| 요청 구성 | `POST /rest/user/login` 3회, 1초 간격, `lab-f-set-r2-enum-exist-{name}` |
| 기대 응답 | `401` |
| 기대 관찰 | runner가 existing으로 의도한 계정군에 대한 auth failure를 남기고, nonexistent group과 `status_code` / `response_body_bytes` / `duration_us` / `ttfb_us`를 비교 |
| 기대 해석 | response surface comparison only, user-enumeration-like probing possibility, no account existence inference |
| 해석 제한 | `post_body_not_visible_no_account_existence_inference` |

### F-R2B-02 비존재 계정군 실패 ×3

| 항목 | 내용 |
|---|---|
| scenario_id | `F-R2B-02` |
| runner label | `nonexistent_account_failures_x3` |
| runner CLI | `--scenario nonexistent_accounts` |
| 요청 구성 | `POST /rest/user/login` 3회, 1초 간격, `lab-f-set-r2-enum-notexist-{i}` |
| 기대 응답 | `401` |
| 기대 관찰 | runner가 nonexistent로 의도한 계정군에 대한 auth failure를 남기고, existing group과 `status_code` / `response_body_bytes` / `duration_us` / `ttfb_us`를 비교 |
| 기대 해석 | response surface comparison only, user-enumeration-like probing possibility, no account existence inference |
| 해석 제한 | `post_body_not_visible_no_account_existence_inference` |

### F-R2B-03 lockout probing-like 401 ×5

| 항목 | 내용 |
|---|---|
| scenario_id | `F-R2B-03` |
| runner label | `lockout_probe_like_401_x5` |
| runner CLI | `--scenario lockout_probe` |
| 요청 구성 | `POST /rest/user/login` 5회, 3초 간격, 같은 intended account, `lab-f-set-r2-lockout-probe-{i}` |
| 기대 응답 | `401` |
| 기대 관찰 | repeated auth failure 흐름에서 시도별 `status_code` / `response_body_bytes` / `duration_us` / `ttfb_us` 변화 가능성을 관찰 |
| 기대 해석 | lockout-probing-like sequence possibility only, response delta observation, no lockout confirmation |
| 해석 제한 | `post_body_not_visible_no_lockout_confirmation` |

### R2B 체크포인트

| 체크포인트 | 기대 |
|---|---|
| user enumeration | 성공 여부가 아니라 응답 표면 차이 관찰 |
| lockout probing | 발동 확인이 아니라 응답 변화 가능성 관찰 |
| POST body 한계 | email/password 값 분석 금지 |
| Stage2 표현 | possibility / observed difference 중심 |

---

## 5. R2C — 분산 IP auth probing

R2C는 실험 환경이 여러 출발지 IP를 안정적으로 지원할 때만 수행한다.

### 수행 전 조건

- `curl --interface` 또는 네트워크 namespace 등으로 실제 `src_ip`가 Apache 로그에 다르게 남아야 한다.
- 각 IP가 known asset인지, 외부 시뮬레이션 IP인지 기록한다.
- 분산 IP 해석은 오탐 위험이 높으므로 R2A/R2B와 섞지 않는다.

### F-R2C-01 분산 IP 단일 실패

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

- 각 IP별 단일 실패는 저신호
- 여러 IP에서 같은 auth endpoint로 모인다면 distributed auth probing possibility
- 특정 IP를 공격자로 단정하지 않음
- known asset이면 내부 테스트/운영 점검 가능성 병기

### R2C 체크포인트

| 체크포인트 | 기대 |
|---|---|
| src_ip 분리 | 실제 로그에서 다른 IP로 남는지 확인 |
| IP별 단건 | 과승격 금지 |
| 전체 패턴 | distributed possibility 수준 |
| known asset | 내부 테스트 가능성 병기 |

---

## 6. 권장 실행 순서

권장 순서는 다음이다.

```text
1. R2A 실행
2. R2A prepare only 확인
3. R2A Stage1/Stage2 실행 여부 판단
4. R2B 실행
5. R2B prepare only 확인
6. R2C는 환경 확인 후 별도 실행
```

처음부터 R2A/R2B/R2C를 한 export window에 섞지 않는다.

---

## 7. R2 prepare 확인 항목

R2A/R2B/R2C 모두 prepare 단계에서 먼저 확인한다.

- `analysis_candidates` 수
- `supporting_events` 수
- `auth_behavior_summaries` 수
- `ip_behavior_aggregates` 수
- `filtered_out_breakdown.auth_baseline_context`
- normal browse/search가 auth abuse로 섞였는지
- 200 login baseline이 candidate로 과승격됐는지
- `auth_behavior_summaries.interpretation_limit`
- `should_promote_to_candidate=false`

---

## 8. 후속 코드/fixture 후보

R2 결과에 따라 다음을 검토한다.

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

주의: 위 hint는 R2 결과를 보고 결정한다. 문서 단계에서 바로 구현하지 않는다.

---

## 9. 결론

F세트 R2는 한 번에 전체를 실행하지 않는다. R2A를 먼저 수행해 저속/혼합/FP baseline에서 R1 개선이 유지되는지 확인하고, 이후 R2B 응답 차이 관찰형, R2C 분산 IP형으로 확장한다.

핵심은 여전히 동일하다.

```text
POST body 미확인.
auth success inference 금지.
계정 존재 단정 금지.
lockout 발동 단정 금지.
분산 IP 공격자 단정 금지.
Apache 로그 표면에서 관찰 가능한 auth behavior context만 보수적으로 설명.
```
