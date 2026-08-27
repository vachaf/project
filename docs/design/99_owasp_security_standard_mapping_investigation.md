# OWASP 2025 / CWE / WSTG Mapping Investigation

기준 HEAD: `1d86040a872bdbf298d050d8cd463ed24aae8695`  
작성일: 2026-08-27  
범위: 조사 및 설계 문서 작성만 수행한다. 구현, prompt, fixture, test, migration은 변경하지 않는다.

## 1. 목적

이 문서는 Apache 로그 분석 시스템의 현재 분류 체계에 OWASP Top 10:2025, CWE, OWASP WSTG 매핑을 추가할 수 있는지 사전 조사한 결과이다.

핵심 원칙은 다음과 같다.

```text
Observed attack pattern != confirmed vulnerability
OWASP mapping != successful exploitation
```

한국어로는 다음 의미이다.

- 로그에서 공격 형태가 관찰되었다고 해서 대상 서버의 취약점이 확인된 것은 아니다.
- OWASP/CWE/WSTG 분류와 연결되었다고 해서 공격 성공, 정보 유출, 권한 상승, 명령 실행, 브라우저 실행을 의미하지 않는다.
- Apache logs-only 분석의 증거 한계를 매핑 후에도 유지해야 한다.

Top 10, CWE, WSTG는 역할이 다르다.

- OWASP Top 10: 위험/취약점 범주의 상위 taxonomy
- CWE: 구체적인 weakness taxonomy
- OWASP WSTG: 보안 테스트 방법과 테스트 시나리오

세 체계를 같은 의미로 취급하면 안 된다.

## 2. 조사 범위

확인한 주요 영역은 다음과 같다.

- Stage1 classifier와 JSON schema: `src/llm_stage1_classifier.py`
- Prepare pipeline: `src/prepare_llm_input.py`, `src/prepare/models.py`, `src/prepare/*.py`
- `reason_hints`, `verdict_hint`, SQLi/XSS/traversal/CMDI/file disclosure/auth/IP/method/protocol 관련 hint
- Stage2 입력 생성과 prompt/report policy: `src/llm_stage2_reporter.py`
- Viewer payload builder와 Report Viewer: `src/viewer_payload_builder.py`, `web/templates/payload_detail.html`
- 현재 fixtures/regression tests와 design/review 문서
- OWASP Top 10:2025, CWE, OWASP WSTG 공식 문서

저장소 전체에서 다음 문자열을 검색했다.

```text
benign_normal
likely_false_positive
suspicious_scan
suspicious_bruteforce
suspicious_sqli
suspicious_xss
suspicious_path_traversal
suspicious_command_injection
suspicious_auth_abuse
suspicious_file_disclosure
server_error_probe
inconclusive
sensitive_path
file_disclosure
file_include
php://
protocol
method
scanner
reason_hints
verdict_hint
```

## 3. 현재 분석 pipeline

현재 흐름은 다음 구조로 보는 것이 맞다.

```text
Apache logs / DB export
-> Prepare deterministic candidate/context extraction
-> Stage1 LLM per-candidate classification
-> Stage2 LLM incident/report synthesis
-> Viewer payload builder
-> Report Viewer
```

Prepare는 request metadata와 rule-based hints를 만든다. Stage1은 Prepare가 만든 candidate 단위 입력과 schema를 보고 verdict를 선택한다. Stage2는 Stage1 결과, 원본 candidate evidence, context-only summaries, policy notes를 받아 보고서를 만든다. Viewer payload builder는 Stage2/Stage1/Prepare 산출물을 read-only 표시용 payload로 정규화한다.

현재 구조에서 보안 표준 매핑은 존재하지 않는다. 향후 넣는다면 Stage1 verdict, Prepare `reason_hints`, Apache observability boundary를 조합하는 deterministic enrichment가 가장 자연스럽다.

## 4. 현재 실제 verdict 목록

현재 Stage1 schema의 실제 verdict enum은 다음 12개이다.

| Verdict | 현재 존재 위치 | 성격 |
| --- | --- | --- |
| `benign_normal` | Stage1 schema/model | 정상 또는 일반 애플리케이션 동작 |
| `likely_false_positive` | Stage1 schema/model | rule hint는 있으나 정상 가능성이 큰 후보 |
| `suspicious_scan` | Stage1 schema/model | scan/recon 행동 |
| `suspicious_bruteforce` | Stage1 schema/model | 반복 인증 시도/brute force 의심 |
| `suspicious_sqli` | Stage1 schema/model | SQLi-like 구조 |
| `suspicious_xss` | Stage1 schema/model | XSS-like payload |
| `suspicious_path_traversal` | Stage1 schema/model | 명시적 directory escape evidence |
| `suspicious_file_disclosure` | Stage1 schema/model, 일부 Prepare hint | file disclosure/PHP wrapper/source disclosure attempt |
| `suspicious_command_injection` | Stage1 schema/model | command injection-like token |
| `suspicious_auth_abuse` | Stage1 schema/model | brute force로 단정하기 어려운 auth abuse |
| `server_error_probe` | Stage1 schema/model | 서버/프록시 error path 탐색 또는 error 유발 |
| `inconclusive` | Stage1 schema/model | 수상하지만 특정 class 부여 부족 |

다음은 verdict가 아니다.

- `sensitive_path`: Prepare reason/context hint 계열
- `file_disclosure:*`: Prepare reason hint 계열이며 Stage1 verdict는 `suspicious_file_disclosure`
- `file_include`: 현재 코드의 verdict/hint 이름으로는 확인되지 않고 WSTG/문서 용어에 가깝다.
- `php://`: file disclosure/PHP wrapper 탐지 pattern
- `protocol`: log field와 protocol anomaly context/hint
- `method`: log field와 method behavior context/hint
- `scanner`: `suspicious_scan` verdict, mixed scanner context, fixtures/docs에서 사용되는 표현
- `reason_hints`: Prepare -> Stage1 -> Stage2 -> Viewer로 전달되는 evidence hint field
- `verdict_hint`: Prepare가 Stage1에 제공하는 보조 hint field

## 5. Prepare/reason 체계

`Candidate` 모델은 Apache 로그 row metadata와 다음 분석 필드를 가진다.

- `score`
- `verdict_hint`
- `reason_hints`
- `request_id`, `error_link_id`
- `raw_request`, `raw_request_target`
- response/content/timing fields
- observability/HPP related fields

현재 Prepare에서 실제로 설정하는 `verdict_hint` 값은 다음 계열이다.

| `verdict_hint` | 발생 조건 요약 | 비고 |
| --- | --- | --- |
| `possible_false_positive_sql_keyword_search` | educational/natural-language SQL keyword search | Stage1 final verdict가 아님 |
| `possible_false_positive_xss_keyword_search` | educational/natural-language XSS keyword search | Stage1 final verdict가 아님 |
| `xss` | XSS pattern score가 충분함 | Stage1 입력 hint |
| `sqli` | SQLi pattern score가 충분함 | Stage1 입력 hint |
| `path_traversal` | traversal pattern score가 충분함 | Stage1 입력 hint |
| `command_injection` | CMDI pattern score가 충분함 | Stage1 입력 hint |
| `suspicious_file_disclosure` | PHP wrapper/resource pattern 등 file disclosure hint | Stage1 verdict 명칭과 같은 문자열 |
| `suspicious_auth_success` | 공격 hint가 있는 auth endpoint 200 JSON 응답 | auth success 단정 금지 |
| `suspicious` | status/error/auth/sensitive/general scoring | 넓은 generic hint |

주요 `reason_hints` prefix는 다음과 같다.

| Prefix | 현재 의미 | 비고 |
| --- | --- | --- |
| `sqli:` | SQLi-like syntax, boolean/time/comment/union 등 | DB 실행/결과는 알 수 없음 |
| `xss:` | script/event/javascript/data access/external navigation 등 | browser execution/reflection은 알 수 없음 |
| `traversal:` | `../`, URL encoded/double encoded traversal, `/etc/passwd`, raw/normalized 차이 | 직접 민감 경로와 분리 필요 |
| `cmdi:` | pipe/semicolon/subshell command token | 명령 실행 성공 알 수 없음 |
| `file_disclosure:` | `php://filter`, base64 source intent, resource parameter, sensitive resource name | disclosure 성공 알 수 없음 |
| `encoding:` | decoded/double-decoded attack signal | 원본/decoded 증거 보강 |
| `sensitive_path:` | `.env`, `/admin`, `config.php`, repeated sensitive sequence | app/file 존재 또는 접근 성공 아님 |
| `dir_probe:` / `file_probe:` | directory/file probing sequence | context-only로 쓰일 수 있음 |
| `auth_abuse:` | repeated auth endpoint, repeated 401, rapid burst, mixed 401/200 | POST body/auth result 없음 |
| `ip_behavior:` | same IP multi-path/error/attack category burst | context-only |
| `method_probe:` | OPTIONS/TRACE/PUT/DELETE/PATCH/unsupported method | method success 아님 |
| `protocol_anomaly:` | HTTP/1.0, malformed, missing/odd Host, long path 등 | protocol bypass 아님 |
| `observability:` | front-controller, reverse proxy, fallback 200, redirect/backend candidate | 해석 보조 |
| `hpp:` | duplicate parameters, embedded attack hint | app-specific parsing 필요 |
| `ua:` | automation/scanner-like User-Agent | 취약점 유형 아님 |
| `l3:` and sub-prefixes | Log4Shell, SSRF, open redirect, SSTI, GraphQL, XXE, webshell | 대부분 attempt/context only |
| `fp_hint:` / `context:` | educational/search false-positive guardrail | 매핑 억제 근거 |
| `baseline:` / `crawler:` / `static_baseline:` | 정상/크롤러/static baseline context | 공격 분류 아님 |

## 6. 공격 유형별 현재 판정 기준

| 분석 유형 | 현재 발생 위치 | 판정 근거 | Stage1 verdict | 관련 reason_hint | FP guardrail | 로그 한계 |
| --- | --- | --- | --- | --- | --- | --- |
| Path Traversal | Prepare traversal hints, Stage1 schema/prompt | `../`, `..\\`, URL encoded/double encoded traversal, `/etc/passwd`, `win.ini`, raw/normalized diff | `suspicious_path_traversal` | `traversal:*`, `encoding:*` | 직접 민감 경로만으로 traversal 금지, PHP wrapper는 file disclosure로 분리 | 파일 읽기/취약점/권한 우회 성공 알 수 없음 |
| SQL Injection | Prepare SQLi hints, Stage1 | `UNION SELECT`, boolean true, SQL comment, time-based token, quote termination 등 | `suspicious_sqli` | `sqli:*`, `encoding:*` | educational SQL/search query는 `fp_hint`와 false-positive hint로 낮춤 | DB query 실행, 결과, schema, data exfiltration 알 수 없음 |
| XSS | Prepare XSS hints, Stage1 | script tag, event handler, `javascript:`, browser data access, external navigation JS pattern | `suspicious_xss` | `xss:*`, `encoding:*` | educational XSS/search query 억제, raw log `location="-"`는 external navigation으로 보지 않음 | response reflection, stored 여부, browser execution, cookie theft 알 수 없음 |
| Command Injection | Prepare CMDI hints, Stage1 | pipe, semicolon, subshell-like command separator | `suspicious_command_injection` | `cmdi:*` | search/educational context는 낮춤, webshell/CMDI 경계 별도 | OS command execution, shell, compromise 알 수 없음 |
| File Disclosure / LFI | Prepare file disclosure hints, Stage1 normalization | `php://filter`, base64 source filter, resource parameter, sensitive resource name | `suspicious_file_disclosure` | `file_disclosure:*` | PHP wrapper를 traversal과 구분, direct config path는 sensitive probe로 조심 | source/config/file content 반환 여부 알 수 없음 |
| Sensitive Path Probe | Prepare sensitive path summaries and row hints | `/.env`, `/admin`, `/config.php`, `/admin/config.php`, `/server-status`, backup path 등 | 직접 verdict 없음. Stage1은 `suspicious`, `suspicious_scan`, `inconclusive` 등 선택 가능 | `sensitive_path:*`, `dir_probe:*`, `file_probe:*` | `no_*_inference` hints와 context-only policy | app/file 존재, 접근 가능, 정보 노출 알 수 없음 |
| Authentication Abuse | Prepare auth behavior context, Stage1 | login endpoint POST, repeated 401, rapid burst, mixed 401/200, JSON 200 with attack hint | `suspicious_auth_abuse` | `auth_abuse:*`, `login_endpoint`, `login_success_json_response` | `auth_abuse:post_body_not_visible`, `no_auth_success_inference`; 단일 auth 실패는 낮춤 | credentials, POST body, login success, lockout, account takeover 알 수 없음 |
| Brute Force | Stage1 verdict, auth behavior summaries | 반복 auth endpoint/401/rapid failure sequence | `suspicious_bruteforce` | `auth_abuse:repeated_*`, `auth_abuse:rapid_fail_burst` | auth success/lockout 단정 금지 | password guessing 성공 여부 알 수 없음 |
| Scanner / Reconnaissance | Stage1 verdict, probing/IP/mixed context | scanner UA, multi-path burst, sensitive path sweep, low-signal dir probing | `suspicious_scan` | `ua:*`, `ip_behavior:*`, `dir_probe:*`, `mixed_context:*` | context-only summaries are not auto-promoted | 취약점 종류나 exploitation success 아님 |
| Method anomaly | Method summaries and row hints | OPTIONS/TRACE/PUT/DELETE/PATCH, unsupported method | 직접 verdict 없음 | `method_probe:*` | method behavior summaries are context-only; `no_method_success_inference` | method enabled/allowed, write/delete/XST/CORS bypass 성공 알 수 없음 |
| Protocol anomaly | Protocol summaries | HTTP/1.0, malformed protocol, missing/odd Host, long path | 직접 verdict 없음 | `protocol_anomaly:*`, `method_probe:unsupported_method` | protocol anomaly summaries are context-only | protocol bypass, backend confusion, exploit success 알 수 없음 |
| Server Error Probe | Stage1 verdict, status/error hints | 4xx/5xx/error table/error_link/proxy/backend/error path context | `server_error_probe` | `error_status:*`, `error_linked`, `error_table_context`, `protocol_anomaly:*` | error status만으로 exploitation/A10 단정 금지 | response body/stack trace/internal exception/failing-open 알 수 없음 |
| 일반 정상 요청 | Prepare baseline/crawler/static filtering | normal search/static/crawler/browser-like behavior | `benign_normal` | `baseline:*`, `crawler:*`, `static_baseline:*` | 공격 hint와 baseline 분리 | 정상 의도 자체도 완전 증명은 아님 |
| False Positive | Prepare FP hints, Stage1 | educational/search/natural language context, weak syntax only | `likely_false_positive` | `fp_hint:*`, `context:educational_*`, `context:natural_language_query` | 공격 category 매핑 금지 또는 비우기 | 실제 무해성도 절대 증명은 아님 |
| Inconclusive | Stage1 fallback/uncertain cases | 수상하지만 특정 class 근거 부족 | `inconclusive` | any weak/mixed hints | 표준 매핑 비우기 우선 | 특정 weakness/category 부여 부족 |

## 7. OWASP 2025 매핑 후보

현재 OWASP Top 10:2025 공식 목록은 A01 Broken Access Control, A02 Security Misconfiguration, A03 Software Supply Chain Failures, A04 Cryptographic Failures, A05 Injection, A06 Insecure Design, A07 Authentication Failures, A08 Software or Data Integrity Failures, A09 Security Logging and Alerting Failures, A10 Mishandling of Exceptional Conditions이다.

매핑 후보는 다음과 같다.

| 현재 프로젝트 분류 | OWASP 2025 | 관계 | 근거와 경계 |
| --- | --- | --- | --- |
| `suspicious_path_traversal` | A01:2025 Broken Access Control | Direct | 명시적 directory escape attempt는 접근제어 우회/파일 경로 제어 실패와 직접 관련된다. 단, 취약점 확인/파일 read success는 아님 |
| `suspicious_sqli` | A05:2025 Injection | Direct | SQL interpreter 대상 injection-like payload. DB 실행/결과는 아님 |
| `suspicious_xss` | A05:2025 Injection | Direct | OWASP 2025 A05가 XSS를 포함한다. reflected/stored 구분과 browser execution은 불가 |
| `suspicious_command_injection` | A05:2025 Injection | Direct | OS command interpreter 대상 injection-like token. command execution은 불가 |
| `suspicious_bruteforce` | A07:2025 Authentication Failures | Direct | automated brute force/credential attack 방어 실패 범주와 직접 관련된다. 성공/lockout 부재는 알 수 없음 |
| `suspicious_auth_abuse` | A07:2025 Authentication Failures | Conditional | verdict 의미가 넓다. 반복 실패/rapid burst가 있을 때만 더 강하게 연결 |
| `suspicious_file_disclosure` | A01/A02/A05 중 조건부 | Conditional | traversal형, PHP wrapper/include형, direct sensitive file probe를 분리해야 한다 |
| `sensitive_path:*` / forced browsing | A01:2025 Broken Access Control, A02:2025 Security Misconfiguration | Related/Conditional | `/admin`, `/.env`, backup/config probing은 관련 있지만 접근 가능성/노출 확인은 없음 |
| `method_probe:*` | A02/A01 | Related/Conditional | 위험 method 노출이 확인되면 misconfiguration/access control과 연결 가능. method anomaly 자체는 Top 10 취약점 아님 |
| `protocol_anomaly:*` | None by default | Related | malformed/legacy protocol context. 실제 misconfiguration/failing-open 증거 없이는 Top 10 직접 매핑 금지 |
| `server_error_probe` | None by default | Related to A10 only with stronger evidence | 단순 4xx/5xx/error 발생은 A10 Mishandling of Exceptional Conditions가 아니다 |
| `suspicious_scan` | None by default | Related | scan/recon 행동이지 취약점 taxonomy가 아니다 |
| `likely_false_positive` | None | None | 표준 매핑을 비우는 것이 안전 |
| `benign_normal` | None | None | 보안 표준 mapping 없음 |
| `inconclusive` | None by default | None | 특정 weakness/category 근거 부족 |

## 8. CWE 매핑 후보

| 현재 프로젝트 분류/근거 | CWE 후보 | 관계 | 비고 |
| --- | --- | --- | --- |
| `suspicious_path_traversal`, `traversal:*` | CWE-22 Path Traversal | Direct | explicit traversal evidence가 있을 때만 |
| `suspicious_sqli`, `sqli:*` | CWE-89 SQL Injection | Direct | SQLi attempt pattern 기준 |
| `suspicious_xss`, `xss:*` | CWE-79 Cross-site Scripting | Direct | XSS attempt pattern 기준. reflected/stored는 미구분 |
| `suspicious_command_injection`, `cmdi:*` | CWE-78 OS Command Injection | Direct | OS command token context가 명확할 때 |
| generic command/control injection | CWE-77 Command Injection | Conditional | OS command로 좁히기 어려울 때 보조 후보 |
| `suspicious_bruteforce`, repeated auth attempts | CWE-307 Improper Restriction of Excessive Authentication Attempts | Direct/Conditional | 반복 auth attempt가 핵심 근거일 때 |
| broad `suspicious_auth_abuse` | CWE-307 | Conditional | 단일 200/401 또는 넓은 auth anomaly에는 강제하지 않음 |
| direct `/admin`, `/administrator` forced browsing | CWE-425 Direct Request | Conditional | 접근 가능 여부가 추가 확인될 때 |
| direct `/.env`, `/config.php`, backup/resource exposure | CWE-552 Files or Directories Accessible to External Parties | Conditional | 실제 외부 접근 가능/노출 확인이 필요 |
| confirmed sensitive information exposure | CWE-200 Exposure of Sensitive Information | Conditional | Apache access log만으로는 기본적으로 확인 불가 |
| PHP include/wrapper pattern | CWE-98 PHP Remote/Local File Include | Conditional | 현재는 `php://filter` source disclosure attempt에 가깝고 include/require 사용 여부는 알 수 없음 |
| `server_error_probe` | CWE-209, CWE-636 등 | Conditional/Do not assign by default | response body/error disclosure가 있어야 함 |

## 9. WSTG 매핑 후보

| 현재 프로젝트 분류/근거 | WSTG 후보 | 관계 | 비고 |
| --- | --- | --- | --- |
| `suspicious_path_traversal`, traversal-based file access | WSTG-ATHZ-01 Testing Directory Traversal File Include | Direct | explicit traversal attempt 기준 |
| PHP wrapper/file include-like attempt | WSTG-ATHZ-01 | Conditional | file include/LFI 테스트 시나리오와 관련. app include behavior는 미확인 |
| `suspicious_sqli` | WSTG-INPV-05 Testing for SQL Injection | Direct | SQLi payload 관찰 |
| `suspicious_xss` | WSTG-INPV-01 Reflected XSS, WSTG-INPV-02 Stored XSS | Conditional | URI/query payload는 reflected 테스트와 더 가깝지만 reflection 불가. stored는 logs-only로 구분 불가 |
| `suspicious_command_injection` | WSTG-INPV-12 Testing for Command Injection | Direct | command token attempt 기준 |
| HPP duplicate params | WSTG-INPV-04 Testing for HTTP Parameter Pollution | Related/Conditional | app-specific parameter handling 필요 |
| Brute force/repeated auth | WSTG-ATHN-03 Testing for Weak Lock Out Mechanism | Direct/Conditional | repeated attempt 관찰. lockout/CAPTCHA/credential result는 불가 |
| Direct sensitive files/backups | WSTG-CONF-04 Review Old Backup and Unreferenced Files | Related/Conditional | 요청 관찰만 가능 |
| Sensitive file extension/config path | WSTG-CONF-03 Test File Extensions Handling | Related/Conditional | 실제 exposed content 확인 불가 |
| Admin path probing | WSTG-CONF-05 Enumerate Infrastructure and Application Admin Interfaces | Related/Conditional | `/admin` 존재/접근 성공 미확인 |
| Method anomaly | WSTG-CONF-06 Test HTTP Methods | Related/Conditional | method enumeration/probe 관점 |
| Server error/protocol anomaly | WSTG-ERRH-01 Testing for Improper Error Handling | Related | response body/stack trace 없으므로 직접 취약점 매핑 불가 |
| Scan/recon | WSTG-INFO-06 Identify Application Entry Points, WSTG-CONF-* depending path | Related | 행동/정찰 context |

## 10. 직접/조건부/관련/비매핑 기준

향후 deterministic enrichment는 관계를 최소 네 가지로 나누어야 한다.

| 관계 | 기준 | 예 |
| --- | --- | --- |
| Direct | 현재 verdict와 strong reason hint가 해당 attack pattern/test scenario와 직접 일치한다. 그래도 success는 의미하지 않는다 | `suspicious_sqli` -> A05/CWE-89/WSTG-INPV-05 |
| Conditional | 추가 증거가 있으면 weakness/category에 연결할 수 있지만, 현재 로그만으로는 부족하다 | `/.env` request -> CWE-552는 실제 external access/exposure 확인 시 |
| Related | 관련 test/recon/error-handling 관점은 있으나 vulnerability category로 부여하면 과장될 수 있다 | `server_error_probe` -> WSTG-ERRH-01 related |
| None | 보안 표준 취약점/테스트 매핑을 부여하지 않는 것이 맞다 | `benign_normal`, `likely_false_positive`, generic `suspicious_scan` |

## 11. Apache logs-only observability

현재 canonical 경계는 `docs/00_apache_logs_only_evidence_boundary.md`와 custom log format contract가 기준이다.

### 관측 가능

현재 log format과 schema에서 관측 가능한 범위는 다음과 같다.

- request time
- request id / error link id
- source IP, peer IP, forwarding headers
- vhost/server/local endpoint metadata
- HTTP method
- raw request line, raw request target
- URI, query string, protocol
- status code, original status code
- response body byte count
- duration/TTFB and byte counts
- handler
- request content type/length metadata
- response content type
- location/referer/origin/user-agent/host/header metadata
- 일부 Apache error/security log context
- request repetition, source IP behavior, sequence/time-window 관계

### 기본적으로 관측 불가능

현재 데이터가 없거나 Apache access/error log만으로 판단할 수 없는 것은 다음과 같다.

- POST body
- HTTP response body
- DB query execution
- DB query result/schema/data exfiltration
- 실제 파일 내용 반환 여부
- OS command execution
- browser-side JavaScript execution
- XSS reflection 또는 stored rendering
- 로그인 성공 후 세션 탈취
- account takeover
- 실제 권한 상승
- 서버 내부 state change
- upload/delete/write 성공
- 실제 침해 성공
- target application의 logging/alerting 동작 전체

현재 코드가 이 경계를 유지하는 위치는 다음과 같다.

- Stage1 system prompt: hints are clues not proof, raw POST body assumptions 금지, traversal success 단정 금지, direct sensitive path != traversal.
- Prepare sensitive/auth/method/protocol/IP summaries: `context_only`, `no_*_inference`, `should_promote_to_candidate:false` 정책.
- Stage2 prompt/policy notes: DB/browser/file/command/auth/method/protocol success assertion 금지.
- Viewer payload builder: read-only deterministic adapter, no new detection/success inference/severity recalculation.

## 12. OWASP Top 10 coverage matrix

| OWASP 2025 | 현재 로그 기반 관측 가능성 | 현재 구현 지원 | 설명 |
| --- | --- | --- | --- |
| A01 Broken Access Control | Partial | Path traversal, forced browsing/sensitive path, method/auth context 일부 | access-control failure 자체는 확인 불가. attempt/context만 가능 |
| A02 Security Misconfiguration | Limited | sensitive files, server-status, backup/config probing, method/protocol anomaly, XXE hint 일부 | 실제 config 상태나 exposure는 response/app 검증 필요 |
| A03 Software Supply Chain Failures | Not Observable | 없음 | dependency/SCA/build provenance data 없음 |
| A04 Cryptographic Failures | Not Observable | 없음 | TLS/crypto 저장/전송/키 관리 판단 데이터 없음 |
| A05 Injection | Partial | SQLi, XSS, CMDI, SSTI/XXE/Log4Shell 등 일부 hints | injection attempt는 관찰 가능. interpreter execution은 불가 |
| A06 Insecure Design | Not Observable | 없음 | design flaw는 로그 한 줄/sequence만으로 직접 판단 어려움 |
| A07 Authentication Failures | Partial | brute force/auth behavior summaries, Stage1 auth verdicts | repeated attempt/status sequence 가능. credentials/body/login result/lockout은 불가 |
| A08 Software or Data Integrity Failures | Not Observable | 없음 | update, CI/CD, deserialization, integrity control 데이터 없음 |
| A09 Security Logging and Alerting Failures | Limited/Not Applicable | report quality/policy는 있으나 target alerting 평가는 아님 | 현재 프로젝트가 로그를 분석할 뿐 target의 logging/alerting failure를 판단하지 않음 |
| A10 Mishandling of Exceptional Conditions | Limited | `server_error_probe`, error/protocol context related | 단순 4xx/5xx/error는 A10 직접 증거가 아니다. response body/internal exception/failing-open 필요 |

## 13. Integration architecture 후보 비교

| 후보 | 설명 | 장점 | 단점 | Stage2 활용 | 호환성/테스트 영향 | 판단 |
| --- | --- | --- | --- | --- | --- | --- |
| A. Stage1 schema에 직접 OWASP/CWE/WSTG 필드 추가 | LLM verdict 출력에 표준 매핑 포함 | Stage1에서 즉시 사용 가능, report로 자연 전달 | prompt/schema churn, LLM nondeterminism, false-positive guardrail 훼손 위험, 기존 artifacts 영향 큼 | 가능 | schema/golden fixture/test 영향 큼 | 1차 구현으로는 비추천 |
| B. Stage1 이후 deterministic enrichment layer 추가 | `Prepare -> Stage1 -> Security Standards Enrichment -> Stage2 -> Viewer` | 기존 verdict/prompt 보존, deterministic, guardrail 표현 강제 가능, optional artifact로 backward compatible | 새 mapping rule module과 tests 필요, rules 유지보수 필요 | 가능 | optional field로 낮게 시작 가능 | 가장 적절 |
| C. Viewer payload 생성 시점에만 enrichment | viewer display adapter에서만 매핑 | 빠르고 UI 영향만 제한 | Stage2가 활용 불가, viewer에 semantic mapping 책임 집중, report와 viewer 불일치 가능 | 불가 | viewer tests 중심 | display-only prototype에는 가능하지만 장기 구조로는 약함 |

가장 작은 의미 변경과 회귀 위험을 고려하면 후보 B가 적절하다.

## 14. Artifact schema 후보

문서상 제안이며 구현하지 않는다. 현재 artifact/report/viewer 구조에는 optional field로 붙이는 방식이 안전하다.

후보 구조는 다음과 같다.

```json
{
  "standards_mapping": {
    "schema_version": "security_standards_mapping.v1",
    "source": "deterministic_stage1_enrichment",
    "observability": "attempt_observed",
    "items": [
      {
        "standard": "OWASP_TOP10",
        "id": "A05:2025",
        "name": "Injection",
        "relationship": "Direct",
        "basis": ["verdict:suspicious_sqli", "reason_hint:sqli:*"],
        "boundary_note": "Observed attack pattern != confirmed vulnerability; OWASP mapping != successful exploitation."
      },
      {
        "standard": "CWE",
        "id": "CWE-89",
        "name": "SQL Injection",
        "relationship": "Direct",
        "basis": ["verdict:suspicious_sqli", "reason_hint:sqli:*"],
        "boundary_note": "Apache logs do not confirm DB query execution or result exposure."
      },
      {
        "standard": "WSTG",
        "id": "WSTG-INPV-05",
        "name": "Testing for SQL Injection",
        "relationship": "Direct",
        "basis": ["verdict:suspicious_sqli", "reason_hint:sqli:*"],
        "boundary_note": "This is a testing scenario relation, not proof of a vulnerability."
      }
    ],
    "unmapped_reason": ""
  }
}
```

이 구조가 적합한 이유는 다음과 같다.

- standard별로 Top 10/CWE/WSTG를 같은 리스트에 담아 확장하기 쉽다.
- `relationship`을 item별로 둘 수 있어 `server_error_probe`처럼 WSTG는 Related, Top 10은 None인 사례를 표현할 수 있다.
- `basis`에 Stage1 verdict와 `reason_hints`를 남겨 deterministic rule 설명이 가능하다.
- optional field로 두면 과거 Stage1/Stage2/viewer artifact와 backward compatibility를 유지하기 쉽다.

단순히 `owasp_top10`, `cwe`, `wstg` 배열만 두는 구조는 표시에는 편하지만 item별 관계와 boundary note가 약해질 수 있다. Viewer summary용으로는 별도 normalized view를 만들 수 있다.

## 15. Viewer 표시 후보

현재 Report Viewer의 finding detail panel은 Request, Analysis Note, Interpretation Aid, Evidence, Related Contexts, Related Supporting Events를 보여준다. 향후 추가한다면 finding detail 내부의 Evidence 전후가 자연스럽다.

추천 표현:

```text
Security Standards

OWASP Top 10
A05:2025 · Injection · Direct

CWE
CWE-89 · SQL Injection · Direct

OWASP WSTG
WSTG-INPV-05 · Testing for SQL Injection · Direct

Evidence Scope
Attempt observed

Boundary
Observed attack pattern does not confirm a vulnerability or exploitation success.
```

표시명 후보 판단:

| 표현 | 판단 |
| --- | --- |
| Security Standards | 가장 무난하다. Top 10/CWE/WSTG를 모두 포괄한다 |
| Standards Mapping | 정확하지만 사용자에게 다소 내부 구현처럼 보일 수 있다 |
| OWASP-related Classification | CWE까지 포함하면 범위가 애매하다 |
| Observed OWASP Category | OWASP Top 10만 강조하고 detection처럼 오해될 수 있다 |

피해야 할 표현:

- Detected Vulnerability
- Confirmed OWASP Vulnerability
- Exploited
- Compromised

## 16. Regression risk

향후 구현 시 가장 큰 위험은 기존 false-positive guardrail 훼손이다.

| 위험 | 현재 보호 장치 | 향후 테스트 필요 |
| --- | --- | --- |
| direct sensitive path를 path traversal로 매핑 | Stage1 prompt가 `/private/secret.txt`, `/.env`, `/admin`, `/config.php` direct request만으로 traversal 금지 | direct path mapping이 A01/CWE-22로 승격되지 않는지 |
| PHP wrapper를 traversal로 흡수 | Stage1 normalization이 wrapper-only traversal verdict를 file disclosure로 교정 | `php://filter`는 file disclosure/include-like로 유지 |
| XSS external navigation false positive 재발 | XSS navigation regex가 `window.location`/`location.href` 등 JS form만 매칭하고 raw log `location="-"`는 배제 | `location="-"`, normal URL location header는 XSS mapping 없음 |
| server error를 A10로 자동 매핑 | Stage2/Viewer guardrail이 error != exploit success를 강제 | `server_error_probe` Top 10 None, WSTG-ERRH-01 Related |
| scan에 취약점 category를 부여 | probing/IP/mixed summaries context-only | `suspicious_scan` default OWASP None |
| auth 200을 login success로 오해 | auth summaries include no auth success inference | A07/CWE-307는 repeated attempts 중심으로만 |
| viewer가 mapping을 new detection처럼 표시 | viewer payload builder는 no new detection/no success inference | labels and badges guardrail |

향후 regression 후보:

| 번호 | 케이스 | 현재 유사 테스트/fixture | 부족한 부분 |
| --- | --- | --- | --- |
| 1 | plain traversal | traversal prepare/stage fixture 계열 | standards mapping Direct 확인 필요 |
| 2 | encoded traversal | prepare traversal expected fixture 계열 | CWE/WSTG basis 확인 필요 |
| 3 | double encoded traversal | lab/generated traffic와 일부 expected artifact | 별도 mapping fixture 고정 필요 |
| 4 | direct `/private/secret.txt` | observability/status-error fixtures | CWE-22 미매핑 확인 필요 |
| 5 | direct `/.env` | sensitive path/status-error tests | CWE-552는 Conditional/Related만 |
| 6 | SQLi | SQLi prepare/stage dry-run fixtures | A05/CWE-89/WSTG-INPV-05 Direct |
| 7 | XSS | XSS prepare tests/fixtures | reflected/stored 미구분 boundary |
| 8 | XSS external-navigation FP | `tests/test_prepare_xss_external_navigation.py` | mapping empty/FP 유지 확인 |
| 9 | command injection | generated lab traffic, CMDI hints | A05/CWE-78/WSTG-INPV-12 mapping fixture |
| 10 | brute force | auth behavior fixtures/tests | A07/CWE-307 조건 확인 |
| 11 | generic scanner | scanner/probing context tests | OWASP None default |
| 12 | server error probe | status-error policy tests | A10 직접 매핑 금지 |
| 13 | file disclosure traversal형 | traversal/file disclosure boundary docs/fixtures | traversal형과 wrapper형 분리 |
| 14 | PHP wrapper형 | `e_r2_php_wrapper` fixture, Stage1 normalization test | CWE-98 Conditional wording |
| 15 | `benign_normal` | Stage1 schema/viewer paths | mapping empty |
| 16 | `likely_false_positive` | educational FP fixtures | mapping empty 또는 suppressed |
| 17 | `inconclusive` | viewer/stage results | mapping empty by default |
| 18 | viewer payload backward compatibility | viewer payload builder tests | old artifacts without `standards_mapping` render safely |

## 17. 향후 구현 권장 순서

이번 작업에서는 구현하지 않는다. 조사 결과 기준의 향후 순서는 다음이 적절하다.

1. Deterministic standards mapping module 설계/구현
2. Unit tests for mapping rules and relationship/boundary labels
3. Stage2 artifact input에 optional `standards_mapping` 전달
4. Stage2 prompt/report wording에 mapping boundary만 최소 반영
5. Viewer finding detail에 `Security Standards` 섹션 추가
6. Coverage summary aggregation 추가
7. WSTG 기반 fixture 확장

## 18. 미결정 사항

- OWASP Top 10:2025의 한국어 표시명을 내부에서 번역할지, 공식 영문명을 유지할지 결정이 필요하다.
- `suspicious_file_disclosure`의 CWE 후보를 얼마나 세분화할지 결정해야 한다. 현재는 CWE-22, CWE-98, CWE-552, CWE-200이 모두 조건부 후보지만, logs-only artifact에는 과한 CWE 부여를 피하는 편이 안전하다.
- L3 hints(Log4Shell, SSRF, open redirect, SSTI, GraphQL, XXE, webshell)를 이번 1차 mapping 범위에 포함할지 별도 phase로 둘지 정해야 한다.
- Stage2가 standards mapping을 요약에 사용할지, Viewer 표시 전용으로 둘지 product decision이 필요하다.
- A09 Logging and Alerting Failures는 이 프로젝트가 분석 시스템이라는 점과 target application 평가라는 점을 분리해야 한다. per-finding mapping에는 기본적으로 부적절하다.

## 19. 결론

OWASP Top 10:2025 / CWE / WSTG 매핑은 현재 구조에 추가 가능하다. 다만 Stage1 schema/prompt에 바로 넣기보다 Stage1 이후 deterministic enrichment layer로 추가하는 것이 가장 작고 안전한 변경이다.

직접 매핑 가능한 축은 `suspicious_path_traversal`, `suspicious_sqli`, `suspicious_xss`, `suspicious_command_injection`, 반복 인증 시도 기반 `suspicious_bruteforce`이다. 조건부 또는 관련 매핑에 머물러야 하는 축은 `suspicious_file_disclosure`, `suspicious_auth_abuse`, sensitive path/forced browsing, method/protocol anomaly, server error probe, scan/recon이다. `benign_normal`, `likely_false_positive`, `inconclusive`는 기본적으로 표준 매핑을 비우는 것이 맞다.

특히 다음 두 정책은 반드시 유지해야 한다.

```text
direct sensitive path != path traversal
server_error_probe != A10 confirmed vulnerability
```

매핑은 분류 보조 정보이지 취약점 확정 정보가 아니다. UI와 report 모두 `Attempt observed`, `Related`, `Conditional`, `No success inferred` 같은 표현을 써야 한다.

## References

- OWASP Top 10:2025: https://owasp.org/Top10/
- OWASP A01:2025 Broken Access Control: https://owasp.org/Top10/2025/A01_2025-Broken_Access_Control/
- OWASP A02:2025 Security Misconfiguration: https://owasp.org/Top10/2025/A02_2025-Security_Misconfiguration/
- OWASP A05:2025 Injection: https://owasp.org/Top10/2025/A05_2025-Injection/
- OWASP A07:2025 Authentication Failures: https://owasp.org/Top10/2025/A07_2025-Authentication_Failures/
- OWASP A09:2025 Security Logging and Alerting Failures: https://owasp.org/Top10/2025/A09_2025-Security_Logging_and_Alerting_Failures/
- OWASP A10:2025 Mishandling of Exceptional Conditions: https://owasp.org/Top10/2025/A10_2025-Mishandling_of_Exceptional_Conditions/
- CWE-22: https://cwe.mitre.org/data/definitions/22.html
- CWE-79: https://cwe.mitre.org/data/definitions/79.html
- CWE-89: https://cwe.mitre.org/data/definitions/89.html
- CWE-77: https://cwe.mitre.org/data/definitions/77.html
- CWE-78: https://cwe.mitre.org/data/definitions/78.html
- CWE-98: https://cwe.mitre.org/data/definitions/98.html
- CWE-200: https://cwe.mitre.org/data/definitions/200.html
- CWE-307: https://cwe.mitre.org/data/definitions/307.html
- CWE-425: https://cwe.mitre.org/data/definitions/425.html
- CWE-552: https://cwe.mitre.org/data/definitions/552.html
- WSTG-ATHZ-01: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/05-Authorization_Testing/01-Testing_Directory_Traversal_File_Include
- WSTG-INPV-01: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/01-Testing_for_Reflected_Cross_Site_Scripting
- WSTG-INPV-02: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/02-Testing_for_Stored_Cross_Site_Scripting
- WSTG-INPV-04: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/04-Testing_for_HTTP_Parameter_Pollution
- WSTG-INPV-05: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/05-Testing_for_SQL_Injection
- WSTG-INPV-12: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/12-Testing_for_Command_Injection
- WSTG-ATHN-03: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/04-Authentication_Testing/03-Testing_for_Weak_Lock_Out_Mechanism
- WSTG-CONF-03: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing/03-Test_File_Extensions_Handling_for_Sensitive_Information
- WSTG-CONF-04: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing/04-Review_Old_Backup_and_Unreferenced_Files_for_Sensitive_Information
- WSTG-CONF-05: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing/05-Enumerate_Infrastructure_and_Application_Admin_Interfaces
- WSTG-CONF-06: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing/06-Test_HTTP_Methods
- WSTG-ERRH-01: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/08-Testing_for_Error_Handling/01-Testing_For_Improper_Error_Handling
- WSTG-INFO-06: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/01-Information_Gathering/06-Identify_Application_Entry_Points
