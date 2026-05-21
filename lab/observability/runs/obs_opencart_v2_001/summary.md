# obs_opencart_v2_001 Summary

## Run Metadata

- `run_id`: `obs_opencart_v2_001`
- `run_dir`: `lab/observability/runs/obs_opencart_v2_001`
- `dry-run artifact`: `obs_opencart_v2_001_current_dryrun`
- `topology`: OpenCart front-controller / routed PHP app
- `log_format_version`: `apache_security_io_v2`

## Observation Summary

- S01~S15 전체 시나리오가 관찰되었다.
- Apache warn/error-level security context는 관찰되지 않았다.
- prohibited inference checks는 pass 상태다.
- S12 scanner burst 구간에서는 `/admin` 요청이 `301` redirect 후 `/admin/index.php`로 follow되었다.

## Evidence Level Summary

- `O1=13`
- `O1/O4=2`
- `O0/O2/O3/O4=0`
- S08 `login_post`와 S09 `upload_like_post`는 `O1/O4`이며, Apache logs-only로 로그인 성공 또는 업로드 저장 성공을 단정하지 않는다.

## Redirect/Follow Summary

- S12 `/admin` 요청은 front-controller / routed PHP app topology에서 `301` redirect 후 `/admin/index.php` follow가 관찰되었다.
- `expected logical=7`, `actual Apache requests=8`, `extra requests=1`이다.
- 이 redirect/follow는 routing/topology context이며 admin access success 근거가 아니다.

## Candidate Policy Distribution

- `candidate_count=5`

| policy_class | count | notes |
|---|---:|---|
| `keep_candidate_payload` | 3 | S13 SQLi-like, S14 XSS-like, S15 traversal-like |
| `demotion_candidate_status_error_only` | 2 | S02 `/static/style.css` 404, S03 `/static/app.js` 404 |

- S13/S14/S15에는 front-controller / `_route_` observability context가 붙는다.
- S15에는 `fallback_200_candidate` context가 붙는다.
- S02/S03 static `404`는 score `4/4`, margin `0`의 status/error metadata 중심 후보다.

## Interpretation

- OpenCart v2 normal run은 payload-only 3건이 아니라 `payload 3 + status-error-only 2` 분포를 보였다.
- 이는 실패가 아니라, front-controller / routed response topology에서도 explicit payload 후보와 약한 status/error-only 후보가 분리됨을 보여주는 실제 distribution 표본이다.
- S13/S14/S15는 request-pattern candidate일 뿐 성공/노출/침해 증거가 아니다.
- S02/S03 static `404`는 exploit success나 static file exposure 근거가 아니라 status/error-only boundary 후보다.
- v2 / front-controller observability context는 topology interpretation context이며 scoring/severity/verdict 변경 근거가 아니다.
- prepare/scoring/filtering 변경은 없다.
- broad demotion은 계속 보류한다.

## Guardrail Notes

- `status_code=200`으로 공격 성공/침해 성공을 단정하지 않는다.
- `status_code=404`만으로 취약점/노출/공격 성공을 단정하지 않는다.
- `response_body_bytes`, `resp_content_type`, `text/html`만으로 파일 노출/정보 유출을 단정하지 않는다.
- POST metadata만으로 로그인 성공/업로드 저장 성공을 단정하지 않는다.
- raw POST body, response body, DB 결과, 브라우저 실행 여부는 Apache logs-only 입력에 없으므로 추론하지 않는다.
- context-only를 finding/incident로 승격하지 않는다.
- Web UI에서 severity/category/verdict를 재계산하지 않는다.
