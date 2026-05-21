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

검증 상태:

- `tests/test_prepare_scanner_probe_candidate_policy.py`: `8 passed`
- candidate policy diagnostic bundle: `24 passed`
- prepare regression: `pass=25 warn=0 fail=0`
- stage dry-run regression: `pass=19 warn=0 fail=0`
- `tests/test_explain_prepare_candidates.py`: `9 passed`
- scenario label diagnostic bundle (`tests/test_explain_prepare_candidates.py`, `tests/test_prepare_status_error_only_candidate_policy.py`, `tests/test_prepare_scanner_probe_candidate_policy.py`): `24 passed`

EHxx error-heavy scenario label diagnostic UX 보강도 완료했다.

- `scenario=EH01` query string 인식
- `obs-error-heavy/EH04` User-Agent 인식
- direct scenario field `eh10` -> `EH10` 정규화
- prepare/scoring/filtering 변경 없음

---

## 2. 검토 입력

이번 검토는 수정 후 현재 코드 기준으로 dry-run을 다시 생성한 artifact를 사용한다.

| run | topology | artifact | candidate_count |
|---|---|---|---:|
| `obs_php_sample_v2_001_current_dryrun` | direct PHP v2 | `runs/obs_php_sample_v2_001_current_dryrun/llm_input.json` | 13 |
| `obs_php_sample_v2_error_heavy_001_current_dryrun` | direct PHP v2 error-heavy | `runs/obs_php_sample_v2_error_heavy_001_current_dryrun/llm_input.json` | 12 |
| `obs_php_sample_002_current_dryrun` | direct PHP v1 | `runs/obs_php_sample_002_current_dryrun/llm_input.json` | 13 |
| `obs_opencart_002_current_dryrun` | front-controller / routed response | `runs/obs_opencart_002_current_dryrun/llm_input.json` | 3 |
| `obs_juiceshop_proxy_001_current_dryrun` | reverse proxy / backend response | `runs/obs_juiceshop_proxy_001_current_dryrun/llm_input.json` | 3 |
| `obs_juiceshop_proxy_v2_001_current_dryrun` | reverse proxy / backend response (v2) | `runs/obs_juiceshop_proxy_v2_001_current_dryrun/llm_input.json` | 3 |
| `obs_juiceshop_proxy_v2_error_check_001_current_dryrun` | reverse proxy backend unavailable check (v2) | `runs/obs_juiceshop_proxy_v2_error_check_001_current_dryrun/llm_input.json` | 2 |

주의:

- 이전 actual/dry-run 산출물은 일부 prepare/scoring/diagnostic 변경 전 산출물이므로 policy distribution 판단 근거로는 제한적이다.
- 이번 문서는 raw log/export를 기준으로 현재 코드에서 재생성한 dry-run 결과를 기준으로 한다.
- `obs_php_sample_v2_error_heavy_001_current_dryrun` 재출력에서 `EH01`~`EH12` 표시를 확인했다. 이는 diagnostic UX 개선이며 policy 분류에는 영향을 주지 않는다.

---

## 3. 전체 distribution 요약

| run | candidate_count | 핵심 분포 | 판단 |
|---|---:|---|---|
| `obs_php_sample_v2_001_current_dryrun` | 13 | payload 3 / probe 5 / status-error 3 / auth 1 / upload 1 | policy bucket 분리 확인 |
| `obs_php_sample_v2_error_heavy_001_current_dryrun` | 12 | payload 3 / probe 4 / status-error 3 / auth 1 / upload 1 | error-linked payload vs status-only 분리 확인 |
| `obs_php_sample_002_current_dryrun` | 13 | payload 3 / probe 5 / status-error 3 / auth 1 / upload 1 | v2와 동일한 분포 반복 확인 |
| `obs_opencart_002_current_dryrun` | 3 | payload 3 | topology 200에서도 payload-only 유지 |
| `obs_juiceshop_proxy_001_current_dryrun` | 3 | payload 3 | topology 200에서도 payload-only 유지 |
| `obs_juiceshop_proxy_v2_001_current_dryrun` | 3 | payload 3 | v2 parser/viewer/LLM input 안정화 관찰 표본 |
| `obs_juiceshop_proxy_v2_error_check_001_current_dryrun` | 2 | payload 1 / status-error 1 | reverse proxy 503에서 payload vs status-only 분리 확인 |

요약하면 direct PHP 계열은 policy bucket 분리 표본을 제공하고, error-heavy run은 error/status 중심 후보와 explicit payload 후보의 분리 근거를 보강한다. OpenCart/Juice Shop 계열은 topology-dependent 200 응답에서도 explicit payload 후보만 보존되는지 확인하는 표본이다.

---

## 4. Direct PHP 분포

### 4.1 PHP sample v2

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |
| `context_candidate_probe` | 5 |
| `demotion_candidate_status_error_only` | 3 |
| `context_candidate_auth_failure` | 1 |
| `context_candidate_upload_failure` | 1 |

관찰 결과:

- S13/S14/S15의 명시 payload 요청은 `keep_candidate_payload`로 유지된다.
- S08 login POST는 `context_candidate_auth_failure`로 분류된다.
- S09 upload-like POST는 `context_candidate_upload_failure`로 분류된다.
- `/.env`, `/wp-login.php`, `/admin`, `does-not-exist` 계열은 `context_candidate_probe`로 분리된다.
- payload 없는 403/500/error-linked 중심 후보는 `demotion_candidate_status_error_only`로 분류된다.

### 4.2 PHP sample v1

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |
| `context_candidate_probe` | 5 |
| `demotion_candidate_status_error_only` | 3 |
| `context_candidate_auth_failure` | 1 |
| `context_candidate_upload_failure` | 1 |

관찰 결과:

- PHP sample v1 current dry-run은 PHP sample v2와 동일한 policy count shape를 보인다.
- v2 converter 필드 보존 여부와 무관하게 candidate policy 분류는 같은 구조로 재현된다.
- S08/S09의 POST metadata는 각각 auth/upload failure context로 분리되며 성공 단정으로 승격되지 않는다.
- S12 계열 probe는 app/file/admin 존재 여부를 단정하지 않고 context 후보로 분리된다.

---

## 5. PHP sample v2 error-heavy 분포

### 5.1 Policy counts

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |
| `context_candidate_probe` | 4 |
| `demotion_candidate_status_error_only` | 3 |
| `context_candidate_auth_failure` | 1 |
| `context_candidate_upload_failure` | 1 |

### 5.2 Candidate shape

| scenario | method | uri | status | verdict_hint | policy_class | 해석 |
|---|---|---|---:|---|---|---|
| EH11 | GET | `/search.php` | 200 | `sqli` | `keep_candidate_payload` | SQLi payload 구조와 `error_linked`가 함께 있어도 payload 후보 유지 |
| EH10 | GET | `/download.php` | 404 | `path_traversal` | `keep_candidate_payload` | traversal payload와 404/error-linked가 함께 있어도 payload 후보 유지 |
| EH12 | GET | `/search.php` | 200 | `xss` | `keep_candidate_payload` | XSS payload와 `error_linked`가 함께 있어도 payload 후보 유지 |
| EH04 | POST | `/login.php` | 401 | `suspicious` | `context_candidate_auth_failure` | 로그인 성공이 아니라 auth failure/context 후보 |
| EH08 | GET | `/wp-login.php` | 404 | `suspicious` | `context_candidate_probe` | WordPress/admin presence를 단정하지 않는 probe context |
| EH06 | POST | `/upload.php` | 400 | `suspicious` | `context_candidate_upload_failure` | upload 성공이 아니라 upload-like failure/context 후보 |
| EH02 | GET | `/private/secret.txt` | 403 | `suspicious` | `demotion_candidate_status_error_only` | 파일 노출 단정 없이 status/error metadata 중심 후보 |
| EH01 | GET | `/error.php` | 500 | `suspicious` | `demotion_candidate_status_error_only` | payload 없는 500/error-linked 후보 |
| EH09 | GET | `/admin` | 404 | `suspicious` | `context_candidate_probe` | admin 존재/접근 성공 단정 없는 probe context |
| EH07 | GET | `/.env` | 404 | `suspicious` | `context_candidate_probe` | `.env` 노출 단정 없는 sensitive-path probe context |
| EH05 | GET | `/login.php` | 200 | `suspicious` | `demotion_candidate_status_error_only` | GET login endpoint 관찰이며 auth success 근거 없음 |
| EH03 | GET | `/does-not-exist-error-heavy-obs_php_sample_v2_error_heavy_001` | 404 | `suspicious` | `context_candidate_probe` | missing path probe/context 후보 |

### 5.3 관찰 결과

PHP sample v2 error-heavy run은 status/error-only demotion 판단에 가장 직접적인 표본이다.

- payload가 있는 SQLi/traversal/XSS 요청은 `error_linked` 또는 404 status가 함께 있어도 `keep_candidate_payload`로 유지된다.
- payload 없는 403/500/error-linked 중심 요청은 `demotion_candidate_status_error_only`로 분리된다.
- POST `/login.php` 401은 `context_candidate_auth_failure`로 분리된다.
- POST `/upload.php` 400은 `context_candidate_upload_failure`로 분리된다.
- `/.env`, `/wp-login.php`, `/admin`, missing path는 `context_candidate_probe`로 분리된다.
- EHxx scenario label도 재출력에서 정상 표시되며, 이는 diagnostic report 가독성 개선에 해당한다.

이 결과는 broad demotion을 적용하라는 근거라기보다, `explain_prepare_candidates.py`의 diagnostic bucket이 실제 error-heavy run에서도 기대한 정책 경계를 설명할 수 있음을 보여준다. 즉, 실제 prepare 변경은 계속 보류하되 status/error-only 후보를 narrow review 대상으로 삼을 근거가 강화되었다.

---

## 6. Topology-heavy 분포

### 6.1 OpenCart

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |

관찰 결과:

- OpenCart front-controller/routed response context가 붙어도 payload 후보로만 유지된다.
- `status_code=200`은 공격 성공/침해 성공/파일 노출 근거로 승격되지 않는다.
- S15 traversal 후보에는 fallback-like response context가 붙지만, 이 역시 success/exposure proof가 아니라 topology interpretation context로만 남는다.
- scanner/probe, status/error-only, auth/upload context 분포를 판단하기에는 표본이 부족하다.

### 6.2 Juice Shop reverse proxy v1

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |

관찰 결과:

- reverse proxy / backend response / fallback 200 관련 observability hint가 붙어도 payload 후보로만 유지된다.
- `status_code=200`은 공격 성공/침해 성공/파일 노출 근거로 승격되지 않는다.
- scanner/probe, status/error-only, auth/upload context 분포를 판단하기에는 표본이 부족하다.

### 6.3 Juice Shop reverse proxy v2 normal run

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |

관찰 결과:

- S13 SQLi-like `GET /search.php` 200, S14 XSS-like `GET /search.php` 200, S15 traversal-like `GET /download.php` 200만 candidate로 유지된다.
- 세 후보 모두 reverse proxy/backend response observability context가 붙고, S15에는 `fallback_200_candidate`/`backend_fallback_200_candidate` context가 함께 붙는다.
- 위 context는 성공/노출/침해 증거가 아니라 topology interpretation context다.
- 따라서 v2 normal run은 성공 판단 강화 표본이 아니라 parser/viewer/LLM input 안정화 관찰 표본으로 기록한다.

### 6.4 Juice Shop reverse proxy v2 proxy_error_check

| policy_class | count |
|---|---:|
| `demotion_candidate_status_error_only` | 1 |
| `keep_candidate_payload` | 1 |

관찰 결과:

- payload 없는 `GET /` 503은 `demotion_candidate_status_error_only`로 분리된다.
- SQLi 구조를 가진 `GET /search` 503은 `keep_candidate_payload`로 유지된다.
- 503/proxy error는 backend availability evidence이며 공격 성공/침해 성공/노출 성공 근거가 아니다.

---

## 7. Demotion 판단

### 7.1 status/error-only demotion

현재 결론: 보류.

근거:

- PHP sample v1/v2에서 `demotion_candidate_status_error_only`는 payload 없는 403/500/error-linked 중심 후보로 반복 분류된다.
- PHP sample v2 error-heavy run에서도 payload 없는 403/500/error-linked 후보가 `demotion_candidate_status_error_only`로 분리된다.
- Juice Shop v2 proxy_error_check에서도 payload 없는 503 요청이 status/error-only bucket으로 분리된다.
- 반대로 payload가 명시된 SQLi/traversal/XSS 요청은 error-linked 또는 404가 함께 있어도 `keep_candidate_payload`로 유지된다.
- 그러나 status/error metadata는 실제 공격 시도에서 보조 신호로 유효할 수 있다.
- broad demotion을 prepare 단계에 바로 적용하면 recall 손실 가능성이 있다.
- 우선 diagnostic bucket으로 관찰하고, 실제 run distribution을 더 쌓는 것이 안전하다.

### 7.2 scanner/probe demotion

현재 결론: 보류.

근거:

- PHP sample v1/v2 및 error-heavy run에서 `context_candidate_probe`는 `.env`, `wp-login`, `admin`, missing path 계열을 반복적으로 분리한다.
- 그러나 scanner/probe context는 sensitive path probe, mixed baseline scanner, probing sequence summary에 유용하다.
- prepare에서 단순 drop/demotion하면 summary/context 관찰성이 줄 수 있다.
- context-only를 finding/incident로 승격하지 않는 guardrail은 유지하되, prepare visibility는 아직 보존한다.

### 7.3 auth/upload context demotion

현재 결론: 별도 demotion을 넣지 않는다.

근거:

- PHP sample v1/v2 및 error-heavy run에서 POST `/login.php`는 `context_candidate_auth_failure`로 반복 분류되어 auth success 단정을 피한다.
- PHP sample v1/v2 및 error-heavy run에서 POST `/upload.php`는 `context_candidate_upload_failure`로 반복 분류되어 upload success 단정을 피한다.
- 현재 narrow guard는 의도대로 작동한다.
- 추가 demotion은 실제 false-positive/recall tradeoff를 더 본 뒤 판단한다.

---

## 8. 추가 관찰 포인트

### 8.1 S07/EH05 GET `/login.php`

PHP sample v1/v2 및 error-heavy run에서 GET `/login.php`는 `demotion_candidate_status_error_only`로 분류되었다.

현재 분류가 크게 문제는 아니다.

- method가 GET이다.
- auth 관련 hint는 `login_endpoint(+1)` 수준이다.
- POST login failure와 달리 `context_candidate_auth_failure`로 분류할 강한 근거가 없다.
- auth success로 단정하지 않는다.

후속 후보:

- 필요하면 `GET login endpoint + error_linked + login_endpoint` 류를 `context_candidate_auth_observation` 같은 별도 bucket으로 분리할 수 있다.
- 단, 현재는 구현하지 않는다.

### 8.2 EH scenario detection

`explain_prepare_candidates.py`의 scenario detector가 `EHxx` error-heavy label을 인식하도록 보강되었다.

- `scenario=EH01` query string을 인식한다.
- `obs-error-heavy/EH04` User-Agent를 인식한다.
- 직접 필드 `eh10`도 `EH10`으로 정규화한다.
- `obs_php_sample_v2_error_heavy_001_current_dryrun` 재출력에서 `EH01`~`EH12` 표시를 확인했다.
- 검증: `tests/test_explain_prepare_candidates.py` `9 passed`, scenario label diagnostic bundle `24 passed`.
- prepare/scoring/filtering 변경은 없다.

### 8.3 OpenCart / Juice Shop 표본 한계

OpenCart와 Juice Shop 계열 current dry-run은 payload-only 또는 payload+status-error 소수 표본으로 남았다.

- front-controller/reverse-proxy topology에서 payload 후보가 conservative하게 유지되는지는 확인된다.
- scanner/probe/status-error demotion 여부 판단에는 아직 표본이 부족하다.
- 필요하면 proxy error check, 외부 client 기반 error-heavy run, 또는 추가 topology run에서 distribution을 더 수집한다.

---

## 9. Apache logs-only guardrail

아래 원칙은 계속 유지한다.

- `status_code=200`으로 공격 성공/침해 성공을 단정하지 않는다.
- `response_body_bytes`, `resp_content_type`, `text/html`만으로 파일 노출/정보 유출을 단정하지 않는다.
- POST metadata만으로 로그인 성공, 업로드 저장 성공, 계정 장악, DB 영향, 서버 내부 상태 변화를 단정하지 않는다.
- raw POST body, response body, DB 결과, 브라우저 실행 여부는 Apache logs-only 입력에 없으므로 추론하지 않는다.
- scanner/probe context-only 항목을 finding/incident로 승격하지 않는다.
- Web UI는 read-only display/interpretation aid 범위로 유지하고, severity/category/verdict를 재계산하지 않는다.

---

## 10. 다음 작업

1. 이 distribution review 확장 내용을 진행상황/TODO/작업일지에 짧게 반영한다.
2. 필요하면 proxy error check 또는 외부 client 기반 error-heavy run에 `explain_prepare_candidates.py`를 적용한다.
3. distribution 표본이 더 쌓이면 demotion이 아니라 narrow rule 후보를 별도 설계한다.
4. 실제 prepare 변경은 다음 조건을 만족할 때만 검토한다.
   - 명시 payload 후보 보존이 fixture/regression/real run에서 계속 확인됨
   - context-only 후보가 summary/context로 보존되는 경로가 명확함
   - drop/demotion이 recall 손실을 만들지 않는다는 근거가 있음
   - Web UI/reporting에서 성공 단정 방지 효과가 diagnostic만으로 부족하다는 실제 사례가 있음

---

## 11. 현재 결론

현재 코드 기준 dry-run distribution은 diagnostic bucket 설계와 대체로 일치한다.

- PHP sample v1/v2는 payload/auth/upload/probe/status-error 분리가 동일하게 재현된다.
- PHP sample v2 error-heavy run은 error-linked payload와 status/error-only 후보가 기대대로 분리됨을 보강한다.
- Juice Shop v2 normal/proxy_error_check는 reverse proxy topology에서 v2 parser/viewer/LLM input 안정화 표본을 제공한다.
- EHxx label support로 error-heavy diagnostic output 가독성이 개선되었다.
- OpenCart/Juice Shop 계열은 topology context를 보강하지만 성공 판단을 강화하지 않는다.
- broad demotion은 아직 적용하지 않는다.
- 다음 단계는 더 많은 error-heavy/topology run에서 distribution을 축적하고, 필요 시 narrow rule로 별도 설계하는 것이다.
