# 101 External Security Benchmark Design — OWASP CRS Path Traversal / File Access

- 문서 상태: Phase 5A 조사 및 상세 설계
- 작성 기준: project HEAD `f9835b3` (`feat: add security standards summary to report viewer`)
- 작성일: 2026-09-01
- 구현 상태: 미구현. 이 문서는 source 선정, observability, annotation, fixture/result contract와 평가 semantics만 정의한다.
- 첫 source snapshot: OWASP CRS upstream commit `96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a` (2026-08-30)
- 관련 project 기준:
  - [Apache logs-only evidence boundary](../00_apache_logs_only_evidence_boundary.md)
  - [현재 architecture](../00_current_architecture.md)
  - [Prepare candidate policy](./99_prepare_candidate_policy.md)
  - [File disclosure verdict taxonomy](./99_file_disclosure_verdict_taxonomy_검토.md)
  - [OWASP security standard mapping design](./99_owasp_security_standard_mapping_design.md)
  - [Security standards coverage summary design](./100_security_standards_coverage_summary_design.md)

## 결정 요약

첫 benchmark의 질문은 “CRS가 match하는가?”가 아니다.

```text
외부에서 expectation이 정의된 HTTP request
  -> 현재 Apache log contract에서 관찰 가능한 형태
  -> Prepare candidate selection
  -> Stage1 project taxonomy
  -> deterministic standards mapping
  -> project-specific expectation과 비교
```

source rule ID와 project verdict는 서로 다른 taxonomy다. `expect_ids: [930120]`을 `suspicious_path_traversal`로 자동 변환하지 않는다. 각 source case에 project annotation을 별도로 붙인다.

현재 고정 snapshot의 eligibility는 다음과 같다. `partial`은 현재 main score에서 제외되는 capability group이며 `eligible`과 중복 집계하지 않는다.

| CRS rule | source cases | directly eligible | partial | out of scope |
| --- | ---: | ---: | ---: | ---: |
| `930100` | 5 | 2 | 2 | 1 |
| `930110` | 13 | 8 | 1 | 4 |
| `930120` | 18 | 17 | 0 | 1 |
| 합계 | 36 | 27 | 3 | 6 |

추천 구조는 두 level이다.

```text
Level 1: pinned source + normalized manifest + synthetic Apache row/log + existing Prepare
         + replay/controlled or explicitly identified live Stage1 + mapping + evaluator

Level 2: selected HTTP request + local Apache + actual log/export + existing pipeline
         + live Stage1 + evaluator
```

Level 1은 deterministic contract와 회귀를 담당하고, Level 2는 Apache parsing/logging realism을 표본 검증한다. benchmark 전용 탐지 로직은 production Prepare/Stage1/mapping path에 넣지 않는다.

---

## 1. 목적

이 설계의 목적은 현재 Apache web-log analysis pipeline을 외부 자료로 평가하는 재현 가능한 구조를 정의하는 것이다. 첫 범위는 OWASP CRS `930100`, `930110`, `930120` regression cases다.

평가 대상은 다음 네 경계다.

1. 외부 request의 핵심 signal이 현재 Apache logs-only input에 남는가.
2. 관찰 가능한 project-positive request를 Prepare가 candidate로 선택하는가.
3. Stage1 verdict가 project-specific exact 또는 compatible set과 양립하는가.
4. 올바른 Stage1 classification에 deterministic standards mapping이 일관되게 붙는가.

attack pattern 또는 probing intent는 평가할 수 있지만 exploit success는 평가하지 않는다. `/etc/passwd` 문자열이 보여도 파일 존재, 파일 내용 반환, LFI 취약점 존재를 ground truth로 만들지 않는다.

## 2. Non-goals

Phase 5A에서는 다음을 구현하지 않는다.

- benchmark runner, source adapter, CRS YAML parser
- pytest parameter generation
- synthetic Apache log generator 또는 local Apache lab
- 실제 LLM API 호출, response replay 파일 생성
- precision/recall 계산 코드와 report generator
- CSIC 2010, ECML/PKDD, CICIDS import
- Prepare detection rule, Stage1 verdict, OWASP/CWE/WSTG mapping 변경
- DB/schema 변경
- upstream CRS YAML vendoring
- Security Standards Summary에 benchmark 결과를 삽입하는 기능

이 문서의 case expectation은 향후 manifest 작성 기준이며 현재 코드를 그 expectation에 맞추는 구현 결정이 아니다.

## 3. 현재 pipeline evaluation surface

### 3.1 Prepare

현재 기본 Prepare CLI는 `security` source table을 사용하고 candidate 최소 점수는 4다. 실제 candidate 선택은 단순 threshold 하나가 아니라 pattern score, context score, category-specific threshold와 일부 보수 guard를 함께 사용한다.

현재 외부 benchmark에서 관찰할 핵심 output은 다음과 같다.

| surface | 현재 contract | benchmark 의미 |
| --- | --- | --- |
| candidate 생성 | `analysis_candidates`에 존재 | `candidate_selected=true` |
| filtered-out | `filtered_out`/`filtered_reasons`에 존재 | candidate miss 또는 기대된 negative suppression. benign 확정이 아님 |
| `reason_hints` | SQLi/XSS/traversal/CMDI, encoding, context 등의 근거 | 진단용. source label 또는 Stage1 verdict가 아님 |
| `verdict_hint` | `path_traversal`, `suspicious`, `sqli` 등 Prepare 내부 힌트 | Stage1 enum과 분리해 기록 |
| dedup | request 단위 후보가 incident group으로 full-dedup될 수 있음 | case identity를 request ID/benchmark case ID로 역추적해야 함 |

candidate 생성의 주요 현재 특성은 다음과 같다.

- access/security의 정상 Socket.IO polling, `access`의 200 static asset 등은 먼저 제외할 수 있다.
- traversal pattern은 `../`, encoded dot/slash 일부와 `/etc/passwd|win.ini`를 점수화한다.
- category verdict hint에는 별도 threshold가 있다. 예를 들어 traversal hint는 보통 score 6 이상에서 `path_traversal` hint가 되고, score 4~5 candidate는 generic `suspicious`일 수 있다.
- direct `/config.php`, `/admin/config.php` 단발 generic candidate는 wrapper evidence가 없으면 context/filtered-out으로 남기는 guard가 있다.
- filtered-out은 “정상” 또는 “공격 실패”를 의미하지 않는다. benchmark에서도 `candidate_expected`와 함께 해석한다.

### 3.2 path, query, raw target

현재 필드 흐름은 다음과 같다.

- Apache security log contract는 `%r`을 `raw_request`, `%U`를 `uri`, `%q`를 `query_string`으로 기록한다.
- Prepare는 `raw_request`의 method와 `HTTP/...` 사이를 잘라 `raw_request_target`을 다시 만든다.
- effective path는 `raw_request_target`의 path를 우선하고 없으면 `uri`를 사용한다.
- `query_string`은 Apache `%q`처럼 선행 `?`가 있어도 parser가 처리할 수 있다.
- `raw_request_target`은 raw representation을 보존한다. `uri`와 normalized query는 편의상 decode된 값일 수 있으므로 raw/normalized 두 표면을 모두 결과에 남겨야 한다.

### 3.3 URL decode behavior

현재 Prepare는 `urllib.parse.unquote_plus` 계열 normalization을 사용한다.

- 일반 `normalize_text()`는 한 번 URL decode하며 `+`를 space로 해석한다.
- raw query와 raw request target은 depth 0을 포함해 최대 depth 2 URL-decoded variant를 만든다.
- variant는 최대 4096자로 제한된다.
- HTML numeric entity variant를 별도로 추가한다.
- raw request target 자체는 보존한다.

CRS와 동일한 transform chain은 아니다. 현재 Prepare에는 CRS의 `utf8toUnicode`, `removeNulls`, `cmdLine`, `normalizePathWin`, CRS 전용 `0x2e`/`0x2f` 해석을 그대로 재현하는 contract가 없다. 따라서 encoded case가 observable하더라도 “CRS와 같은 방식으로 decode해야 한다”를 runner 요구사항으로 만들지 않는다. miss가 발생하면 현재 normalization coverage의 평가 결과로 기록한다.

### 3.4 direct sensitive path

현재 policy의 핵심 guardrail은 다음과 같다.

```text
direct sensitive path != path traversal
```

`/private/secret.txt`, `/.env`, `/config.php`, `/admin/config.php` 같은 직접 요청은 explicit directory escape가 없으면 `suspicious_path_traversal`의 충분조건이 아니다. 단발 direct config path는 context-only/low-signal로 남을 수 있다. 반면 query value가 명시적인 file-read primitive처럼 보이면 `suspicious_file_disclosure` 또는 `suspicious_scan`이 project-compatible할 수 있다.

현재 Prepare의 sensitive path classifier는 고정된 request path 중심이며, 모든 query value의 OS resource 이름을 일반적으로 분류하지 않는다. `/etc/passwd|win.ini`는 현재 traversal pattern group에도 포함되어 있어 direct path가 traversal hint를 얻을 가능성이 있다. 930120 direct-resource negative guardrail은 이 taxonomy mismatch를 드러내는 중요한 외부 평가다. 이 Phase에서 detection rule은 고치지 않는다.

### 3.5 Stage1

현재 Stage1 verdict enum은 다음 12개다.

```text
benign_normal
likely_false_positive
suspicious_scan
suspicious_bruteforce
suspicious_sqli
suspicious_xss
suspicious_path_traversal
suspicious_file_disclosure
suspicious_command_injection
suspicious_auth_abuse
server_error_probe
inconclusive
```

Stage1 prompt는 `suspicious_path_traversal`에 explicit directory-escape evidence를 요구하고 direct sensitive path만으로 traversal을 선택하지 않도록 한다. PHP wrapper + base64 + resource hint 조합은 post-parse guard가 `suspicious_file_disclosure`로 보수 정규화하지만, 모든 direct OS file probe를 deterministic하게 정규화하지는 않는다.

severity와 confidence도 output에 있으나 CRS source에는 project severity/confidence ground truth가 없다. 첫 benchmark의 primary score에는 포함하지 않고 distribution과 `high/critical` 과승격을 diagnostic으로만 기록한다.

### 3.6 deterministic standards mapping

현재 mapping은 새 공격을 탐지하지 않고 Stage1 verdict와 기존 reason hint를 읽는다.

| Stage1/evidence branch | 현재 핵심 mapping |
| --- | --- |
| `suspicious_path_traversal` | `A01:2025` direct, `CWE-22` direct, `WSTG-ATHZ-01` direct |
| `suspicious_file_disclosure` + traversal hint | traversal과 같은 A01/CWE-22/WSTG-ATHZ-01 branch |
| `suspicious_file_disclosure` + PHP wrapper | `A05:2025` related, `CWE-98` conditional, `WSTG-ATHZ-01` related |
| `suspicious_file_disclosure` + direct sensitive evidence | `A02:2025` related, `CWE-552` conditional, `WSTG-CONF-03/04` related |
| `suspicious_scan` + file/dir probe hint | WSTG discovery/config relation. 근거가 없으면 empty mapping 가능 |
| non-security verdict | empty mapping |

standards mapping은 classification을 대신하지 않는다. classification이 틀리면 결과 mapping이 기대와 달라도 mapping algorithm의 독립 failure로 중복 계산하지 않는다.

## 4. OWASP CRS 성격

OWASP CRS는 ModSecurity 또는 호환 WAF에서 HTTP transaction의 여러 surface를 검사하는 rule set이다. 고정 source snapshot에서 세 rule의 역할은 다음과 같다.

- `930100`: raw URI, args, request headers, uploaded filename, XML node/attribute 등에서 encoded `/../` 또는 `/.../` 구조를 찾는다.
- `930110`: transform 후 decoded `../`, `.../`, semicolon/backslash variant를 찾는다.
- `930120`: cookies, argument names/values, XML node/attribute를 OS file 목록과 대조하는 OS File Access Attempt rule이다.

CRS는 request body, arbitrary header, multipart filename, XML attribute처럼 현재 project log에 없는 surface도 볼 수 있다. 또한 CRS rule match는 WAF anomaly signal이며 project의 Stage1 verdict, exploit success 또는 file disclosure success ground truth가 아니다.

## 5. Project taxonomy와 CRS rule 차이

다음 변환은 금지한다.

```text
930100/930110/930120 match -> suspicious_path_traversal
```

대신 case 의미를 project 기준으로 다시 annotate한다.

| case family | project expectation 원칙 |
| --- | --- |
| 명시적 `../`, `..\`, triple-dot escape, encoded equivalent | strict `suspicious_path_traversal` |
| LFI-like parameter에 direct `/etc/passwd` | strict 또는 compatible `suspicious_file_disclosure`; traversal forbidden |
| `.ssh/id_rsa`, `/sys`, `.docker/secrets`, backup/dependency metadata direct probe | compatible `{suspicious_file_disclosure, suspicious_scan}`; traversal forbidden |
| command-like `cat /etc/...`, `>/tmp/file` | case별 `{suspicious_command_injection, suspicious_file_disclosure, suspicious_scan}` compatible set |
| CRS rule-specific lookalike negative | project negative control로 별도 검토; source `no_expect_ids`만으로 모든 공격 negative로 복사하지 않음 |

project verdict는 실제 취약점 확인이 아니라 관찰된 request의 가장 적합한 pattern family다.

## 6. Apache logs-only observability

현재 canonical log surface는 method, raw request line/target, URI, query, protocol, status, bytes, timing, fixed request/response headers, request/error ID와 Apache error/security context다. raw POST body, multipart body, XML body, response body는 저장하지 않는다.

현재 fixed header fields에는 `User-Agent`, `Referer`, `Origin`, `Host`, forwarding headers, content type/length와 authorization/cookie 존재 flag 등이 있으나 arbitrary `FoobarHeader` 값은 없다. 그러므로 header payload가 `FoobarHeader`에만 있는 CRS case는 현재 main score에 넣지 않는다.

observability와 semantics는 별도 축이다.

```text
observable=true  -> payload 문자열이 현재 입력에 남는다.
attack_positive  -> project annotation이 해당 request를 공격 pattern 평가 대상으로 정했다.
exploit_success  -> 이 benchmark에서는 항상 평가 대상이 아니다.
```

## 7. Eligibility classification

### 7.1 stable status

| status | 의미 | main score |
| --- | --- | --- |
| `direct` | 핵심 signal이 method/request target/query 또는 현재 저장 필드에 직접 존재 | 포함 |
| `partial` | 특정 header/log configuration 또는 Apache normalization에 따라 보일 수 있으나 현재 canonical schema에는 충분하지 않음 | 제외, capability group으로 별도 보고 |
| `out_of_scope` | body/response 등 현재 input boundary에 핵심 signal이 없음 | 제외 |

`partial` case는 `eligible=false`다. 다만 `out_of_scope`와 별도 count로 보여 향후 header capability 확장을 추적한다.

### 7.2 exclusion reason enum

초기 stable enum은 다음과 같이 둔다.

```text
post_body_not_logged
xml_body_not_logged
multipart_body_not_logged
multipart_filename_not_logged
header_not_available
apache_normalization_not_preserved
unsupported_input_surface
requires_response_body
ambiguous_project_taxonomy
```

`ambiguous_project_taxonomy`는 observable data 부재가 아니라 annotation review 상태다. 첫 manifest를 freeze하기 전 가능한 한 exact/compatible/forbidden-only로 해결하고, 정말 합의되지 않은 case만 classification denominator에서 제외한다.

## 8. CRS 930100 inventory

Source: pinned upstream `tests/regression/tests/REQUEST-930-APPLICATION-ATTACK-LFI/930100.yaml`.

| rule_id / test_id | description | method / URI | payload location | original expectation | observable scope | proposed project expectation | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 930100 / 1 | encoded `/../` | GET `/get` | custom `FoobarHeader=0x5c0x2e.%00/` | `expect_ids:[930100]` | `partial`, `header_not_available` | not scored; future header lane에서는 strict traversal | 현재 schema에 arbitrary header value 없음 |
| 930100 / 2 | triple-dot `/.../` | GET `/get?foo=.../.../WINDOWS/win.ini` | request-target query value | `expect_ids:[930100]` | `direct` | candidate true; exact traversal; `CWE-22` | 첫 positive 후보. triple-dot escape가 raw target에 존재 |
| 930100 / 3 | encoded triple-dot | GET `/get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini` | request-target query value | `expect_ids:[930100]` | `direct` | candidate true; exact traversal; `CWE-22` | observable하지만 current URL decoder가 CRS `0x`/NUL transform을 재현하지 않음. normalization coverage test |
| 930100 / 4 | partially encoded backslash traversal | GET `/get` | custom `FoobarHeader=0x5c0x2e./` | `expect_ids:[930100]` | `partial`, `header_not_available` | not scored; future header lane에서는 strict traversal | URI 자체에는 payload 없음 |
| 930100 / 5 | XML attribute injection | POST `/post` | XML body attribute | `expect_ids:[930100]` | `out_of_scope`, `xml_body_not_logged` | not scored | Content-Type만 보이고 payload body는 보이지 않음 |

930100의 첫 main benchmark positive는 test 2와 3이다. test 3은 “현재 Prepare가 CRS와 같아야 한다”는 요구가 아니라, observable encoded semantics를 현재 contract가 얼마나 처리하는지 보여주는 case다.

## 9. CRS 930110 inventory

Source: pinned upstream `930110.yaml` 전체 13건.

| rule_id / test_id | description | method / URI | payload location | original expectation | observable scope | proposed project expectation | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 930110 / 1 | complex `/../` | GET `/get` | custom `FoobarHeader` | `expect_ids:[930110]` | `partial`, `header_not_available` | not scored; future header lane strict traversal | payload가 request target에 없음 |
| 930110 / 2 | `/../` query | GET `/get?arg=../../../etc/passwd` | query value | `expect_ids:[930110]` | `direct` | candidate true; exact traversal; A01/CWE-22/WSTG-ATHZ-01 | 가장 강한 첫 positive |
| 930110 / 3 | `/../` form data | POST `/post` | URL-encoded POST body | `expect_ids:[930110]` | `out_of_scope`, `post_body_not_logged` | not scored | request target은 `/post`뿐 |
| 930110 / 4 | lookalike `foo../1234` | GET `/get/foo../1234` | path | `no_expect_ids:[930110]` | `direct` | candidate false; forbidden traversal; negative control | current substring-style traversal detection의 FP guardrail 후보 |
| 930110 / 5 | lookalike `foo.../1234` | GET `/get/foo.../1234` | path | `no_expect_ids:[930110]` | `direct` | candidate false; forbidden traversal; negative control | triple dot이 segment boundary에 있지 않음 |
| 930110 / 6 | lookalike `/..foo` | GET `/get/..foo` | path | `no_expect_ids:[930110]` | `direct` | candidate false; forbidden traversal; negative control | bare prefix dots, directory escape 아님 |
| 930110 / 7 | bare `/..` | GET `/get/..` | path/raw request line | `no_expect_ids:[930110]` | `direct` for Level 1 | candidate false; forbidden traversal; negative control | upstream은 httpd가 REQUEST_URI dots를 제거할 수 있음을 명시. Level 2에서 `%r` preservation을 별도 확인 |
| 930110 / 8 | Windows `..\` | GET `/get?arg=..\pineapple` | query value | `expect_ids:[930110]` | `direct` | candidate true; exact traversal | backslash directory escape coverage |
| 930110 / 9 | triple-dot | GET `/get?foo=.../.../WINDOWS/win.ini` | query value | `expect_ids:[930110]` | `direct` | candidate true; exact traversal | 930100/2와 같은 request가 source provenance상 별도 case |
| 930110 / 10 | upload filename `../1.7z` | POST `/post` | multipart filename | `expect_ids:[930110]` | `out_of_scope`, `multipart_filename_not_logged` | not scored | req Content-Type만으로 filename 복원 불가 |
| 930110 / 11 | upload filename `..\1.7z` | POST `/post` | multipart filename | `expect_ids:[930110]` | `out_of_scope`, `multipart_filename_not_logged` | not scored | 동일 |
| 930110 / 12 | semicolon/backslash traversal | GET `/get?a=..;.\.;\.` | query value | `expect_ids:[930110]` | `direct` | candidate true; exact traversal | CRS transform/Tomcat-style variant와 current pattern 차이를 측정 |
| 930110 / 13 | XML attribute traversal | POST `/post` | XML body attribute | `expect_ids:[930110]` | `out_of_scope`, `xml_body_not_logged` | not scored | body payload 없음 |

Strong direct traversal positive는 tests 2, 8, 9, 12다. Tests 4~7은 lookalike/bare-dot negative control이다. 이 negative들은 positive 수를 늘리는 것보다 더 중요하게, explicit directory escape boundary를 검증한다.

## 10. CRS 930120 inventory

Source: pinned upstream `930120.yaml` 전체 18건.

| rule_id / test_id | description | method / URI | payload location | original expectation | observable scope | proposed project expectation | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 930120 / 1 | traversal to `boot.ini` | GET `/get/index.php?file=News&op=../../../../../boot.ini%00` | query value | `expect_ids:[930120]` | `direct` | candidate true; exact traversal | NUL suffix는 success 의미 아님 |
| 930120 / 2 | direct `/etc/passwd` | GET `/get/index.php?file=News&op=/etc/passwd%00` | query value | `expect_ids:[930120]` | `direct` | candidate true; exact file disclosure; forbidden traversal | LFI-like parameter의 direct file-read probe. CWE-22 금지 |
| 930120 / 3 | traversal to `httpd.conf` | GET `/get/index.php?...op=../../../../../../../../../../usr/local/apps/apache2/conf/httpd.conf%00` | query value | `expect_ids:[930120]` | `direct` | candidate true; exact traversal | explicit directory escape |
| 930120 / 4 | `.ssh/id_rsa` | GET `/get?foo=arg&path_comp=.ssh/id_rsa` | query value | `expect_ids:[930120]` | `direct` | candidate true; compatible file disclosure/scan; forbidden traversal | direct sensitive resource probe |
| 930120 / 5 | `/sys` in argument name | GET `/get?/sys/class=test` | query parameter name | `expect_ids:[930120]` | `direct` | candidate true; compatible file disclosure/scan; forbidden traversal | argument name도 raw query에 보임 |
| 930120 / 6 | `/sys` in value | GET `/get?test=/sys/class` | query value | `expect_ids:[930120]` | `direct` | candidate true; compatible file disclosure/scan; forbidden traversal | filesystem namespace probe |
| 930120 / 7 | `cat /etc/subuid` | GET `/get?code=cat+%2Fetc%2Fsubuid` | query value | `expect_ids:[930120]` | `direct` | candidate true; compatible command injection/file disclosure/scan; forbidden traversal | `cat` intent와 sensitive file가 함께 보이나 실행 success는 모름 |
| 930120 / 8 | `cat /etc/subuid-` | GET `/get?code=cat+%2Fetc%2Fsubuid-` | query value | `expect_ids:[930120]` | `direct` | candidate true; compatible command injection/file disclosure/scan; forbidden traversal | test 7과 같은 family |
| 930120 / 9 | write target `/tmp/curl` | GET `/get?code=>/tmp/curl` | query value | `expect_ids:[930120]` | `direct` | candidate true; compatible command injection/scan; forbidden traversal | disclosure보다는 shell/file-write intent. execution은 평가하지 않음 |
| 930120 / 10 | lookalike `>/tmp` | GET `/get?code=>/tmp` | query value | `no_expect_ids:[930120]` | `direct` | candidate false; forbidden traversal/file disclosure/command injection; negative control | incomplete redirection fragment로 보수 처리 |
| 930120 / 11 | `.environment` lookalike | GET `/get?code=>/test.environment` | query value | `no_expect_ids:[930120]` | `direct` | candidate false; forbidden high-confidence suspicious verdicts | `.env` suffix FP control |
| 930120 / 12 | `.dockery` email | GET `/get?code=firstname.dockery@host.tld` | query value | `no_expect_ids:[930120]` | `direct` | candidate false; forbidden high-confidence suspicious verdicts | `.docker` boundary FP control |
| 930120 / 13 | `.docker/secrets` | GET `/get?code=/path/to/.docker/secrets` | query value | `expect_ids:[930120]` | `direct` | candidate true; compatible file disclosure/scan; forbidden traversal | direct hidden sensitive directory |
| 930120 / 14 | `backup.sql.zip` | GET `/get?code=backup.sql.zip` | query value | `expect_ids:[930120]` | `direct` | candidate true; compatible file disclosure/scan; forbidden traversal | backup artifact probe |
| 930120 / 15 | `../.history` | GET `/get?code=../.history` | query value | `expect_ids:[930120]` | `direct` | candidate true; exact traversal | explicit `../`가 있으므로 direct history file case와 다름 |
| 930120 / 16 | `.history` in parameter name | GET `/get?history.history=test` | query parameter name | `no_expect_ids:[930120]` | `direct` | candidate false; forbidden high-confidence suspicious verdicts | hidden history filename FP control |
| 930120 / 17 | XML attribute `/etc/passwd` | POST `/post` | XML body attribute | `expect_ids:[930120]` | `out_of_scope`, `xml_body_not_logged` | not scored | Content-Type만 보임 |
| 930120 / 18 | `node_modules/.../package.json` | GET `/get?file=node_modules/some-package/package.json` | query value | `expect_ids:[930120]` | `direct` | candidate true; compatible file disclosure/scan; forbidden traversal | direct dependency metadata probe |

930120은 traversal benchmark 하나로 취급하면 안 된다. Tests 1, 3, 15만 explicit traversal strict family다. Test 2는 file disclosure strict family, tests 4~9, 13, 14, 18은 compatible-set direct resource/command-like family다. Tests 10~12, 16은 project annotation을 별도로 검토한 negative controls다.

## 11. Project-specific benchmark annotation

원본 YAML과 project expectation을 섞지 않는다. source adapter는 원본을 읽고 식별자와 request를 보존하며, 별도 manifest가 observability와 project taxonomy를 제공한다.

annotation은 최소 다음 질문에 답해야 한다.

- 이 signal은 현재 logs-only surface에 있는가.
- project ground truth는 `attack_positive`, `project_negative`, `not_scored` 중 무엇인가.
- candidate가 기대되는가.
- Stage1은 exact, compatible set, forbidden-only 중 무엇으로 평가하는가.
- actual verdict가 올바를 때 어떤 standards mapping이 필요한가.
- exploit success와 무관하다는 boundary note는 무엇인가.

source case가 바뀌어 checksum이 달라지면 자동으로 기존 annotation을 재사용하지 않는다. source drift review 후 annotation version을 올린다.

## 12. Fixture schema

추천 manifest case 예시는 다음과 같다.

```json
{
  "schema_version": "external_security_benchmark_case.v1",
  "case_id": "owasp_crs.930110.2",
  "benchmark_source": "owasp_crs",
  "source_revision": "96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a",
  "source_rule_id": 930110,
  "source_test_id": 2,
  "description": "Path Traversal Attack (/../) query string",
  "source_expectation": {
    "kind": "expect_ids",
    "ids": [930110]
  },
  "request": {
    "method": "GET",
    "request_target": "/get?arg=../../../etc/passwd",
    "http_version": "HTTP/1.1",
    "headers": {
      "User-Agent": "OWASP CRS test agent"
    }
  },
  "observability": {
    "eligible": true,
    "status": "direct",
    "surface": "request_target.query_value",
    "required_capabilities": ["raw_request", "raw_request_target", "query_string"],
    "exclusion_reason": null,
    "note": "Directory escape is visible in the request target."
  },
  "expected": {
    "project_ground_truth": "attack_positive",
    "candidate_expected": true,
    "classification_policy": "exact",
    "allowed_stage1_verdicts": ["suspicious_path_traversal"],
    "forbidden_stage1_verdicts": [
      "suspicious_sqli",
      "suspicious_xss",
      "suspicious_file_disclosure"
    ],
    "mapping_by_verdict": {
      "suspicious_path_traversal": {
        "required_ids": ["A01:2025", "CWE-22", "WSTG-ATHZ-01"],
        "forbidden_ids": ["CWE-552"]
      }
    },
    "boundary": "attempt_pattern_only_no_file_read_or_exploit_success"
  },
  "annotation": {
    "version": "owasp_crs_path_file_access.v1",
    "review_status": "approved",
    "note": "CRS rule ID is provenance, not the project verdict."
  }
}
```

Schema validation 규칙은 다음과 같다.

- `case_id`는 source revision 안에서 stable하고 unique하다.
- `status=direct`만 main score에서 `eligible=true`다.
- `exact`는 allowed verdict가 정확히 하나다.
- allowed/forbidden verdict set은 겹치지 않는다.
- `not_scored`는 `candidate_expected=null`, classification policy `not_scored`다.
- mapping expectation은 allowed verdict별로 둔다. compatible verdict가 서로 다른 올바른 mapping을 갖기 때문이다.
- `source_expectation`은 upstream 사실을 보존할 뿐 project label 계산에 직접 사용하지 않는다.

## 13. Positive/negative semantics

`expect_ids`는 “해당 CRS rule이 이 test transaction에서 log에 나타나야 한다”는 upstream regression expectation이다. 이것은 project `attack_positive`와 동일하지 않다.

`no_expect_ids`는 “해당 CRS rule이 나타나지 않아야 한다”는 rule-specific negative다. 이것은 모든 공격 family가 negative라는 뜻이 아니다. 예를 들어 어떤 930120 negative가 별도의 command-injection 구조를 포함한다면 project annotation은 그 구조를 독립 검토해야 한다.

첫 manifest는 다음 project ground truth를 사용한다.

```text
attack_positive  observable request pattern을 project attack taxonomy로 평가
project_negative isolated request가 forbidden high-confidence verdict를 만들면 안 되는 control
not_scored       현재 input surface에 핵심 signal이 없거나 annotation이 freeze되지 않음
```

project negative는 “정상 사용자 행위임이 증명됨”이 아니라 이 isolated fixture에서 명시한 forbidden verdict가 정당화되지 않는다는 뜻이다.

## 14. Allowed/forbidden verdict policy

모든 case에 exact label 하나를 강요하지 않는다.

### 14.1 exact

explicit directory escape처럼 의미가 명확한 case에 사용한다.

```json
{
  "classification_policy": "exact",
  "allowed_stage1_verdicts": ["suspicious_path_traversal"]
}
```

### 14.2 compatible set

외부 source가 project taxonomy를 위해 만들어지지 않았고 둘 이상의 project verdict가 합리적인 경우 사용한다.

```json
{
  "classification_policy": "compatible_set",
  "allowed_stage1_verdicts": [
    "suspicious_file_disclosure",
    "suspicious_scan"
  ],
  "forbidden_stage1_verdicts": [
    "suspicious_path_traversal"
  ]
}
```

compatible set은 score를 쉽게 만들기 위한 escape hatch가 아니다. 각 verdict가 왜 양립 가능한지 annotation note에 기록하고, manifest review에서 set 크기를 최소화한다.

### 14.3 forbidden-only negative control

negative case는 non-security verdict 하나를 exact로 강요하지 않는다. 증거가 약할 때 `inconclusive`는 정당할 수 있기 때문이다.

```json
{
  "project_ground_truth": "project_negative",
  "candidate_expected": false,
  "classification_policy": "forbidden_only",
  "allowed_stage1_verdicts": [
    "benign_normal",
    "likely_false_positive",
    "inconclusive"
  ],
  "forbidden_stage1_verdicts": [
    "suspicious_path_traversal"
  ]
}
```

isolated 930110/4~7에는 `suspicious_scan`을 기본 allowed로 넣지 않는다. sequence/repetition evidence가 없는 single lookalike이기 때문이다. 향후 multi-request scenario manifest가 scan context를 제공하면 별도 case로 annotate한다.

## 15. Primary metrics

`accuracy`라는 단일 이름은 observability exclusion, candidate gate, LLM classification을 숨기므로 사용하지 않는다.

### 15.1 eligibility accounting

항상 가장 먼저 다음 count를 표시한다.

```text
source_cases_total
directly_eligible_cases
partial_capability_cases
out_of_scope_cases
project_positive_eligible_cases
project_negative_eligible_cases
```

`observability_coverage = directly_eligible_cases / source_cases_total`은 score가 아니라 input coverage 지표다.

### 15.2 candidate recall

```text
candidate_recall_on_expected_candidates
  = selected cases 중 candidate_expected=true 수
    / eligible cases 중 candidate_expected=true 수
```

명백한 attack-positive eligible case가 filtered-out되면 candidate miss다. negative/low-signal case의 filtered-out은 failure가 아니다.

### 15.3 Stage1 compatibility

candidate selection과 분리하기 위해 primary Stage1 metric은 Stage1에 실제 도달한 positive case를 조건으로 한다.

```text
stage1_verdict_compatibility_given_candidate
  = actual verdict가 allowed set에 속한 positive cases
    / candidate로 선택되고 valid Stage1 output을 얻은 positive cases
```

candidate miss는 `classification=not_reached`이며 이 metric에서 두 번째로 중복 penalty하지 않는다. 다만 전체 pipeline 관점 diagnostic도 함께 낸다.

```text
end_to_end_verdict_compatibility
  = candidate selected AND verdict compatible인 positive cases
    / eligible positive cases
```

### 15.4 negative control pass rate

```text
negative_control_pass_rate
  = forbidden verdict가 발생하지 않은 eligible project-negative cases
    / validly evaluated eligible project-negative cases
```

- candidate가 기대대로 filtered-out되면 pass다.
- candidate로 올라가도 Stage1이 `likely_false_positive`, `benign_normal`, `inconclusive`로 보수 분류하면 pass다.
- case별 forbidden suspicious verdict가 나오면 fail이다.
- API/parser/evaluator error는 pass/fail이 아니라 run incomplete다. completeness가 100%가 아닌 run의 headline metric은 publish하지 않는다.

negative candidate gate 자체는 별도 diagnostic으로 둔다.

```text
negative_candidate_suppression_rate
  = filtered-out project-negative cases / eligible project-negative cases
```

이는 Stage1 false-positive resistance를 대체하지 않는다.

## 16. Standards mapping metric

Standards mapping은 secondary consistency metric이다.

```text
mapping_consistency_given_compatible_classification
  = actual allowed verdict에 해당하는 required/forbidden mapping contract를 만족한 cases
    / classification-compatible하고 mapping-applicable한 cases
```

상태를 명확히 분리한다.

| classification | mapping result |
| --- | --- |
| correct/compatible, mapping correct | pass |
| correct/compatible, mapping missing/wrong | fail |
| incorrect verdict | `not_scored_due_to_classification` |
| candidate miss | `not_reached` |
| non-security negative | `not_applicable` |

strict traversal은 A01/CWE-22/WSTG-ATHZ-01을 요구할 수 있다. direct file disclosure는 actual verdict가 `suspicious_file_disclosure`일 때 A02/CWE-552/WSTG-CONF branch를 평가한다. `suspicious_scan`이 compatible한 case는 scan branch에 맞는 별도 expectation을 사용하며 file-disclosure mapping을 강요하지 않는다.

## 17. Out-of-scope accounting

out-of-scope와 partial case를 false negative로 계산하지 않는다. 결과에는 source rule별 count와 reason breakdown을 반드시 남긴다.

초기 snapshot breakdown:

| reason | cases |
| --- | --- |
| `header_not_available` | 930100/1, 930100/4, 930110/1 |
| `post_body_not_logged` | 930110/3 |
| `multipart_filename_not_logged` | 930110/10, 930110/11 |
| `xml_body_not_logged` | 930100/5, 930110/13, 930120/17 |

header cases는 `partial`, 나머지 body cases는 `out_of_scope`다. reason count와 status count를 혼합하지 않는다.

현재 benchmark에서 다음은 계산하지 않는다.

- exploit/vulnerability confirmation accuracy
- file content disclosure, DB compromise, command execution, browser XSS execution
- authentication bypass success, compliance, CVE, impact
- response body correctness

## 18. LLM nondeterminism

세 실행 mode를 별도 artifact와 별도 metric series로 둔다.

### 18.1 replay

저장된 schema-valid Stage1 response를 replay한다.

- 장점: deterministic, 비용 없음, evaluator/mapping regression에 적합
- 한계: 현재 model behavior score가 아님
- 표기: `stage1_mode=replay`, response fixture revision과 생성 model/prompt commit을 기록

Replay headline은 “pipeline/evaluator regression”이며 “현재 LLM benchmark score”로 발표하지 않는다.

### 18.2 live single run

release candidate 또는 milestone에서 현재 provider/model로 한 번 실행한다.

- provider, exact model, mode, prompt code commit, timestamp, response ID, token usage를 기록한다.
- API availability와 schema failure를 run completeness에 포함한다.
- replay 수치와 한 평균으로 합치지 않는다.

### 18.3 repeated live runs

발표 전 대표 set을 3회, 중요한 milestone은 최대 5회 실행하는 방안을 권장한다.

case별로 다음 diagnostic을 기록한다.

```text
compatible_run_count / attempted_run_count
modal_verdict
verdict_distribution
unanimous_or_majority_compatible
mapping_stability
```

첫 구현 순서는 deterministic source conversion + Prepare-only + replay integration이다. 실제 모델 품질 headline은 이후 live validation에서만 만든다.

## 19. Benchmark runner architecture

```text
pinned external source
  -> source adapter (source semantics only)
  -> project manifest join
  -> normalized benchmark case
  -> Apache fixture adapter
  -> existing export/parser and/or Prepare
  -> Stage1 execution mode (replay/live)
  -> existing deterministic standards mapping
  -> evaluator
  -> separate benchmark result/report
```

책임 경계:

- source adapter는 `expect_ids`를 project verdict로 변환하지 않는다.
- manifest는 observability와 project expectation을 소유한다.
- Apache adapter는 request를 log row로 변환할 뿐 탐지 힌트를 주입하지 않는다.
- evaluator는 actual output을 해석하지만 production verdict/mapping을 수정하지 않는다.
- production code는 benchmark case ID나 CRS rule ID에 따라 다른 detection을 하지 않는다.

## 20. Synthetic Apache adapter options

### 20.1 normalized row direct supply

normalized request target에서 current export row를 만들어 existing `build_outputs`/Prepare에 공급한다.

권장 deterministic defaults:

```text
source_table = security
method = source method
raw_request = "<METHOD> <request_target> HTTP/1.1"
uri = request_target의 path component
query_string = source raw query, 선행 ? 포함
request_id = "bench-<case_id>"
src_ip = documentation range의 고정 IP
status_code = 200
response_body_bytes = 0
resp_content_type = ""
duration_us/ttfb_us = 0
referer = ""
user_agent = source User-Agent 또는 고정 neutral value
```

200/empty response metadata를 쓰는 이유는 request-pattern benchmark에서 synthetic 403/404/error boost가 candidate를 대신 만들지 않게 하기 위해서다. source request header 중 현재 schema에 있는 값만 채운다. body는 절대 query나 raw log에 복사하지 않는다.

장점은 빠르고 deterministic하다는 점이고, parser/log format을 검증하지 못한다는 한계가 있다.

### 20.2 serialized synthetic security log

`apache_security_core_v1` key-value line을 만들고 existing parser/export를 거쳐 Prepare에 넣는다. normalized row lane보다 느리지만 `%r`, `%U`, `%q`, quote/backslash preservation을 검증한다. Level 1 integration subset으로 권장한다.

### 20.3 actual local Apache

실제 HTTP request를 local Apache에 보내고 생성된 security/access log를 export한다. parser realism, Apache canonicalization, invalid/encoded target handling을 검증한다. 환경 의존성과 unsafe client normalization 때문에 전체 36건의 기본 CI lane으로 쓰지 않는다.

### 20.4 추천

- Level 1A: normalized row direct supply — 전체 27 directly eligible cases
- Level 1B: serialized log/parser — raw target, backslash, percent/NUL, bare-dot 대표 subset
- Level 2: actual Apache — 대표 positive/negative와 normalization-risk subset

## 21. Level 1 / Level 2 evaluation

### Level 1 — deterministic pipeline benchmark

```text
normalized manifest
  -> synthetic row/log
  -> Prepare
  -> replay/controlled Stage1 or explicit live submode
  -> deterministic mapping
  -> evaluation
```

주 목적:

- candidate selection coverage
- strict/compatible taxonomy handling
- negative lookalike resistance
- mapping contract와 evaluator regression
- source/manifest drift detection

controlled Stage1 stub은 runner plumbing만 검증하며 model classification score로 보고하지 않는다.

### Level 2 — E2E lab benchmark

```text
selected actual HTTP request
  -> local Apache
  -> actual security/access log
  -> parser/export
  -> Prepare
  -> live Stage1
  -> mapping/evaluator
```

주 목적:

- raw request target과 Apache normalization realism
- log format/parser/export 완전성
- 실제 model 포함 full pipeline 확인

추천 Level 2 첫 subset:

- positive: 930110/2, /8, /9; 930100/3; 930120/1, /2, /15
- negative: 930110/4, /5, /6, /7; 930120/11, /12, /16
- direct resource: 930120/4, /13, /14, /18 중 각 family 1개 이상

## 22. Provenance

첫 source snapshot:

```text
repository: https://github.com/coreruleset/coreruleset
revision: 96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a
retrieved_at: 2026-09-01
```

검증 checksum:

```text
930100.yaml  ba821dc9e205e932da60af2f5e9a9afe69597e8d2a07820ed264aba4bd1baa10
930110.yaml  d53c1f718a044bf5773b9efa77fd7d01f6b0c94ef152d9398df2aeb2762329f8
930120.yaml  333adb7b8264897893d6ce58ee46f5c8ab7e44fbde5dbb21f933dc27589abdd3
```

향후 repository layout 추천:

```text
benchmarks/
  README.md
  sources/
    owasp_crs/
      96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a/
        LICENSE
        SOURCE.json
        930100.yaml
        930110.yaml
        930120.yaml
  manifests/
    owasp_crs_path_file_access.v1.json
  fixtures/
    apache_security_core_v1/
  replays/
    <model-and-prompt-revision>/
  schemas/
```

OWASP CRS repository는 Apache License 2.0이다. vendoring 단계에서는 upstream 원본을 수정하지 않고 LICENSE/필요한 NOTICE와 source URL, revision, checksum을 함께 보존한다. project annotation은 별도 manifest에 둔다. 실제 redistribution 전 repository의 현재 LICENSE/NOTICE 요구를 다시 확인한다.

## 23. Result schema

추천 top-level result 예시는 다음과 같다.

```json
{
  "schema_version": "external_security_benchmark_result.v1",
  "benchmark": "owasp_crs_path_file_access.v1",
  "source_revision": "96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a",
  "project_revision": "f9835b3",
  "run": {
    "level": "level_1_normalized_row",
    "stage1_mode": "replay",
    "provider": "openai",
    "model": "example-model",
    "prompt_revision": "f9835b3",
    "attempts_per_case": 1,
    "started_at": "2026-09-01T00:00:00Z",
    "complete": true
  },
  "counts": {
    "source_cases_total": 36,
    "directly_eligible_cases": 27,
    "partial_capability_cases": 3,
    "out_of_scope_cases": 6,
    "project_positive_eligible_cases": 19,
    "project_negative_eligible_cases": 8,
    "validly_evaluated_cases": 27
  },
  "metrics": {
    "observability_coverage": 0.75,
    "candidate_recall_on_expected_candidates": 0.0,
    "stage1_verdict_compatibility_given_candidate": 0.0,
    "end_to_end_verdict_compatibility": 0.0,
    "negative_control_pass_rate": 0.0,
    "negative_candidate_suppression_rate": 0.0,
    "mapping_consistency_given_compatible_classification": 0.0
  },
  "out_of_scope_reason_counts": {
    "post_body_not_logged": 1,
    "multipart_filename_not_logged": 2,
    "xml_body_not_logged": 3
  },
  "partial_reason_counts": {
    "header_not_available": 3
  },
  "diagnostics": {
    "severity_distribution": {},
    "confidence_distribution": {},
    "stage1_error_count": 0,
    "verdict_stability": null
  },
  "cases": []
}
```

위 positive/negative count는 이 문서의 현재 proposed annotation 기준이다. manifest review에서 compatible family의 `candidate_expected`를 바꾸면 schema가 아니라 count만 달라진다. metric 값 `0.0`은 형식 예시이지 현재 pipeline 측정 결과가 아니다.

per-case result:

```json
{
  "case_id": "owasp_crs.930110.2",
  "source_rule_id": 930110,
  "source_test_id": 2,
  "observability": {
    "eligible": true,
    "status": "direct"
  },
  "expected": {
    "candidate_expected": true,
    "classification_policy": "exact",
    "allowed_verdicts": ["suspicious_path_traversal"]
  },
  "actual": {
    "candidate_selected": true,
    "prepare_verdict_hint": "path_traversal",
    "prepare_reason_hints": ["traversal:dotdot_slash(+4)"],
    "stage1_status": "completed",
    "verdict": "suspicious_path_traversal",
    "severity": "medium",
    "confidence": "high",
    "standards_ids": ["A01:2025", "CWE-22", "WSTG-ATHZ-01"]
  },
  "result": {
    "candidate": "pass",
    "classification": "pass",
    "standards_mapping": "pass",
    "overall_case": "pass"
  },
  "boundary": {
    "exploit_success_evaluated": false,
    "file_contents_disclosed_evaluated": false
  }
}
```

candidate miss case는 classification/mapping을 `not_reached`로, classification mismatch case의 mapping은 `not_scored_due_to_classification`으로 기록한다.

## 24. Negative controls

첫 구현의 핵심 negative controls:

- 930110/4 `/foo../1234`
- 930110/5 `/foo.../1234`
- 930110/6 `/..foo`
- 930110/7 bare `/..`
- 930120/10 `>/tmp`
- 930120/11 `/test.environment`
- 930120/12 `firstname.dockery@host.tld`
- 930120/16 `history.history=test`

두 종류의 boundary를 검증한다.

```text
segment-bound directory escape vs embedded/lookalike dots
sensitive file/directory token vs longer benign-looking token boundary
```

negative candidate가 Stage1까지 올라오는 것 자체는 최종 false positive와 같지 않다. Prepare gate와 Stage1 forbidden verdict를 별도로 기록한다. 다만 negative가 반복해서 candidate가 되면 비용/운영 부담 diagnostic으로 남는다.

## 25. Existing project guardrails

기존 `/private/secret.txt` regression과 CRS direct resource case의 관계는 다음과 같다.

- direct sensitive path는 explicit traversal이 아니다.
- 직접 접근이 file disclosure/scan context일 수는 있으나 파일 존재·노출을 증명하지 않는다.
- 930120이 OS file access pattern으로 match해도 project Stage1이 traversal이어야 하는 것은 아니다.
- direct `/etc/passwd`가 LFI-like parameter value로 주어지면 단순 direct route보다 file-read intent가 강하므로 `suspicious_file_disclosure`를 기대할 수 있다.
- `.ssh/id_rsa`, `.docker/secrets`, backup, node_modules metadata는 application context가 없으므로 compatible `{file_disclosure, scan}`을 허용하되 traversal을 금지한다.
- `../.history`는 explicit escape가 있으므로 traversal strict case다.

이 benchmark는 기존 guardrail을 완화하지 않고 외부 case에 확장한다.

## 26. Regression plan

구현 후 regression layer를 다음처럼 분리한다.

1. source integrity: pinned SHA와 file checksum 검증
2. source adapter: 모든 source test ID inventory와 original expectation 보존
3. manifest schema: unique ID, enum, allowed/forbidden disjoint, count 합계 검증
4. observability: header/body case가 main denominator에 들어오지 않는지 검증
5. Apache adapter golden: raw target, query, backslash, percent/NUL 표현 보존
6. Prepare-only: candidate expected positive/negative와 filtered reason 기록
7. replay evaluator: exact/compatible/forbidden-only semantics와 `not_reached` 처리
8. mapping: compatible verdict별 expected mapping, classification mismatch 시 not-scored 처리
9. result accounting: 36 = 27 direct + 3 partial + 6 out-of-scope
10. Level 2 smoke: selected cases의 real Apache log fidelity

Live LLM 결과는 일반 unit CI의 hard gate로 시작하지 않는다. deterministic replay와 contract tests를 CI gate로 두고, live validation은 milestone job/report로 운영한 뒤 안정성 자료가 쌓이면 별도 threshold를 검토한다.

## 27. Performance/cost

첫 source는 36건, directly eligible 27건으로 작다. Prepare-only와 replay는 CI에서 충분히 가볍다. 비용은 live Stage1 call 수가 지배한다.

```text
single live 최대: candidate로 선택된 eligible case 수
3회 반복 최대: 27 x 3 = 81 case-attempts
5회 반복 최대: 27 x 5 = 135 case-attempts
```

실제 call 수는 filtered-out case 때문에 더 작을 수 있지만 candidate recall을 높이기 위해 count를 줄이는 것을 목표로 삼지 않는다. 결과에는 input/output token과 latency를 기록하고 replay cache key에 project revision, prompt revision, provider/model, normalized case hash를 포함한다.

model price는 시간에 따라 바뀌므로 manifest나 score에 고정 비용을 넣지 않는다. 실행 시점의 usage와 별도 cost calculation metadata를 report한다.

## 28. Future CSIC/ECML expansion

### CSIC 2010

CRS 다음 단계의 HTTP request corpus adapter 후보로 둔다. GET query와 POST body가 함께 있는 자료라도 현재 main score에는 logs-only로 observable한 request target/header subset만 넣는다. body-only attack을 false negative로 계산하지 않는다. 원 자료가 오래되고 synthetic/lab 성격이며 timestamp가 없거나 제한적일 수 있으므로 sequence/bruteforce metric에 바로 쓰지 않는다.

### ECML/PKDD 2007 Web Traffic Attack Challenge

challenge는 HTTP query log에서 multi-class/context classification과 attack substring isolation을 다뤘다. project taxonomy와 class가 다르므로 CRS와 동일하게 source class를 Stage1 verdict로 자동 매핑하지 않는다. context-dependent 또는 out-of-context label은 current single-request Level 1과 별도 scenario manifest가 필요하다.

### import 전 공통 gate

- 원본 source와 license/provenance를 1차 출처에서 다시 확인
- raw/converted/repackaged 자료를 구분하고 checksum 고정
- request surface별 observability inventory
- label semantics와 project taxonomy annotation review
- train/test leakage, duplicate, generated traffic 특성 기록
- timestamp/sequence 유무에 따른 metric 제한

CSIC/ECML의 third-party repackaged repository는 discovery aid로만 사용할 수 있으며 canonical source로 바로 vendor하지 않는다.

## 29. Implementation phases

### Phase 5B-1 — source adapter + normalized manifest

- pinned CRS source vendoring, license/source metadata
- 36 case source inventory parser
- project manifest schema와 v1 annotation freeze
- source drift/checksum validation

### Phase 5B-2 — Apache synthetic adapter + Prepare-only

- Level 1A normalized row adapter
- representative Level 1B security log/parser lane
- candidate recall, negative candidate suppression, observability report

### Phase 5B-3 — Stage1 replay/live runner

- saved response replay contract
- live single run metadata/completeness
- optional 3/5 repeated stability report
- exact/compatible/forbidden-only evaluator

### Phase 5B-4 — mapping consistency + report

- verdict-specific mapping contract
- classification-dependent mapping status
- JSON/Markdown report와 source/eligibility breakdown
- production Security Standards Summary와 분리된 artifact

### Phase 5C — CSIC 2010 adapter

- provenance/license 확인 후 logs-only eligible subset
- GET/query 중심 시작, body cases exclusion accounting

### Phase 5D — ECML/PKDD auxiliary evaluation

- multi-class/context semantics 조사
- project annotation과 scenario-level adapter
- CRS/CSIC score와 별도 dataset series

## 30. Final recommendation

1. 첫 manifest는 pinned CRS 36건을 모두 보존하되 main score는 direct 27건만 사용한다.
2. 930110 query/path traversal과 negative lookalike을 첫 strict core로 삼는다.
3. 930100 encoded cases는 current decode contract의 coverage test로 유지한다.
4. 930120은 traversal, direct file disclosure, compatible resource/scan, command-like, negative control로 나눠 annotate한다.
5. exact verdict는 explicit traversal과 `/etc/passwd` LFI-like direct probe에 제한하고, context가 부족한 direct resource는 작은 compatible set을 사용한다.
6. candidate recall, Stage1 compatibility, negative pass, mapping consistency를 서로 다른 denominator로 보고한다.
7. replay는 regression, live는 model validation, repeated live는 stability로 이름과 artifact를 분리한다.
8. Level 1은 전체 eligible case를 deterministic하게 돌리고 Level 2는 normalization-risk와 대표 family만 표본 검증한다.
9. benchmark result는 별도 artifact다. Stage2/Viewer의 Security Standards Summary나 production finding count에 섞지 않는다.
10. Phase 5B 구현 전 manifest annotation review를 먼저 freeze한다. detection 변경은 benchmark baseline을 한 번 측정한 뒤 별도 change로 다룬다.

---

## Appendix A. 필수 질문에 대한 답

### 1. CRS `expect_ids`를 우리 positive label로 그대로 사용할 수 있는가?

아니다. CRS rule-specific regression expectation일 뿐 Stage1 taxonomy나 exploit ground truth가 아니다. project manifest를 별도 작성한다.

### 2. 어떤 CRS test는 Apache logs-only에서 평가 불가능한가?

- XML body: 930100/5, 930110/13, 930120/17
- form POST body: 930110/3
- multipart filename/body: 930110/10, /11
- 현재 없는 arbitrary header: 930100/1, /4, 930110/1은 partial capability group

### 3. GET query-based traversal 중 첫 benchmark에 사용할 수 있는 것은 무엇인가?

930100/2, /3; 930110/2, /8, /9, /12; 930120/1, /3, /15를 우선 사용한다. 930110/4~7과 930120 negative는 negative controls다.

### 4. direct `/etc/passwd`를 무엇으로 기대하는가?

930120/2처럼 LFI-like parameter value이면 `suspicious_file_disclosure`를 exact 기대하고 `suspicious_path_traversal`과 CWE-22를 금지한다. 실제 파일 노출 성공은 평가하지 않는다.

### 5. negative CRS cases는 어떤 expectation으로 사용하는가?

source `no_expect_ids`를 보존한 뒤 project별 forbidden-only negative control로 annotate한다. filtered-out, benign, likely FP, inconclusive는 pass 가능하며 case별 forbidden high-confidence verdict가 나오면 fail이다.

### 6. candidate selection과 Stage1 classification을 별도 metric으로 보는가?

그렇다. candidate recall과 Stage1 compatibility-given-candidate를 분리하고, end-to-end compatibility를 보조로 낸다.

### 7. exact와 allowed set 중 무엇을 사용하는가?

둘 다 사용한다. explicit traversal은 exact, direct sensitive resource처럼 project taxonomy상 둘 이상의 합리적 해석이 있는 case는 최소 compatible set을 사용한다. negative는 forbidden-only가 기본이다.

### 8. standards mapping은 어느 수준에서 평가하는가?

classification-compatible case에 한해 secondary consistency metric으로 평가한다. verdict가 틀린 case의 mapping은 `not_scored_due_to_classification`이다.

### 9. live LLM nondeterminism은 어떻게 다루는가?

deterministic replay를 regression에 사용하고 live single run을 별도 validation으로 운영한다. 발표 전 대표 set은 3회 또는 5회 반복해 verdict distribution과 compatibility stability를 보고한다.

### 10. 외부 benchmark score와 Security Standards Summary를 어떻게 분리하는가?

benchmark는 별도 JSON/Markdown artifact와 별도 count/metric을 가진다. production Stage2 aggregate/Viewer Security Standards Summary에 fixture case나 score를 삽입하지 않는다. mapping output은 per-case consistency 검사 입력으로만 읽는다.

## Appendix B. Source references

- OWASP CRS official repository: <https://github.com/coreruleset/coreruleset>
- pinned 930 test directory: <https://github.com/coreruleset/coreruleset/tree/96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a/tests/regression/tests/REQUEST-930-APPLICATION-ATTACK-LFI>
- pinned rule definition: <https://github.com/coreruleset/coreruleset/blob/96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf>
- OWASP CRS license: <https://github.com/coreruleset/coreruleset/blob/96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a/LICENSE>
- ECML/PKDD 2007 Web Traffic Attack Challenge: <https://www.lirmm.fr/pkdd2007-challenge/>

