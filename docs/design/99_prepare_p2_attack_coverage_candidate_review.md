# P2 Attack Coverage Candidate Review

- 문서 상태: P2 후보 비교 문서
- 기준 시점: 2026-05-07
- 목적: P1 신규 coverage 이후 다음 후보를 선택하기 위한 판단 기준을 고정한다.
- 상단 결론: GraphQL / API introspection attempt, Open redirect / redirect abuse attempt, SSTI / template injection, XXE / XML parser abuse attempt는 1차 regression 완료. API key / secret token probe와 Webshell command query endpoint는 coverage plan 작성 완료 상태이며, regression은 보수적으로 별도 fixture plan 후보로 유지한다.

관련 문서:

- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_ssrf_log4shell_coverage_plan.md](./99_prepare_ssrf_log4shell_coverage_plan.md)
- [99_prepare_ssrf_log4shell_fixture_plan.md](./99_prepare_ssrf_log4shell_fixture_plan.md)
- [99_prepare_webshell_probe_coverage_plan.md](./99_prepare_webshell_probe_coverage_plan.md)
- [99_prepare_webshell_probe_fixture_plan.md](./99_prepare_webshell_probe_fixture_plan.md)
- [99_prepare_api_key_secret_probe_coverage_plan.md](./99_prepare_api_key_secret_probe_coverage_plan.md)
- [99_prepare_webshell_command_query_coverage_plan.md](./99_prepare_webshell_command_query_coverage_plan.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "graphql\|__schema\|__type\|IntrospectionQuery\|redirect=\|next=\|return=\|continue=\|{{\|DOCTYPE\|ENTITY\|api_key\|access_token\|cmd=\|exec=" src tests docs
```

확인 요약:

```text
- P2 후보 신호는 docs/design의 기존 candidate review에 이미 폭넓게 정리되어 있다.
- tests/fixtures에서는 webshell command-query 관련 기존 샘플(l3_ssti_webshell_context)의 /upload/shell.php?cmd=id가 확인된다.
- 이번 문서는 구현 지시가 아니라 다음 coverage 후보 선택을 위한 비교/판단 문서로 유지한다.
```

## 1. 목적

- SSRF metadata / Log4Shell obfuscated / Webshell admin path probe regression 이후 다음 P2 후보를 비교한다.
- 바로 구현하지 않고 후보의 가치, 위험, fixture 난이도, Apache logs-only 해석 한계를 비교한다.

## 2. 현재 완료 상태

- `l3_ssrf_metadata_endpoint_context`
- `l3_log4shell_obfuscated_payload_context`
- `l3_webshell_admin_tool_probe_context`
- `l3_graphql_introspection_context`
- `l3_open_redirect_external_url_context`
- `l3_ssti_template_expression_context`
- `l3_xxe_external_entity_context`
- prepare regression `pass=25 warn=0 fail=0`
- stage dry-run regression `pass=19 warn=0 fail=0`
- Stage2 report quality tests `14 passed`

## 3. P2 후보 목록

완료된 P2 후보:

- GraphQL / API introspection attempt
- Open redirect / redirect abuse attempt
- SSTI / template injection
- XXE / XML parser abuse attempt

다음 후보:

- API key / secret token probe
- Webshell command query endpoint

보수적/별도 검토 후보:

- API key / secret token probe
- Webshell command query endpoint

장기 후보로 유지:

- Deserialization / object injection-like payload
- LDAP / NoSQL injection-like payload
- request smuggling / header anomaly
- scanner / tool behavior 확장

## 4. 공통 Apache logs-only boundary

Apache access logs에서 볼 수 있는 것:

- method/path/query string
- 일부 request target
- status_code
- response_body_bytes
- content-type
- timing metadata
- repeated/sequence/context pattern

Apache access logs만으로 볼 수 없는 것:

- response body 원문
- raw POST body
- DB/API/backend response content
- browser execution
- XML parser execution
- template rendering result
- redirect follow success
- schema disclosure success
- credential/token exposure
- command execution success
- internal request success
- server compromise
- attacker identity

금지 표현:

- GraphQL schema exposed
- open redirect confirmed
- SSTI executed
- XXE file read succeeded
- API key leaked
- command executed
- exploit succeeded
- server compromised

허용 표현:

- GraphQL introspection-like request observed
- open-redirect-like parameter observed
- template-expression-like payload observed
- XXE-like marker observed
- secret-token-like parameter probe observed
- command-like query parameter observed
- requires manual review

## 5. 후보별 비교표

| 후보 | 기존 module 관계 | 관찰 가능한 signal | false positive 위험 | fixture 난이도 | Stage2 wording 위험 | 추천 |
|---|---|---|---|---|---|---|
| GraphQL / API introspection | shared attack hint path, API endpoint 분류 인접 | `/graphql`, `__schema`, `__type`, `IntrospectionQuery` | 중간 | 낮음~중간 | 중간 | 1순위(1차 완료) |
| Open redirect / redirect abuse | shared attack/search policy, SSRF parameter family 인접 | `redirect=`, `url=`, `next=`, `return=`, `continue=` | 높음 | 낮음~중간 | 중간~높음 | 2순위(1차 완료) |
| SSTI / template injection | shared attack hint path, decoded/expression 경계 인접 | `{{7*7}}`, `${7*7}`, `<%= 7*7 %>`, `#{7*7}` | 중간~높음 | 중간 | 높음 | 3순위(1차 완료) |
| XXE / XML parser abuse | shared attack hint path, SSRF/file disclosure 경계 인접 | `<!DOCTYPE`, `<!ENTITY`, `SYSTEM "file://..."` | 중간 | 중간~높음 | 높음 | 4순위(1차 완료) |
| API key / secret token probe | file disclosure/sensitive path/shared policy 인접 | `api_key=`, `access_token=`, `token=`, `secret=`, `.env`, `/config` | 높음 | 중간 | 높음 | 다음 후보 |
| Webshell command query endpoint | `l3_hints` + traversal/CMDI + webshell 경계 중첩 | `/cmd.php?cmd=id`, `/shell.php?exec=whoami` | 중간~높음 | 낮음~중간 | 높음 | coverage plan 완료, 별도 fixture plan 후보 |

## 6. 후보별 상세 검토

### 6.1 GraphQL / API introspection attempt

목표:

- GraphQL endpoint 또는 introspection-like query가 관찰되는 경우를 보수적으로 후보화할지 검토한다.

관찰 가능한 signal:

- `/graphql`
- `/api/graphql`
- `query={__schema{...}}`
- `query={__type(name:"...")}`
- `IntrospectionQuery`
- `__schema`
- `__type`

단정 금지:

- schema disclosure success
- introspection enabled confirmed
- API structure exposed
- data exfiltration
- auth bypass
- GraphQL vulnerability confirmed

candidate/context 판단:

- `/graphql` 단순 접근만 있으면 context-only 또는 low signal
- `__schema`, `__type`, `IntrospectionQuery`가 query string에 보이면 analysis candidate 가능
- status/bytes만으로 schema 노출 성공 주장 금지

fixture 아이디어:

- `l3_graphql_introspection_context`
- `GET /graphql?query={__schema{types{name}}}`
- `GET /api/graphql?query=IntrospectionQuery`
- benign baseline: `GET /graphql/playground` 또는 `GET /api/search?q=graphql`

추천:

- 1차 regression 완료된 P2 후보로 유지

### 6.2 Open redirect / redirect abuse attempt

관찰 가능한 signal:

- `redirect=http://external.example/`
- `url=https://external.example/`
- `next=//external.example/`
- `return=https://...`
- `continue=https://...`

단정 금지:

- redirect succeeded
- victim followed redirect
- phishing succeeded
- open redirect vulnerability confirmed

추천:

- 1차 regression 완료
- false positive가 높아 Apache logs-only 경계와 wording guard를 고정한 상태로 유지

### 6.3 SSTI / template injection

관찰 가능한 signal:

- `{{7*7}}`
- `{{config}}`
- `${7*7}`
- `<%= 7*7 %>`
- `#{7*7}`

단정 금지:

- template execution succeeded
- expression evaluated
- RCE succeeded
- server-side template engine confirmed

추천:

- 1차 regression 완료
- 기존 L3 힌트와 연결 가능하고 Apache logs-only 경계/wording guard를 고정한 상태로 유지

### 6.4 XXE / XML parser abuse attempt

관찰 가능한 signal:

- `<!DOCTYPE`
- `<!ENTITY`
- `SYSTEM "file:///etc/passwd"`
- `SYSTEM "http://..."`

단정 금지:

- file read succeeded
- external entity resolved
- SSRF succeeded
- XML parser vulnerable
- response body contained file contents

추천:

- 1차 regression 완료
- raw POST body/response body 비가시성 전제와 success 단정 금지 경계를 유지한 상태로 완료 후보에 편입

### 6.5 API key / secret token probe

관찰 가능한 signal:

- `api_key=`
- `access_token=`
- `token=`
- `secret=`
- `.env`
- `/config`

단정 금지:

- API key leaked
- token exfiltrated
- secret exposed
- credential theft
- auth bypass

추천:

- coverage plan 작성 완료
- false positive 위험이 높아 regression은 보류/별도 fixture plan 후보로 유지

### 6.6 Webshell command query endpoint

관찰 가능한 signal:

- `/cmd.php?cmd=id`
- `/shell.php?exec=whoami`
- `/upload/shell.php?cmd=id`

단정 금지:

- command executed
- shell access gained
- webshell exists
- RCE succeeded
- server compromised

추천:

- coverage plan 작성 완료
- traversal/CMDI와 의미 경계가 민감해 regression은 보류/별도 fixture plan 후보로 유지

## 7. 추천 우선순위

완료:

- GraphQL / API introspection attempt
- Open redirect / redirect abuse attempt
- SSTI / template injection
- XXE / XML parser abuse attempt

다음 후보:

- API key / secret token probe
- Webshell command query endpoint

보수적/별도 검토 후보:

- API key / secret token probe
- Webshell command query endpoint

## 8. 팀원 검토 요청 포인트

- API key / secret token probe에서 false positive 억제 경계를 어떻게 고정할지
- Webshell command query를 진행할 때 traversal/CMDI 경계를 어떻게 분리할지
- Stage2 lint/QA에서 추가로 금지해야 할 wording risk가 있는지

## 9. 다음 문서 후보

- `docs/design/99_prepare_api_key_secret_probe_coverage_plan.md` (작성 완료)
- `docs/design/99_prepare_webshell_command_query_coverage_plan.md` (작성 완료)

별도 검토 후보:

- API key / secret token fixture plan(미작성)
- Webshell command query fixture plan(미작성)
- `docs/design/99_prepare_api_key_secret_probe_coverage_plan.md`

## 10. 결론

- GraphQL / API introspection attempt, Open redirect / redirect abuse attempt, SSTI / template injection, XXE / XML parser abuse attempt 1차 regression은 완료되었다.
- GraphQL, Open redirect, SSTI, XXE는 완료된 P2 coverage로 이동한다.
- API key / secret token probe와 Webshell command query endpoint는 coverage plan 작성까지 완료되었다.
- 두 후보는 regression 완료 상태가 아니며, 별도 fixture plan 또는 round summary 판단 이후 진행한다.
- Webshell command query는 traversal/CMDI와 의미 경계가 민감하므로 별도 검토를 유지한다.
- API key/secret token probe는 false positive 위험 때문에 보수적으로 유지한다.
