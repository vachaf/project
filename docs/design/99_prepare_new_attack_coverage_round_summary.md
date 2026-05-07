# 99_prepare_new_attack_coverage_round_summary

- 문서 상태: 신규 공격 coverage 확장 1라운드 summary
- 기준 시점: 2026-05-07
- 성격: 구현 계획 문서가 아니라 완료/보류 상태를 정리하는 요약 문서

관련 문서:

- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_ssrf_log4shell_coverage_plan.md](./99_prepare_ssrf_log4shell_coverage_plan.md)
- [99_prepare_ssrf_log4shell_fixture_plan.md](./99_prepare_ssrf_log4shell_fixture_plan.md)
- [99_prepare_webshell_probe_coverage_plan.md](./99_prepare_webshell_probe_coverage_plan.md)
- [99_prepare_webshell_probe_fixture_plan.md](./99_prepare_webshell_probe_fixture_plan.md)
- [99_prepare_graphql_introspection_coverage_plan.md](./99_prepare_graphql_introspection_coverage_plan.md)
- [99_prepare_graphql_introspection_fixture_plan.md](./99_prepare_graphql_introspection_fixture_plan.md)
- [99_prepare_open_redirect_coverage_plan.md](./99_prepare_open_redirect_coverage_plan.md)
- [99_prepare_open_redirect_fixture_plan.md](./99_prepare_open_redirect_fixture_plan.md)
- [99_prepare_ssti_coverage_plan.md](./99_prepare_ssti_coverage_plan.md)
- [99_prepare_ssti_fixture_plan.md](./99_prepare_ssti_fixture_plan.md)
- [99_prepare_xxe_coverage_plan.md](./99_prepare_xxe_coverage_plan.md)
- [99_prepare_xxe_fixture_plan.md](./99_prepare_xxe_fixture_plan.md)
- [99_prepare_api_key_secret_probe_coverage_plan.md](./99_prepare_api_key_secret_probe_coverage_plan.md)
- [99_prepare_webshell_command_query_coverage_plan.md](./99_prepare_webshell_command_query_coverage_plan.md)
- [../진행상황.md](../진행상황.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)
- [../../작업일지/0507.md](../../작업일지/0507.md)

## 1. 목적

- prepare split 추가 분리 대신 신규 공격/시나리오 coverage를 확장한 1라운드 결과를 요약한다.
- 완료된 항목과 남은 후보를 분리해 현재 상태를 고정한다.
- 다음 라운드 진입 전 판단 기준을 정리한다.

## 2. 1라운드 완료 regression

완료된 regression 7종:

- `l3_ssrf_metadata_endpoint_context`
  - signal: metadata endpoint/IP/hostname을 향하는 SSRF-like request pattern
  - 단정 금지 고정: outbound request success, metadata retrieval success, credential theft 단정 금지
- `l3_log4shell_obfuscated_payload_context`
  - signal: `${jndi:...}` 및 obfuscated JNDI-like payload, callback-like scheme marker
  - 단정 금지 고정: lookup resolution success, exploit success, RCE success 단정 금지
- `l3_webshell_admin_tool_probe_context`
  - signal: webshell/admin tool path probe (`/wso.php`, `/c99.php`, `/vendor/phpunit/...`)
  - 단정 금지 고정: webshell 존재, command execution, compromise 단정 금지
- `l3_graphql_introspection_context`
  - signal: `/graphql` + `__schema`/`__type`/`IntrospectionQuery` introspection-like marker
  - 단정 금지 고정: schema disclosure success, auth bypass success 단정 금지
- `l3_open_redirect_external_url_context`
  - signal: external URL + redirect-like parameter(`next`, `return`, `continue`, `redirect`, 제한적 `url`)
  - 단정 금지 고정: redirect success, phishing success, credential theft 단정 금지
- `l3_ssti_template_expression_context`
  - signal: template-expression-like payload(`{{7*7}}`, `${7*7}`, `<%=7*7%>`, `{{config}}`, `{{request}}`)
  - 단정 금지 고정: template execution success, expression evaluation success, RCE success 단정 금지
- `l3_xxe_external_entity_context`
  - signal: `DOCTYPE`/`ENTITY`/`SYSTEM`/`file://`/external entity URL marker
  - 단정 금지 고정: entity resolution success, file read success, SSRF success 단정 금지

## 3. 수정 범위 요약

1라운드 전체 범위:

- `src/prepare/l3_hints.py` 최소 확장 적용 항목 존재
  - Log4Shell obfuscated marker
  - Webshell admin path probe
  - Open redirect marker
  - XXE marker(`detect_xxe_hints`)
- `src/prepare_llm_input.py` 최소 연동 적용 항목 존재
  - GraphQL introspection
  - Open redirect
  - XXE
- 코드 수정 없이 기존 경계로 처리한 항목 존재
  - SSRF metadata endpoint
  - SSTI template expression
- 회귀 데이터 확장
  - `tests/fixtures/prepare_regression` 추가
  - `tests/expected/prepare_regression` 추가
  - `tests/expected/stage_dryrun_regression` 추가
- 변경하지 않은 범위
  - supporting_events/scoring/filtering 변경 없음
  - Stage2 reporter 변경 없음
  - `detect_decoded_attack_hints` 변경 없음

## 4. 검증 결과

현재 기준:

- `python3 -m py_compile ...` 통과
- prepare regression: `pass=25 warn=0 fail=0`
- stage dry-run regression: `pass=19 warn=0 fail=0`
- Stage2 report quality tests: `14 passed`

## 5. 유지한 Apache logs-only boundary

공통 단정 금지:

- exploit success
- server compromise
- RCE success
- command execution
- file read success
- credential theft
- browser execution
- schema disclosure success
- redirect success
- XXE entity resolution success
- metadata credential theft
- outbound request success

허용 표현:

- observed request pattern
- attempt
- probe
- requires manual review
- Apache logs alone do not confirm success

## 6. 남은 후보

- API key / secret token probe
  - 남긴 이유: `api_key`/`token`/`access_token`/`secret`/`.env`/config 계열은 coverage 가치가 있음
  - 바로 regression 미진행 이유: 정상 API traffic과 신호가 겹쳐 false positive 위험이 큼
  - 선행 필요: `99_prepare_api_key_secret_probe_coverage_plan.md` 기반 fixture plan 필요성 판단
- Webshell command query endpoint
  - 남긴 이유: `/cmd.php?cmd=id`, `/shell.php?exec=whoami`는 고신호 후보
  - 바로 regression 미진행 이유: traversal/CMDI와 webshell 경계가 민감함
  - 선행 필요: `99_prepare_webshell_command_query_coverage_plan.md` 기반 별도 fixture plan 필요성 판단
- Deserialization / object injection-like payload
  - 남긴 이유: 장기 coverage 후보로 의미가 큼
  - 바로 regression 미진행 이유: Apache logs 가시성과 payload 해석 난이도가 높음
  - 선행 필요: 후보 상세 review 및 marker catalog 정리
- LDAP / NoSQL injection-like payload
  - 남긴 이유: non-SQL 계열 확장 후보
  - 바로 regression 미진행 이유: false positive 및 taxonomy 경계 리스크
  - 선행 필요: 기존 injection family와 경계 검토 문서
- request smuggling / header anomaly
  - 남긴 이유: protocol anomaly 계열 확장 가치가 있음
  - 바로 regression 미진행 이유: Apache access log만으로 성공 여부/영향 판단 한계가 큼
  - 선행 필요: protocol anomaly 해석 한계 검토 선행
- scanner / tool behavior 확장
  - 남긴 이유: 운영 관점에서 반복 scan context 요약 가치가 있음
  - 바로 regression 미진행 이유: tool identity/행위 확정 표현 리스크와 노이즈 혼합
  - 선행 필요: summary 중심 보수 설계 및 wording guard 검토

## 7. 다음 라운드 판단 기준

- false positive 위험
- Apache logs-only 가시성
- existing module과의 경계
- fixture 작성 난이도
- Stage2 wording risk
- 발표/보고 가치
- expected fixture 안정성

## 8. 추천 다음 방향

- 바로 구현보다 2라운드 후보 비교 또는 API key/Webshell command fixture plan 검토를 우선한다.
- Webshell command query는 traversal/CMDI 경계 때문에 별도 검토를 선행한다.
- API key/token은 정상 API traffic과 FP 위험이 커서 별도 fixture plan 검토를 선행한다.
- request smuggling/header anomaly는 Apache log 가시성 한계 검토를 먼저 수행한다.

## 9. 결론

- 신규 coverage 1라운드는 완료되었다.
- 다음 단계는 추가 regression 즉시 확대보다, round summary 기반으로 2라운드 후보를 신중히 선택한다.
- prepare split 추가 분리는 계속 보류한다.
