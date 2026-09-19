# Final Demo Casebook

## 1. 역할

이 문서는 최종 발표와 시연에서 사용할 대표 사례와 **각 사례가 보여줘야 하는 의미 경계**를 정리한다.

현재 runtime 구조는 [Current Architecture](../00_current_architecture.md), 표현 경계는 [Apache logs-only Evidence Boundary](../00_apache_logs_only_evidence_boundary.md), revision별 검증 상태는 [Final Verification Record](./final-verification-record.md)를 따른다.

이 문서는 공격 성공을 증명하는 사례집이 아니다.

~~~text
관찰 입력
  -> Prepare / Stage1 / Standards / Stage2 처리
  -> 사람이 검토할 결과

!= exploit success proof
~~~

## 2. 공통 발표 원칙

모든 사례에 다음 경계를 적용한다.

~~~text
candidate-excluded != benign
no_signal != safe
HTTP status != exploit success
file/resource request != file disclosure success
SQLi-like request != DB execution
XSS-like request != browser execution
CMDi-like request != command execution
Standards Mapping != vulnerability confirmation
Standards Summary != compliance score
~~~

발표에서는 다음 세 층을 분리한다.

1. Apache 로그에서 실제로 관찰된 것
2. 시스템이 구조화하거나 분류한 것
3. 현재 evidence로는 확정할 수 없는 것

## 3. 권장 Demo 순서

실제 Web UI 시연의 기본 순서:

~~~text
Dashboard
  -> Live Monitoring
  -> selected logs / Analysis Job
  -> Job Detail
  -> Analysis Viewer
~~~

새 provider-backed Job을 현장에서 즉석 실행하는 대신, 동일한 흐름으로 미리 완료·검증한 Job을 사용해도 된다.

본편에서는 다음 4개 의미를 우선 보여준다.

1. suspicious request를 candidate로 보존
2. normalization/decoding의 필요성
3. candidate와 context/resource taxonomy 구분
4. false-positive 억제와 logs-only limitation

## 4. Primary Demo

### CASE-01 — PHP wrapper / file-resource

근거:

- `tests/fixtures/prepare_regression/e_r2_php_wrapper.json`
- 대응 expected contract
- traversal/file-disclosure semantic tests

관찰 포인트:

- PHP filter/resource structure
- encoded resource reference
- HTTP status/size는 보조 metadata

시스템이 할 수 있는 것:

- Prepare candidate와 deterministic hint 구성
- Stage1 evidence-based classification
- 해당 verdict에 대한 Standards Mapping enrichment

확정하지 않는 것:

- 실제 source/file 내용 반환
- credential 노출
- file disclosure success
- server compromise

발표 문장:

> PHP wrapper/resource pattern은 분석 후보로 보존하지만, HTTP 상태만으로 파일 노출 성공을 말하지 않습니다.

### CASE-02 — Double-encoded SQLi

근거:

- `tests/fixtures/prepare_regression/b_r2b_double_encoded_sqli.json`
- 대응 expected contract

관찰 포인트:

- URL decode depth
- quote / boolean / SQL comment-like structure

시스템이 할 수 있는 것:

- normalized variant에서 SQLi-like structure 관찰
- candidate 보존
- Stage1 classification 및 standards enrichment

확정하지 않는 것:

- DB query 실행
- data extraction
- authentication bypass
- SQL injection weakness 존재

발표 문장:

> 두 단계 정규화로 드러나는 SQLi-like request를 분석할 수 있지만, DB 공격 성공을 의미하지는 않습니다.

### CASE-03 — Traversal vs direct resource

근거:

- traversal/file-disclosure semantic tests
- direct config/resource fixtures
- frozen CASE-03 runtime/artifact evidence

현재 상태:

~~~text
runtime / artifact identity: PASS / FROZEN
evidence freeze: PASS / FROZEN
~~~

관찰 포인트:

- bounded dot-dot traversal syntax
- direct sensitive-resource request
- candidate와 context/resource signal 구분

시스템이 할 수 있는 것:

- traversal syntax와 direct resource를 orthogonal signal로 유지
- direct resource request만으로 traversal/CWE-22로 승격하지 않음
- Viewer에서 candidate/context 역할을 구분

확정하지 않는 것:

- requested resource 실제 존재
- file read 성공
- traversal success

발표 문장:

> 민감한 파일 이름이 보인다고 모두 traversal로 보지 않고, 경로 탈출 구문과 direct resource request를 구분합니다.

### CASE-04 — HTML entity XSS

근거:

- `tests/fixtures/prepare_regression/c_html_entity_xss.json`
- 대응 expected contract
- CMDi/XSS semantic tests

관찰 포인트:

- HTML entity decoding
- executable-looking event/script context

확정하지 않는 것:

- reflection
- browser JavaScript execution
- cookie/browser-data access
- XSS weakness 존재

발표 문장:

> HTML entity decode는 request 의도를 읽기 위한 정규화이며, browser 실행 성공을 증명하지 않습니다.

### CASE-05 — XSS false-positive boundary

근거:

- `tests/fixtures/prepare_regression/c_xss_fp_review.json`
- 대응 expected contract
- CMDi/XSS semantic tests

관찰 포인트:

- XSS 관련 keyword
- executable assignment/context 부재
- filtered / false-positive-review context

시스템이 할 수 있는 것:

- keyword-only 입력을 candidate로 과승격하지 않음
- filtered/context 근거를 보존

확정하지 않는 것:

- benign/safe
- 사용자의 실제 의도
- XSS weakness 부재

발표 문장:

> 공격 관련 단어가 있어도 executable context가 없으면 candidate로 과승격하지 않으며, 제외는 안전 판정이 아닙니다.

### CASE-06 — CMDi bounded grammar

근거:

- CMDi/XSS semantic tests
- verified selected-log Job runtime
- Viewer presentation verification

대표 request:

~~~text
GET /search?cmd=%3Bps
~~~

최근 verified evidence:

~~~text
Prepare
  -> cmdi:semicolon_exec 계열 signal

Stage1
  -> suspicious_command_injection

Standards
  -> CWE-78
  -> WSTG-INPV-12
  -> OWASP Injection-related enrichment

Stage2 / Viewer
  -> CMDi-like request
  -> command execution unverified
~~~

현재 상태:

~~~text
runtime / artifact identity: PASS / FROZEN
Viewer presentation: PASS
~~~

시스템이 확정하지 않는 것:

- OS command 실행
- reverse shell / outbound connection
- RCE success
- server compromise

발표 문장:

> shell separator와 bounded command context를 관찰해 CMDi-like request로 분류하지만, 실제 명령 실행 여부는 확인할 수 없습니다.

## 5. Supporting Demo

### CASE-S01 — Directory probe / context-only

목적:

- 반복적인 probe-like request를 context로 요약할 수 있음을 보여준다.
- context-only가 finding으로 자동 승격되지 않는다는 점을 설명한다.

~~~text
context-only != finding
~~~

### CASE-S02 — Static / crawler baseline

목적:

- baseline/crawler-like context가 candidate 의미와 분리됨을 보여준다.
- User-Agent나 반복 패턴만으로 실제 crawler identity를 확정하지 않는다는 점을 설명한다.

~~~text
baseline-like != benign
crawler-like != verified crawler identity
~~~

## 6. 화면 연결

발표에서는 artifact 파일 자체보다 Web UI의 다음 화면을 우선한다.

| 단계 | 화면 | 설명 |
| --- | --- | --- |
| 관찰 | Live Monitoring | 최근 security log와 선택 대상 |
| 선택 | Live selected rows | exact selected IDs |
| 분석 | Job Detail | lifecycle, event, usage, artifacts |
| 검토 | Analysis Viewer | Finding / Context / Supporting Event |
| taxonomy | Viewer standards 영역 | Mapping / Summary의 deterministic 의미 |

필요한 기술 질문이 들어올 때만 Prepare/Stage1 raw artifact를 보조 자료로 사용한다.

## 7. 발표 금지 표현

별도 evidence가 없으면 다음을 말하지 않는다.

- 공격 성공
- 침해 성공
- SQL injection 성공
- XSS 실행 성공
- RCE 성공
- 파일 유출 성공
- 취약점 확인
- OWASP 위반 확정
- CWE 발생 확인
- 정상/안전 판정

권장 표현:

- SQLi-like request pattern
- XSS-like request pattern
- CMDi-like grammar
- traversal syntax signal
- sensitive-resource request
- analysis candidate
- classified finding
- deterministic standards enrichment
- context-only
- candidate-excluded

## 8. 현재 발표 준비 상태

CASE-03과 CASE-06은 runtime/evidence 측면에서 발표 가능한 상태다.

최종 발표 준비에서 남은 것은 기술 구현보다 다음 산출물 정리다.

- PPT
- demo 순서
- fallback screenshot/video
- 발표 스크립트
- Q&A
- 리허설

revision별 검증 근거는 [Final Verification Record](./final-verification-record.md)를 우선한다.
