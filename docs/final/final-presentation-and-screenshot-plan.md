# Final Presentation & Screenshot Plan

- 기준일: 2026-09-11
- 목적: 2026년 9월 말 Code Freeze 이후 Final 발표·시연·화면 캡처를 일관되게 준비하기 위한 canonical presentation plan
- 범위 기준: `docs/final/final-scope.md`
- runtime 기준: `docs/00_current_architecture.md`
- demo 기준: `docs/final/final-demo-casebook.md`
- limitation/terminology 기준: `docs/final/final-known-limitations.md`
- freeze 기준: `docs/final/final-status-and-freeze-criteria.md`

> 이 문서는 실제 screenshot을 지금 생성하는 문서가 아니다. Freeze revision과 runtime verification이 확정된 뒤 어떤 화면을 어떤 사례와 메시지에 연결해 확보할지를 미리 고정한다.

---

## 1. 목적과 기준

Final 발표의 목표는 기능 수를 많이 보여주는 것이 아니라, 다음 질문에 짧고 일관되게 답하는 것이다.

```text
무엇을 입력으로 받는가?
어떻게 분석하는가?
어떤 결과를 보여주는가?
어떤 근거를 보존하는가?
어디까지 말할 수 있고 어디부터는 말하지 않는가?
실제로 어디까지 검증했는가?
```

발표 본편의 중심은 현재 Final runtime이다.

```text
Apache Logs
→ MariaDB
→ DB-backed full_report Job
→ Analysis Job Worker
→ Export
→ Prepare
→ Stage1
→ Security Standards Mapping
→ Stage2
→ Security Standards Summary
→ Report Viewer
```

CRS/CSIC benchmark, Prepare full-output harness, Shared Extractor, Live 관련 Conditional 기능은 제품 본편과 검증/Conditional 영역을 구분해 설명한다.

---

## 2. 발표 핵심 메시지

### 2.1 제품 메시지

```text
Apache 로그를 그대로 나열하는 것이 아니라,
분석 후보·문맥·제외 근거를 분리하고,
LLM 분석과 deterministic standards enrichment를 거쳐
사람이 검토 가능한 보고서와 Viewer 결과로 정리한다.
```

### 2.2 증거 메시지

```text
관찰 가능한 로그 evidence를 기반으로 분석하되,
로그만으로 확인할 수 없는 exploit success,
취약점 존재, 침해 성공은 확정하지 않는다.
```

### 2.3 검증 메시지

```text
코드 존재 ≠ 실행 PASS
과거 PASS ≠ freeze revision PASS
PASS / FAIL / BLOCKED / NOT RUN을 분리한다.
```

### 2.4 범위 메시지

```text
Final ≠ 모든 아이디어 구현 완료
Conditional Final ≠ 실패
Deferred ≠ 버림
이번 Final은 핵심 경로의 재현성·설명 가능성·증거성을 우선한다.
```

---

## 3. 권장 발표 흐름

10~15분 발표를 기준으로 다음 순서를 권장한다.

### 3.1 문제와 목표 — 약 1분

- Apache access/security/error 로그가 누적된다.
- 단순 raw log 조회만으로는 조사 우선순위와 근거 정리가 어렵다.
- 모든 로그를 동일하게 LLM에 보내는 대신 deterministic preprocessing과 evidence-aware 분석 구조를 사용한다.

핵심 한 문장:

```text
로그를 자동으로 '공격 성공'으로 판정하는 시스템이 아니라,
관찰 근거를 분석·정리해서 사람이 검토할 수 있게 만드는 시스템입니다.
```

### 3.2 전체 Architecture — 약 1~1.5분

보여줄 것:

```text
Apache → MariaDB → Job → Worker
→ Export → Prepare → Stage1
→ Standards Mapping → Stage2
→ Standards Summary → Viewer
```

강조:

- Job/Worker 기반 비동기 분석
- artifact와 DB metadata 분리
- Standards Mapping/Summary가 detector가 아님

### 3.3 Prepare — 약 1분

```text
raw log
→ candidate
→ filtered / context-only
→ reason / evidence
```

강조:

- candidate-excluded ≠ benign
- context-only ≠ finding
- false-positive 억제
- encoded/normalized evidence 보존

### 3.4 Stage1 / Stage2 — 약 1분

- Stage1: candidate evidence 기반 분류
- Stage2: deduplicated finding 중심 종합
- Viewer가 verdict를 다시 계산하지 않음

### 3.5 Standards Mapping / Summary — 약 1분

```text
Mapping = finding-level deterministic enrichment
Summary = deduplicated finding aggregate
```

금지 설명:

```text
vulnerability scanner
compliance checker
OWASP violation detector
```

### 3.6 대표 Demo — 약 4~5분

본편 4개 사례를 권장한다.

```text
CASE-01 PHP wrapper / file-resource
CASE-02 Double-encoded SQLi
CASE-03 Traversal vs direct resource
CASE-05 XSS false-positive boundary
```

이 4개가 보여주는 핵심은 서로 다르다.

```text
명확한 suspicious request
→ normalization
→ taxonomy/evidence boundary
→ false-positive suppression
```

### 3.7 Evidence Boundary — 약 1분

```text
HTTP 200 ≠ exploit success
file/resource request ≠ 실제 파일 노출
SQLi-like request ≠ DB 실행
XSS-like request ≠ browser execution
CMDi-like request ≠ OS command execution
```

### 3.8 Verification / 상태 — 약 1분

```text
PASS
FAIL
BLOCKED
NOT RUN
```

Final / Conditional Final / Deferred와 Verification Status를 분리한다.

### 3.9 결론 — 약 30초

```text
기능 수를 늘리는 것보다
핵심 분석 경로를 실제로 재현하고
근거와 한계를 함께 설명할 수 있는 상태를 만드는 것을 우선했습니다.
```

---

## 4. 본편 Demo 선정

### 4.1 DEMO-P01 — PHP wrapper / file-resource

연결 Case: `CASE-01`

발표 가치:

- 첫 사례로 이해하기 쉽다.
- suspicious file/resource request를 보여준다.
- HTTP 200과 exploit success를 분리해 설명하기 좋다.
- Standards Mapping까지 연결하기 좋다.

발표 메시지:

```text
PHP wrapper와 resource pattern은 분석 후보로 보존하지만,
HTTP 200만으로 파일 유출 성공을 말하지 않습니다.
```

권장 화면:

```text
Prepare candidate
Stage1 evidence
Standards Mapping
Viewer finding
```

### 4.2 DEMO-P02 — Double-encoded SQLi

연결 Case: `CASE-02`

발표 가치:

- normalization이 필요한 이유를 설명한다.
- 단순 문자열 검색 이상의 preprocessing을 보여준다.
- encoded evidence와 decode depth 개념을 보여주기 좋다.

발표 메시지:

```text
한 번의 decode로 보이지 않는 SQLi-like pattern도
정규화 후 분석 후보가 될 수 있지만,
DB 실행 성공의 증거는 아닙니다.
```

권장 화면:

```text
Prepare decoded hint
Stage1 evidence
Viewer finding
```

### 4.3 DEMO-P03 — Traversal vs direct resource

연결 Case: `CASE-03`

발표 가치:

- traversal syntax와 sensitive-resource request를 구분한다.
- taxonomy distinction을 보여준다.
- 과도한 탐지/과승격을 피하는 설계를 설명하기 좋다.

발표 메시지:

```text
민감한 파일 이름이 보인다고 모두 traversal로 보지 않고,
경로 탈출 구문과 resource request를 별도 signal로 유지합니다.
```

권장 화면:

```text
Prepare candidate/context 비교
filtered/context artifact
```

주의: freeze 전 dedicated traversal reproduction fixture를 고정해야 한다.

### 4.4 DEMO-P04 — XSS false-positive boundary

연결 Case: `CASE-05`

발표 가치:

- keyword가 있어도 executable context가 없으면 candidate로 과승격하지 않는 점을 보여준다.
- false-positive suppression을 설명하기 가장 좋다.

발표 메시지:

```text
XSS 관련 keyword가 있다고 곧바로 공격 candidate로 만들지 않습니다.
제외는 정상 판정이 아니라 현재 policy상 candidate가 아니라는 뜻입니다.
```

권장 화면:

```text
filtered reason
false-positive review/context
Job Detail candidate count
```

---

## 5. 시간 여유 시 추가 Demo

### DEMO-O01 — HTML entity XSS

연결 Case: `CASE-04`

- encoded XSS normalization을 추가로 보여줄 시간이 있을 때
- Double-encoded SQLi와 다른 encoding 사례가 필요한 경우

### DEMO-O02 — CMDi bounded grammar

연결 Case: `CASE-06`

- bounded grammar 설계 질문이 나왔을 때
- false-positive 억제 기준을 더 기술적으로 설명할 때
- freeze 전 dedicated export/reproduction fixture 고정 필요

### DEMO-O03 — Directory probe / context-only

연결 Case: `CASE-S01`

- candidate와 context-only 차이를 질문받았을 때
- 여러 저신호 request를 침해 결과로 과승격하지 않는 설계를 보여줄 때

### DEMO-O04 — Static / crawler baseline

연결 Case: `CASE-S02`

- no-signal / baseline-like / safe의 차이를 설명할 때
- User-Agent spoofability 질문이 나왔을 때

---

## 6. Screenshot Inventory

실제 screenshot은 freeze revision과 runtime verification 이후 확보한다.

| Screen ID | 화면 | 목적 | 보여줄 핵심 | 피해야 할 노출 | 상태 |
| --- | --- | --- | --- | --- | --- |
| `SHOT-01` | Analysis Jobs / New Job | 분석 진입점 설명 | 시간 범위 기반 `full_report` Job | credential, 내부 endpoint | Required |
| `SHOT-02` | Job Detail | Job lifecycle 설명 | PENDING/RUNNING/terminal, artifact/event 연결 | 민감 raw payload | Required |
| `SHOT-03` | Job Events / Timeline | Worker 실행 추적 | EXPORT / PIPELINE / REPORT_SAVE / JOB event | 내부 오류 stack 전체 | Required |
| `SHOT-04` | Prepare candidate | deterministic preprocessing 설명 | candidate, reason, normalized evidence | 민감 URI/query | Required |
| `SHOT-05` | Prepare filtered/context | false-positive/context 경계 | filtered reason, context-only | 실제 사용자 식별정보 | Required |
| `SHOT-06` | Stage1 evidence | evidence-based 분류 설명 | evidence / limitation / verdict context | secret/raw body | Required |
| `SHOT-07` | Stage2 report | finding 종합 설명 | deduplicated finding, report synthesis | 민감 원문 | Optional |
| `SHOT-08` | Report Viewer finding | 최종 사용자 결과 | finding/context/limitation | 과장된 label | Required |
| `SHOT-09` | Security Standards Mapping | enrichment 설명 | OWASP/CWE/WSTG relationship | compliance처럼 보이는 표현 | Required |
| `SHOT-10` | Security Standards Summary | aggregate 설명 | deduplicated finding aggregate | vulnerability count처럼 보이는 구성 | Required |
| `SHOT-11` | No-data Job | no-data 의미 설명 | 로그 없음과 no-signal 분리 | safe/normal 표현 | Optional |
| `SHOT-12` | Failure Job / event | truthful failure handling | FAILED terminal + event | secret/stack trace | Optional |

### 6.1 Required 최소 세트

```text
SHOT-01 Analysis Jobs/New Job
SHOT-02 Job Detail
SHOT-04 Prepare candidate
SHOT-05 Prepare filtered/context
SHOT-06 Stage1 evidence
SHOT-08 Viewer finding
SHOT-09~10 Standards Mapping/Summary
```

---

## 7. Demo ↔ Screenshot Matrix

| Demo | Prepare | Filter/Context | Stage1 | Mapping | Summary | Viewer | 비고 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PHP wrapper | Required | - | Required | Required | Optional | Required | 첫 사례 |
| Double-encoded SQLi | Required | - | Required | Optional | - | Required | normalization 강조 |
| Traversal vs direct resource | Required | Required | Optional | Optional | - | Optional | taxonomy 비교 |
| XSS false-positive | Optional | Required | - | - | - | Optional | 과승격 억제 |
| HTML entity XSS | Required | - | Optional | Optional | - | Optional | Appendix/Optional |
| CMDi bounded grammar | Required | - | Optional | Optional | - | Optional | Appendix/Optional |
| Directory probe | - | Required | - | - | - | Optional | context-only |
| Static/crawler | - | Required | - | - | - | - | baseline context |

---

## 8. Security Standards 화면 계획

### 8.1 Mapping

발표 메시지:

```text
Stage1 finding에 대해
OWASP / CWE / WSTG 관계를
deterministic rule로 enrichment한다.
```

보여줄 요소:

- finding identifier
- mapped category
- relationship type
- mapping rationale / note
- observability limitation

피할 요소:

```text
취약점 수
compliance score
위반 점수
confirmed CWE
```

### 8.2 Summary

발표 메시지:

```text
Summary는 finding-level mapping을
deduplicated finding 기준으로 집계한 결과다.
```

주의:

- category count를 incident total처럼 합산하지 않는다.
- 전체 환경 coverage처럼 설명하지 않는다.
- compliance dashboard처럼 보이게 구성하지 않는다.

### 8.3 화면 수

가능하면 Mapping 1장, Summary 1장을 별도로 확보한다. Viewer 한 화면 안에서 둘 다 충분히 읽을 수 있으면 하나의 full Viewer screenshot + crop 2개로 대체할 수 있다.

---

## 9. Evidence / Privacy Review

### 9.1 반드시 확인할 항목

```text
Authorization
Cookie
API key
DB credential
connection string
internal hostname
internal IP
real user identifier
email / account id
sensitive URI/query
raw POST body
stack trace secret
```

### 9.2 IP / URI 처리

```text
runtime에는 raw 표시 가능
발표 screenshot은 최소 필요 정보만 노출
```

발표 목적에 불필요한 실환경 IP/hostname은 mask 또는 fixture data로 대체한다.

### 9.3 표현 검토

```text
Detected
Attack
Incident
Normal
Safe
Success
```

같은 단어가 과도한 의미를 만들 경우 발표 멘트에서 실제 단계 의미를 명시한다.

---

## 10. Conditional Final Screenshot Plan

Conditional 기능은 Final 승격 후에만 본편 screenshot으로 추가한다.

### 10.1 Live Monitoring

승격된 경우 후보:

| ID | 화면 | 목적 |
| --- | --- | --- |
| `SHOT-L01` | Live latest 50 | raw log observation 역할 |
| `SHOT-L02` | filters | period/status/method/IP/request target |
| `SHOT-L03` | pagination/detail | 이전/다음 50 + raw detail |
| `SHOT-L04` | DB/latest-query metadata | 최신 로그 시각과 조회 시각 분리 |

발표 메시지:

```text
Live는 분석 파이프라인의 빠른 버전이 아니라
원천 로그를 read-only로 관찰하는 별도 화면입니다.
```

### 10.2 Live Security Observation

Final 승격된 경우에만 다음을 보여준다.

```text
processing_status
assessment
observation reason
standards refs
```

반드시:

```text
review_required ≠ incident
no_signal ≠ safe
undetermined ≠ no_signal
```

을 설명한다.

### 10.3 Live → Analysis Job

Final 승격된 경우 후보:

```text
Live row selection
→ existing Job creation
→ Job Detail
→ Viewer
```

발표 핵심:

```text
Live가 Prepare/Stage1/Stage2를 직접 호출하지 않고
기존 Job lifecycle을 재사용한다.
```

### 10.4 Shared Extractor

Shared Extractor는 내부 구조이므로 사용자 화면보다 다음이 더 적절하다.

```text
architecture diagram
before/after compatibility evidence
verification table
```

---

## 11. Appendix 구성

### Appendix A — Additional Demo Cases

- HTML entity XSS
- CMDi bounded grammar
- Directory probe/context-only
- Static/crawler baseline

### Appendix B — Offline Verification

- Prepare regression fixtures
- full-output harness
- before/after compatibility
- source/corpus identity
- regression table

### Appendix C — External Benchmark Evidence

- OWASP CRS
- CSIC
- provenance / annotation / controlled review

```text
historical benchmark PASS ≠ freeze revision PASS
```

### Appendix D — Conditional Final

- Shared Extractor
- Live Monitoring
- Live Security Observation
- Live → Analysis Job

각 항목은 실제 freeze 시점의 Scope Status와 Verification Status를 그대로 표시한다.

### Appendix E — Deferred / Post-final

- Sliding Window
- operator queue expansion
- retry/requeue/cancel UX
- Viewer compare/history
- WebSocket/SSE Live
- duplicate collapse
- new attack family expansion

---

## 12. Screenshot Freeze Checklist

```text
[ ] freeze candidate revision 확정
[ ] 해당 component runtime verification PASS
[ ] demo fixture / input identity 고정
[ ] 실제 Job reproduction 완료
[ ] Viewer output 확인
[ ] Mapping/Summary artifact 확인
[ ] screenshot 내용과 발표 문구 일치
[ ] secret / sensitive data 검토 완료
[ ] UI label이 evidence boundary를 위반하지 않음
[ ] screenshot이 현재 freeze revision 결과임을 확인
```

각 screenshot별 metadata:

```text
Screen ID:
Revision:
Job ID:
Case ID:
Captured at:
Environment:
Source fixture/input:
Notes:
```

---

## 13. 발표 당일 체크리스트

### 13.1 시작 전

```text
[ ] freeze revision 확인
[ ] demo Job 준비
[ ] Viewer URL/route 확인
[ ] fixture/case ID 확인
[ ] DB/Worker/Web 상태 확인
[ ] LLM/provider 사용 가능 여부 확인
[ ] 민감정보 노출 재확인
[ ] fallback screenshot 준비
[ ] fallback 영상 준비
```

### 13.2 발표 중

```text
[ ] 관찰 → 분석 → enrichment → limitation 순서 유지
[ ] HTTP status를 success evidence로 설명하지 않음
[ ] candidate-excluded를 정상으로 설명하지 않음
[ ] Mapping을 vulnerability confirmation으로 설명하지 않음
[ ] Summary를 compliance score로 설명하지 않음
[ ] Live 미승격 시 Final 기능처럼 발표하지 않음
```

### 13.3 Demo 실패 시

```text
1. 실제 runtime 상태 설명
2. fallback screenshot / 영상 사용
3. 동일 freeze revision의 evidence인지 명시
4. 과거 revision screenshot을 current PASS처럼 사용하지 않음
```

---

## 14. 발표용 금지 주장

다음 표현은 별도 evidence가 없으면 사용하지 않는다.

```text
공격 성공
침해 성공
SQL Injection 성공
XSS 실행 성공
RCE 성공
파일 유출 성공
취약점 확인
CWE 발생
OWASP 위반
정상/안전 판정
```

권장 표현:

```text
SQLi 관련 request pattern 관찰
XSS-like request pattern 관찰
CMDi-like grammar/context 관찰
file/resource disclosure intent 관찰
traversal syntax signal 관찰
analysis candidate
classified finding
deterministic standards enrichment
context-only
candidate-excluded
```

---

## 15. 팀 기술 결과와 발표 계획 연결

### 15.1 Shared Extractor

```text
compatibility PASS
→ architecture / verification appendix에 반영

Conditional 유지
→ 본편 runtime diagram에는 넣지 않음
```

### 15.2 Live Monitoring

```text
Final 승격
→ 본편 또는 보조 Demo에 Live 화면 추가 가능

Conditional 유지
→ appendix / 향후 작업
```

### 15.3 Live Security Observation

```text
Final 승격
→ assessment UI 설명 가능

미승격
→ no_signal / review_required를 current Final 기능처럼 발표하지 않음
```

### 15.4 Live → Job

```text
Final 승격
→ Live→Job→Viewer 시연 추가 가능

미승격
→ 기존 시간 범위 full_report Job을 canonical 분석 진입점으로 유지
```

---

## 16. 9월 말~10월 발표 준비 일정

### 9/11~9/20

```text
Presentation plan 고정
본편 Demo 후보 확정
Required screenshot inventory 고정
발표 스토리라인 초안
팀 C/D/E/Shared Extractor 결과 수령 시작
```

### 9/21~9/25

```text
팀 regression/E2E 결과 반영
Conditional 승격 여부 판단
본편 Demo 3~4개 최종 후보 좁히기
CASE-03 / CASE-06 reproduction 상태 확인
```

### 9/26

```text
Demo fixture / input freeze
발표 사례 의미 경계 고정
```

### 9/27~9/30

```text
Final regression
freeze candidate 확정
Final Verification Record 작성 시작
Code Freeze
```

### 10월 초

```text
실제 screenshot 확보
fallback 영상/화면 확보
PPT에 freeze 결과 반영
architecture / status / limitations 최종 정리
```

### 10월 중순

```text
발표 스크립트
Q&A
demo 재기동 절차
실패 fallback
리허설
```

### 발표 전

```text
critical fix만 허용
최종 리허설
제출본 백업
offline copy
영상/스크린샷 백업
```

---

## 17. 현재 상태에서의 Action Items

### 사용자 작업

```text
[ ] 이 Presentation Plan 검토/commit
[ ] 본편 Demo 4개 승인
[ ] 발표 스토리라인 승인
[ ] 팀 결과 수령 시 Final 상태 판정
[ ] freeze 후 screenshot/영상 최종 선택
[ ] Final Verification Record 정리
[ ] PPT/발표 스크립트/Q&A 완성
```

### 팀 기술 작업

```text
[ ] C harness self-validation
[ ] D source/corpus/input identity
[ ] E before baseline
[ ] Shared Extractor before/after compatibility
[ ] Live main integration/regression/E2E
[ ] Core Final Runtime regression/E2E
[ ] Demo reproduction
[ ] freeze candidate SHA 확정
```

---

## 18. 최종 발표용 최소 확보 산출물

Code Freeze 이후 최소 다음을 확보한다.

```text
1. freeze candidate SHA
2. Final Verification Record
3. Architecture 1장
4. Job/Worker lifecycle 화면
5. Prepare candidate 화면
6. false-positive/context 화면
7. Stage1 evidence 화면
8. Viewer finding 화면
9. Standards Mapping 화면
10. Standards Summary 화면
11. 본편 Demo 3~4개
12. fallback screenshot
13. fallback video
14. Known Limitations 요약
15. Conditional / Deferred 요약
```

이 15개가 준비되면 발표 자료와 시연은 기술 구현과 독립된 별도 작업으로 안정적으로 마무리할 수 있다.
