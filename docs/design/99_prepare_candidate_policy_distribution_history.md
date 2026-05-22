# 99_prepare_candidate_policy_distribution_history

- 기준 시점: 2026-05-22
- 문서 역할: prepare candidate policy distribution 관찰/history 문서
- 현재 기준 문서: [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md)
- 관련 run index: [99_observability_run_summary_index.md](./99_observability_run_summary_index.md)
- 관련 historical review:
  - [99_prepare_candidate_policy_distribution_review.md](../archive/design/99_prepare_candidate_policy_distribution_review.md)
  - [99_prepare_php_sample_candidate_policy_review.md](../archive/design/99_prepare_php_sample_candidate_policy_review.md)
  - [99_prepare_status_error_only_candidate_demotion_review.md](../archive/design/99_prepare_status_error_only_candidate_demotion_review.md)
  - [99_prepare_scanner_probe_context_candidate_demotion_review.md](../archive/design/99_prepare_scanner_probe_context_candidate_demotion_review.md)
  - [99_prepare_upload_multipart_sql_comment_false_positive_review.md](../archive/design/99_prepare_upload_multipart_sql_comment_false_positive_review.md)

## 1. 목적

이 문서는 “현재 정책이 실제로 어떤 분포를 보였는지”를 기록한다.

이 문서는 다음을 하지 않는다.

- 새로운 prepare policy 확정
- broad demotion 반영 선언
- 성공/노출/침해 판정 강화

## 2. 관찰 축

| run_id | 대상 환경 | logformat | topology | 목적 | 주요 결론 | summary | candidate policy 판단에 사용 |
|---|---|---|---|---|---|---|---|
| `obs_php_sample_002` | php sample | v1 | direct | baseline 분포 확인 | payload/auth/upload/probe/status-error bucket 분리의 v1 표본 | [summary](../../lab/observability/runs/obs_php_sample_002/summary.md) | yes |
| `obs_php_sample_v2_001` | php sample | v2 | direct | v2에서도 v1과 같은 policy shape인지 확인 | v1과 같은 분포가 재현되어 v2 field effect가 아니라 prepare policy effect임을 확인 | [summary](../../lab/observability/runs/obs_php_sample_v2_001/summary.md) | yes |
| `obs_php_sample_v2_error_heavy_001` | php sample | v2 | direct / error-heavy | error/status-linked bucket 관찰 | payload 후보와 status-error-only 후보를 분리해서 볼 수 있는 표본이지만 broad demotion 근거로 확정되지는 않음 | [summary](../../lab/observability/runs/obs_php_sample_v2_error_heavy_001/summary.md) | yes |
| `obs_php_sample_v2_error_heavy_external_001` | php sample | v2 | direct / controlled external client / error-heavy | external client에서도 error-heavy distribution이 유지되는지 확인 | local/internal baseline과 같은 `payload 3 / probe 4 / status-error 3 / auth 1 / upload 1` shape 유지, scenario label UX는 후속 점검 후보 | [summary](../../lab/observability/runs/obs_php_sample_v2_error_heavy_external_001/summary.md) | yes |
| `obs_opencart_002` | OpenCart | v1 | front-controller / routed response | topology-dependent 200 응답 baseline 확인 | payload-only 3건 유지, `status_code=200`은 성공 근거가 아님을 재확인 | [summary](../../lab/observability/runs/obs_opencart_002/summary.md) | yes |
| `obs_opencart_v2_001` | OpenCart | v2 | front-controller / routed response | v2 front-controller 표본 확인 | payload 3 + static 404 status-error 2 분포 관찰, broad demotion은 계속 보류 | [summary](../../lab/observability/runs/obs_opencart_v2_001/summary.md) | yes |
| `obs_juiceshop_proxy_v2_001` | Juice Shop | v2 | reverse proxy / backend response | proxy topology의 normal run 표본 | payload 3건 유지, fallback/proxy context는 interpretation context일 뿐 | [summary](../../lab/observability/runs/obs_juiceshop_proxy_v2_001/summary.md) | yes |
| `obs_juiceshop_proxy_v2_error_check_001` | Juice Shop | v2 | reverse proxy / backend unavailable | proxy error 표본 확인 | payload 1 / status-error 1 분리가 관찰되지만 prepare/scoring/filtering 변경은 없음 | [summary](../../lab/observability/runs/obs_juiceshop_proxy_v2_error_check_001/summary.md) | yes |

## 3. 현재까지의 관찰 요약

### 3.1 direct PHP 계열

직접적인 policy bucket 분리 표본은 direct PHP 계열이 제공한다.

- `keep_candidate_payload`
- `context_candidate_probe`
- `demotion_candidate_status_error_only`
- `context_candidate_auth_failure`
- `context_candidate_upload_failure`

현재 해석:

- bucket 분리가 관찰되었다.
- 이것이 곧 broad demotion 반영을 뜻하지는 않는다.
- `obs_php_sample_v2_error_heavy_external_001`에서도 controlled external client identity로 바뀌었지만 local/internal error-heavy baseline과 같은 bucket shape가 유지되었다.

### 3.2 topology-heavy 계열

OpenCart/Juice Shop 계열은 다음 관찰에 유용하다.

- front-controller / routed response / reverse proxy에서도 explicit payload 후보가 유지되는지
- static 404, proxy error 같은 약한 status/error row가 별도 bucket으로 설명 가능한지
- `status_code=200`, redirect-follow, `_route_`, `proxy-server`가 success proof가 아님을 재확인하는지

현재 해석:

- topology interpretation context는 policy 설명 보조 자료다.
- scoring/severity/verdict 변경 근거는 아니다.

## 4. 실제 반영과 관찰-only의 경계

### 4.1 실제 반영됨

- upload/sql-comment narrow guard
- diagnostic helper bucket 정리

### 4.2 관찰-only

- status/error-only broad demotion
- scanner/probe broad demotion
- topology-driven broad demotion
- proxy error context의 정식 candidate policy 반영
- external client identity를 바탕으로 한 attribution policy

## 5. 유지해야 할 guardrail

- payload 후보 유지가 곧 성공/노출/침해 증거를 뜻하지 않는다.
- status/error-only bucket 분리가 곧 자동 demotion 로직 반영을 뜻하지 않는다.
- `status_code=200`, `response_body_bytes`, `resp_content_type`, `handler`, route 이름, `_route_`, redirect-follow, `proxy-server`만으로 성공을 단정하지 않는다.
- POST metadata만으로 로그인 성공/업로드 저장 성공을 단정하지 않는다.
- `src_ip`, `peer_ip`, `X-Forwarded-For`, `X-Real-IP`, `Forwarded`는 관찰값이며 attacker attribution proof가 아니다.
- Web UI는 이 분포 문서를 바탕으로 새 verdict나 incident를 만들지 않는다.

## 6. 다음 표본 후보

- `obs_php_sample_v2_error_heavy_external_001`의 scenario label UX 원인 조사
- `proxy_error_check`의 scenario catalog extension 분리 여부
- OpenCart v2 추가 표본 필요 여부
- `mod_remoteip`/remoteIP 환경 구성 필요 여부

이 항목들도 현재는 관찰/history 영역이다.
