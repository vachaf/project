# 99_prepare_new_attack_coverage_candidate_review

- 문서 상태: prepare 새 공격/시나리오 coverage candidate review
- 기준 시점: 2026-05-07
- 목적: prepare split 이후 다음 큰 작업 축으로 새 공격/시나리오 coverage 후보를 비교하고, Apache access logs-only evidence boundary를 먼저 고정한 뒤 단기 우선순위와 장기 roadmap을 정리한다.

관련 문서:

- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [99_prepare_deferred_split_reentry_review.md](./99_prepare_deferred_split_reentry_review.md)
- [99_prepare_shared_attack_policy_reentry_review.md](./99_prepare_shared_attack_policy_reentry_review.md)
- [99_prepare_search_false_positive_policy_reentry_review.md](./99_prepare_search_false_positive_policy_reentry_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)
- [../진행상황.md](../진행상황.md)

## 1. 목적

- prepare split 이후 다음 큰 작업 축으로 새 공격 coverage 후보를 비교한다.
- 바로 코드 구현하지 않고 후보별 evidence boundary와 regression/fixture 가능성을 먼저 검토한다.
- 장기적으로 모든 후보를 순차 대응할 roadmap을 마련한다.
- 이번 문서는 구현 계획서가 아니라 candidate review 문서다.
- 어떤 후보를 먼저 fixture/regression 기반 coverage로 다룰지 판단하기 위한 문서다.

명시적 범위:

```text
- 코드 구현 문서가 아님
- fixture 추가 문서가 아님
- expected/test 변경 문서가 아님
- split 실행 문서가 아님
- Apache logs-only evidence boundary와 우선순위 판단을 고정하는 review 문서임
```

## 2. 현재 상태

prepare 계열은 현재 stable 상태이며, 추가 split보다 coverage candidate 검토가 더 생산적인 단계로 본다.

현재 상태 요약:

```text
- prepare module split round1/round2 완료
- constants mini-move 완료
- SQLi/XSS/file disclosure/traversal-CMDI hint split 완료
- auth/crawler constants move 완료
- deferred split re-entry review 완료
- shared attack/search policy re-entry review 완료
- search false-positive policy re-entry review 완료
- 추가 prepare split은 현재 보류
```

현재 안정 기준:

```text
- prepare regression pass=18 warn=0 fail=0
- stage dry-run regression pass=12 warn=0 fail=0
- Stage2 report quality tests 14 passed
```

현재 판단:

```text
- 위험한 추가 split을 구조 정리 목적만으로 재개하지 않음
- 다음 큰 축은 새 공격/시나리오 coverage 확장 검토로 전환
- 단, 구현보다 evidence boundary와 fixture/regression 설계 적합성 검토가 선행
```

## 3. 공통 Apache logs-only evidence boundary

각 후보에 공통 적용하는 해석 경계는 아래와 같다.

Apache logs에서 볼 수 있는 것:

- request method/path/query/header 일부
- status_code
- response_body_bytes
- content-type
- timing metadata
- repeated/sequence/context pattern

Apache logs만으로 볼 수 없는 것:

- response body 원문
- raw POST body
- DB 결과
- browser execution
- outbound request success
- internal network access success
- RCE success
- file read success
- exploit success
- credential theft
- server compromise
- attacker identity

공통 금지 표현:

```text
- 공격 성공, 침해, 유출, RCE, 브라우저 실행, 파일 읽기 성공 단정 금지
- internal network access success 단정 금지
- metadata access success 단정 금지
- redirect success 또는 phishing success 단정 금지
- admin access success 단정 금지
- schema exposure success 단정 금지
- 성공 확정형, 신원 확정형, 유출 확정형 표현 사용 금지
```

공통 해석 원칙:

```text
- status_code=200, response_body_bytes, content-type만으로 성공을 단정하지 않음
- payload marker는 request surface signal이지 execution proof가 아님
- sequence/context summary는 보조 문맥이지 단독 확정 근거가 아님
- fixture/regression 설계도 위 경계를 깨지 않는 범위에서만 검토
```

## 4. 후보별 비교표

| 후보 | 현재 관련 module | Apache logs에서 관찰 가능한 signal | 절대 단정 금지 항목 | candidate로 둘지 context-only로 둘지 | fixture 추가 난이도 | Stage1/Stage2 영향 | false positive 위험 | 추천 우선순위 | 장기 대응 방식 |
|---|---|---|---|---|---|---|---|---|---|
| SSRF / metadata endpoint attempt | shared attack hint path, `src/prepare_llm_input.py` 중심 | `url=`, `target=`, `dest=` 계열 외부/내부 URL, metadata IP/hostname, callback/redirect-like parameter, internal path probing | outbound request success, metadata retrieval success, internal access success | candidate | 중간 | Stage1 wording, Stage2 wording guard 필요 | 중간 | P1 | 별도 coverage plan + fixture/regression 검토 후 shared 또는 신규 module 판단 |
| Log4Shell / JNDI lookup | shared attack hint path, 기존 JNDI-like signal | `${jndi:ldap://...}`, `${jndi:rmi://...}`, header/query/path 내 JNDI marker, obfuscated lookup string | JNDI resolution success, RCE success, callback success | candidate | 중간 | Stage1/Stage2 wording guard 중요 | 중간 | P1 | dedicated coverage plan으로 패턴 family와 obfuscation 범위 고정 |
| SSTI / template injection | shared attack hint path, XSS/decoded boundary 인접 | `{{7*7}}`, `${...}`, `<%= ... %>`, Jinja/Twig/Velocity-like marker | template execution success, server-side code execution success | candidate | 중간 | Stage2 wording guard 필요 | 중간~높음 | P2 | SSTI 전용 candidate review 또는 shared expression family 정리 |
| Webshell / admin tool probe | scanner/sensitive path context + shared attack hint path | `/shell.php`, `/cmd.php`, `/upload.php`, `/wso.php`, `/c99.php`, `/vendor/phpunit/...`, `/cgi-bin/...` | webshell 존재, admin tool 존재, command execution success | candidate | 낮음~중간 | Stage1 taxonomy, Stage2 wording guard 필요 | 중간 | P1 | sensitive path/context와 candidate 경계 정리 후 별도 coverage plan |
| Deserialization / object injection-like payload | shared attack hint path | Java/PHP serialized object marker, object-like gadget string, unsafe deserialize parameter pattern | deserialization success, gadget execution success, RCE success | context-only에서 시작, 장기적으로 candidate 검토 | 높음 | Stage1 wording guard 부담 큼 | 높음 | P3 | 초기에는 marker catalog, 이후 필요 시 후보 승격 |
| XXE / XML parser abuse attempt | shared attack hint path | `<!DOCTYPE`, `<!ENTITY`, external entity marker, XML endpoint probing | file read success, SSRF success, parser execution success | candidate | 중간 | Stage2 wording guard 필요 | 중간 | P2 | XXE 전용 coverage plan 또는 SSTI와 분리된 parser abuse plan |
| Open redirect / redirect abuse attempt | shared attack/search policy와 인접 | `redirect=`, `url=`, `next=`, `return=`, `continue=` + 외부 URL 값 | redirect success, phishing success, token theft success | candidate | 낮음~중간 | wording guard 중심 | 중간~높음 | P2 | parameter family boundary 문서화 후 fixture 검토 |
| Request smuggling / header anomaly attempt | `protocol_anomalies.py`, method/protocol summary 인접 | suspicious `Transfer-Encoding`, `Content-Length` anomaly, malformed request signal | smuggling success, proxy desync success, internal routing success | context-only 우선 | 높음 | Stage1/Stage2 과해석 위험 큼 | 높음 | P3 | protocol anomaly 보강 후보로 장기 관리 |
| API key / secret token probe | file disclosure/sensitive path/shared attack policy 인접 | `api_key=`, `token=`, `access_token=`, `.env`, config path probe | secret exposure success, credential theft success | candidate | 중간 | wording/taxonomy guard 필요 | 중간~높음 | P2 | file disclosure 보강과 연계해 family 단위로 정리 |
| GraphQL / API introspection attempt | shared attack hint path | `/graphql`, `__schema`, `__type`, introspection-like query | schema exposure success, auth bypass success | candidate | 낮음~중간 | Stage2 wording guard 필요 | 중간 | P2 | dedicated API introspection family 검토 |
| LDAP/NoSQL injection-like payload | shared attack hint path, SQLi boundary 인접 | LDAP filter-like payload, Mongo operator-like payload, query structure marker | auth bypass success, DB result success | context-only에서 시작, 장기적으로 candidate 검토 | 중간~높음 | Stage1 taxonomy 확장 필요 | 높음 | P3 | SQLi와 분리된 non-SQL injection family로 장기 검토 |
| Path traversal / CMDI 보강 후보 | `traversal_cmdi_hints.py` | 추가 traversal wrapper, shell metacharacter, encoded family, OS command pattern | file read success, command execution success | candidate | 낮음~중간 | 기존 module 보강 범위 | 중간 | 기반 보강 | 기존 module 확장 우선, 새 module은 지양 |
| File disclosure 보강 후보 | `file_disclosure_hints.py` | wrapper, backup, env, config probe family | file disclosure success, config exposure success | candidate | 낮음~중간 | 기존 taxonomy/wording guard 필요 | 중간 | 기반 보강 | 기존 module 확장 우선 |
| Scanner/tool behavior summary 확장 후보 | `sensitive_path_probe.py`, `mixed_baseline_scanner.py`, `crawler_baseline.py`, `src/prepare_llm_input.py`의 `AUTOMATION_UA_PATTERNS` | tool-like UA, high-rate probe, multi-family path probe, mixed baseline/scanner sequence | tool identity, operator identity, exploit success | context-only 우선 | 중간 | Stage1/Stage2 wording guard 중요 | 높음 | P3 | policy review 우선, 코드 분리보다 summary/guard 강화 |

## 5. 후보별 상세 메모

### 5.1 SSRF / metadata endpoint attempt

목표:

- URL parameter 기반 SSRF 의심 요청, metadata endpoint 접근 시도, internal URL probing, callback URL abuse를 fixture/regression 후보로 볼 수 있을지 검토한다.

관찰 가능한 request pattern:

- `url=`, `uri=`, `dest=`, `target=`, `feed=`, `callback=` 등 URL parameter
- `http://169.254.169.254`, cloud metadata hostname, `localhost`, RFC1918 주소, internal hostname
- 외부 URL 또는 internal URL을 값으로 가지는 redirect-like/callback-like parameter

해석 한계:

- Apache logs만으로 outbound request가 실제로 발생했는지 볼 수 없다.
- metadata 응답이 반환됐는지, internal network 접근이 성공했는지 단정할 수 없다.

기존 module과의 관계:

- 현재는 shared attack hint path 또는 coordinator 영역에서 다루는 성격이 강하다.
- dedicated SSRF module이 바로 필요한지보다 coverage boundary 고정이 먼저다.

새 module 필요 여부:

- 현재 단계에서는 미정.
- 첫 구현 시에도 shared family 확장으로 충분할 수 있으므로 바로 새 module을 전제하지 않는다.

fixture/regression 아이디어:

- metadata IP/hostname parameter probe
- internal admin URL 또는 localhost probe
- callback URL에 외부 URL이 주입된 요청
- mixed benign URL parameter와 비교하는 false-positive 억제 샘플

Stage2 wording guard 필요 여부:

- 필요.
- outbound request success, metadata exposure success, internal access success 단정 금지 문구가 필요하다.

우선순위:

```text
P1
```

### 5.2 Log4Shell / JNDI lookup

목표:

- `${jndi:ldap://...}` 계열 payload와 obfuscated JNDI lookup string을 fixture/regression 기반 coverage 후보로 정리한다.

관찰 가능한 request pattern:

- `${jndi:ldap://...}`
- `${jndi:rmi://...}`
- header, query, path에 포함된 JNDI lookup string
- case variation, delimiter variation, simple obfuscation

해석 한계:

- lookup resolution success, callback success, RCE success를 Apache logs만으로 볼 수 없다.
- response status만으로 exploit 여부를 판단할 수 없다.

기존 module과의 관계:

- 현재는 shared attack hint path 성격이 강하다.
- Log4Shell family는 기존 JNDI-like signal 정리를 더 formal하게 만들 candidate다.

새 module 필요 여부:

- 미정.
- dedicated module보다 candidate review와 coverage plan이 먼저다.

fixture/regression 아이디어:

- query, path, header 위치별 JNDI marker 샘플
- 단순 obfuscation variation
- benign `${...}`와의 구분 샘플

Stage2 wording guard 필요 여부:

- 필요.
- JNDI resolution success, callback success, RCE success 금지 문구가 중요하다.

우선순위:

```text
P1
```

### 5.3 SSTI / template injection

목표:

- template-like expression family를 별도 coverage 후보로 볼지, 기존 expression 계열 shared signal로 남길지 판단한다.

관찰 가능한 request pattern:

- `{{7*7}}`
- `${...}`
- `<%= ... %>`
- Jinja/Twig/Velocity-like marker

해석 한계:

- template execution success나 server-side expression evaluation 성공을 단정할 수 없다.
- `${...}` 계열은 benign placeholder와 섞일 수 있다.

기존 module과의 관계:

- XSS/decoded/shared expression boundary와 인접하다.
- false positive 관리가 중요하다.

새 module 필요 여부:

- 현재 단계에서는 미정.
- coverage plan 전까지는 shared family 후보로 유지한다.

fixture/regression 아이디어:

- 대표 marker family 샘플
- placeholder-like benign expression과 대비 샘플
- query/path 위치별 variation

Stage2 wording guard 필요 여부:

- 필요.
- execution success, RCE success 단정 금지.

우선순위:

```text
P2
```

### 5.4 Webshell / admin tool probe

목표:

- webshell-like path probe와 admin tool probe를 scanner context에서 candidate coverage로 승격할지 검토한다.

관찰 가능한 request pattern:

- `/shell.php`, `/cmd.php`, `/upload.php`, `/wso.php`, `/c99.php`
- `/vendor/phpunit/...`
- `/cgi-bin/...`
- admin tool 또는 upload endpoint probing

해석 한계:

- webshell 존재, phpunit 노출, admin access success, command execution success를 단정할 수 없다.

기존 module과의 관계:

- `sensitive_path_probe.py`, `mixed_baseline_scanner.py`와 강하게 연결된다.
- 단순 context-only에 머무를지 candidate화할지가 핵심 판단 포인트다.

새 module 필요 여부:

- 보수적으로는 필요하지 않을 수 있다.
- path probe family 보강으로 먼저 다룰 가능성이 크다.

fixture/regression 아이디어:

- 대표 webshell filename probe
- phpunit probe
- `/cgi-bin/` probe
- benign upload path와의 구분 샘플

Stage2 wording guard 필요 여부:

- 필요.
- webshell 존재/실행 성공 표현 금지.

우선순위:

```text
P1
```

### 5.5 Deserialization / object injection-like payload

목표:

- serialized object marker 계열을 즉시 candidate화할지, 우선 context-only marker catalog로 둘지 판단한다.

관찰 가능한 request pattern:

- Java serialized object marker
- PHP object injection marker
- serialized object-like blob
- unsafe deserialize parameter naming

해석 한계:

- deserialization success, gadget chain execution success, RCE success를 단정할 수 없다.
- raw POST body 부재로 coverage가 제한될 수 있다.

기존 module과의 관계:

- shared attack hint path 성격이 강하다.
- fixture 설계 난도가 다른 후보보다 높다.

새 module 필요 여부:

- 현재 단계에서는 불필요.
- 먼저 marker 정리와 boundary 문서화가 우선이다.

fixture/regression 아이디어:

- URL surface에서 확인 가능한 serialized marker 예시
- parameter name/context 기반 샘플

Stage2 wording guard 필요 여부:

- 매우 필요.
- RCE, deserialization success 단정 금지.

우선순위:

```text
P3
```

### 5.6 XXE / XML parser abuse attempt

목표:

- XML parser abuse 시도 family를 별도 candidate로 정리한다.

관찰 가능한 request pattern:

- `<!DOCTYPE`
- `<!ENTITY`
- external entity marker
- XML endpoint probing

해석 한계:

- external entity fetch success, file read success, SSRF success를 단정할 수 없다.
- raw POST body 부재 때문에 coverage surface가 제한될 수 있다.

기존 module과의 관계:

- shared attack hint path에 가깝다.
- SSRF/file disclosure와의 wording 경계가 필요하다.

새 module 필요 여부:

- 미정.
- 전용 coverage plan 전까지 shared parser abuse family로 본다.

fixture/regression 아이디어:

- query/path/header에 드러나는 XML marker 샘플
- XML endpoint probing 샘플

Stage2 wording guard 필요 여부:

- 필요.
- file read/SSRF success 단정 금지.

우선순위:

```text
P2
```

### 5.7 Open redirect / redirect abuse attempt

목표:

- redirect-like parameter family를 별도 coverage 후보로 둘지 판단한다.

관찰 가능한 request pattern:

- `redirect=`, `url=`, `next=`, `return=`, `continue=`
- 외부 URL 값
- callback/return target 조작

해석 한계:

- redirect success, phishing success, token theft success를 단정할 수 없다.
- 단순 URL navigation parameter와의 false positive 구분이 중요하다.

기존 module과의 관계:

- shared attack/search policy, SSRF-like parameter family와 인접하다.

새 module 필요 여부:

- 낮다.
- parameter family coverage로 먼저 다루는 편이 자연스럽다.

fixture/regression 아이디어:

- 외부 URL target이 들어간 redirect parameter
- benign same-site return URL과 비교 샘플

Stage2 wording guard 필요 여부:

- 필요.
- redirect success, phishing success 단정 금지.

우선순위:

```text
P2
```

### 5.8 Request smuggling / header anomaly attempt

목표:

- request smuggling-like signal을 candidate로 볼지, protocol anomaly context-only로 유지할지 판단한다.

관찰 가능한 request pattern:

- suspicious `Transfer-Encoding`
- `Content-Length` anomaly signal
- malformed request / header anomaly

해석 한계:

- smuggling success, proxy desync success, backend bypass success를 볼 수 없다.
- access log surface만으로는 정밀 판단이 어렵다.

기존 module과의 관계:

- `protocol_anomalies.py`, `method_summaries.py`와 경계가 맞닿아 있다.

새 module 필요 여부:

- 현재 단계에서는 불필요하다.
- protocol anomaly 보강 후보로 장기 관리한다.

fixture/regression 아이디어:

- malformed request summary surface 샘플
- header anomaly sequence 샘플

Stage2 wording guard 필요 여부:

- 매우 필요.
- smuggling success 단정 금지.

우선순위:

```text
P3
```

### 5.9 API key / secret token probe

목표:

- secret token parameter probe와 `.env`/config probe를 별도 coverage family로 정리한다.

관찰 가능한 request pattern:

- `api_key=`, `token=`, `access_token=`
- `.env`, config path probing
- secret filename/path relation

해석 한계:

- secret 노출 success, credential theft success를 단정할 수 없다.
- parameter 이름만으로 민감 정보 노출을 확정할 수 없다.

기존 module과의 관계:

- `file_disclosure_hints.py`, `sensitive_path_probe.py`, shared policy와 맞닿아 있다.

새 module 필요 여부:

- 낮다.
- file disclosure 보강 family로 다루는 편이 우선이다.

fixture/regression 아이디어:

- token parameter probe 샘플
- `.env`, config path probe 샘플
- benign token-like parameter와 비교 샘플

Stage2 wording guard 필요 여부:

- 필요.
- secret exposure success 단정 금지.

우선순위:

```text
P2
```

### 5.10 GraphQL / API introspection attempt

목표:

- GraphQL endpoint 및 introspection-like query를 별도 API coverage 후보로 둘지 판단한다.

관찰 가능한 request pattern:

- `/graphql`
- `__schema`
- `__type`
- introspection-like query

해석 한계:

- schema exposure success, authorization bypass success를 단정할 수 없다.

기존 module과의 관계:

- shared attack hint path에 가깝다.
- API-specific family로 묶는 것이 자연스럽다.

새 module 필요 여부:

- 미정.
- 초기에는 dedicated family plan 정도로 충분하다.

fixture/regression 아이디어:

- `/graphql` introspection-like query 샘플
- benign GraphQL endpoint access와 비교 샘플

Stage2 wording guard 필요 여부:

- 필요.
- schema exposure success 단정 금지.

우선순위:

```text
P2
```

### 5.11 LDAP / NoSQL injection-like payload

목표:

- SQLi 바깥의 injection-like family를 장기 coverage 후보로 정리한다.

관찰 가능한 request pattern:

- LDAP filter-like payload
- Mongo/NoSQL operator-like payload
- query structure marker

해석 한계:

- auth bypass success, DB result success, data access success를 단정할 수 없다.
- surface signal이 SQLi보다 약할 수 있다.

기존 module과의 관계:

- SQLi boundary와 인접하지만 별도 family로 보는 편이 안전하다.

새 module 필요 여부:

- 현재 단계에서는 불필요하다.
- marker catalog와 false-positive 기준이 먼저다.

fixture/regression 아이디어:

- 대표 LDAP filter-like string
- `$ne`, `$gt`, `$regex` 등 NoSQL operator-like query 샘플

Stage2 wording guard 필요 여부:

- 필요.
- auth bypass/DB result 단정 금지.

우선순위:

```text
P3
```

### 5.12 Path traversal / CMDI 보강 후보

목표:

- 이미 split이 끝난 `traversal_cmdi_hints.py`에 대해 추가 payload family 보강 범위를 검토한다.

관찰 가능한 request pattern:

- 추가 traversal wrapper
- shell metacharacter variation
- encoded traversal/CMDI family
- OS command-like separator/payload

해석 한계:

- file read success, command execution success를 단정할 수 없다.

기존 module과의 관계:

- `traversal_cmdi_hints.py` 직접 보강 후보다.

새 module 필요 여부:

- 원칙적으로 없다.
- 기존 module 확장을 우선한다.

fixture/regression 아이디어:

- encoded variation 보강 샘플
- baseline false-positive 비교 샘플

Stage2 wording guard 필요 여부:

- 기존 guard 유지 필요.

우선순위:

```text
기반 보강
```

### 5.13 File disclosure 보강 후보

목표:

- 이미 split이 끝난 `file_disclosure_hints.py`의 wrapper / backup / env / config probe family를 보강할지 검토한다.

관찰 가능한 request pattern:

- backup/config/env file probe
- wrapper family variation
- source/config path probe

해석 한계:

- response body 원문을 볼 수 없으므로 file disclosure success를 단정할 수 없다.
- config 내용 노출, secret exposure success를 단정할 수 없다.

기존 module과의 관계:

- `file_disclosure_hints.py` 직접 보강 후보다.
- `sensitive_path_probe.py`와 경계 점검이 필요하다.

새 module 필요 여부:

- 원칙적으로 없다.
- 기존 module 확장을 우선한다.

fixture/regression 아이디어:

- backup/env/config probe variation 샘플
- wrapper family variation 샘플

Stage2 wording guard 필요 여부:

- 필요.
- file disclosure success, config exposure success 단정 금지.

우선순위:

```text
기반 보강
```

### 5.14 Scanner / tool behavior summary 확장 후보

목표:

- tool-like UA, high-rate probe, multi-family path probe를 candidate화할지보다 policy review 대상으로 관리한다.

관찰 가능한 request pattern:

- tool-like UA
- high-rate probing
- multi-family sensitive path probe
- mixed baseline + scanner sequence

해석 한계:

- tool identity, attacker identity, exploit success를 단정할 수 없다.
- UA만으로 scanner를 확정하면 과해석 위험이 크다.

기존 module과의 관계:

- `sensitive_path_probe.py`, `mixed_baseline_scanner.py`, `crawler_baseline.py`, `AUTOMATION_UA_PATTERNS`와 연결된다.

새 module 필요 여부:

- 현재는 아니다.
- 코드 분리보다 policy review와 wording guard가 우선이다.

fixture/regression 아이디어:

- mixed benign + multi-family probe sequence 샘플
- tool-like UA가 있으나 공격 강신호가 약한 비교 샘플

Stage2 wording guard 필요 여부:

- 매우 필요.
- attacker identity, tool identity 단정 금지.

우선순위:

```text
P3
```

## 6. 우선순위 제안

단기 P1:

- SSRF / metadata endpoint attempt
- Log4Shell / JNDI lookup 보강
- Webshell / admin tool probe

중기 P2:

- SSTI / template injection
- XXE
- Open redirect
- GraphQL / API introspection
- API key / secret token probe

장기 P3:

- Deserialization / object injection
- LDAP / NoSQL injection-like payload
- request smuggling / header anomaly
- scanner / tool behavior 확장

이미 기반 있는 후보 보강:

- traversal / CMDI 보강
- file disclosure 보강

우선순위 판단 기준:

```text
- Apache logs surface에서 marker가 비교적 명확한가
- fixture/regression 샘플을 과도한 추정 없이 설계할 수 있는가
- Stage1/Stage2 wording guard를 명확히 둘 수 있는가
- false positive 위험을 비교 샘플로 통제할 수 있는가
- 기존 module 보강으로 충분한가, 아니면 별도 plan이 필요한가
```

## 7. 장기 roadmap

모든 후보를 순차 대응하기 위한 단계:

1. candidate review 작성
2. evidence boundary 고정
3. fixture 설계
4. prepare regression fixture 추가 여부 판단
5. Stage dry-run regression 추가 여부 판단
6. hint module 확장 또는 신규 module 여부 결정
7. Stage2 wording/lint guard 필요 여부 판단
8. dry-run spot check
9. actual LLM spot check 필요 시 수행
10. docs/TODO/진행상황 반영

roadmap 원칙:

```text
- 모든 후보를 장기적으로 순차 대응할 수 있도록 유지
- 단기 우선순위만 먼저 실행 후보로 올림
- 구현은 fixture/regression 설계와 wording guard 검토 뒤에만 진행
- Apache logs-only evidence boundary를 모든 단계의 선행 조건으로 유지
```

## 8. 다음 실행 후보

추천:

- 첫 번째 실제 설계 후보는 SSRF / Log4Shell / Webshell 중 하나를 고르되, 바로 코드 작성하지 말고 별도 split/coverage plan을 작성한다.

문서 후보:

- `docs/design/99_prepare_ssrf_log4shell_coverage_plan.md`
- `docs/design/99_prepare_webshell_probe_coverage_plan.md`
- `docs/design/99_prepare_ssti_xxe_coverage_candidate_review.md`

선택 기준:

```text
- request surface marker 명확성
- false positive 통제 가능성
- dedicated module 없이도 fixture/regression 설계가 가능한지
- Stage2 wording risk가 관리 가능한지
```

## 9. 결론

최종 결론:

```text
- 추가 prepare split보다 새 공격 coverage 후보 검토가 더 생산적
- 단기적으로 SSRF / Log4Shell / Webshell 계열부터 검토
- 중기에는 SSTI / XXE / Open redirect / GraphQL 등으로 확장
- 장기적으로 모든 후보를 순차 대응하되, Apache logs-only boundary를 먼저 문서화
- 구현은 fixture/regression 설계 후 진행
```
