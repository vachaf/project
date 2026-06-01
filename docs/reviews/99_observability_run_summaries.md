# 99_observability_run_summaries

- 문서 상태: review / lab observability run summary 이관 요약
- 기준 시점: 2026-06-01
- 목적: `lab/observability/runs/*/summary.md` 8개에 분산된 run별 결론을 docs에서 직접 읽을 수 있게 모은다.
- 관련 design index: [../design/99_observability_run_summary_index.md](../design/99_observability_run_summary_index.md)
- 관련 policy history: [../design/99_prepare_candidate_policy_distribution_history.md](../design/99_prepare_candidate_policy_distribution_history.md)

## 1. 이 문서의 역할

이 문서는 lab run artifact 원본을 삭제하지 않는다.

역할은 다음과 같다.

- run별 목적, 주요 관찰, candidate policy 의미, Apache logs-only guardrail을 docs에 보존한다.
- lab run summary 직접 링크 없이도 observability 판단 근거를 읽을 수 있게 한다.
- 추후 lab artifact 제거 또는 ignore 전환 여부를 별도 PR에서 판단할 수 있게 한다.

## 2. Run Summary Table

| run_id | 대상 환경 | logformat | topology | 목적 | 주요 관찰 | candidate policy 의미 | docs 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `obs_php_sample_002` | PHP sample | v1 | direct Apache/PHP | direct baseline과 access/error correlation 확인 | S01~S15 관찰, request_id 기반 error correlation, `/server-status` 외부 노출 단정 금지 | payload/auth/upload/probe/status-error bucket 분리의 v1 표본 | historical observation / candidate policy history 근거 |
| `obs_php_sample_v2_001` | PHP sample | v2 | direct Apache/PHP | v2 field 보존과 dry-run 연결 확인 | `request_target`, `req_host`, `client_ip_source`, Cookie/Auth presence flag 보존 | candidate count 증가는 v2 field 효과가 아니라 current prepare policy 결과 | historical observation / v2 field 검증 근거 |
| `obs_php_sample_v2_error_heavy_001` | PHP sample | v2 | direct / error-heavy | status/error-linked 표본 id 보존 | summary 원문은 skeleton 성격이지만 error-heavy local baseline id로 유지 | broad demotion 확정 근거가 아니라 후속 비교 기준 | historical observation / needs review |
| `obs_php_sample_v2_error_heavy_external_001` | PHP sample | v2 | direct / controlled external client / error-heavy | external client identity와 bucket shape 비교 | `192.168.56.114 -> 192.168.56.115`, direct identity metadata 보존, stale explanation artifact 이슈 해소 | local baseline과 같은 conservative bucket split 유지, attribution policy 근거 아님 | candidate policy history 근거 |
| `obs_opencart_002` | OpenCart | v1 | front-controller / routed response | real PHP app topology baseline | `_route_=`, `redirect-handler`, fallback 200, redirect-follow 관찰 | 200 fallback은 success proof가 아니며 topology context 필요 | historical observation / topology guardrail 근거 |
| `obs_opencart_v2_001` | OpenCart | v2 | front-controller / routed response | v2 OpenCart distribution 확인 | payload 3 + status-error-only 2, S12 redirect-follow, `fallback_200_candidate` context | broad demotion 보류, topology context는 scoring 변경 근거 아님 | candidate policy history 근거 |
| `obs_juiceshop_proxy_v2_001` | Juice Shop | v2 | reverse proxy / backend response | proxy topology normal run | 대부분 200 + `handler=proxy-server` + `text/html`, S08/S09 context-only | payload 3 유지, backend/fallback context는 interpretation context | historical observation / topology guardrail 근거 |
| `obs_juiceshop_proxy_v2_error_check_001` | Juice Shop | v2 | reverse proxy / backend unavailable | proxy error check | 503/proxy error, payload 없는 503과 SQLi-like 503 분리 | availability context이며 prepare/scoring/filtering 변경 없음 | candidate policy history 근거 |

## 3. Run별 보존 결론

### 3.1 `obs_php_sample_002`

- 대상: PHP sample
- logformat: `apache_security_io_v1`
- topology: direct Apache/PHP
- 목적: 단순 Apache/PHP baseline에서 LogFormat, parser, scenario marker, access/error correlation을 확인한다.

주요 관찰:

- S01~S15가 User-Agent marker 기준으로 관찰되었다.
- S08/S09는 request body/form에 scenario marker가 들어갈 수 있으므로 query_string만으로 필터링하면 누락될 수 있다.
- request_id 기반으로 security/access row와 error log context를 연결할 수 있다.
- notice-level app/PHP context와 warn/error-level context는 분리해서 해석해야 한다.
- `/server-status` local 200은 외부 노출 증거가 아니다.

candidate policy 의미:

- direct PHP baseline에서 payload/auth/upload/probe/status-error bucket을 관찰하는 v1 표본이다.
- status/error 분포는 prepare policy history의 관찰 근거지만, broad demotion 확정 근거는 아니다.

Apache logs-only guardrail:

- Apache 로그만으로 로그인 성공, 업로드 저장 성공, SQLi/XSS/traversal 성공을 판단하지 않는다.

현재 docs 상태:

- canonical policy가 아니라 historical observation이다.
- candidate policy distribution history의 근거로 사용한다.

### 3.2 `obs_php_sample_v2_001`

- 대상: PHP sample
- logformat: `apache_security_io_v2`
- topology: direct Apache/PHP
- 목적: v2 LogFormat 추가 필드가 raw log, export JSON, prepare/stage/viewer dry-run까지 손실 없이 연결되는지 확인한다.

주요 관찰:

- S01~S15 evidence level은 v1 PHP sample과 동일하게 유지된다.
- v2 추가 필드 `request_target`, `req_host`, `client_ip_source`, `has_cookie`, `has_authorization`가 보존된다.
- `request_target`은 normalized convenience target이고, raw fidelity가 필요한 경우 `raw_request` 또는 `raw_request_target`을 우선한다.
- Cookie/Auth presence flag는 헤더 존재 여부일 뿐 인증 성공 증거가 아니다.

candidate policy 의미:

- `candidate_rows=13`은 v2 field 추가 때문이 아니라 current prepare scoring/filtering 기준 결과로 분리한다.
- v2 field는 score, severity, verdict를 올리는 용도가 아니다.

Apache logs-only guardrail:

- S13/S14 200은 SQLi/XSS 성공 증거가 아니다.
- S15 404/text/html은 파일 내용 노출 증거가 아니다.
- POST metadata와 Cookie/Auth presence flag로 로그인/업로드/인증 성공을 단정하지 않는다.

현재 docs 상태:

- historical observation이자 v2 field preservation 검증 근거다.
- v2 production migration 결정 문서가 아니다.

### 3.3 `obs_php_sample_v2_error_heavy_001`

- 대상: PHP sample
- logformat: `apache_security_io_v2`
- topology: direct / error-heavy
- 목적: error/status-linked request bucket을 관찰하기 위한 local/internal error-heavy 표본을 보존한다.

주요 관찰:

- lab 원문 summary는 아직 skeleton 성격이다.
- run id와 artifact는 external client error-heavy run의 비교 baseline으로 의미가 있다.

candidate policy 의미:

- payload candidate와 status/error-only candidate를 분리해서 볼 수 있는 표본이다.
- broad demotion 적용 근거로 확정하지 않는다.

Apache logs-only guardrail:

- status/error row는 diagnostic context이지 vulnerability, file exposure, compromise proof가 아니다.

현재 docs 상태:

- historical observation이며 내용 보강 필요성이 남아 있다.
- 삭제 후보로 두기보다는 external run과 함께 policy history 근거로 보존한다.

### 3.4 `obs_php_sample_v2_error_heavy_external_001`

- 대상: PHP sample
- logformat: `apache_security_io_v2`
- topology: direct / controlled external client / error-heavy
- 목적: controlled external client에서 error-heavy distribution과 identity/header 관찰이 안정적으로 유지되는지 확인한다.

주요 관찰:

- client `192.168.56.114`에서 Apache/PHP server `192.168.56.115`로 요청한 direct path가 관찰되었다.
- `client_ip_source=direct`, `src_ip`, `peer_ip`, `req_host` 같은 metadata가 보존되었다.
- `remoteip_proxy_chain`, `x_forwarded_for`, `x_real_ip`, `forwarded`는 없었다.
- stale `candidate_policy_explanation.md` artifact의 scenario label 이슈는 최신 script 재생성으로 해소되었다.

candidate policy 의미:

- local/internal error-heavy baseline과 같은 conservative distribution shape를 유지했다.
- external client identity 변화가 scoring/filtering 변경 근거가 아니었다.
- direct identity metadata는 attacker attribution proof가 아니다.

Apache logs-only guardrail:

- `src_ip`/`peer_ip`와 header metadata는 관찰값이지 공격자 신원 증거가 아니다.
- POST body, response body, DB result, browser execution은 추론하지 않는다.
- broad demotion 변경은 없다.

현재 docs 상태:

- candidate policy history 근거다.
- attribution policy 확정 문서가 아니다.

### 3.5 `obs_opencart_002`

- 대상: OpenCart
- logformat: `apache_security_io_v1`
- topology: real PHP app / front-controller / routed response
- 목적: 실제 PHP app topology에서 Apache LogFormat과 S01~S15 observability를 확인한다.

주요 관찰:

- S01~S15 전체가 관찰되었다.
- OpenCart rewrite/front-controller 영향으로 없는 path, sensitive-looking path, traversal-like path도 200으로 관찰될 수 있다.
- `query_string`의 `_route_=`와 `handler=redirect-handler`가 routed/fallback response context를 제공한다.
- S12 `/admin`은 redirect-follow로 logical request 1개가 actual Apache request 2개로 확장될 수 있다.
- warn/error-level PHP/Apache error context는 거의 관찰되지 않았다.

candidate policy 의미:

- `status_code=200`이 success proof가 아님을 보여주는 topology baseline이다.
- OpenCart-like context는 candidate 설명 보조 자료이며 verdict 강화 근거가 아니다.

Apache logs-only guardrail:

- fallback 200은 파일 존재, 파일 노출, traversal success, login success, upload success를 뜻하지 않는다.
- `_route_=`는 routing marker이지 backend/app 내부 결과 증거가 아니다.

현재 docs 상태:

- historical observation이자 topology guardrail 근거다.

### 3.6 `obs_opencart_v2_001`

- 대상: OpenCart
- logformat: `apache_security_io_v2`
- topology: front-controller / routed response
- 목적: v2 field 환경에서 OpenCart front-controller distribution과 candidate policy boundary를 확인한다.

주요 관찰:

- S01~S15 전체가 관찰되었다.
- S12 `/admin`은 301 redirect 후 `/admin/index.php` follow가 관찰되었다.
- candidate distribution은 `payload 3 + status-error-only 2`였다.
- S13/S14/S15에는 front-controller / `_route_` observability context가 붙는다.
- S15에는 `fallback_200_candidate` context가 붙는다.

candidate policy 의미:

- explicit payload 후보와 약한 status/error-only 후보가 분리되는 실제 distribution 표본이다.
- broad demotion은 계속 보류한다.
- topology context는 scoring/severity/verdict 변경 근거가 아니다.

Apache logs-only guardrail:

- `status_code=200`, `status_code=404`, `response_body_bytes`, `resp_content_type`, `text/html`만으로 성공/노출/침해를 단정하지 않는다.
- context-only를 finding/incident로 승격하지 않는다.
- Web UI에서 severity/category/verdict를 재계산하지 않는다.

현재 docs 상태:

- candidate policy history 근거다.
- 새 policy 확정 문서가 아니다.

### 3.7 `obs_juiceshop_proxy_v2_001`

- 대상: Juice Shop
- logformat: `apache_security_io_v2`
- topology: reverse proxy / backend response
- 목적: Apache reverse proxy 뒤의 backend app normal run에서 fallback/proxy context를 관찰한다.

주요 관찰:

- S01~S15 전체가 관찰되었다.
- 대부분 요청은 `status_code=200`, `handler=proxy-server`, `resp_content_type=text/html`로 기록되었다.
- S12 `/server-status`는 `handler=server-status`로 기록되었다.
- Apache warn/error-level security context는 관찰되지 않았다.
- S08/S09는 context-only 관찰이다.

candidate policy 의미:

- `candidate_count=3`, `keep_candidate_payload=3`이다.
- S13 SQLi-like, S14 XSS-like, S15 traversal-like request-pattern payload 후보는 유지된다.
- reverse proxy/backend response context와 fallback 200 context는 interpretation context다.

Apache logs-only guardrail:

- `handler=proxy-server` + 200은 backend route success, backend file exposure, exploitation success를 증명하지 않는다.
- Apache는 backend 내부 인증/업로드/DB 결과와 response body 의미를 알 수 없다.

현재 docs 상태:

- historical observation이자 topology guardrail 근거다.

### 3.8 `obs_juiceshop_proxy_v2_error_check_001`

- 대상: Juice Shop
- logformat: `apache_security_io_v2`
- topology: reverse proxy / backend unavailable
- 목적: backend unavailable/proxy error 상황에서 status/error-only와 payload 후보가 어떻게 분리되는지 확인한다.

주요 관찰:

- payload 없는 `GET /` 503은 `demotion_candidate_status_error_only`로 분리되었다.
- SQLi 구조가 있는 `GET /search` 503은 `keep_candidate_payload`로 유지되었다.
- 두 후보 모두 reverse proxy/backend response observability context가 붙는다.

candidate policy 의미:

- proxy error context에서도 payload 후보와 status/error-only 후보가 분리된다.
- 503/proxy error는 backend availability context다.
- prepare/scoring/filtering 변경은 없다.

Apache logs-only guardrail:

- 503/proxy error는 공격 성공, 침해 성공, DB 영향, 파일 노출 근거가 아니다.
- availability context를 security verdict로 승격하지 않는다.

현재 docs 상태:

- candidate policy history 근거다.
- proxy error policy 확정 문서가 아니다.

## 4. 공통 Guardrail

모든 run에 공통으로 적용하는 해석 원칙은 다음이다.

- payload 후보 유지는 성공/노출/침해 증거가 아니다.
- status/error-only bucket 분리는 자동 demotion 정책 확정을 뜻하지 않는다.
- topology context는 interpretation guardrail이며 scoring 상승 근거가 아니다.
- `status_code`, `response_body_bytes`, `resp_content_type`, `handler`, route 이름, `_route_=`, `proxy-server`만으로 성공을 단정하지 않는다.
- POST metadata만으로 로그인 성공, credential stuffing 성공, 업로드 저장 성공을 단정하지 않는다.
- `src_ip`, `peer_ip`, `X-Forwarded-For`, `X-Real-IP`, `Forwarded`는 관찰값이며 attribution proof가 아니다.

## 5. lab artifact와의 관계

원본 run artifact는 아직 `../../lab/observability/runs/*`에 남아 있다.

이번 문서는 docs-side summary로서 다음 역할을 한다.

- docs에서 observability 판단 근거를 읽을 수 있게 한다.
- `docs/design/99_observability_run_summary_index.md`의 우선 summary 링크가 될 수 있다.
- `docs/design/99_prepare_candidate_policy_distribution_history.md`가 lab run summary에 직접 의존하지 않도록 보조한다.

lab 원문 삭제, 이동, archive 여부는 별도 PR에서 판단한다.
