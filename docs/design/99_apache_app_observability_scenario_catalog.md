# 99_apache_app_observability_scenario_catalog

- 문서 상태: design summary / lab scenario catalog 이관 요약
- 기준 원문: `../../lab/observability/scenario_catalog.md`
- 기준 catalog version: `apache_observability_s01_s15_v1`
- 목적: Apache app observability 비교 실험에서 scenario id, request shape, marker, expected evidence boundary를 정리하기 위한 catalog

## 1. 적용 대상

이 catalog summary는 다음 topology baseline의 observability 비교 기준이다.

- PHP sample direct baseline
- OpenCart front-controller/routed response baseline
- Juice Shop reverse proxy/backend app baseline

각 대상은 서로 대체 관계가 아니다. PHP sample은 단순 Apache/PHP 처리와 error correlation 기준점이고, OpenCart는 실제 PHP app의 routed/fallback response 기준점이며, Juice Shop은 reverse proxy 뒤 backend app response 기준점이다.

## 2. Catalog의 역할

scenario catalog가 하는 일은 다음이다.

- observability run의 logical scenario를 정의한다.
- expected request/response metadata 관찰 범위를 정리한다.
- `User-Agent: obs-test/<scenario_id> run=<run_id>` marker 기반 run 재현성을 보조한다.
- observation matrix 작성 기준을 제공한다.

scenario catalog가 하지 않는 일은 다음이다.

- 공격 성공 판정
- response body, POST body, DB result 확인
- backend route 존재 판정
- severity, category, verdict 확정
- attacker attribution 확정

## 3. Marker와 재현성 기준

canonical marker는 User-Agent header다.

```text
User-Agent: obs-test/<scenario_id> run=<run_id>
```

`obs_run`과 `scenario` 값은 query/body/header에 들어갈 수 있는 helper marker다. S08 login POST와 S09 upload-like POST처럼 scenario 값이 body/form에만 들어갈 수 있는 요청은 Apache access/security log의 query string 필터만으로 누락될 수 있다. 따라서 run 필터링과 scenario count는 User-Agent marker를 우선 기준으로 삼는다.

## 4. Scenario 묶음 요약

| scenario | 목적 | expected evidence boundary |
| --- | --- | --- |
| S01 `normal_main` | 정상 메인 요청 baseline | `status_code=200` 계열은 HTTP response 관찰일 뿐 앱 기능 정상 완료 증거가 아니다. |
| S02 `static_css` | CSS 정적 파일 요청 관찰 | content type과 handler는 정적 리소스 처리 hint이며 파일 내용 검증이 아니다. |
| S03 `static_js` | JS 정적 파일 요청 관찰 | JS 파일 요청/응답 metadata를 볼 수 있어도 browser execution은 판단하지 않는다. |
| S04 `query_search` | query string 분리와 기록 확인 | query parameter 관찰은 request metadata이며 검색 결과나 DB 결과를 뜻하지 않는다. |
| S05 `not_found` | 존재하지 않는 경로의 404 관찰 | 404는 해당 request target의 응답 metadata이며 전체 app route 구조나 파일 부재 확정이 아니다. |
| S06 `forbidden_or_sensitive_path` | forbidden/sensitive-looking path probe 관찰 | 200/403/404, response size만으로 파일 존재나 민감정보 노출을 단정하지 않는다. |
| S07 `login_get` | 로그인 페이지 접근 요청 관찰 | login endpoint-like GET 관찰이지 로그인 페이지 내용 또는 인증 상태 확인이 아니다. |
| S08 `login_post` | login-like POST metadata 관찰 | POST 존재, content type, content length만으로 로그인 성공/실패나 계정 탈취를 단정하지 않는다. |
| S09 `upload_like_post` | multipart upload-like POST metadata 관찰 | multipart POST 관찰은 업로드 저장 성공, 파일 persistence, 파일 삭제/노출 증거가 아니다. |
| S10 `slow_or_large_request` | duration/TTFB/size 계열 필드 관찰 | 지연이나 크기 metadata만으로 DoS, 침해, 내부 처리 성공을 단정하지 않는다. |
| S11 `server_error` | 500과 error log correlation 확인 | 500/error message는 diagnostic context이며 exploit success나 데이터 유출 증거가 아니다. |
| S12 `scanner_burst` | 반복 요청과 scanner-like grouping 관찰 | 반복 probe 패턴은 suspicious context일 수 있으나 침해 성공이나 crawler 정체 확정이 아니다. |
| S13 `sqli_like` | SQLi-like query/payload 관찰 | SQLi-like 문자열 관찰은 payload candidate이며 SQL injection 성공이나 DB 결과 증거가 아니다. |
| S14 `xss_like` | XSS-like query/payload 관찰 | XSS-like 문자열 관찰은 payload candidate이며 browser JavaScript execution 증거가 아니다. |
| S15 `traversal_like` | traversal-like query/path 관찰 | traversal-like 요청은 payload candidate이며 파일 읽기 성공이나 `/etc/passwd` 노출 증거가 아니다. |

## 5. Topology별 해석 경계

PHP sample direct baseline에서는 handler/status/error correlation이 비교적 직관적일 수 있다. 그래도 200/404/500과 PHP warning만으로 성공, 노출, 침해를 확정하지 않는다.

OpenCart front-controller/routed response baseline에서는 없는 path, sensitive-looking path, traversal-like path도 200으로 관찰될 수 있다. `_route_=`, `redirect-handler`, directory redirect, fallback 200은 routed response context이며 파일 존재, 파일 노출, traversal success, login success, upload success를 뜻하지 않는다.

Juice Shop reverse proxy/backend app baseline에서는 `handler=proxy-server`, backend/SPA fallback, 200/503 response가 관찰될 수 있다. Apache는 backend response metadata를 볼 수 있지만 backend route 존재, 인증 결과, DB 결과, response body 의미, exploit success를 판단하지 못한다.

## 6. Apache Logs-Only Guardrail

- `status_code=200`은 success proof가 아니다.
- `handler`, route name, `_route_=`, `proxy-server`는 topology hint일 뿐이다.
- POST body, response body, DB result, JS execution은 Apache access/security/error log만으로 확인하지 않는다.
- login success, upload persistence, file exposure, command execution success는 단정하지 않는다.
- `src_ip`, `peer_ip`, `X-Forwarded-For`, `X-Real-IP`, `Forwarded`는 관찰값이며 attacker attribution proof가 아니다.

허용되는 표현은 “요청이 관찰됨”, “payload-like pattern이 관찰됨”, “fallback/routed/proxy response context가 관찰됨”, “추가 증거 없이는 성공 여부 판단 불가” 수준이다.

## 7. Lab 원본과의 관계

현재 observability scripts는 `lab/observability/scenario_catalog.md`와 `lab/observability/runs/*` 구조를 사용할 수 있다. 따라서 lab 원본은 보존한다.

이 문서는 장기적인 lab 제거 또는 이관 검토를 위한 docs-side 요약이다. 실제 script 경로 변경, lab catalog 삭제, lab artifact 이동 또는 archive 여부는 후속 PR에서만 검토한다.
