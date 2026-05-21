# obs_juiceshop_proxy_v2_001 Summary

## Run Metadata

- `run_id`: `obs_juiceshop_proxy_v2_001`
- `topology`: Juice Shop reverse proxy v2 normal run (proxy/backend response 관찰)
- `log_format_version`: `apache_security_io_v2`

## Observation Summary (S01~S15)

- S01~S15 전체 시나리오가 관찰되었다.
- Apache error log 기준 warn/error-level security context는 관찰되지 않았다.
- 대부분 요청은 `status_code=200`, `handler=proxy-server`, `resp_content_type=text/html`로 기록되었다.
- S12 `/server-status`는 `handler=server-status`로 기록되었다.
- prohibited inference checks는 pass 상태다.

## Evidence Level Summary

- `O1=13`
- `O1/O4=2` (S08 `login_post`, S09 `upload_like_post`)
- `O0/O2/O3/O4=0`

해석 원칙:

- S08/S09는 context-only 관찰이며 Apache logs-only로 로그인 성공/업로드 저장 성공을 단정하지 않는다.
- raw POST body, response body, DB 결과, 브라우저 실행 여부는 추론하지 않는다.

## Candidate Policy Distribution

- `candidate_count=3`
- `keep_candidate_payload=3`
- candidate 유지 대상: S13 (SQLi-like), S14 (XSS-like), S15 (traversal-like)

해석 원칙:

- 세 후보는 request-pattern payload candidate 유지이며 성공/노출/침해 증거를 의미하지 않는다.
- reverse proxy/backend response context, fallback 200 context(`fallback_200_candidate`, `backend_fallback_200_candidate`)는 topology interpretation context다.
- `status_code=200` 또는 `text/html` 응답만으로 파일 노출/정보 유출/침해 성공을 단정하지 않는다.

## v2 Field Note

- v2 환경에서는 legacy `host` 필드가 `no`로 보일 수 있다.
- 이 summary는 raw log에서 `req_host`, `client_ip_source`, `request_target`의 존재를 직접 재검증한 결과를 포함하지 않는다.
- v2 checklist에서는 `req_host`/`client_ip_source`/`request_target`를 별도 확인 대상으로 유지한다.
