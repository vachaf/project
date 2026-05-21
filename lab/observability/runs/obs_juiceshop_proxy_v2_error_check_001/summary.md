### Juice Shop v2 proxy_error_check

`obs_juiceshop_proxy_v2_error_check_001_current_dryrun`에서
backend unavailable / reverse proxy 503 상황의 candidate policy distribution을 확인했다.

| policy_class | count |
|---|---:|
| `demotion_candidate_status_error_only` | 1 |
| `keep_candidate_payload` | 1 |

관찰 결과:

- `GET /` 503은 `error_status:503`, `error_linked`,
  `no_referer_non_browser_error` 중심으로
  `demotion_candidate_status_error_only`에 분류되었다.
- `GET /search` 503은 SQLi 구조
  (`sqli:quote_termination`, `sqli:or_true`, `sqli:sql_comment`)가 있어
  `keep_candidate_payload`로 유지되었다.
- 두 후보 모두 reverse proxy/backend response observability context가 붙었다.
- 503/proxy error는 backend availability evidence이며,
  공격 성공, 침해 성공, DB 영향, 파일 노출 근거가 아니다.
- prepare/scoring/filtering 변경은 없다.

판단:

이 표본은 v2 Juice Shop reverse proxy 환경에서도
status/error-only 후보와 explicit payload 후보가 기대대로 분리됨을 보여준다.
따라서 broad demotion은 계속 보류하고,
diagnostic distribution 관찰 표본으로만 기록한다.