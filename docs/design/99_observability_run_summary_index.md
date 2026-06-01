# 99_observability_run_summary_index

- 기준 시점: 2026-05-22
- 문서 역할: Apache observability run summary 상위 색인
- docs에서 읽을 run별 요약본: [../reviews/99_observability_run_summaries.md](../reviews/99_observability_run_summaries.md)
- topology 비교 요약: [../reviews/99_observability_topology_comparison_review.md](../reviews/99_observability_topology_comparison_review.md)
- run artifact 원본은 아직 `../../lab/observability/runs/*`에 남아 있다.
- lab 원본 링크는 장기적으로 제거/이관 대상이지만, 이번 작업에서는 lab 파일을 삭제하거나 이동하지 않는다.

## run index

| run_id | 대상 환경 | logformat | topology | 목적 | 주요 결론 | docs summary | lab artifact | candidate policy 판단에 사용 |
|---|---|---|---|---|---|---|---|---|
| `obs_php_sample_002` | php sample | v1 | direct | Apache+PHP baseline 관찰 | S01~S15 관찰, direct PHP baseline 분포 표본 | [docs summary](../reviews/99_observability_run_summaries.md) | [legacy artifact](../../lab/observability/runs/obs_php_sample_002/summary.md) | yes |
| `obs_php_sample_v2_001` | php sample | v2 | direct | v2 field 보존과 dry-run 연결 확인 | v2 추가 필드 보존, v1과 같은 candidate shape 관찰 | [docs summary](../reviews/99_observability_run_summaries.md) | [legacy artifact](../../lab/observability/runs/obs_php_sample_v2_001/summary.md) | yes |
| `obs_php_sample_v2_error_heavy_001` | php sample | v2 | direct / error-heavy | error/status-linked 표본 보강 | summary는 아직 skeleton 성격이지만 error-heavy 표본 id는 유지 | [docs summary](../reviews/99_observability_run_summaries.md) | [legacy artifact](../../lab/observability/runs/obs_php_sample_v2_error_heavy_001/summary.md) | yes |
| `obs_php_sample_v2_error_heavy_external_001` | php sample | v2 | direct / controlled external client / error-heavy | external client identity와 error-heavy distribution 비교 | `192.168.56.114 -> 192.168.56.115` direct identity 보존, local baseline과 같은 conservative distribution shape 유지 | [docs summary](../reviews/99_observability_run_summaries.md) | [legacy artifact](../../lab/observability/runs/obs_php_sample_v2_error_heavy_external_001/summary.md) | yes |
| `obs_opencart_002` | OpenCart | v1 | front-controller / routed response | 실제 PHP app topology baseline | `status_code=200`을 성공/노출 증거로 쓰면 안 됨을 재확인 | [docs summary](../reviews/99_observability_run_summaries.md) | [legacy artifact](../../lab/observability/runs/obs_opencart_002/summary.md) | yes |
| `obs_opencart_v2_001` | OpenCart | v2 | front-controller / routed response | v2 front-controller 표본 | payload 3 + status-error 2 분포 관찰, broad demotion은 보류 | [docs summary](../reviews/99_observability_run_summaries.md) | [legacy artifact](../../lab/observability/runs/obs_opencart_v2_001/summary.md) | yes |
| `obs_juiceshop_proxy_v2_001` | Juice Shop | v2 | reverse proxy / backend response | proxy topology normal run | payload 3 유지, fallback/proxy context는 interpretation context | [docs summary](../reviews/99_observability_run_summaries.md) | [legacy artifact](../../lab/observability/runs/obs_juiceshop_proxy_v2_001/summary.md) | yes |
| `obs_juiceshop_proxy_v2_error_check_001` | Juice Shop | v2 | reverse proxy / backend unavailable | proxy error check | payload 1 / status-error 1 분리 관찰, prepare 변경 없음 | [docs summary](../reviews/99_observability_run_summaries.md) | [legacy artifact](../../lab/observability/runs/obs_juiceshop_proxy_v2_error_check_001/summary.md) | yes |

## 읽는 순서

1. 각 run의 목적과 큰 결론은 이 문서에서 본다.
2. docs-side run별 요약은 [../reviews/99_observability_run_summaries.md](../reviews/99_observability_run_summaries.md)를 본다.
3. topology 비교 결론은 [../reviews/99_observability_topology_comparison_review.md](../reviews/99_observability_topology_comparison_review.md)를 본다.
4. 원본 artifact가 필요할 때만 `lab artifact` 링크를 확인한다.
5. candidate policy와의 연결은 [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md)를 본다.

## 공통 해석 원칙

- 개별 run summary는 request/response metadata 관찰 문서다.
- POST body, response body, DB 결과, 브라우저 실행 결과를 추론하지 않는다.
- `status_code=200`, `response_body_bytes`, `resp_content_type`, `handler`, route 이름만으로 공격 성공/유출/침해를 단정하지 않는다.
- `server-status`, `admin`, static path, upload/login POST, proxy error는 모두 topology/context를 포함해 해석한다.
- `src_ip`, `peer_ip`, `X-Forwarded-For`, `X-Real-IP`, `Forwarded`는 관찰값이며 attacker attribution proof가 아니다.
