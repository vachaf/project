# obs_juiceshop_proxy_v2_error_check_001 Summary

## Run Metadata

- `run_id`: `obs_juiceshop_proxy_v2_error_check_001`
- `topology`: Juice Shop reverse proxy v2 backend unavailable/proxy error check
- `log_format_version`: `apache_security_io_v2`

## Candidate Policy Distribution

| policy_class | count |
|---|---:|
| `demotion_candidate_status_error_only` | 1 |
| `keep_candidate_payload` | 1 |

- payload 없는 `GET /` 503은 `demotion_candidate_status_error_only`로 분리되었다.
- SQLi 구조가 있는 `GET /search` 503은 `keep_candidate_payload`로 유지되었다.
- 두 후보 모두 reverse proxy/backend response observability context가 붙는다.

## Interpretation

- 503/proxy error는 backend availability context이며 공격 성공/침해 성공/DB 영향/파일 노출 근거가 아니다.
- normal v2 run(`obs_juiceshop_proxy_v2_001`)과 비교하면, v2에서도 payload 후보와 status/error-only 후보가 분리됨을 확인했다.
- prepare/scoring/filtering 변경은 없다.
