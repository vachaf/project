# OWASP 2025 / CWE / WSTG Deterministic Enrichment 상세 설계

기준 HEAD: `08541424bebfae0236871c2eb09d2ee42bb71c0d`  
기준 조사 문서: [`99_owasp_security_standard_mapping_investigation.md`](./99_owasp_security_standard_mapping_investigation.md)  
작성일: 2026-09-01  
범위: 상세 구현 설계만 수행한다. Python/HTML/CSS/JS, prompt, schema, test, fixture, migration, artifact 생성 로직은 변경하지 않는다.

## 1. 목적

이 문서는 현재 Apache logs-only 분석 pipeline에 OWASP Top 10:2025, CWE, OWASP WSTG 정보를 deterministic enrichment로 추가하기 위한 상세 구현 설계이다.

핵심 목적은 다음이다.

- 기존 Stage1 verdict와 Prepare evidence를 바탕으로 보안 표준 taxonomy/test scenario 정보를 추가한다.
- OWASP/CWE/WSTG ID를 LLM이 자유 생성하지 않도록 한다.
- 로그에서 관찰된 attack pattern과 실제 취약점 존재/공격 성공을 명확히 분리한다.
- 구현자가 그대로 코드로 옮길 수 있는 rule table, function contract, artifact schema, integration point, regression test specification을 고정한다.

## 2. Non-goals

이번 설계 및 1차 구현 범위의 non-goals는 다음이다.

- 새로운 공격 탐지기를 만들지 않는다.
- Prepare regex/pattern을 복제하지 않는다.
- Stage1 prompt 또는 JSON schema에 OWASP/CWE/WSTG 필드를 추가하지 않는다.
- Stage2 prompt를 이번 작업에서 수정하지 않는다.
- Viewer HTML/CSS/JS를 이번 작업에서 수정하지 않는다.
- DB migration, 새 table, 새 column을 만들지 않는다.
- old artifact를 강제로 재생성하지 않는다.
- mapping을 severity 상향, confidence 상향, incident 승격 근거로 사용하지 않는다.

## 3. 기존 조사 결과 요약

기존 조사 문서의 핵심 결론은 유지한다.

현재 pipeline은 다음 구조이다.

```text
Apache logs / DB export
-> Prepare deterministic candidate/context extraction
-> Stage1 LLM per-candidate classification
-> Security Standards Enrichment
-> Stage2 LLM incident/report synthesis
-> Viewer payload builder
-> Report Viewer
```

현재 Stage1 verdict enum은 코드 기준으로 다음 12개이다.

| Verdict | Mapping 기본 정책 |
| --- | --- |
| `benign_normal` | empty mapping |
| `likely_false_positive` | empty mapping |
| `suspicious_scan` | default empty, 특정 evidence가 있으면 WSTG Related만 허용 |
| `suspicious_bruteforce` | A07 Direct, CWE-307 Conditional, WSTG-ATHN-03 Related |
| `suspicious_sqli` | A05/CWE-89/WSTG-INPV-05 Direct |
| `suspicious_xss` | A05/CWE-79 Direct, WSTG-INPV-01 Related |
| `suspicious_path_traversal` | A01/CWE-22/WSTG-ATHZ-01 Direct |
| `suspicious_file_disclosure` | evidence decision tree |
| `suspicious_command_injection` | A05/CWE-78/WSTG-INPV-12 Direct |
| `suspicious_auth_abuse` | A07 Related 또는 Conditional, CWE/WSTG 없음 by default |
| `server_error_probe` | WSTG-ERRH-01 Related only |
| `inconclusive` | empty mapping |

현재 주요 reason/hint prefix는 조사 문서와 현재 HEAD가 일치한다.

```text
sqli: xss: traversal: cmdi: file_disclosure: sensitive_path:
dir_probe: file_probe: auth_abuse: ip_behavior: method_probe:
protocol_anomaly: observability: hpp: ua: l3: fp_hint:
context: baseline:
```

현재 HEAD에서 확인한 보정 사항은 다음이다.

- Stage1 결과는 [`src/llm_stage1_classifier.py`](../../src/llm_stage1_classifier.py)의 `main()`에서 `result_payload["results"]`로 저장된다.
- Stage1에는 `maybe_normalize_file_disclosure_verdict()`가 있으며, PHP wrapper/source disclosure 조합을 `suspicious_path_traversal`에서 `suspicious_file_disclosure`로 보수 정규화한다.
- Stage2는 [`src/llm_stage2_reporter.py`](../../src/llm_stage2_reporter.py)의 `build_report_input()` -> `build_incident_briefs()`에서 Stage1 result와 Prepare candidate evidence를 병합해 `top_incidents`를 만든다.
- Viewer payload는 [`src/viewer_payload_builder.py`](../../src/viewer_payload_builder.py)의 `select_findings_source()`와 `build_finding()`에서 `stage2_report_input.top_incidents`, `stage1_results.results`, `llm_input.analysis_candidates` 순서로 finding을 만든다.
- 현재 Viewer template은 finding detail에서 `Analysis Note`, `Interpretation Aid`, `Evidence`, `Related Contexts`, `Related Supporting Events`를 표시한다. `Security Standards`는 `Interpretation Aid` 다음, `Evidence` 앞이 가장 자연스럽다.

## 4. 설계 원칙

다음 원칙을 모든 rule, artifact, Stage2/Viewer 표현에 적용한다.

```text
Observed attack pattern != confirmed vulnerability
OWASP mapping != successful exploitation
```

다음 경계는 고정한다.

```text
direct sensitive path != path traversal
server_error_probe != A10 confirmed vulnerability
generic scan != OWASP vulnerability category
```

`Direct` 관계도 취약점 확인을 의미하지 않는다. 예를 들어 `suspicious_sqli -> CWE-89 Direct`는 SQL injection 형태의 요청이 관찰되었다는 뜻이며, 대상 애플리케이션에 CWE-89 weakness가 실제 존재한다고 확정하는 뜻이 아니다.

## 5. Standards semantics

| Standard | 의미 | 이 설계에서의 사용 |
| --- | --- | --- |
| OWASP Top 10:2025 | 상위 위험/취약점 category | 관찰된 attack pattern이 관련 category와 의미상 직접/조건부/관련되는지 표시 |
| CWE | software weakness taxonomy | 실제 weakness 존재를 확정하지 않고, logs-only evidence로 연결 가능한 weakness 후보를 보수적으로 표시 |
| OWASP WSTG | 보안 테스트 방법/test scenario | vulnerability relation이 아니라 관련 test scenario relation으로 표시 |

Viewer와 Stage2에서는 WSTG를 `Related WSTG Test` 또는 `WSTG Test Scenario`로 표시한다. WSTG ID를 취약점 category처럼 보이게 만들지 않는다.

## 6. Relationship semantics

relationship enum은 소문자 snake_case를 artifact canonical value로 사용한다.

| Enum | Display | 의미 | 예 |
| --- | --- | --- | --- |
| `direct` | Direct | 관찰한 attack pattern과 taxonomy/test scenario 사이에 직접적인 의미 대응이 있다. 취약점 확인이나 exploit 성공을 뜻하지 않는다. | `suspicious_sqli -> CWE-89` |
| `conditional` | Conditional | 추가 evidence가 있다면 해당 weakness/category에 연결할 수 있지만 현재 logs-only evidence만으로는 확정할 수 없다. | `/.env request -> CWE-552` |
| `related` | Related | 관련 공격/테스트/조사 시나리오이지만 vulnerability taxonomy를 직접 부여하면 과장될 수 있다. | `server_error_probe -> WSTG-ERRH-01` |
| `none` | None | 표준 매핑을 부여하지 않는다. artifact `items`에는 저장하지 않는다. | `benign_normal` |

`none`은 내부 rule evaluation 결과나 설계 표기용으로만 사용하고, artifact item으로 생성하지 않는다.

## 7. Observability semantics

observability enum은 소문자 snake_case를 사용한다.

| Enum | 의미 |
| --- | --- |
| `attempt_only` | 요청 payload/path/method에서 공격 시도 형태는 관찰되지만 interpreter 실행, 파일 반환, 브라우저 실행, 권한 우회 성공은 확인되지 않는다. |
| `behavior_only` | 반복, sequence, status 분포, scan/recon/auth behavior 같은 행동 패턴은 관찰되지만 구체 weakness/exploit 성공은 확인되지 않는다. |
| `partial` | logs-only 범위에서 일부 결과 정황이 보조적으로 관찰되지만 취약점/성공 확정에는 부족하다. 1차 rule에서는 보수적으로 거의 사용하지 않는다. |
| `not_applicable` | 보안 표준 매핑이 없거나 정상/FP/inconclusive라 observability scope를 적용하지 않는다. |

기본 verdict별 observability는 다음이다.

| Verdict | Observability |
| --- | --- |
| `suspicious_path_traversal` | `attempt_only` |
| `suspicious_sqli` | `attempt_only` |
| `suspicious_xss` | `attempt_only` |
| `suspicious_command_injection` | `attempt_only` |
| `suspicious_file_disclosure` | `attempt_only` |
| `suspicious_bruteforce` | `behavior_only` |
| `suspicious_auth_abuse` | `behavior_only` |
| `suspicious_scan` | `behavior_only` |
| `server_error_probe` | `behavior_only` |
| `benign_normal` | `not_applicable` |
| `likely_false_positive` | `not_applicable` |
| `inconclusive` | `not_applicable` |
| unknown future verdict | `not_applicable` |

## 8. Deterministic rule evaluation order

Rule evaluation은 first-match가 아니라 additive evaluation이다. 단, suppression과 branch priority는 고정한다.

1. Input normalization: verdict, verdict_hint, reason_hints, method, uri, query_string, raw_request_target, status_code를 읽는다.
2. Suppression: `benign_normal`, `likely_false_positive`, `inconclusive`, unknown verdict는 empty mapping을 반환한다. `fp_hint:*`, `context:educational_*`, `context:natural_language_query`가 있고 final verdict가 `likely_false_positive`이면 모든 mapping을 suppress한다.
3. Stage1 verdict primary rules: SQLi, XSS, path traversal, command injection, brute force, auth abuse, server error, scan을 verdict 기준으로 평가한다.
4. `suspicious_file_disclosure` decision tree: explicit traversal -> PHP wrapper/include-like -> direct sensitive file -> weak/ambiguous 순서로 평가한다.
5. Evidence-combination rules: final verdict가 보안 의심 계열일 때만 `sensitive_path:*`, `dir_probe:*`, `file_probe:*`, `file_disclosure:sensitive_resource:*`, `method_probe:*`, `protocol_anomaly:*`, `hpp:*`의 보조 mapping을 추가할 수 있다.
6. Sensitive/admin evidence-combination rules는 raw `uri`, `query_string`, `raw_request_target` 문자열을 새 탐지 근거로 사용하지 않는다. Standards mapping layer는 `secret`, `passwd`, `/admin` 같은 문자열을 직접 검사해 새로운 sensitive-path/admin detector가 되면 안 된다.
7. Duplicate removal: `(standard, id)` 기준으로 중복 제거한다. 동일 standard/id가 여러 relationship으로 생성되면 `direct > conditional > related` precedence를 적용하고, stronger relationship item의 `rule_id`, `basis`, `boundary_note`를 유지한다.
8. Stable ordering: OWASP_TOP10, CWE, WSTG 순서와 rule id lexical order를 함께 사용한다.
9. Empty normalization: item이 없으면 `items: []`, `observability: not_applicable` 또는 verdict별 behavior scope, `unmapped_reason`을 채운다.

## 9. Full mapping rule table

| Rule ID | Stage1 verdict | Required evidence | Suppression evidence | Standard | Standard ID | Relationship | Observability | Boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STD-MAP-TRAVERSAL-001 | `suspicious_path_traversal` | final verdict only, and Stage1 guardrail already requires explicit directory escape | `likely_false_positive`, no final traversal verdict | OWASP_TOP10 | `A01:2025` | `direct` | `attempt_only` | Direct sensitive path is not traversal; no file read/access-control bypass success inferred. |
| STD-MAP-TRAVERSAL-002 | `suspicious_path_traversal` | final verdict or `traversal:*` in file disclosure branch | same as above | CWE | `CWE-22` | `direct` | `attempt_only` | CWE weakness is not confirmed; only traversal-like request pattern observed. |
| STD-MAP-TRAVERSAL-003 | `suspicious_path_traversal` | final verdict or `traversal:*` in file disclosure branch | same as above | WSTG | `WSTG-ATHZ-01` | `direct` | `attempt_only` | Test scenario relation; file include/read success not confirmed. |
| STD-MAP-SQLI-001 | `suspicious_sqli` | final verdict | `likely_false_positive`, `fp_hint:sql_keyword_without_attack_structure` with non-SQLi final verdict | OWASP_TOP10 | `A05:2025` | `direct` | `attempt_only` | DB query execution/result/schema/data exposure unknown. |
| STD-MAP-SQLI-002 | `suspicious_sqli` | final verdict | same as above | CWE | `CWE-89` | `direct` | `attempt_only` | SQLi weakness not confirmed. |
| STD-MAP-SQLI-003 | `suspicious_sqli` | final verdict | same as above | WSTG | `WSTG-INPV-05` | `direct` | `attempt_only` | SQLi test scenario relation only. |
| STD-MAP-XSS-001 | `suspicious_xss` | final verdict | `likely_false_positive`, educational XSS final FP | OWASP_TOP10 | `A05:2025` | `direct` | `attempt_only` | Reflection/stored persistence/browser execution unknown. |
| STD-MAP-XSS-002 | `suspicious_xss` | final verdict | same as above | CWE | `CWE-79` | `direct` | `attempt_only` | XSS weakness not confirmed. |
| STD-MAP-XSS-003 | `suspicious_xss` | final verdict and URI/query/logged input payload context | `location="-"` external-navigation FP handled before Stage1 | WSTG | `WSTG-INPV-01` | `related` | `attempt_only` | Reflected XSS test relation; response reflection/browser execution unknown. |
| STD-MAP-CMDI-001 | `suspicious_command_injection` | final verdict | `likely_false_positive` | OWASP_TOP10 | `A05:2025` | `direct` | `attempt_only` | Shell invocation/command execution/process creation unknown. |
| STD-MAP-CMDI-002 | `suspicious_command_injection` | final verdict | same as above | CWE | `CWE-78` | `direct` | `attempt_only` | Use CWE-78 as default because current verdict means OS command injection-like token. |
| STD-MAP-CMDI-003 | `suspicious_command_injection` | final verdict | same as above | WSTG | `WSTG-INPV-12` | `direct` | `attempt_only` | Command injection test scenario relation only. |
| STD-MAP-BRUTE-001 | `suspicious_bruteforce` | final verdict | no repeated auth behavior and non-bruteforce final verdict | OWASP_TOP10 | `A07:2025` | `direct` | `behavior_only` | Authentication attack behavior observed; login success/lockout absence unknown. |
| STD-MAP-BRUTE-002 | `suspicious_bruteforce` | final verdict plus `auth_abuse:repeated_*` or `auth_abuse:rapid_fail_burst` preferred | single auth request only | CWE | `CWE-307` | `conditional` | `behavior_only` | Excessive-auth-attempt restriction weakness not confirmed. |
| STD-MAP-BRUTE-003 | `suspicious_bruteforce` | final verdict plus repeated auth evidence preferred | single auth request only | WSTG | `WSTG-ATHN-03` | `related` | `behavior_only` | Weak lockout test scenario relation; lockout/CAPTCHA/rate limit not observed. |
| STD-MAP-AUTH-001 | `suspicious_auth_abuse` | final broad auth abuse verdict without repeated auth evidence | final `suspicious_bruteforce` already uses brute rules; repeated auth evidence uses STD-MAP-AUTH-002 instead | OWASP_TOP10 | `A07:2025` | `related` | `behavior_only` | Broad auth abuse, not proof of authentication control failure. |
| STD-MAP-AUTH-002 | `suspicious_auth_abuse` | `auth_abuse:repeated_*` or `auth_abuse:rapid_fail_burst` | single 200/401 or endpoint touch only | OWASP_TOP10 | `A07:2025` | `conditional` | `behavior_only` | Stronger repeated evidence exists, but credential success/lockout unknown. This replaces A07 related in the final artifact. |
| STD-MAP-AUTH-003 | `suspicious_auth_abuse` | repeated auth evidence | single 200/401 or endpoint touch only | CWE | `CWE-307` | `conditional` | `behavior_only` | Never Direct for current logs-only auth abuse. |
| STD-MAP-FILE-TRAV-001 | `suspicious_file_disclosure` | `traversal:*` or existing explicit traversal evidence | none | OWASP_TOP10 | `A01:2025` | `direct` | `attempt_only` | File disclosure verdict with directory escape evidence; file read still unknown. |
| STD-MAP-FILE-TRAV-002 | `suspicious_file_disclosure` | same as above | none | CWE | `CWE-22` | `direct` | `attempt_only` | Only if explicit traversal evidence exists. |
| STD-MAP-FILE-TRAV-003 | `suspicious_file_disclosure` | same as above | none | WSTG | `WSTG-ATHZ-01` | `direct` | `attempt_only` | Directory traversal/file include test scenario relation. |
| STD-MAP-FILE-PHP-001 | `suspicious_file_disclosure` | `file_disclosure:php_filter_wrapper` or `file_disclosure:base64_source_intent` and `file_disclosure:resource_parameter` | explicit traversal branch already matched | OWASP_TOP10 | `A05:2025` | `related` | `attempt_only` | PHP wrapper/source disclosure attempt; include/require behavior unknown. |
| STD-MAP-FILE-PHP-002 | `suspicious_file_disclosure` | same as above | same as above | CWE | `CWE-98` | `conditional` | `attempt_only` | PHP file include weakness requires application include/require behavior evidence. |
| STD-MAP-FILE-PHP-003 | `suspicious_file_disclosure` | same as above | same as above | WSTG | `WSTG-ATHZ-01` | `related` | `attempt_only` | LFI/source disclosure test scenario relation, not confirmed inclusion. |
| STD-MAP-FILE-DIRECT-001 | `suspicious_file_disclosure` | `file_disclosure:sensitive_resource:*` or `sensitive_path:*` direct file/config/backup path | `traversal:*`, PHP wrapper branch | OWASP_TOP10 | `A02:2025` | `related` | `attempt_only` | Direct sensitive file probe; actual exposure/config state unknown. |
| STD-MAP-FILE-DIRECT-002 | `suspicious_file_disclosure` | direct sensitive file/config/backup path | traversal/PHP wrapper branch | CWE | `CWE-552` | `conditional` | `attempt_only` | External accessibility/content exposure not confirmed. |
| STD-MAP-FILE-DIRECT-003 | `suspicious_file_disclosure` | config extension or backup/unreferenced path evidence | traversal/PHP wrapper branch | WSTG | `WSTG-CONF-04` | `related` | `attempt_only` | Backup/unreferenced sensitive file review scenario. |
| STD-MAP-FILE-DIRECT-004 | `suspicious_file_disclosure` | extension/config path evidence | traversal/PHP wrapper branch | WSTG | `WSTG-CONF-03` | `related` | `attempt_only` | File extension handling scenario; content exposure unknown. |
| STD-MAP-SENSITIVE-001 | security suspicious final verdict | `sensitive_path:admin*`, `dir_probe:admin*`, or `file_probe:admin*` Prepare evidence | non-security final verdict; raw `/admin` string only | OWASP_TOP10 | `A01:2025` | `related` | verdict-derived | Forced browsing/admin enumeration context only. |
| STD-MAP-SENSITIVE-002 | security suspicious final verdict | `sensitive_path:admin*`, `dir_probe:admin*`, or `file_probe:admin*` Prepare evidence | non-security final verdict; raw `/admin` string only | CWE | `CWE-425` | `conditional` | verdict-derived | Direct request weakness requires access-control result evidence. |
| STD-MAP-SENSITIVE-003 | security suspicious final verdict | `sensitive_path:*`, `file_probe:*`, or `file_disclosure:sensitive_resource:*` Prepare evidence for sensitive file/config/backup probing | non-security final verdict; raw `secret`/`passwd`/config-like string only | CWE | `CWE-552` | `conditional` | verdict-derived | File accessibility not confirmed. |
| STD-MAP-SENSITIVE-004 | security suspicious final verdict | `sensitive_path:admin*`, `dir_probe:admin*`, or `file_probe:admin*` Prepare evidence | non-security final verdict; raw `/admin` string only | WSTG | `WSTG-CONF-05` | `related` | verdict-derived | Admin interface enumeration test scenario. |
| STD-MAP-SENSITIVE-005 | security suspicious final verdict | `sensitive_path:*`, `file_probe:*`, or `file_disclosure:sensitive_resource:*` Prepare evidence for backup/config/direct file probing | non-security final verdict; raw `secret`/`passwd`/config-like string only | WSTG | `WSTG-CONF-04` | `related` | verdict-derived | Backup/unreferenced file review scenario. |
| STD-MAP-METHOD-001 | security suspicious final verdict | `method_probe:*` | non-security final verdict | WSTG | `WSTG-CONF-06` | `related` | `behavior_only` | Method allowed/state change/bypass unknown. |
| STD-MAP-PROTOCOL-001 | security suspicious final verdict | `protocol_anomaly:*` | non-security final verdict | WSTG | `WSTG-ERRH-01` | `related` | `behavior_only` | Protocol anomaly may relate to error handling; no A02/A10 by default. |
| STD-MAP-HPP-001 | security suspicious final verdict | `hpp:duplicate_param_names` | non-security final verdict | WSTG | `WSTG-INPV-04` | `related` | `attempt_only` | App-specific parameter parsing unknown. |
| STD-MAP-ERROR-001 | `server_error_probe` | final verdict | none | WSTG | `WSTG-ERRH-01` | `related` | `behavior_only` | Error probe is not A10; stack trace/internal state/fail-open unknown. |
| STD-MAP-SCAN-001 | `suspicious_scan` | `sensitive_path:admin*`, `dir_probe:admin*`, or `file_probe:admin*` Prepare evidence | generic scan without specific evidence; raw `/admin` string only | WSTG | `WSTG-CONF-05` | `related` | `behavior_only` | Scan behavior itself is not vulnerability category. |
| STD-MAP-SCAN-002 | `suspicious_scan` | dir/file probing evidence | generic scan without specific evidence | WSTG | `WSTG-INFO-06` | `related` | `behavior_only` | Entry-point discovery scenario, not weakness. |
| STD-MAP-NONSEC-001 | `benign_normal` | final verdict | none | none | none | `none` | `not_applicable` | Empty mapping. |
| STD-MAP-NONSEC-002 | `likely_false_positive` | final verdict | none | none | none | `none` | `not_applicable` | Empty mapping, even if raw hints contain attack-looking strings. |
| STD-MAP-NONSEC-003 | `inconclusive` | final verdict | none | none | none | `none` | `not_applicable` | Empty mapping by default. |
| STD-MAP-UNKNOWN-001 | unknown | verdict not in known enum | none | none | none | `none` | `not_applicable` | Fail open with empty mapping and explicit unmapped reason. |

`verdict-derived` observability means `attempt_only` for payload-style final verdicts and `behavior_only` for scan/auth/error final verdicts.

## 10. Path Traversal rules

기본 조건은 다음이다.

```text
stage1 verdict == suspicious_path_traversal
```

현재 Stage1 prompt와 Prepare guardrail이 explicit directory escape evidence를 요구하므로 mapping layer는 traversal 재탐지 regex를 구현하지 않는다. 기본적으로 final verdict를 신뢰한다. 다만 `suspicious_file_disclosure` branch에서 traversal mapping을 추가할 때는 기존 `traversal:*` reason hint가 있어야 한다.

기본 mapping:

- OWASP_TOP10 `A01:2025` Broken Access Control, `direct`
- CWE `CWE-22` Path Traversal, `direct`
- WSTG `WSTG-ATHZ-01` Testing Directory Traversal File Include, `direct`

boundary:

- direct sensitive path는 traversal이 아니다.
- `/private/secret.txt`, `/.env`, `/admin`, `/config.php` 단독 요청은 CWE-22로 매핑하지 않는다.
- status 200, response bytes, content type만으로 파일 읽기 성공을 추론하지 않는다.
- 명시적인 `traversal:*` evidence가 별도로 있으면 direct sensitive path와 결합되어 traversal branch로 갈 수 있다.

## 11. SQLi rules

조건:

```text
stage1 verdict == suspicious_sqli
```

기본 mapping:

- OWASP_TOP10 `A05:2025` Injection, `direct`
- CWE `CWE-89` SQL Injection, `direct`
- WSTG `WSTG-INPV-05` Testing for SQL Injection, `direct`

boundary:

- DB query execution 확인 불가
- DB result/schema/data exposure 확인 불가
- time delay가 있더라도 DB 함수 실행 성공으로 단정하지 않음
- final verdict가 `likely_false_positive`이면 `sqli:*` hint가 있어도 mapping 없음

## 12. XSS rules

조건:

```text
stage1 verdict == suspicious_xss
```

기본 mapping:

- OWASP_TOP10 `A05:2025` Injection, `direct`
- CWE `CWE-79` Cross-site Scripting, `direct`
- WSTG `WSTG-INPV-01` Testing for Reflected Cross Site Scripting, `related`

WSTG-INPV-01을 `related`로 두는 이유:

- 현재 Apache logs-only 구조에서는 response reflection 확인이 없다.
- stored persistence 확인이 없다.
- browser execution 확인이 없다.
- cookie/session theft 확인이 없다.
- URI/query 입력 위치의 XSS-like payload는 reflected XSS 테스트 시나리오와 관련 있지만 취약점 확정이 아니다.

`WSTG-INPV-02` Stored XSS는 1차 기본 mapping에서 자동 부여하지 않는다. stored 여부는 서버 저장/후속 rendering evidence가 있어야 하며 현재 artifact에는 없다.

기존 `location="-"` external navigation false-positive guardrail은 Stage1/Prepare에서 유지한다. mapping layer는 XSS 재탐지 regex를 만들지 않고 final `suspicious_xss` verdict만 사용한다.

## 13. Command Injection rules

조건:

```text
stage1 verdict == suspicious_command_injection
```

기본 mapping:

- OWASP_TOP10 `A05:2025` Injection, `direct`
- CWE `CWE-78` OS Command Injection, `direct`
- WSTG `WSTG-INPV-12` Testing for Command Injection, `direct`

CWE-77은 1차 기본 mapping에서 사용하지 않는다. 현재 verdict semantics와 `cmdi:*` hints는 pipe, semicolon, subshell-like command separator처럼 OS command injection attempt로 충분히 좁혀져 있으므로 CWE-78을 기본값으로 둔다. 향후 non-OS command language/control interpreter injection verdict가 생기면 CWE-77을 conditional 후보로 재검토한다.

boundary:

- shell invocation 불명
- command execution 불명
- process creation 불명
- compromise 불명

## 14. Brute Force/Auth Abuse rules

### Brute force

조건:

```text
stage1 verdict == suspicious_bruteforce
```

기본 mapping:

- OWASP_TOP10 `A07:2025` Authentication Failures, `direct`
- CWE `CWE-307` Improper Restriction of Excessive Authentication Attempts, `conditional`
- WSTG `WSTG-ATHN-03` Testing for Weak Lock Out Mechanism, `related`

CWE-307을 `direct`로 두지 않는 이유:

- 반복 인증 시도는 관찰 가능하지만 excessive attempts 제한 부재는 확인할 수 없다.
- lockout 존재 여부를 알 수 없다.
- CAPTCHA/rate limit 존재 여부를 알 수 없다.
- credential guess 성공 여부를 알 수 없다.

WSTG-ATHN-03도 실제 weak lockout mechanism 확인이 아니라 관련 테스트 시나리오다. 따라서 1차 기본값은 `related`이다.

### Authentication abuse

`suspicious_auth_abuse`는 broad verdict이므로 하나의 CWE/WSTG로 고정하지 않는다.

기본 mapping:

- OWASP_TOP10 `A07:2025`, `related`
- CWE 없음
- WSTG 없음

다음 evidence가 있을 때만 보조 rule을 추가한다.

- `auth_abuse:repeated_auth_endpoint`
- `auth_abuse:repeated_401`
- `auth_abuse:rapid_fail_burst`
- short-window auth sequence

이 경우 최종 artifact는 다음만 저장한다.

- OWASP_TOP10 `A07:2025`, `conditional`
- CWE `CWE-307`, `conditional`

이때 A07 `related`와 A07 `conditional`을 동시에 저장하지 않는다. 동일 `(standard, id)`에 여러 relationship이 생성되면 `direct > conditional > related` precedence에 따라 stronger relationship item만 남긴다. 따라서 repeated auth evidence가 있으면 A07 `conditional` item의 `rule_id`, `basis`, `boundary_note`를 유지한다.

CWE-307은 이 경우에도 `conditional`을 유지한다. 단일 200/401 status나 auth endpoint 접근만으로 CWE-307을 생성하지 않는다.

## 15. File Disclosure decision tree

`suspicious_file_disclosure`는 static mapping을 만들지 않고 evidence decision tree로 평가한다.

Priority는 다음 순서로 고정한다.

1. Branch A: explicit traversal evidence
2. Branch B: PHP wrapper / include-like evidence
3. Branch C: direct sensitive file request
4. Branch D: weak/ambiguous file probe

### Branch A: explicit traversal evidence

Required evidence:

- `traversal:*`
- 또는 현재 Prepare/Stage1에서 이미 산출한 explicit directory escape evidence

Mapping:

- OWASP_TOP10 `A01:2025`, `direct`
- CWE `CWE-22`, `direct`
- WSTG `WSTG-ATHZ-01`, `direct`

Boundary:

- Stage1 final verdict가 `suspicious_file_disclosure`인 이유가 PHP wrapper normalization인지 확인한다.
- `traversal:*`가 없으면 direct sensitive file request를 traversal로 승격하지 않는다.

### Branch B: PHP wrapper / include-like evidence

Required evidence:

- `file_disclosure:php_filter_wrapper`
- `file_disclosure:base64_source_intent`
- `file_disclosure:resource_parameter`
- `encoding:url_decoded_php_wrapper` 또는 `encoding:double_decoded_php_wrapper`는 보조 basis

Mapping:

- OWASP_TOP10 `A05:2025`, `related`
- CWE `CWE-98`, `conditional`
- WSTG `WSTG-ATHZ-01`, `related`

Boundary:

- 대상 PHP 코드가 `include` / `require`를 실제 호출하는지 알 수 없다.
- source/config disclosure 시도는 관찰되지만 파일 내용 반환 성공은 알 수 없다.
- CWE-98은 Direct로 두지 않는다.

### Branch C: direct sensitive file request

Required evidence:

- `file_disclosure:sensitive_resource:*`
- `sensitive_path:*`
- backup/config/direct sensitive file probing에 해당하는 기존 Prepare evidence

Mapping:

- CWE-22 없음
- OWASP_TOP10 `A02:2025` Security Misconfiguration, `related`
- CWE `CWE-552`, `conditional`
- WSTG `WSTG-CONF-04`, `related`
- evidence가 file extension/config handling에 가까우면 WSTG `WSTG-CONF-03`, `related`

`CWE-200`은 actual exposure evidence 없이는 생성하지 않는다.

Phase 1.1 보정:

- `suspicious_file_disclosure` Branch C에서도 raw `uri`, `query_string`, `raw_request_target` 문자열 fallback을 우선하지 않는다.
- 실제 pipeline에서는 Prepare가 `file_disclosure:sensitive_resource:*` 또는 `sensitive_path:*` reason hint를 전달하므로, mapping layer는 그 evidence를 신뢰한다.
- raw `secret`, `passwd`, `/.env`, `/config.php` 같은 문자열 검사는 Prepare의 책임이며 standards mapping layer의 책임이 아니다.

### Branch D: weak/ambiguous file probe

충분한 evidence가 없으면 empty mapping 또는 WSTG Related 최소 매핑만 허용한다. 기본은 empty mapping이다.

## 16. Sensitive Path rules

`sensitive_path:*`, `dir_probe:*`, `file_probe:*`는 Stage1 verdict가 아니라 Prepare evidence이다. 이 evidence만으로 standalone standards mapping을 생성하지 않는다.

기본 정책:

```text
Stage1 final verdict + Prepare evidence
```

둘을 함께 사용한다. Prepare hint 단독으로 새 finding이나 standards mapping item을 만들지 않는다.

허용 후보:

- OWASP_TOP10 `A01:2025`, `related`
- OWASP_TOP10 `A02:2025`, `related`
- CWE `CWE-425`, `conditional`
- CWE `CWE-552`, `conditional`
- WSTG `WSTG-CONF-04`, `related`
- WSTG `WSTG-CONF-05`, `related`

실제 접근 가능/노출 여부는 추론하지 않는다.

Phase 1.1 evidence policy:

- cross-category standards mapping에서는 raw `uri`, `query_string`, `raw_request_target`의 `secret`, `passwd`, `/admin`, `/wp-admin`, `/administrator` 같은 문자열을 새 근거로 사용하지 않는다.
- 다음 Prepare evidence family가 있을 때만 sensitive/admin related mapping을 추가한다.
  - `sensitive_path:*`
  - `dir_probe:*`
  - `file_probe:*`
  - `file_disclosure:sensitive_resource:*`
- 따라서 `suspicious_sqli`의 `q=UNION SELECT secret FROM users` 또는 `q=UNION SELECT passwd FROM users`는 SQLi mapping만 가진다.
- `suspicious_xss`의 `next=/admin`도 `sensitive_path:*`, `dir_probe:*`, `file_probe:*` evidence가 없으면 admin enumeration mapping을 가지지 않는다.

이 정책의 요약은 다음이다.

```text
standards mapping != new detector
```

Standards mapping layer는 Prepare detection logic을 복제하지 않는다.

## 17. Method/Protocol rules

### Method anomaly

`method_probe:*`는 context/reason 계열이고 직접 verdict가 아니다.

기본 mapping:

- WSTG `WSTG-CONF-06`, `related`
- OWASP Top 10 없음
- CWE 없음

다음 evidence가 추가로 존재하지 않는 한 A01/A02를 자동 부여하지 않는다.

- method가 실제 허용됨
- state change 발생
- authorization bypass 발생

현재 Apache logs-only artifact에서는 이러한 evidence를 안정적으로 확보할 수 없으므로 Top 10 None이 기본이다.

### Protocol anomaly

`protocol_anomaly:*` 기본 정책:

- OWASP Top 10 없음
- CWE 없음
- WSTG는 `WSTG-ERRH-01` Related만 제한적으로 허용

단순 HTTP/1.0, malformed request, odd Host, missing Host, unusual protocol만으로 Security Misconfiguration 또는 A10을 부여하지 않는다.

## 18. Server Error rules

조건:

```text
stage1 verdict == server_error_probe
```

기본 mapping:

- OWASP Top 10 없음
- CWE 없음
- WSTG `WSTG-ERRH-01`, `related`

`A10:2025 Mishandling of Exceptional Conditions`는 자동 생성하지 않는다.

A10 매핑을 향후 고려할 최소 추가 evidence:

- fail-open behavior
- security check bypass after exception
- clearly exposed internal exception state
- exception handling 때문에 security decision이 변경됨
- response body에 stack trace/internal secret/error detail이 명확히 노출됨

현재 Apache access/error logs-only 구조에서는 위 evidence를 안정적으로 확보할 수 없으므로 1차 구현 범위에서는 A10 rule을 만들지 않는다.

## 19. Scan/Recon rules

조건:

```text
stage1 verdict == suspicious_scan
```

기본 mapping:

- OWASP Top 10 없음
- CWE 없음
- WSTG 없음

단, evidence에 특정 테스트 시나리오가 있으면 WSTG Related를 추가할 수 있다.

예:

- sensitive admin path enumeration -> `WSTG-CONF-05`, `related`
- broad entry point discovery -> `WSTG-INFO-06`, `related`

scan이라는 행동 자체에 취약점 category를 부여하지 않는다.

## 20. Non-security verdict rules

다음 verdict는 기본적으로 standards mapping을 비운다.

- `benign_normal`
- `likely_false_positive`
- `inconclusive`
- unknown future verdict

schema 표현 후보 비교:

| 후보 | 형태 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- | --- |
| A | `"standards_mapping": null` | 작다 | downstream null-check가 반복되고 unmapped reason 표현이 약함 | 비추천 |
| B | `"standards_mapping": {"items": [], "unmapped_reason": "..."}` | downstream 단순, old/new distinction 가능, empty reason 명시 가능 | artifact가 조금 커짐 | 추천 |
| C | field 없음 | old artifact와 동일 | enrichment 실행 여부를 알기 어렵고 Viewer/Stage2 분기가 불명확 | old artifact compatibility용 only |

권장안은 B이다. old artifact에 field가 없으면 C로 읽되, 새 artifact는 항상 B 형태를 쓴다.

## 21. Function contract

추천 module path:

```text
src/security_standards_mapping.py
```

추천 public function:

```python
def build_security_standards_mapping(
    stage1_result: Mapping[str, Any],
    candidate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ...
```

계약:

| 항목 | 결정 |
| --- | --- |
| 함수 성격 | pure deterministic function |
| LLM/API/network dependency | 없음 |
| DB dependency | 없음 |
| filesystem dependency | 없음 |
| input 최소 필드 | `verdict`, `reason_hints`, `verdict_hint`, `uri`, `query_string`, `raw_request_target`, `method`, `status_code` |
| candidate 사용 | Stage1 result에 없는 Prepare evidence 보강용 optional input |
| output | `standards_mapping` dict |
| invalid input | dict-like가 아니어도 empty mapping 반환. 예외를 pipeline 밖으로 전파하지 않음 |
| unknown verdict | empty mapping + `unmapped_reason: "unknown_verdict"` |
| duplicate 제거 | `(standard, id)` 기준. relationship precedence는 `direct > conditional > related` |
| stable ordering | `standard_order`, rule id 순 |
| raw reason_hints 처리 | exact raw hint는 저장하지 않고 canonical basis token으로 변환 |

동일 `(standard, id)` 충돌 처리:

- 더 강한 relationship item을 유지한다.
- precedence가 같으면 더 이른 stable rule order의 item을 유지한다.
- 최종 artifact에는 선택된 item의 `rule_id`, `basis`, `boundary_note`가 그대로 남는다.
- 예: repeated `suspicious_auth_abuse`는 A07 `related`와 A07 `conditional`을 동시에 저장하지 않고 A07 `conditional`만 저장한다.

권장 helper:

```python
def get_security_standards_mapping_schema_version() -> str:
    return "security_standards_mapping.v1"
```

실패 정책:

- mapping function 내부 예외는 구현 시 catch하여 empty mapping with `unmapped_reason: "mapping_error"`로 변환한다.
- standards enrichment failure 때문에 원래 Stage1 classification을 무효화하지 않는다.
- pipeline command exit code를 실패로 만들지 않는다. 필요하면 Stage1 meta warnings에만 기록한다.

## 22. Rule representation

비교:

| 방식 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| Python constant table | 가장 단순, review 쉬움, 별도 parser 없음 | 타입 안정성은 약함 | 1차 추천 |
| dataclass 기반 rule definitions | IDE/type hint 좋음, 구조 명확 | 초기 코드가 길어짐 | Phase 2에서 필요 시 |
| JSON/YAML external registry | 비개발자 수정 가능, configurable | parser/validation/배포 복잡도 증가, 현재 규모에 과함 | 비추천 |

1차 구현은 Python constant table과 작은 helper function 조합을 추천한다.

예상 구조:

```python
STANDARD_NAMES = {...}
RELATIONSHIP_DISPLAY = {...}
OBSERVABILITY_BY_VERDICT = {...}
RULE_ORDER = [...]
```

불필요하게 configurable framework를 만들지 않는다.

## 23. Artifact schema

새 Stage1 result row에 optional field로 추가한다.

```json
{
  "standards_mapping": {
    "schema_version": "security_standards_mapping.v1",
    "source": "deterministic_stage1_enrichment",
    "observability": "attempt_only",
    "items": [
      {
        "rule_id": "STD-MAP-SQLI-002",
        "standard": "CWE",
        "id": "CWE-89",
        "name": "SQL Injection",
        "relationship": "direct",
        "basis": [
          "stage1_verdict:suspicious_sqli",
          "prepare_hint_family:sqli"
        ],
        "boundary_note": "Apache logs do not confirm DB query execution, DB results, schema exposure, or data exposure."
      }
    ],
    "unmapped_reason": ""
  }
}
```

세부 결정:

| 항목 | 결정 |
| --- | --- |
| field names | snake_case |
| relationship enum casing | artifact는 lowercase snake_case, Viewer display는 Title Case |
| observability enum casing | lowercase snake_case |
| `basis` raw reason hint 저장 | 저장하지 않음. canonical basis token 저장 |
| wildcard 저장 | `prepare_hint_family:sqli`처럼 stable token 사용 |
| `boundary_note` 위치 | item별 boundary를 기본으로 두고, Viewer에서 공통 boundary도 추가 표시 |
| standard display name | artifact에 저장. Viewer는 모르는 ID도 표시 가능해야 함 |
| `schema_version` | 필요 |
| `source` | 필요 |
| `unmapped_reason` | item empty일 때 필요. mapped면 empty string |
| old artifact field 없음 | enrichment not available로 취급하고 표시 생략 |

표준명 canonical 후보:

| Standard | ID | Name |
| --- | --- | --- |
| OWASP_TOP10 | `A01:2025` | Broken Access Control |
| OWASP_TOP10 | `A02:2025` | Security Misconfiguration |
| OWASP_TOP10 | `A05:2025` | Injection |
| OWASP_TOP10 | `A07:2025` | Authentication Failures |
| CWE | `CWE-22` | Path Traversal |
| CWE | `CWE-78` | OS Command Injection |
| CWE | `CWE-79` | Cross-site Scripting |
| CWE | `CWE-89` | SQL Injection |
| CWE | `CWE-98` | PHP Remote File Inclusion |
| CWE | `CWE-307` | Improper Restriction of Excessive Authentication Attempts |
| CWE | `CWE-425` | Direct Request |
| CWE | `CWE-552` | Files or Directories Accessible to External Parties |
| WSTG | `WSTG-ATHZ-01` | Testing Directory Traversal File Include |
| WSTG | `WSTG-ATHN-03` | Testing for Weak Lock Out Mechanism |
| WSTG | `WSTG-INPV-01` | Testing for Reflected Cross Site Scripting |
| WSTG | `WSTG-INPV-04` | Testing for HTTP Parameter Pollution |
| WSTG | `WSTG-INPV-05` | Testing for SQL Injection |
| WSTG | `WSTG-INPV-12` | Testing for Command Injection |
| WSTG | `WSTG-CONF-03` | Test File Extensions Handling for Sensitive Information |
| WSTG | `WSTG-CONF-04` | Review Old Backup and Unreferenced Files for Sensitive Information |
| WSTG | `WSTG-CONF-05` | Enumerate Infrastructure and Application Admin Interfaces |
| WSTG | `WSTG-CONF-06` | Test HTTP Methods |
| WSTG | `WSTG-ERRH-01` | Testing for Improper Error Handling |
| WSTG | `WSTG-INFO-06` | Identify Application Entry Points |

## 24. Basis 정보 노출 정책

두 후보를 비교한다.

| 후보 | 예 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- | --- |
| A raw basis | `reason_hint:sqli:boolean_true_condition` | debugging이 쉽다 | hint rename에 취약, 내부 점수/세부 탐지명 노출, artifact stability 낮음 | 비추천 |
| B canonical basis | `prepare_hint_family:sqli` | 안정적, 내부 구현 노출 감소, Viewer 표현 쉬움 | 상세 디버깅은 원래 `reason_hints`를 같이 봐야 함 | 추천 |

권장 basis token:

- `stage1_verdict:<verdict>`
- `prepare_hint_family:sqli`
- `prepare_hint_family:xss`
- `prepare_hint_family:traversal`
- `prepare_hint_family:cmdi`
- `prepare_hint_family:file_disclosure`
- `prepare_hint_family:sensitive_path`
- `prepare_hint_family:auth_abuse`
- `prepare_hint_family:method_probe`
- `prepare_hint_family:protocol_anomaly`
- `prepare_hint_family:hpp`
- `stage1_guardrail:file_disclosure_wrapper_normalized`

상세 raw `reason_hints`는 Stage1 result와 Viewer finding에 이미 존재하므로 `basis`에 반복 저장하지 않는다.

## 25. Pipeline integration point

정확한 구현 지점:

1. [`src/llm_stage1_classifier.py`](../../src/llm_stage1_classifier.py)
   - `classify_candidate()`는 기존처럼 `Stage1Result`를 반환한다.
   - `main()` loop에서 `result`를 받으면 `row = asdict(result)` 직후 `build_security_standards_mapping(row, candidate)`를 호출한다.
   - `row["standards_mapping"] = ...`를 설정한 뒤 `results.append(row)`를 수행한다.
   - 이 방식은 `Stage1Result` dataclass field 추가 없이도 1차 구현 가능하다.

2. [`src/llm_stage2_reporter.py`](../../src/llm_stage2_reporter.py)
   - `IncidentBrief` dataclass에 `standards_mapping: Dict[str, Any]`를 optional/default 없이 추가하려면 생성부도 함께 변경해야 한다.
   - 더 작은 구현은 `build_incident_briefs()`가 `asdict()` 이후 dict에 `standards_mapping`을 병합하는 방식이다.
   - 권장 구현은 `IncidentBrief`에 field를 명시 추가하여 schema를 눈에 보이게 하는 것이다.
   - `build_incident_briefs()`에서 representative item의 `standards_mapping`을 그대로 전달한다.
   - dedup 그룹 내 여러 row의 mapping이 다를 수 있으므로 Phase 1에서는 representative mapping만 사용한다. Phase 2에서 group merge가 필요하면 item union을 별도 설계한다.

3. [`src/viewer_payload_builder.py`](../../src/viewer_payload_builder.py)
   - `build_finding()`에서 `standards_mapping`을 copy-through한다.
   - `merge_missing()` 흐름상 stage2 top_incident에 없고 stage1 result에 있으면 채워질 수 있다.
   - old artifact에는 field가 없으므로 Viewer는 section을 숨긴다.

4. [`src/run_analysis_pipeline.py`](../../src/run_analysis_pipeline.py)
   - 별도 pipeline step을 추가하지 않는다.
   - enrichment는 Stage1 result post-processing의 일부로 취급한다.
   - manifest에 새 step을 추가하지 않아도 된다. 필요하면 Stage1 meta에 `standards_mapping_schema_version`을 기록한다.

실패 정책:

- standards enrichment failure should not invalidate the original Stage1 classification.
- mapping이 없어도 Stage2와 Viewer는 정상 동작해야 한다.
- mapping failure는 Stage1 meta warning 또는 row-level `unmapped_reason: "mapping_error"`로 충분하다.

## 26. Stage2 integration design

1차 권고는 다음이다.

```text
Stage2에는 standards_mapping을 optional로 전달하되, prompt 활용은 최소화한다.
Viewer 표시를 1차 primary consumer로 둔다.
```

세 후보 비교:

| 후보 | 설명 | 판단 |
| --- | --- | --- |
| A | Stage2가 mapping을 적극 활용해 보고서에 표준 섹션 작성 | prompt 변경과 과장 위험이 커서 1차 비추천 |
| B | Stage2에 optional 전달하되 boundary를 prompt에 최소 반영 | Phase 2 권장 |
| C | Viewer만 사용 | 가장 안전하지만 report와 viewer 불일치 가능 |

최종 권고:

- Phase 1: Stage1 artifact enrichment + unit tests.
- Phase 2: Stage2 `top_incidents`에 optional copy-through. prompt는 별도 변경 작업에서 boundary 문구만 추가.
- Phase 3: Viewer 표시.

Stage2가 절대 확대해석하면 안 되는 내용:

- vulnerability confirmed
- exploitation succeeded
- data leaked
- command executed
- authentication bypassed
- lockout absent
- browser executed JavaScript

## 27. Viewer design

Viewer `Security Standards` 섹션 위치:

```text
Finding Detail
-> Analysis Note
-> Interpretation Aid
-> Security Standards
-> Evidence
-> Related Contexts
-> Related Supporting Events
```

권장 표시:

```text
Security Standards

OWASP Top 10
A05:2025 · Injection
Relationship: Direct

CWE
CWE-89 · SQL Injection
Relationship: Direct

Related WSTG Test
WSTG-INPV-05 · Testing for SQL Injection
Relationship: Direct

Evidence Scope
Attempt observed

Boundary
Observed attack pattern does not confirm a vulnerability or exploitation success.
```

표시 정책:

- WSTG 그룹 제목은 `Related WSTG Test` 또는 `WSTG Test Scenario`를 사용한다.
- `relationship`은 Title Case로 표시하되 tooltip/help text에서 Direct의 한계를 설명한다.
- `observability`는 사용자용 문구로 변환한다.
  - `attempt_only` -> `Attempt observed`
  - `behavior_only` -> `Behavior pattern observed`
  - `partial` -> `Partial log evidence`
  - `not_applicable` -> 표시 생략
- item이 없으면 섹션 전체를 숨긴다.
- old artifact라 field가 없으면 섹션을 숨긴다.

피해야 할 표현:

- Detected Vulnerability
- Confirmed Vulnerability
- OWASP Vulnerability Detected
- Exploited
- Compromised

## 28. Backward compatibility

| Case | Behavior |
| --- | --- |
| standards_mapping 없는 기존 Stage1 artifact | Stage2/Viewer는 없는 field로 처리하고 표시 생략 |
| standards_mapping v1 artifact | schema_version이 `security_standards_mapping.v1`이면 그대로 표시 |
| unknown future standard | raw `standard`, `id`, `name`을 fallback text로 표시. crash 금지 |
| unknown future relationship | raw relationship을 표시하되 boundary note를 유지. badge style fallback |
| Viewer가 old/new artifact 모두 읽음 | old는 section 숨김, new는 item 있을 때 표시 |
| Stage2가 old artifact를 읽음 | optional field absent로 정상 동작 |
| items empty | section 숨김. debugging view에서는 `unmapped_reason` 표시 가능 |

Fail-open/fail-safe:

- Enrichment absence는 analysis failure가 아니다.
- Unknown value는 display fallback으로 처리한다.
- Mapping item은 severity/confidence/recommended_actions를 변경하지 않는다.

## 29. Regression test specification

테스트는 실제 구현 시 `tests/test_security_standards_mapping.py`를 우선 추가한다. 각 case는 mapping function 단위 테스트로 시작하고, Stage1/Stage2/Viewer integration은 별도 test로 나눈다.

| Test name 후보 | Input verdict | Input reason_hints | Expected mapping | Unexpected mapping | Expected observability | Boundary assertion |
| --- | --- | --- | --- | --- | --- | --- |
| `test_plain_traversal_maps_direct` | `suspicious_path_traversal` | `traversal:dotdot_slash(+4)` | A01 direct, CWE-22 direct, WSTG-ATHZ-01 direct | CWE-552 | `attempt_only` | no file read success text |
| `test_url_encoded_traversal_maps_direct` | `suspicious_path_traversal` | `traversal:url_encoded_dotdot_slash(+4)` | A01, CWE-22, WSTG-ATHZ-01 | CWE-552 | `attempt_only` | encoded evidence is existing Prepare evidence |
| `test_double_encoded_traversal_maps_direct` | `suspicious_path_traversal` | `traversal:double_encoded_dotdot_slash(+4)`, `encoding:decoded_depth_2` | A01, CWE-22, WSTG-ATHZ-01 | CWE-552 | `attempt_only` | no decode regex required in mapping layer |
| `test_direct_private_secret_is_not_traversal` | `suspicious_scan` or `inconclusive` | `sensitive_path:private_file` | optional WSTG-CONF-04 related only if scan | CWE-22 | `behavior_only` or `not_applicable` | direct path != traversal |
| `test_direct_env_is_not_cwe22` | `suspicious_file_disclosure` | `sensitive_path:env_file` | CWE-552 conditional, WSTG-CONF-04 related | CWE-22, CWE-200 | `attempt_only` | exposure not confirmed |
| `test_sqli_maps_injection_direct` | `suspicious_sqli` | `sqli:boolean_true_condition` | A05 direct, CWE-89 direct, WSTG-INPV-05 direct | A01 | `attempt_only` | DB execution/result unknown |
| `test_sqli_query_secret_string_does_not_add_sensitive_file_mapping` | `suspicious_sqli` | `sqli:union_select`, query contains `secret` | A05 direct, CWE-89 direct, WSTG-INPV-05 direct | CWE-552, WSTG-CONF-04, A01, A02 | `attempt_only` | raw query word is not sensitive-file Prepare evidence |
| `test_sqli_query_passwd_string_does_not_add_sensitive_file_mapping` | `suspicious_sqli` | `sqli:union_select`, query contains `passwd` | A05 direct, CWE-89 direct, WSTG-INPV-05 direct | CWE-552, WSTG-CONF-04, A01, A02 | `attempt_only` | standards mapping must not become a sensitive-file detector |
| `test_xss_maps_without_stored_claim` | `suspicious_xss` | `xss:script_tag` | A05 direct, CWE-79 direct, WSTG-INPV-01 related | WSTG-INPV-02 | `attempt_only` | reflection/browser execution unknown |
| `test_xss_query_admin_string_without_prepare_hint_does_not_add_admin_mapping` | `suspicious_xss` | `xss:script_tag`, query contains `next=/admin` | A05 direct, CWE-79 direct, WSTG-INPV-01 related | WSTG-CONF-05, CWE-425, A01 related | `attempt_only` | raw `/admin` string is not admin enumeration Prepare evidence |
| `test_location_dash_xss_fp_has_empty_mapping` | `likely_false_positive` | `xss:external_navigation`, `context:educational_xss_search` | empty items | CWE-79, WSTG-INPV-01 | `not_applicable` | final FP suppresses mapping |
| `test_cmdi_maps_cwe78_not_cwe77` | `suspicious_command_injection` | `cmdi:semicolon` | A05 direct, CWE-78 direct, WSTG-INPV-12 direct | CWE-77 | `attempt_only` | command execution unknown |
| `test_repeated_bruteforce_cwe307_conditional` | `suspicious_bruteforce` | `auth_abuse:repeated_401`, `auth_abuse:rapid_fail_burst` | A07 direct, CWE-307 conditional, WSTG-ATHN-03 related | CWE-307 direct | `behavior_only` | lockout/rate limit unknown |
| `test_broad_auth_abuse_no_default_cwe` | `suspicious_auth_abuse` | `login_endpoint(+1)`, `auth_abuse:no_auth_success_inference` | A07 related | CWE-307, WSTG-ATHN-03 | `behavior_only` | single auth access is insufficient |
| `test_repeated_auth_abuse_adds_conditional_cwe307` | `suspicious_auth_abuse` | `auth_abuse:repeated_auth_endpoint`, `auth_abuse:no_auth_success_inference` | A07 conditional, CWE-307 conditional | A07 related, WSTG-ATHN-03 | `behavior_only` | same standard/id keeps stronger relationship only |
| `test_generic_scanner_empty_mapping` | `suspicious_scan` | `ua:scanner(+1)` | empty items | OWASP_TOP10, CWE | `behavior_only` | scan is not vulnerability category |
| `test_admin_path_enumeration_scanner_wstg_related` | `suspicious_scan` | `sensitive_path:admin`, `dir_probe:admin_sequence` | WSTG-CONF-05 related | A01 direct, CWE-425 direct | `behavior_only` | admin existence/access unknown |
| `test_prepare_admin_enumeration_hint_preserves_cross_category_mapping` | `suspicious_sqli` | `sqli:union_select`, `sensitive_path:admin`, `dir_probe:admin_sequence` | SQLi direct items plus A01 related, CWE-425 conditional, WSTG-CONF-05 related | A01 direct, CWE-425 direct | `attempt_only` | actual Prepare evidence permits related admin mapping |
| `test_server_error_probe_wstg_only` | `server_error_probe` | `error_status:500(+2)`, `error_table_context(+2)` | WSTG-ERRH-01 related | A10:2025, CWE-209 | `behavior_only` | error != A10 |
| `test_php_wrapper_file_disclosure_conditional_cwe98` | `suspicious_file_disclosure` | `file_disclosure:php_filter_wrapper`, `file_disclosure:base64_source_intent`, `file_disclosure:resource_parameter` | A05 related, CWE-98 conditional, WSTG-ATHZ-01 related | CWE-22 direct | `attempt_only` | include/require unknown |
| `test_traversal_based_file_disclosure_uses_traversal_branch` | `suspicious_file_disclosure` | `traversal:dotdot_slash(+4)`, `file_disclosure:sensitive_resource:config_php` | A01 direct, CWE-22 direct, WSTG-ATHZ-01 direct | CWE-98 | `attempt_only` | branch priority traversal first |
| `test_direct_sensitive_file_disclosure_probe` | `suspicious_file_disclosure` | `file_disclosure:sensitive_resource:config_php` | A02 related, CWE-552 conditional, WSTG-CONF-03/04 related | CWE-22, CWE-200 | `attempt_only` | direct config path != traversal/exposure |
| `test_benign_normal_empty_mapping` | `benign_normal` | `baseline:static_asset` | empty items | any standard item | `not_applicable` | normal verdict suppresses standards |
| `test_likely_false_positive_empty_mapping` | `likely_false_positive` | `fp_hint:sql_keyword_without_attack_structure`, `sqli:select_keyword` | empty items | A05, CWE-89 | `not_applicable` | final FP wins |
| `test_inconclusive_empty_mapping` | `inconclusive` | `special_char_ratio_high(+1)` | empty items | any standard item | `not_applicable` | insufficient class |
| `test_unknown_future_verdict_empty_mapping` | `suspicious_new_future` | `l3:new_hint` | empty items, `unmapped_reason=unknown_verdict` | any standard item | `not_applicable` | fail open |
| `test_old_artifact_without_standards_mapping_viewer_safe` | old artifact | none | Viewer hides section | template crash | n/a | backward compatible |
| `test_duplicate_reason_hints_deduplicate_items` | `suspicious_sqli` | duplicate `sqli:*` hints | one A05, one CWE-89, one WSTG-INPV-05 | duplicate items | `attempt_only` | `(standard,id,relationship)` unique |
| `test_deterministic_output_ordering` | mixed evidence | SQLi + HPP + sensitive path | OWASP before CWE before WSTG, stable rule order | nondeterministic order | verdict-derived | repeated calls produce equal JSON |

Integration test 후보:

- `test_stage1_results_include_standards_mapping_optional_field`
- `test_stage2_report_input_preserves_standards_mapping`
- `test_viewer_payload_build_finding_preserves_standards_mapping`
- `test_viewer_old_payload_without_mapping_renders`

## 30. L3 hint scope

현재 `l3:*` 계열은 다음이 있다.

- Log4Shell
- SSRF
- open redirect
- SSTI
- GraphQL introspection
- XXE
- webshell

1차 구현 범위에서는 제외한다.

이유:

- 대부분 Stage1에 독립 verdict가 없는 hint-only class이다.
- mapping layer가 Stage1 classifier를 우회해 새로운 공격 탐지기로 동작할 위험이 있다.
- 각 L3 hint는 OWASP/CWE/WSTG semantic 경계가 다르고 별도 설계가 필요하다.

Phase 2+ 후보:

- `l3:ssrf` -> A01:2025/CWE-918 후보
- `l3:xxe_probe` -> A05:2025/CWE-611/WSTG-INPV-07 후보
- `l3:ssti` -> A05:2025/CWE-94 or CWE-1336 후보
- `l3:open_redirect_probe` -> CWE-601/WSTG-CLNT or validation scenario 후보
- `l3:graphql_introspection` -> WSTG-APIT/GraphQL test scenario 후보
- `l3:log4shell` -> CWE-917/Log injection style 후보 별도 검토
- `l3:webshell_probe` -> webshell access/probe와 command execution 경계 별도 검토

## 31. DB 저장 여부

비교:

| 방식 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| artifact-only | migration 없음, 기존 pipeline에 additive | DB query로 집계 어려움 | 1차 추천 |
| report JSON 내부 optional field | Stage2/Viewer 전달 쉬움 | Stage2 생성 전 원본 Stage1에는 없을 수 있음 | artifact-only의 일부로 허용 |
| 별도 DB column | 검색/필터 편함 | migration 필요, schema churn | 1차 제외 |
| 별도 table | 다대다 mapping query 가능 | 가장 복잡, migration/관리 필요 | 1차 제외 |

1차 구현은 migration 없이 Stage1 artifact row와 Stage2 report input/report JSON 내부 optional field로 충분하다.

## 32. Performance/failure policy

성능 영향:

- LLM 호출 없음
- network 없음
- API 비용 없음
- DB query 추가 없음
- per candidate small CPU-only dict/list evaluation

반복 parsing:

- mapping layer는 raw URL decoding/normalization을 새로 하지 않는다.
- 기존 `reason_hints`, `verdict`, `uri` family만 읽는다.
- 따라서 Prepare와 중복되는 regex/decode 비용이 없다.

Failure policy:

- mapping failure는 Stage1 result를 실패시키지 않는다.
- row-level empty mapping으로 대체한다.
- Stage2/Viewer는 field absence, invalid shape, unknown enum을 모두 display fallback 또는 section hide로 처리한다.

## 33. Implementation phases

### Phase 1

- `src/security_standards_mapping.py` 추가
- Python constant table/rule helpers 추가
- `build_security_standards_mapping()` pure function 구현
- mapping unit tests 추가
- Stage1 pipeline에는 아직 연결하지 않아도 독립 검증 가능

### Phase 2

- `llm_stage1_classifier.py`의 `main()` result append 직전에 enrichment 호출
- Stage1 artifact에 optional `standards_mapping` field 추가
- `llm_stage2_reporter.py`의 `build_incident_briefs()`에서 optional field copy-through
- Stage2 prompt는 별도 작업으로 boundary 문구만 최소 반영
- compatibility tests 추가

### Phase 3

- `viewer_payload_builder.py`의 `build_finding()`에서 `standards_mapping` copy-through
- `web/templates/payload_detail.html`에 `Security Standards` 섹션 추가
- Viewer regression tests 추가

### Phase 4

- coverage summary 설계/구현
- L3 hint mappings 별도 설계 후 추가
- WSTG/API/GraphQL 등 세부 test scenario 확장

## 34. Coverage summary 향후 설계

Coverage summary는 1차 implementation과 분리한다.

권장 표현:

```text
OWASP-related Observed Categories

A01 Broken Access Control        4 findings
A05 Injection                    7 findings
A07 Authentication Failures      2 findings
```

피해야 할 표현:

```text
OWASP Vulnerabilities Detected
```

향후 결정 사항:

- count가 raw finding count인지 incident count인지 결정해야 한다.
- dedup 이후 `top_incidents` 기준인지 전체 Stage1 result 기준인지 결정해야 한다.
- `related`와 `conditional`을 Direct와 같은 count에 합칠지 분리할지 결정해야 한다.

1차 권고는 summary를 만들지 않는 것이다. Phase 4에서 `relationship`별 count를 분리해 추가한다.

## 35. Open questions

- Stage2 prompt에 standards mapping boundary를 언제 반영할지 별도 작업으로 결정해야 한다.
- dedup된 incident 안에 서로 다른 standards_mapping이 섞이면 representative만 쓸지 union할지 Phase 2에서 재검토한다.
- WSTG-INPV-01을 XSS에서 `related`로 유지할지, query/URI payload에 한해 `direct` test scenario relation으로 바꿀지 실제 fixture 검증 후 재검토할 수 있다. 1차는 `related`가 안전하다.
- `suspicious_file_disclosure` Branch C에서 A01 Related와 A02 Related를 둘 다 낼지, 기본 A02만 낼지 product display 밀도에 따라 결정할 수 있다. 1차는 A02 Related 중심이 안전하다.
- Korean display name을 artifact에 같이 저장할지 Viewer resolve table에서 처리할지 결정해야 한다. 1차 artifact는 공식 영문 name만 저장한다.

## 36. Final recommendation

최종 권고는 다음이다.

- `src/security_standards_mapping.py`에 pure deterministic enrichment function을 둔다.
- public function은 `build_security_standards_mapping(stage1_result, candidate=None) -> dict[str, Any]`로 한다.
- Stage1 result row에 `standards_mapping` object를 optional/additive field로 저장한다.
- Non-security verdict도 새 artifact에서는 `items: []` 형태의 object를 저장한다.
- Stage2는 Phase 2에서 optional copy-through만 하고, prompt 활용은 boundary wording 추가 후 제한적으로 한다.
- Viewer는 Phase 3에서 `Security Standards` 섹션을 finding detail의 `Interpretation Aid`와 `Evidence` 사이에 표시한다.
- 1차 scope는 Stage1 독립 verdict가 있는 SQLi/XSS/path traversal/CMDI/brute force/auth abuse/file disclosure/server error/scan에 한정한다.
- L3 hint-only class와 coverage summary는 Phase 4 이후로 둔다.

References:

- OWASP Top 10:2025: https://owasp.org/Top10/
- OWASP Web Security Testing Guide: https://owasp.org/www-project-web-security-testing-guide/
- CWE: https://cwe.mitre.org/
