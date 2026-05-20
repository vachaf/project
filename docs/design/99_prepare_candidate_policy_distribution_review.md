# Prepare Candidate Policy Distribution Review

- 기준 시점: 2026-05-20
- 목적: 현재 코드 기준 dry-run 산출물에 `explain_prepare_candidates.py`를 적용해 candidate policy 분포를 관찰하고, 실제 prepare demotion 적용 여부를 판단한다.
- 결론: broad demotion은 아직 적용하지 않는다. 현재 단계는 diagnostic bucket 안정화와 실제 run artifact 기반 분포 관찰 단계로 유지한다.

---

## 1. 검토 배경

최근 작업에서 다음 diagnostic bucket이 `scripts/explain_prepare_candidates.py` 기준으로 정리되었다.

- `keep_candidate_payload`
- `context_candidate_probe`
- `context_only_server_status`
- `demotion_candidate_status_error_only`
- `context_candidate_auth_failure`
- `context_candidate_upload_failure`

fixture/regression 기준 검증은 1차 통과했다.

- `tests/test_prepare_scanner_probe_candidate_policy.py`: `8 passed`
- candidate policy diagnostic bundle: `24 passed`
- prepare regression: `pass=25 warn=0 fail=0`
- stage dry-run regression: `pass=19 warn=0 fail=0`

다만 fixture는 synthetic policy boundary 검증에 가깝다. 실제 demotion 여부를 판단하려면 실제 observability run artifact를 현재 코드로 다시 생성한 뒤 policy distribution을 확인해야 한다.

---

## 2. 검토 입력

이번 검토는 수정 후 현재 코드 기준으로 dry-run을 다시 생성한 artifact를 사용한다.

### PHP sample v2

- run artifact: `runs/obs_php_sample_v2_001_current_dryrun/llm_input.json`
- source: `analysis_candidates`
- candidate count: `13`

### Juice Shop reverse proxy

- run artifact: `runs/obs_juiceshop_proxy_001_current_dryrun/llm_input.json`
- source: `analysis_candidates`
- candidate count: `3`

주의:

- 이전 actual/dry-run 산출물은 일부 prepare/scoring/diagnostic 변경 전 산출물이므로 policy distribution 판단 근거로는 제한적이다.
- 이번 문서는 raw log/export를 기준으로 현재 코드에서 재생성한 dry-run 결과를 기준으로 한다.

---

## 3. PHP sample v2 current dry-run 분포

### 3.1 Policy counts

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |
| `context_candidate_probe` | 5 |
| `demotion_candidate_status_error_only` | 3 |
| `context_candidate_auth_failure` | 1 |
| `context_candidate_upload_failure` | 1 |

### 3.2 Candidate shape

| scenario | method | uri | status | verdict_hint | policy_class | 해석 |
|---|---|---|---:|---|---|---|
| S15 | GET | `/download.php` | 404 | `path_traversal` | `keep_candidate_payload` | traversal payload 구조가 명시되어 있으므로 유지 |
| S14 | GET | `/search.php` | 200 | `xss` | `keep_candidate_payload` | XSS payload 구조가 명시되어 있으므로 유지 |
| S13 | GET | `/search.php` | 200 | `sqli` | `keep_candidate_payload` | SQLi payload 구조가 명시되어 있으므로 유지 |
| S08 | POST | `/login.php` | 401 | `suspicious` | `context_candidate_auth_failure` | 로그인 성공이 아니라 auth failure/context 후보 |
| S12 | GET | `/wp-login.php` | 404 | `suspicious` | `context_candidate_probe` | WordPress/admin presence를 단정하지 않는 probe context |
| S11 | GET | `/error.php` | 500 | `suspicious` | `demotion_candidate_status_error_only` | status/error metadata 중심 후보 |
| S06 | GET | `/private/secret.txt` | 403 | `suspicious` | `demotion_candidate_status_error_only` | 파일 노출 단정 없이 status/error metadata 중심 후보 |
| S09 | POST | `/upload.php` | 400 | `suspicious` | `context_candidate_upload_failure` | upload 성공이 아니라 upload-like failure/context 후보 |
| S12 | GET | `/does-not-exist` | 404 | `suspicious` | `context_candidate_probe` | 존재 여부 단정 없는 probe context |
| S12 | GET | `/.env` | 404 | `suspicious` | `context_candidate_probe` | `.env` 노출 단정 없는 sensitive-path probe context |
| S12 | GET | `/admin` | 404 | `suspicious` | `context_candidate_probe` | admin 존재/접근 성공 단정 없는 probe context |
| S07 | GET | `/login.php` | 200 | `suspicious` | `demotion_candidate_status_error_only` | GET login endpoint 관찰이며 auth success 근거 없음 |
| S05 | GET | `/does-not-exist-obs_php_sample_v2_001` | 404 | `suspicious` | `context_candidate_probe` | missing path probe/context 후보 |

### 3.3 관찰 결과

PHP sample v2 current dry-run은 policy bucket 분리가 비교적 명확하다.

- S13/S14/S15의 명시 payload 요청은 `keep_candidate_payload`로 유지된다.
- S08 login POST는 `context_candidate_auth_failure`로 분류된다.
- S09 upload-like POST는 `context_candidate_upload_failure`로 분류된다.
- `/.env`, `/wp-login.php`, `/admin`, `does-not-exist` 계열은 `context_candidate_probe`로 분리된다.
- payload 없는 403/500/error-linked 중심 후보는 `demotion_candidate_status_error_only`로 분류된다.

이 분포는 diagnostic bucket이 의도한 방향으로 작동함을 보여준다. 다만 이 결과만으로 실제 prepare filtering/demotion을 적용하기에는 아직 표본이 제한적이다.

---

## 4. Juice Shop reverse proxy current dry-run 분포

### 4.1 Policy counts

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |

### 4.2 Candidate shape

| scenario | method | uri | status | verdict_hint | policy_class | 해석 |
|---|---|---|---:|---|---|---|
| S14 | GET | `/search.php` | 200 | `xss` | `keep_candidate_payload` | XSS payload 구조가 명시되어 있으므로 유지 |
| S13 | GET | `/search.php` | 200 | `sqli` | `keep_candidate_payload` | SQLi payload 구조가 명시되어 있으므로 유지 |
| S15 | GET | `/download.php` | 200 | `path_traversal` | `keep_candidate_payload` | traversal payload 구조가 명시되어 있으므로 유지 |

### 4.3 관찰 결과

Juice Shop reverse proxy current dry-run은 candidate count가 3개뿐이며 모두 explicit payload 후보이다.

- reverse proxy / backend response / fallback 200 관련 observability hint가 붙어도 payload 후보로만 유지된다.
- `status_code=200`은 공격 성공/침해 성공/파일 노출 근거로 승격되지 않는다.
- scanner/probe, status/error-only, auth/upload context 분포를 판단하기에는 표본이 부족하다.

따라서 Juice Shop 결과는 `keep_candidate_payload` 보존과 topology hint의 conservative interpretation 확인에는 의미가 있지만, broad demotion 판단 근거로 쓰기에는 제한적이다.

---

## 5. Demotion 판단

### 5.1 status/error-only demotion

현재 결론: 보류.

근거:

- PHP sample v2에서 `demotion_candidate_status_error_only`는 payload 없는 403/500/error-linked 중심 후보로 잘 분류된다.
- 그러나 status/error metadata는 실제 공격 시도에서 보조 신호로 유효할 수 있다.
- broad demotion을 prepare 단계에 바로 적용하면 recall 손실 가능성이 있다.
- 우선 diagnostic bucket으로 관찰하고, 실제 run distribution을 더 쌓는 것이 안전하다.

### 5.2 scanner/probe demotion

현재 결론: 보류.

근거:

- `context_candidate_probe`는 `.env`, `wp-login`, `admin`, missing path 계열을 잘 분리한다.
- 그러나 scanner/probe context는 sensitive path probe, mixed baseline scanner, probing sequence summary에 유용하다.
- prepare에서 단순 drop/demotion하면 summary/context 관찰성이 줄 수 있다.
- context-only를 finding/incident로 승격하지 않는 guardrail은 유지하되, prepare visibility는 아직 보존한다.

### 5.3 auth/upload context demotion

현재 결론: 별도 demotion을 넣지 않는다.

근거:

- S08 login POST는 `context_candidate_auth_failure`로 분류되어 auth success 단정을 피한다.
- S09 upload-like POST는 `context_candidate_upload_failure`로 분류되어 upload success 단정을 피한다.
- 현재 narrow guard는 의도대로 작동한다.
- 추가 demotion은 실제 false-positive/recall tradeoff를 더 본 뒤 판단한다.

---

## 6. 추가 관찰 포인트

### 6.1 S07 GET `/login.php`

PHP sample v2에서 S07 GET `/login.php`는 `demotion_candidate_status_error_only`로 분류되었다.

현재 분류가 크게 문제는 아니다.

- method가 GET이다.
- auth 관련 hint는 `login_endpoint(+1)` 수준이다.
- POST login failure와 달리 `context_candidate_auth_failure`로 분류할 강한 근거가 없다.
- auth success로 단정하지 않는다.

후속 후보:

- 필요하면 `GET login endpoint + error_linked + login_endpoint` 류를 `context_candidate_auth_observation` 같은 별도 bucket으로 분리할 수 있다.
- 단, 현재는 구현하지 않는다.

### 6.2 Juice Shop 표본 한계

Juice Shop current dry-run은 payload-only 3건만 남았다.

- reverse proxy topology에서 payload 후보가 conservative하게 유지되는지는 확인된다.
- scanner/probe/status-error demotion 여부 판단에는 부족하다.
- 필요하면 OpenCart, PHP sample v1, proxy error check, 또는 추가 topology run에서 distribution을 더 수집한다.

---

## 7. Apache logs-only guardrail

아래 원칙은 계속 유지한다.

- `status_code=200`으로 공격 성공/침해 성공을 단정하지 않는다.
- `response_body_bytes`, `resp_content_type`, `text/html`만으로 파일 노출/정보 유출을 단정하지 않는다.
- POST metadata만으로 로그인 성공, 업로드 저장 성공, 계정 장악, DB 영향, 서버 내부 상태 변화를 단정하지 않는다.
- raw POST body, response body, DB 결과, 브라우저 실행 여부는 Apache logs-only 입력에 없으므로 추론하지 않는다.
- scanner/probe context-only 항목을 finding/incident로 승격하지 않는다.
- Web UI는 read-only display/interpretation aid 범위로 유지하고, severity/category/verdict를 재계산하지 않는다.

---

## 8. 다음 작업

1. 이 distribution review를 진행상황/TODO/작업일지에 반영한다.
2. 필요하면 OpenCart 또는 PHP sample v1 current dry-run에도 `explain_prepare_candidates.py`를 적용한다.
3. distribution 표본이 더 쌓이면 demotion이 아니라 narrow rule 후보를 별도 설계한다.
4. 실제 prepare 변경은 다음 조건을 만족할 때만 검토한다.
   - 명시 payload 후보 보존이 fixture/regression/real run에서 계속 확인됨
   - context-only 후보가 summary/context로 보존되는 경로가 명확함
   - drop/demotion이 recall 손실을 만들지 않는다는 근거가 있음
   - Web UI/reporting에서 성공 단정 방지 효과가 diagnostic만으로 부족하다는 실제 사례가 있음

---

## 9. 현재 결론

현재 코드 기준 dry-run distribution은 diagnostic bucket 설계와 대체로 일치한다.

- PHP sample v2는 payload/auth/upload/probe/status-error 분리가 명확하다.
- Juice Shop은 payload-only 표본이며 topology hint가 conservative하게 붙는다.
- broad demotion은 아직 적용하지 않는다.
- 다음 단계는 더 많은 actual/topology run에서 distribution을 축적하고, 필요 시 narrow rule로 별도 설계하는 것이다.
