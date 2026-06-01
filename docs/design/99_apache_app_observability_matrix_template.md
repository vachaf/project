# 99_apache_app_observability_matrix_template

- 문서 상태: design summary / lab observation matrix template 이관 요약
- 기준 원문: `../../lab/observability/observation_matrix_template.md`
- 관련 scenario summary: [99_apache_app_observability_scenario_catalog.md](./99_apache_app_observability_scenario_catalog.md)
- 목적: run별 observation matrix가 어떤 항목을 기록해야 하는지 설명한다.

## 1. Matrix의 역할

Observation matrix는 run별 관찰 원장에 가깝다. 각 scenario에서 Apache request/response metadata가 어떻게 남았는지, error log와 어떤 수준으로 연결되는지, 그리고 어떤 해석을 금지해야 하는지를 기록한다.

이 문서는 template 원문을 대체해 scripts input 경로를 바꾸려는 문서가 아니다. docs에서 lab template 없이도 matrix의 구조와 해석 기준을 읽을 수 있게 하는 summary다.

## 2. Matrix가 기록하는 항목

matrix가 기록하는 핵심 항목은 다음이다.

- scenario id와 scenario name
- request metadata: method, URI, query string, content type, content length, User-Agent marker
- status code와 response metadata: response size, content type, duration/TTFB, handler
- handler/topology hint: direct PHP, front-controller/routed response, reverse proxy/backend response 같은 context
- error log correlation: `request_id`, `error_link_id`, error level, module, warn/error 여부
- candidate policy 관련 관찰: payload candidate, status/error-only candidate, topology context, redirect/follow candidate
- evidence boundary / guardrail note: 성공, 노출, 침해, 인증, 업로드, DB 결과를 단정하지 않는 메모

run metadata에는 run id, target app, topology, app stack, OS/runtime/Apache version, log format version, WAF/app/DB audit availability, start/end time, scenario catalog version을 기록할 수 있다.

## 3. Matrix가 기록하지 않는 항목

matrix는 다음을 기록하거나 확정하지 않는다.

- raw POST body
- response body
- DB result
- browser execution result
- exploit success 확정
- login success, upload persistence, file exposure, command execution success
- attacker attribution 확정

WAF/app/DB audit log가 있더라도 Apache logs-only matrix의 결론을 자동으로 success verdict로 승격하지 않는다. 추가 증거는 별도 출처와 별도 해석 경계로 분리한다.

## 4. 해석 기준

관찰값과 결론을 분리한다.

- `status_code=200`은 HTTP response 관찰이지 success proof가 아니다.
- status/error-only 관찰은 broad demotion 확정 근거가 아니다.
- topology context는 interpretation guardrail로 사용한다.
- `handler=redirect-handler`, `_route_=`, `handler=proxy-server`는 routed/fallback/proxy hint이며 backend route 존재나 파일 존재 증거가 아니다.
- candidate policy 변경은 별도 design 문서와 regression을 거쳐야 한다.
- Web UI, Stage1, Stage2는 matrix의 metadata를 severity/category/verdict 강화 근거로 재해석하지 않는다.

관찰 가능한 suspicious evidence는 보존하되, Apache log에 없는 POST body, response body, DB, browser, filesystem, application state는 추론하지 않는다.

## 5. Run Summary와의 관계

- observation matrix는 run별 관찰 원장이다.
- [../reviews/99_observability_run_summaries.md](../reviews/99_observability_run_summaries.md)는 run별 결론 요약이다.
- [99_observability_run_summary_index.md](./99_observability_run_summary_index.md)는 상위 색인이다.
- [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md)는 run 분포와 candidate policy 판단 이력을 정리한 관찰 기록이다.

읽을 때는 matrix를 원자료 성격의 관찰 문서로 보고, review 문서의 결론과 design policy 문서의 기준을 구분한다.

## 6. Lab 원본과의 관계

현재 scripts가 `lab/observability/observation_matrix_template.md`를 사용할 수 있으므로 lab 원본은 유지한다.

이 docs 문서는 lab 제거 전 docs-side 설명 보강이다. script input 경로 변경, lab template 삭제, lab run artifact 이동 또는 archive 여부는 후속 PR에서만 검토한다.
