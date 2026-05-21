## Candidate Policy Distribution

`obs_juiceshop_proxy_v2_001_current_dryrun`에서
Juice Shop reverse proxy + apache_security_io_v2 정규 S01~S15 run의
candidate policy distribution을 확인했다.

| policy_class | count |
|---|---:|
| `keep_candidate_payload` | 3 |

관찰 결과:

- S13 SQLi-like, S14 XSS-like, S15 traversal-like 요청만 analysis candidate로 유지되었다.
- 세 후보 모두 explicit attack-like payload structure가 있어 `keep_candidate_payload`로 분류되었다.
- reverse proxy/backend response observability context가 함께 붙었지만,
  이는 topology interpretation context일 뿐 scoring/severity/verdict 변경 근거가 아니다.
- S15 traversal-like 요청에는 fallback 200 관련 observability hint가 붙었지만,
  `status_code=200` 또는 `text/html` 응답은 파일 읽기 성공이나 정보 노출 근거가 아니다.
- S08 login POST와 S09 upload-like POST는 observation matrix상 O1/O4로 남으며,
  Apache logs alone으로 로그인 성공 또는 업로드 저장 성공을 판단하지 않는다.
- prepare/scoring/filtering 변경은 없다.

판단:

Juice Shop v2 정규 run은 기존 v1 Juice Shop baseline과 같은 conservative shape를 보인다.
reverse proxy / backend fallback / 200 HTML 응답 환경에서도
명시 payload 후보만 보존되고, topology-dependent 200 응답은 성공 단정으로 승격되지 않는다.