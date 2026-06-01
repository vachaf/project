# 99_observability_topology_comparison_review

- 문서 상태: review / lab observability comparison 이관 요약
- 기준 시점: 2026-06-01
- 목적: `lab/observability/comparison_*.md`에 흩어진 Apache topology 비교 결론을 docs 쪽 판단 근거로 요약한다.
- 원문 artifact:
  - `../../lab/observability/comparison_php_sample_vs_opencart.md`
  - `../../lab/observability/comparison_php_sample_vs_opencart_vs_juiceshop.md`
  - `../../lab/observability/comparison_php_sample_v1_vs_v2.md`

## 1. 이 문서의 역할

이 문서는 lab comparison 원문을 바로 삭제하기 위한 문서가 아니다.

역할은 다음과 같다.

- PHP sample, OpenCart, Juice Shop의 Apache observability 차이를 docs에서 읽을 수 있게 요약한다.
- `status_code=200`, `handler`, `_route_=`, `proxy-server`, response size를 성공 증거로 승격하지 않는 이유를 보존한다.
- 추후 lab 원문 삭제 또는 archive 여부를 판단할 때, docs 쪽 대체 근거로 사용한다.

lab 원문과 run artifact는 이번 단계에서 그대로 둔다.

## 2. 비교 대상의 역할

| 대상 | topology 역할 | observability 가치 | 성공 단정 금지 지점 |
| --- | --- | --- | --- |
| PHP sample | direct Apache/PHP baseline | LogFormat, parser, access/error correlation, 단순 status/error 분포 확인 | 200/404/500이나 PHP warning만으로 공격 성공/노출/침해를 단정하지 않음 |
| OpenCart | real PHP app / front-controller / routed response baseline | `_route_=`, `redirect-handler`, directory redirect, fallback 200 관찰 | 200 fallback이 파일 존재, 파일 노출, login/upload 성공 증거가 아님 |
| Juice Shop | reverse proxy / backend app 기반 대표 공격 재현 대상 | `handler=proxy-server`, backend/SPA fallback, backend response metadata 관찰 | proxy 200/503이 backend route success, DB 영향, 침해 증거가 아님 |

## 3. PHP sample direct baseline

PHP sample은 단순하고 예측 가능한 direct Apache/PHP baseline이다.

보존할 결론:

- PHP endpoint는 주로 `handler=application/x-httpd-php`로 관찰된다.
- static asset 또는 missing path는 `handler=-`와 200/404 분포로 비교적 직관적으로 관찰된다.
- 의도된 `/error.php`는 500 및 PHP warning/error correlation 확인에 유용하다.
- `request_id` / `error_link_id` 기반 access/security/error log 연결 검증에 적합하다.
- S08/S09 같은 POST 요청은 관찰되지만 Apache 로그만으로 login success 또는 upload persistence를 알 수 없다.

PHP sample은 실제 서비스의 rewrite/fallback/proxy behavior를 대표하지 않는다. 따라서 PHP sample에서 직관적으로 보이는 status 분포를 OpenCart나 Juice Shop에 그대로 적용하면 안 된다.

## 4. OpenCart front-controller baseline

OpenCart는 실제 PHP app의 front-controller/routed response behavior를 보여주는 baseline이다.

보존할 결론:

- 존재하지 않는 path, sensitive-looking path, traversal-like path도 200으로 관찰될 수 있다.
- `query_string`에 `_route_=`가 추가되어 원 요청 target과 routed target이 함께 드러난다.
- `handler=redirect-handler`는 rewrite/front-controller/fallback 처리 힌트다.
- `/admin` 같은 요청은 redirect-follow 때문에 logical request 1개가 actual Apache request 여러 건으로 확장될 수 있다.
- S08/S09 POST는 request metadata로 관찰되지만 app/DB audit 없이는 login/upload 결과를 판단하지 않는다.

OpenCart에서 특히 중요한 guardrail은 다음이다.

```text
status_code=200 + handler=redirect-handler + _route_=...
```

이 조합은 공격 성공이 아니라 fallback/routed response 후보로 해석한다. 파일 존재, 파일 노출, traversal success, login success, upload success를 의미하지 않는다.

## 5. Juice Shop reverse proxy baseline

Juice Shop은 Apache reverse proxy 뒤의 backend app을 관찰하는 대표 공격 재현 대상이다.

보존할 결론:

- 대부분의 backend app 요청은 `handler=proxy-server`로 관찰된다.
- probe-like path도 backend 또는 SPA fallback으로 `status_code=200`, `resp_content_type=text/html`을 반환할 수 있다.
- Apache는 backend response metadata를 볼 수 있지만 backend 내부 인증, 라우팅, DB 결과, response body 의미를 알 수 없다.
- backend unavailable check에서는 503과 proxy/proxy_http error log가 관찰될 수 있다.

`handler=proxy-server`와 200 응답은 reverse proxy를 통해 backend가 HTTP response를 반환했다는 metadata일 뿐이다. backend route 존재, backend file exposure, 인증 성공, DB 영향, exploit success를 증명하지 않는다.

## 6. 공통 결론

세 topology 비교에서 유지해야 할 공통 결론은 다음이다.

- `status_code=200`은 topology-dependent weak signal이다.
- `response_body_bytes`, `resp_content_type`, `handler`, `_route_=`, `proxy-server`는 성공 증거가 아니다.
- payload-like query가 관찰되면 candidate로 유지할 수 있지만 exploitation success는 단정하지 않는다.
- front-controller, reverse proxy, fallback context는 scoring 상승 근거가 아니라 interpretation guardrail에 가깝다.
- redirect-follow로 actual Apache request 수가 logical scenario 수보다 많아질 수 있다.
- 동일 scenario label이라도 앱별 endpoint 의미가 다를 수 있다.

## 7. Apache logs-only guardrail

Apache access/security/error log만으로 다음을 단정하지 않는다.

- raw POST body 원문
- response body 내용
- DB query 결과
- 브라우저 JavaScript 실행 여부
- 로그인 성공 또는 계정 탈취 성공
- 업로드 저장 성공 또는 파일 삭제 성공
- 파일 노출, 서버 침해, 명령 실행 성공
- backend route 존재 또는 파일 존재
- `src_ip`, `peer_ip`, `X-Forwarded-For`, `X-Real-IP`, `Forwarded` 기반 공격자 attribution

허용되는 표현은 “요청이 관찰됨”, “payload-like pattern이 관찰됨”, “fallback/routed/proxy response context가 관찰됨”, “추가 증거 없이는 성공 여부 판단 불가” 수준이다.

## 8. prepare / report 해석에 주는 의미

이 비교는 detection 강화보다 interpretation guardrail 강화에 가깝다.

- explicit payload 후보는 candidate로 유지할 수 있다.
- status/error-only 후보와 topology context는 별도 bucket/context로 설명할 수 있다.
- broad demotion, severity 상승, verdict 강화는 이 비교만으로 확정하지 않는다.
- Stage1/Stage2/report/viewer는 topology context를 성공 근거로 재해석하지 않는다.

## 9. lab 제거와의 관계

이 문서는 lab comparison 원문을 대체하기 위한 docs-side review다.

다만 다음 작업은 별도 PR에서 판단한다.

- lab comparison 원문 삭제 여부
- lab comparison 원문 archive 여부
- observability scenario catalog/template 이관 여부
- scripts가 사용하는 `lab/observability` 기본 경로 변경 여부

이번 문서는 lab 파일을 삭제하거나 이동하지 않는다.
