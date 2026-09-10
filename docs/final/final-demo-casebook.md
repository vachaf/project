# Final Demo Casebook

## 1. 목적

이 문서는 2026년 9월 Final 발표와 시연에서 사용할 대표 security-analysis 사례를 고정한다. 목표는 많은 benchmark 수치나 공격 family를 나열하는 것이 아니라, Apache logs-only 분석이 무엇을 관찰하고 어디까지 보수적으로 해석하는지 보여주는 것이다.

- 기준 revision: 429615aee91903ae84390f541687e97160390eca
- 기준 범위: [final-scope.md](./final-scope.md)
- runtime 구조: [Current Architecture](../00_current_architecture.md)
- 증거 표현 기준: [Apache logs-only evidence boundary](../00_apache_logs_only_evidence_boundary.md)
- fixture와 문서 권위: [design index](../design/README.md)
- 기존 대표 샘플 review: [A~F세트 대표 샘플 6선](../reviews/99_A-F세트_대표샘플_6선.md)

이 문서는 fixture와 source/test를 읽어 선정한 사례집이다. Fixture reviewed는 fixture와 current expected/test contract를 읽었다는 뜻이며, Runtime verification pending은 현재 revision에서 실제 Job, Viewer, regression을 실행해 검증하지 않았다는 뜻이다.

## 2. Demo 선정 원칙

이 Casebook의 Primary + Supporting Demo는 다음 의미 경계를 균형 있게 보여준다.

1. suspicious pattern의 관찰
2. encoded/normalized evidence의 해석
3. file/resource request와 traversal taxonomy의 구분
4. false-positive suppression
5. context-only 또는 candidate-excluded의 경계
6. logs-only 한계와 bounded grammar

각 사례는 다음 세 문장을 분리한다.

~~~text
관찰 입력: Apache 로그에서 실제로 보이는 request metadata와 패턴
시스템 판단: Prepare/Stage1/Mapping/Stage2가 보수적으로 할 수 있는 처리
비확정 사항: response body, DB, browser, OS, 인증 또는 서버 상태가 없으면 말할 수 없는 것
~~~

Security Standards Mapping은 deterministic relationship/enrichment이며 finding-level enrichment다. Security Standards Summary는 deduplicated finding 기반 deterministic aggregate다. 둘 다 attack detector, 취약점 존재 확인, OWASP 위반 확정 또는 CWE 발생 확인으로 표현하지 않는다.

## 3. 공통 Evidence Boundary

모든 사례에 다음 공통 경계를 적용한다.

~~~text
관찰 신호 없음 != 정상 != 안전
candidate-excluded != benign
HTTP 200 / 403 / 500 != 공격 성공 또는 실패의 단독 확정
file/resource request != 실제 파일 노출 확인
XSS-like request != browser 실행 확인
SQLi-like request != DB 실행 또는 데이터 추출 확인
CMDi-like request != OS command 실행 확인
~~~

발표에서는 request path, query, method, status, 반복 패턴, deterministic hint를 관찰 근거로만 쓴다. response body, application/auth/DB log, file system, browser telemetry가 없으면 exploit success, compromise, data disclosure, login success를 확정하지 않는다.

각 Primary Demo의 공통 상태는 다음과 같다.

~~~text
Fixture/test evidence reviewed
Runtime verification pending
Final demo fixture freeze 전 실제 Job/Viewer 재현 필요
~~~

## 4. Primary Demo 6개

### CASE-01 — PHP wrapper / file-resource

#### 근거 파일

- [e_r2_php_wrapper fixture](../../tests/fixtures/prepare_regression/e_r2_php_wrapper.json)
- [e_r2_php_wrapper expected contract](../../tests/expected/prepare_regression/e_r2_php_wrapper.expected.json)
- [traversal/file-disclosure semantic test](../../tests/test_prepare_traversal_file_disclosure_semantics.py)

#### 관찰 입력

GET /file 요청의 target parameter에 php://filter, base64 conversion, config.php resource를 가리키는 encoded PHP wrapper pattern이 있다. fixture에는 HTTP 200과 response size도 기록돼 있으나, 이것만으로 response body 내용을 알 수는 없다.

#### 시스템이 할 수 있는 판단

- Prepare에서 PHP filter wrapper, base64 source intent, resource parameter signal을 가진 analysis candidate로 보존할 수 있다.
- Stage1은 evidence 기반 분류를 수행할 수 있다.
- Stage1 결과가 해당 mapping 규칙의 대상이면 Security Standards Mapping에 deterministic relationship/enrichment를 부가할 수 있다.

#### 시스템이 확정하지 않는 것

- config.php 또는 source 내용이 실제로 반환됐는지
- base64 결과에 credential이 있었는지
- 파일 노출, 취약점 존재, 서버 침해가 확인됐는지

#### 발표 핵심 한 문장

PHP wrapper pattern은 file/resource disclosure 시도로 보이는 요청을 보존하지만, HTTP 200만으로 파일 노출 성공을 말하지 않는다.

#### 화면에서 보여줄 위치

- Prepare artifact의 candidate와 reason hints
- Stage1 result의 evidence/limitations
- Standards Mapping과 Report Viewer finding

#### 주의할 표현

파일 노출 확인, config 유출 성공, credential 탈취라는 표현을 쓰지 않는다. Mapping은 deterministic enrichment라고 설명한다.

#### Final 사용 상태

Primary Demo — Fixture reviewed / Runtime verification pending.

### CASE-02 — Double-encoded SQLi

#### 근거 파일

- [b_r2b_double_encoded_sqli fixture](../../tests/fixtures/prepare_regression/b_r2b_double_encoded_sqli.json)
- [b_r2b_double_encoded_sqli expected contract](../../tests/expected/prepare_regression/b_r2b_double_encoded_sqli.expected.json)
- [A~F세트 review의 B세트 설명](../reviews/99_A-F세트_대표샘플_6선.md)

#### 관찰 입력

GET /search 요청의 q parameter에 two-pass decoding이 필요한 quote, boolean condition, comment-like SQLi pattern이 있다. fixture는 HTTP 200을 기록하지만 DB response나 query result는 제공하지 않는다.

#### 시스템이 할 수 있는 판단

- Prepare가 decoded depth 2와 SQLi structure hint를 근거로 analysis candidate를 보존하도록 기대 contract가 정의돼 있다.
- Stage1은 SQLi-like request pattern을 evidence로 분류할 수 있다.
- 대상 Stage1 verdict에 대해서만 CWE/WSTG 등의 deterministic mapping enrichment가 가능하다.

#### 시스템이 확정하지 않는 것

- SQL query가 실행됐는지
- DB error, data extraction, authentication bypass가 발생했는지
- 애플리케이션에 SQL injection weakness가 존재하는지

#### 발표 핵심 한 문장

한 번의 decode로 보이지 않는 request pattern도 두 단계 정규화로 분석 후보가 될 수 있지만, 이것은 DB 공격 성공의 증거가 아니다.

#### 화면에서 보여줄 위치

- Prepare artifact의 decoded-depth와 SQLi reason hints
- Stage1 evidence
- Report Viewer finding과 Standards Mapping

#### 주의할 표현

SQL injection 성공, DB dump, 데이터 유출, CWE-89 확인이라는 표현을 피한다.

#### Final 사용 상태

Primary Demo — Fixture reviewed / Runtime verification pending.

### CASE-03 — Traversal vs direct resource

#### 근거 파일

- [traversal/file-disclosure semantic test](../../tests/test_prepare_traversal_file_disclosure_semantics.py)
- [e_r2_direct_config_path fixture](../../tests/fixtures/prepare_regression/e_r2_direct_config_path.json)
- [e_r2_direct_config_path expected contract](../../tests/expected/prepare_regression/e_r2_direct_config_path.expected.json)

#### 관찰 입력

semantic test는 ../../etc/passwd 같은 bounded dot-dot path escape와 direct OS file token을 서로 다른 signal로 다룬다. direct fixture는 /config.php와 /admin/config.php 요청 두 건을 HTTP 404 metadata와 함께 제공한다.

#### 시스템이 할 수 있는 판단

- bounded dot-dot escape는 traversal syntax signal로, direct OS file token은 sensitive resource signal로 각각 관찰할 수 있다.
- 두 signal이 함께 있어도 같은 의미로 합치지 않고 orthogonal하게 유지할 수 있다.
- direct config path fixture는 low-signal filtered context로 남기고 PHP wrapper disclosure hint를 상속하지 않도록 expected contract가 정의돼 있다.

#### 시스템이 확정하지 않는 것

- direct config path가 실제 존재하는지
- requested resource가 노출됐는지
- traversal이 성공했는지
- 해당 서버에 파일 disclosure weakness가 존재하는지

#### 발표 핵심 한 문장

경로 탈출 구문과 민감 resource 이름은 별도 signal이며, 단순 config 경로 요청을 traversal 또는 파일 노출로 과승격하지 않는다.

#### 화면에서 보여줄 위치

- Prepare artifact의 filtered_out/context와 reason hints
- 후보가 아닌 direct-resource 행의 boundary 설명
- 필요 시 Stage1/Viewer에는 후보와 문맥의 차이만 표시

#### 주의할 표현

config.php 존재, file disclosure 확인, traversal 성공, CWE-22 확정이라는 표현을 쓰지 않는다.

#### Final 사용 상태

Primary Demo — Test/fixture reviewed / Runtime verification pending. Traversal의 Job/Viewer 재현 입력은 fixture freeze에서 별도로 고정한다.

### CASE-04 — HTML entity XSS

#### 근거 파일

- [c_html_entity_xss fixture](../../tests/fixtures/prepare_regression/c_html_entity_xss.json)
- [c_html_entity_xss expected contract](../../tests/expected/prepare_regression/c_html_entity_xss.expected.json)
- [CMDi/XSS semantic test](../../tests/test_prepare_cmdi_xss_candidate_semantics.py)

#### 관찰 입력

GET /search 요청의 q parameter에 HTML entity로 encoded된 script-like element와 alert call pattern이 있다. fixture의 HTTP 200과 text/html metadata는 reflection이나 browser execution을 증명하지 않는다.

#### 시스템이 할 수 있는 판단

- Prepare는 HTML entity decoded XSS hint와 XSS structure hint를 가진 analysis candidate를 보존하도록 expected contract가 정의돼 있다.
- Stage1은 executable-looking request pattern을 evidence로 분류할 수 있다.
- 해당 Stage1 verdict에는 deterministic standards mapping enrichment가 가능하다.

#### 시스템이 확정하지 않는 것

- browser에서 script가 실행됐는지
- cookie 또는 browser data가 접근·전송됐는지
- stored/reflected XSS weakness가 실제로 존재하는지

#### 발표 핵심 한 문장

HTML entity decode는 request 의도를 읽기 위한 정규화이며, HTTP 응답 metadata만으로 XSS 실행을 확정하지 않는다.

#### 화면에서 보여줄 위치

- Prepare artifact의 decoded XSS hint
- Stage1 evidence와 limitation
- Standards Mapping 및 Report Viewer finding

#### 주의할 표현

XSS 실행 성공, cookie 탈취, browser compromise, CWE-79 발생 확인이라는 표현을 피한다.

#### Final 사용 상태

Primary Demo — Fixture reviewed / Runtime verification pending.

### CASE-05 — XSS false-positive boundary

#### 근거 파일

- [c_xss_fp_review fixture](../../tests/fixtures/prepare_regression/c_xss_fp_review.json)
- [c_xss_fp_review expected contract](../../tests/expected/prepare_regression/c_xss_fp_review.expected.json)
- [CMDi/XSS semantic test](../../tests/test_prepare_cmdi_xss_candidate_semantics.py)

#### 관찰 입력

GET /search 요청은 onerror event handler에 관한 tutorial/search 문장이다. keyword는 XSS 문맥과 닮았지만 executable assignment나 payload structure를 직접 보여주지 않는다.

#### 시스템이 할 수 있는 판단

- expected contract는 이 요청을 false_positive_review_candidates 또는 filtered_out에 남길 수 있게 하고 analysis candidate로는 올리지 않도록 정의한다.
- onerror 단어 하나만 XSS event-handler evidence로 취급하지 않는 boundary를 설명할 수 있다.

#### 시스템이 확정하지 않는 것

- 요청이 benign 또는 안전한지
- 사용자의 의도나 실제 browser 동작
- XSS weakness의 부재

#### 발표 핵심 한 문장

공격 keyword가 있어도 executable context가 없으면 분석 후보로 과승격하지 않으며, 제외는 안전 판정이 아니다.

#### 화면에서 보여줄 위치

- Prepare artifact의 false-positive review 또는 filtered_out
- Job Detail의 candidate count와 filtered reason
- 후보 finding이 없는 경우 Viewer에 공격 결과를 억지로 만들지 않음

#### 주의할 표현

정상 요청, 무해함, XSS가 아님, 공격 차단 성공이라는 표현을 쓰지 않는다.

#### Final 사용 상태

Primary Demo — Fixture reviewed / Runtime verification pending.

### CASE-06 — CMDi bounded grammar

#### 근거 파일

- [CMDi/XSS semantic test](../../tests/test_prepare_cmdi_xss_candidate_semantics.py)
- [Current Architecture의 Prepare/Stage1 경계](../00_current_architecture.md)

#### 관찰 입력

semantic test는 cmd parameter의 shell separator와 bounded command vocabulary가 함께 있는 cmd=;ps 같은 request shape를 비교한다. 단순 whoami, cat notes, regedit, 일반 기호 문자열은 같은 CMDi evidence로 취급하지 않는 대비도 포함한다.

#### 시스템이 할 수 있는 판단

- shell grammar와 bounded command context가 함께 있을 때 Prepare candidate와 cmdi reason hint를 만들 수 있다.
- 단순 command-like word 또는 SQL DML은 CMDi evidence로 올리지 않는 경계를 설명할 수 있다.
- Stage1은 candidate evidence를 분류할 수 있고, 해당 verdict에 한해 deterministic mapping enrichment가 가능하다.

#### 시스템이 확정하지 않는 것

- OS command가 실행됐는지
- outbound connection, shell 획득, RCE가 성공했는지
- 서버 compromise가 확인됐는지

#### 발표 핵심 한 문장

CMDi는 명령어 단어 하나가 아니라 bounded shell grammar와 command context의 조합으로 후보화하며, 그 자체가 command execution 성공은 아니다.

#### 화면에서 보여줄 위치

- Prepare reason hints와 candidate boundary
- Stage1 evidence/limitation
- freeze 후 확보한 Job Detail 또는 Viewer finding

#### 주의할 표현

명령 실행 성공, RCE 성공, reverse shell 연결, 서버 장악이라는 표현을 쓰지 않는다.

#### Final 사용 상태

Primary Demo — Test reviewed / Runtime verification pending. 현재 dedicated Prepare regression fixture가 아닌 semantic test 근거이므로 demo fixture freeze 전 export fixture와 Viewer 재현을 별도로 고정한다.

## 5. Supporting Demo

### CASE-S01 — Directory probe / context-only

#### 근거 파일

- [d_r3_directory_probing fixture](../../tests/fixtures/prepare_regression/d_r3_directory_probing.json)
- [d_r3_directory_probing expected contract](../../tests/expected/prepare_regression/d_r3_directory_probing.expected.json)

#### 관찰 입력

같은 source IP가 짧은 시간 안에 /admin/, /backup/, /config/ 경로를 요청한다. fixture의 세 응답은 HTTP 404이며, 개별 경로 요청만으로 resource 존재 여부는 알 수 없다.

#### 시스템이 할 수 있는 판단

expected contract는 individual row를 analysis candidate로 승격하지 않고 directory probing burst를 probing_sequence_summary context로 보존하도록 정의한다.

#### 시스템이 확정하지 않는 것

admin/backup/config resource의 존재, 접근 성공, 침해 또는 reconnaissance tool의 실제 정체.

#### 발표 핵심 한 문장

여러 저신호 path request는 침해 결과로 만들지 않고 context-only probing 흐름으로 보존할 수 있다.

#### 화면에서 보여줄 위치

- Prepare artifact의 probing_sequence_summary
- Job Detail의 context count 또는 Report Viewer context

#### 주의할 표현

관리자 경로 발견, backup 노출, scan 성공이라는 표현을 쓰지 않는다.

#### Final 사용 상태

Supporting Demo — Fixture reviewed / Runtime verification pending.

### CASE-S02 — Static / crawler baseline

#### 근거 파일

- [h_r1_static_baseline_context fixture](../../tests/fixtures/prepare_regression/h_r1_static_baseline_context.json)
- [h_r1_static_baseline_context expected contract](../../tests/expected/prepare_regression/h_r1_static_baseline_context.expected.json)
- [h_r2_crawler_baseline_context fixture](../../tests/fixtures/prepare_regression/h_r2_crawler_baseline_context.json)
- [h_r2_crawler_baseline_context expected contract](../../tests/expected/prepare_regression/h_r2_crawler_baseline_context.expected.json)

#### 관찰 입력

favicon, robots.txt, sitemap.xml, static asset, health endpoint, normal browse와 crawler-like user agent가 있는 browse sequence가 fixture에 있다. HTTP 200, robots/sitemap path, crawler-like UA는 content, page existence 또는 crawler identity를 증명하지 않는다.

#### 시스템이 할 수 있는 판단

expected contracts는 static_baseline_summaries 또는 crawler_baseline_summaries를 context-only로 만들고 analysis candidate 수를 0으로 제한한다. crawler-like UA는 spoofable이며 정책·site structure·page existence를 추론하지 않는다는 hint를 보존한다.

#### 시스템이 확정하지 않는 것

robots/sitemap 내용, static file 노출, JavaScript 실행, health status, page existence, crawler의 실제 정체 또는 정상/안전 상태.

#### 발표 핵심 한 문장

정상처럼 보이는 static/crawler traffic도 안전 판정으로 바꾸지 않고, 관찰 가능한 baseline context로만 보존한다.

#### 화면에서 보여줄 위치

- Prepare artifact의 static_baseline_summaries 또는 crawler_baseline_summaries
- filtered_out reason hints

#### 주의할 표현

정상 트래픽 확인, 실제 Googlebot 확인, robots 내용 확인, 사이트 구조 확인이라는 표현을 쓰지 않는다.

#### Final 사용 상태

Supporting Demo — Fixture reviewed / Runtime verification pending.

## 6. 발표 순서 권장안

발표는 attack family 목록이 아니라 의미 경계를 단계적으로 이해시키는 순서를 따른다.

1. CASE-01 PHP wrapper: 명확한 suspicious file-resource pattern과 logs-only 한계
2. CASE-02 Double-encoded SQLi: 정규화가 왜 필요한지
3. CASE-03 Traversal vs direct resource: taxonomy와 candidate/context 구분
4. CASE-04 HTML entity XSS: encoded evidence와 browser execution 비확정
5. CASE-05 XSS false-positive boundary: keyword만으로 과승격하지 않음
6. CASE-06 CMDi bounded grammar: 신호를 좁게 정의하는 이유
7. CASE-S01/S02: context-only와 관찰 신호 없음이 안전을 뜻하지 않는다는 보조 설명

## 7. 화면 캡처 체크리스트

실제 캡처는 fixture freeze와 runtime verification 이후에만 만든다.

| 사례 | 권장 캡처 |
| --- | --- |
| CASE-01 | [ ] Job Detail  [ ] Prepare candidate/hints  [ ] Stage1 evidence  [ ] Standards Mapping  [ ] Viewer finding |
| CASE-02 | [ ] Prepare decoded hint  [ ] Stage1 evidence  [ ] Standards Mapping  [ ] Viewer finding |
| CASE-03 | [ ] Prepare filtered_out/context  [ ] candidate/context 비교 |
| CASE-04 | [ ] Prepare decoded hint  [ ] Stage1 limitation  [ ] Viewer finding |
| CASE-05 | [ ] Prepare false-positive review 또는 filtered_out  [ ] Job Detail count |
| CASE-06 | [ ] Prepare cmdi hint  [ ] Stage1 limitation  [ ] Job Detail 또는 Viewer |
| CASE-S01 | [ ] probing_sequence_summary  [ ] context display |
| CASE-S02 | [ ] static/crawler baseline summary  [ ] filtered reason |

Standards Summary는 finding이 여러 개인 최종 Job에서 aggregate 화면을 따로 확보한다. 단일 finding 사례의 Summary를 compliance, coverage score 또는 vulnerability count처럼 보이게 캡처하지 않는다.

## 8. 금지 주장 / 표현

| 피할 표현 | 발표에서 사용할 표현 |
| --- | --- |
| SQL injection 성공 | SQLi-like request pattern 관찰 |
| XSS 실행 성공 | XSS-like request pattern 관찰 |
| 파일 노출 확인 | file/resource request 또는 disclosure intent 관찰 |
| traversal 성공 | traversal syntax signal 관찰 |
| 명령 실행 또는 RCE 성공 | CMDi-like grammar와 command context 관찰 |
| 취약점 확인 또는 OWASP 위반 확정 | deterministic Security Standards Mapping 관계/enrichment |
| CWE 발생 확인 | 관련 CWE relationship/enrichment 가능 |
| 정상 또는 안전 | 관찰 신호 없음, candidate-excluded, context-only를 각각 그대로 설명 |
| HTTP 200이므로 성공 | HTTP 200은 response metadata이며 성공 증거가 아님 |
| crawler 확인 | crawler-like user agent 또는 browse pattern 관찰 |

## 9. Freeze 전 확인사항

2026-09-26 demo fixture freeze 전 각 Primary Demo에 대해 다음을 다시 확인한다.

- [ ] freeze revision과 fixture/expected/test path를 고정
- [ ] 실제 regression 결과를 별도 verification record에 기록
- [ ] 실제 full_report Job에서 artifact가 생성되는지 확인
- [ ] Stage1/Stage2/Viewer 재현 여부와 provider/환경을 기록
- [ ] Mapping과 Summary가 stored artifact에 있는지 확인
- [ ] 화면 캡처가 raw data·secret을 노출하지 않는지 확인
- [ ] CASE-03 traversal input의 Job/Viewer 재현 fixture를 고정
- [ ] CASE-06 CMDi bounded grammar의 dedicated export fixture와 Job/Viewer 재현을 고정
- [ ] runtime 결과와 fixture expected를 혼동하지 않도록 상태를 PASS, FAIL, BLOCKED, NOT RUN으로 기록

## 10. Appendix Regression Evidence

이 사례집의 본편은 representative demo이며 전체 offline verification 보고서가 아니다.

- Prepare regression fixtures와 expected contracts는 candidate, filtered, context-only, hint 경계를 보존하는 offline verification 근거다.
- OWASP CRS benchmark와 CSIC provenance chain은 source integrity, annotation, semantic validation, controlled review를 위한 appendix evidence다.
- Prepare full-output harness는 typed capture, identity, comparison을 위한 Conditional Final verification infrastructure다.

이 자료의 historical PASS, benchmark 수치, review 결론은 freeze revision의 current PASS로 표현하지 않는다. Final verification 결과는 별도 final-verification-record.md에서 관리해야 한다.
