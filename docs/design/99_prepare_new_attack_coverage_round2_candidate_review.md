# 99_prepare_new_attack_coverage_round2_candidate_review

- 문서 상태: 신규 공격 coverage 2라운드 후보 비교 문서
- 기준 시점: 2026-05-07
- 성격: 구현 문서가 아니라 후보 우선순위 판단용 review 문서

관련 문서:

- [99_prepare_new_attack_coverage_round_summary.md](./99_prepare_new_attack_coverage_round_summary.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_api_key_secret_probe_coverage_plan.md](./99_prepare_api_key_secret_probe_coverage_plan.md)
- [99_prepare_webshell_command_query_coverage_plan.md](./99_prepare_webshell_command_query_coverage_plan.md)
- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [../진행상황.md](../진행상황.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 목적

- 신규 coverage 2라운드 후보를 비교한다.
- 바로 구현하지 않고 후보의 가치/위험/검증 가능성을 비교한다.
- false positive 위험, Apache logs-only 가시성, Stage2 wording risk를 기준으로 우선순위를 정한다.

## 2. 1라운드 완료 상태

완료된 regression 7개:

- `l3_ssrf_metadata_endpoint_context`
- `l3_log4shell_obfuscated_payload_context`
- `l3_webshell_admin_tool_probe_context`
- `l3_graphql_introspection_context`
- `l3_open_redirect_external_url_context`
- `l3_ssti_template_expression_context`
- `l3_xxe_external_entity_context`

현재 검증 기준:

- prepare regression: `pass=25 warn=0 fail=0`
- stage dry-run regression: `pass=19 warn=0 fail=0`
- Stage2 report quality tests: `14 passed`

공통 원칙:

- Apache logs-only evidence boundary 유지
- 성공/침해/유출/RCE/credential theft/command execution/server compromise 단정 금지

## 3. 후보별 비교표

| 후보 | 관찰 가능한 signal | Apache logs-only 한계 | false positive 위험 | Stage2 wording risk | fixture 작성 난이도 | 기존 module과의 경계 | 추천 우선순위 |
|---|---|---|---|---|---|---|---|
| API key / secret token probe | `api_key=`, `token=`, `access_token=`, `secret=`, `.env`, config path probe | response body/실제 secret 노출 여부 비가시 | 높음 | 높음 | 중간 | `file_disclosure_hints`, `sensitive_path_probe`, shared policy 경계 민감 | P2-R2-1 |
| Webshell command query endpoint | `/cmd.php?cmd=id`, `/shell.php?exec=whoami`, `/upload/shell.php?cmd=id` | command output/실행 여부 비가시 | 중간~높음 | 높음 | 중간 | `l3_hints` + `traversal_cmdi_hints` 경계 민감 | P2-R2-2 |
| Deserialization / object injection-like payload | Java serialized marker, PHP object marker | backend execution/result 비가시 | 높음 | 높음 | 높음 | 기존 hint family와 taxonomy 확장 필요 | 장기 |
| LDAP / NoSQL injection-like payload | LDAP filter-like marker, NoSQL operator-like query | DB/backend result 비가시 | 높음 | 높음 | 중간~높음 | SQLi/기존 injection family 경계 민감 | 장기 |
| request smuggling / header anomaly | malformed request/header anomaly, TE/CL mismatch marker(로그에 남는 범위) | access log만으로 smuggling success 판단 어려움 | 중간~높음 | 높음 | 높음 | `protocol_anomalies`와 별도 경계 필요 | P2-R2-3(가시성 검토 우선) |
| scanner / tool behavior 확장 | tool-like UA, high-rate probe, multi-family probe | attacker/tool identity 확정 불가 | 높음 | 중간~높음 | 중간 | `AUTOMATION_UA_PATTERNS`, summary policy 경계 민감 | 보류 |

## 4. 후보별 상세

### API key / secret token probe

- signal: `api_key=`, `token=`, `access_token=`, `secret=`, `.env/config` path
- 위험: 정상 API traffic과 신호가 겹쳐 false positive 위험이 높다.
- 단정 금지: `API key leaked`, `token exfiltrated`, `credential theft`, `auth bypass`
- 추천: 보수 후보. fixture plan 선행 필요

### Webshell command query endpoint

- signal: `/cmd.php?cmd=id`, `/shell.php?exec=whoami`
- 위험: command execution/RCE 단정 risk가 높다.
- 경계: traversal/CMDI와 의미 경계가 민감하다.
- 추천: 보수 후보. fixture plan 선행 필요

### Deserialization / object injection-like payload

- signal: Java serialized marker, PHP object marker
- 한계: exploit success/RCE 단정 불가
- 추천: 장기 후보

### LDAP / NoSQL injection-like payload

- signal: LDAP filter-like marker, NoSQL operator-like query
- 한계: DB/backend result 비가시
- 추천: 장기 후보

### Request smuggling / header anomaly

- signal: malformed request/header anomaly, `Transfer-Encoding`/`Content-Length` mismatch가 access log에 남는 경우
- 한계: Apache access log만으로 smuggling success 확인이 어렵다.
- 추천: 장기 후보 또는 별도 로그 가시성 검토 필요

### Scanner / tool behavior 확장

- signal: tool-like UA, high-rate probe, multi-family probe
- 한계: attacker/tool identity 단정 금지
- 연결: `AUTOMATION_UA_PATTERNS`와 policy 경계 검토 필요
- 추천: 보류. policy review 선행

## 5. 추천 우선순위

- P2-R2-1: API key / secret token probe fixture plan 여부 판단
- P2-R2-2: Webshell command query fixture plan 여부 판단
- P2-R2-3: request smuggling/header anomaly 로그 가시성 검토
- 장기: deserialization, LDAP/NoSQL, scanner/tool behavior

## 6. 결론

- 2라운드는 바로 regression 추가보다 API key와 Webshell command query의 fixture plan 필요성 판단부터 시작한다.
- 두 후보 모두 위험도가 높아 구현 전 false positive/wording boundary를 더 강화한다.
- prepare split 추가 분리는 계속 보류한다.
