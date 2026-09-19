# Final Presentation & Screenshot Plan

## 1. 역할

이 문서는 최종 발표에서 **PPT와 Web UI Live Demo를 어떻게 연결할지**, 그리고 fallback screenshot/video를 어떤 기준으로 준비할지 정리한다.

기준 문서:

- [Current Architecture](../00_current_architecture.md)
- [Apache logs-only Evidence Boundary](../00_apache_logs_only_evidence_boundary.md)
- [Final Verification Record](./final-verification-record.md)
- [Final Demo Casebook](./final-demo-casebook.md)

## 2. 발표 핵심 메시지

프로젝트의 핵심 질문:

> 쌓여 있는 웹 로그를 어떻게 근거가 있는 보안 분석 정보로 바꿀 것인가?

발표 mental model:

~~~text
관찰
  -> 선택
  -> 분석
  -> 검토
~~~

제품 메시지:

~~~text
Apache 로그를 그대로 나열하는 것이 아니라,
검토할 요청과 문맥을 deterministic하게 구조화하고,
LLM 분석과 standards enrichment를 거쳐
사람이 검토 가능한 결과로 연결한다.
~~~

증거 메시지:

~~~text
관찰 가능한 로그 evidence를 분석하지만,
로그에서 확인할 수 없는 exploit success나 compromise를 확정하지 않는다.
~~~

## 3. Architecture 설명 순서

발표의 canonical pipeline:

~~~text
Apache Logs
  -> Log Shipper / MariaDB
  -> Live Monitoring 또는 time-range input
  -> Analysis Job
  -> Analysis Job Worker
  -> Export
  -> Prepare
  -> Stage1 Classification
  -> Security Standards Mapping
  -> Stage2 Report Input + Security Standards Summary
  -> Stage2 Report Synthesis
  -> Viewer Payload / Artifacts
  -> Job Detail / Analysis Viewer
~~~

중요:

- Analysis Job이 Stage2 뒤에 생기는 것이 아니다.
- Standards Summary는 Stage2 LLM 호출 이후 후처리가 아니라 Stage2 report input 구성 시 계산된다.
- Viewer는 verdict/severity를 재계산하지 않는다.

## 4. 권장 10분 발표 흐름

### 4.1 문제와 목표 — 약 1분

- Apache 로그가 많이 쌓인다.
- raw log만으로 조사 우선순위와 근거를 정리하기 어렵다.
- 모든 로그를 그대로 LLM에 보내지 않고 candidate/context를 deterministic하게 구조화한다.

### 4.2 Architecture — 약 1.5분

PPT의 architecture diagram으로 전체 흐름을 설명한다.

강조:

- Web/Worker 분리
- exact selected-log input
- deterministic Prepare/Standards
- LLM Stage1/Stage2
- human-review Viewer

### 4.3 Prepare / AI / Standards — 약 1.5분

~~~text
Prepare
  -> candidate / context / filtered reason

Stage1
  -> candidate classification

Standards Mapping
  -> deterministic taxonomy enrichment

Stage2 input
  -> dedup + Standards Summary

Stage2
  -> report synthesis
~~~

설명 경계:

~~~text
candidate-excluded != benign
Mapping != detector
Summary != compliance score
~~~

### 4.4 Web UI Demo — 약 4~5분

권장 순서:

~~~text
1. Dashboard
2. Live Monitoring
3. selected logs / Analysis Job 설명
4. Job Detail
5. Analysis Viewer
~~~

현장에서 새 provider-backed Job을 반드시 실행할 필요는 없다.

권장 멘트:

> 오늘은 새 작업을 즉석에서 실행하기보다, 동일한 흐름으로 미리 완료하고 검증한 분석 작업을 이어서 보여드리겠습니다.

### 4.5 Evidence Boundary — 약 1분

~~~text
HTTP 200 != exploit success
file/resource request != file exposure
SQLi-like request != DB execution
XSS-like request != browser execution
CMDi-like request != OS command execution
~~~

### 4.6 결론 — 약 30초

> 이 시스템의 목표는 공격 성공을 자동 확정하는 것이 아니라, 로그에서 관찰 가능한 근거를 구조화하고 사람이 검토할 수 있는 분석 결과로 연결하는 것입니다.

## 5. Demo 사례

본편에서 모두 보여줄 필요는 없다.

권장 본편:

- CASE-03 — Traversal vs direct resource
- CASE-06 — CMDi bounded grammar

보조/질문 대응:

- CASE-01 — PHP wrapper / file-resource
- CASE-02 — Double-encoded SQLi
- CASE-04 — HTML entity XSS
- CASE-05 — XSS false-positive boundary
- CASE-S01/S02 — context/baseline

각 사례의 의미와 금지 표현은 [Final Demo Casebook](./final-demo-casebook.md)을 따른다.

## 6. Required Screenshot Set

현재 UI audit에서 점검한 실제 사용자 흐름에 맞춰 fallback screenshot을 준비한다.

| ID | 화면 | 핵심 |
| --- | --- | --- |
| SHOT-01 | Job Dashboard | Job 목록/상태와 분석 진입 |
| SHOT-02 | Live Monitoring | 최근 로그, 선택 row, observation |
| SHOT-03 | New Job 또는 selected-log Job | 분석 입력 방식 |
| SHOT-04 | Job Detail 상단 | Job identity/status/input |
| SHOT-05 | Job Detail artifact/usage | 실행 provenance와 Viewer 진입 |
| SHOT-06 | Analysis Viewer 요약 | Assessment/Takeaway/Executive Summary |
| SHOT-07 | Viewer Finding + Context | 역할 분리 |
| SHOT-08 | Viewer Timeline / Supporting Event | 주변 evidence |
| SHOT-09 | Standards Mapping | finding-level enrichment |
| SHOT-10 | Standards Summary | deduplicated-finding aggregate |

한 화면에서 여러 항목이 충분히 읽히면 full screenshot + crop으로 줄여도 된다.

## 7. Screenshot metadata

fallback asset은 최소한 다음 identity를 추적 가능하게 한다.

~~~text
Screen ID
Revision
Job ID
Case ID (해당 시)
Captured at
Environment
Notes
~~~

실제 발표 화면에는 metadata를 모두 노출할 필요는 없지만, 어떤 revision/Job에서 캡처했는지는 내부적으로 추적 가능해야 한다.

## 8. Privacy / evidence review

캡처 전 확인:

- Authorization / Cookie
- API key
- DB credential
- connection string
- 불필요한 내부 hostname/IP
- 실제 사용자 식별정보
- 민감 query/raw payload
- stack trace의 secret

실환경 정보가 발표 목적에 필요하지 않으면 fixture 또는 mask된 화면을 사용한다.

## 9. Live Monitoring 설명

Live는 이제 현재 사용자 흐름의 일부다.

~~~text
Live Monitoring
  -> source log observation
  -> optional security observation
  -> selected-log Analysis Job
~~~

주의:

~~~text
review_required != incident
no_signal != safe
undetermined != no_signal
~~~

Live snapshot/raw 조회와 selected-log Job 생성 POST는 DB 권한/책임이 다르다.

## 10. CASE-03 / CASE-06

### CASE-03

현재 발표 상태:

~~~text
runtime/artifact identity: PASS / FROZEN
evidence freeze: PASS / FROZEN
~~~

핵심 메시지:

> traversal syntax와 direct sensitive-resource request를 구분한다.

### CASE-06

현재 발표 상태:

~~~text
runtime/artifact identity: PASS / FROZEN
Viewer presentation: PASS
~~~

핵심 메시지:

> CMDi-like grammar를 분류할 수 있지만 실제 OS command 실행 여부는 확인할 수 없다.

## 11. Demo 실패 시 fallback

1. 현재 runtime 상태를 짧게 설명한다.
2. 동일 흐름의 검증된 completed Job으로 이동한다.
3. 필요하면 동일 revision의 fallback screenshot/video를 사용한다.
4. 과거 revision 결과를 current PASS처럼 표현하지 않는다.

실시간 Provider/API 장애가 발생해도 발표 전체가 중단되지 않도록 한다.

## 12. 발표 당일 체크리스트

시작 전:

~~~text
[ ] 발표용 revision 확인
[ ] Web UI 접속 확인
[ ] DB / Worker 상태 확인
[ ] demo Job ID 확인
[ ] Viewer route 확인
[ ] fallback screenshot/video 확인
[ ] 민감정보 노출 확인
[ ] PPT와 실제 UI label 일치 확인
~~~

발표 중:

~~~text
[ ] 관찰 -> 선택 -> 분석 -> 검토 흐름 유지
[ ] HTTP status를 success evidence로 설명하지 않음
[ ] candidate-excluded를 normal/safe로 설명하지 않음
[ ] Mapping을 vulnerability confirmation으로 설명하지 않음
[ ] Summary를 compliance score로 설명하지 않음
~~~

## 13. PPT와 Web Demo 연결

권장 구성:

~~~text
PPT
  문제 / 목표
  Architecture
  Prepare / AI / Standards

        ↓

Web UI Demo
  Dashboard
  Live
  Job Detail
  Viewer

        ↓

PPT
  Evidence Boundary
  Verification
  결론
~~~

PPT만으로 끝내지 않고 실제 사용자 흐름을 Web UI에서 연결해 보여주는 것이 핵심이다.

## 14. 현재 남은 발표 작업

- PPT 최종 디자인
- architecture diagram 최종 배치
- demo Job/URL 고정
- fallback screenshot/video
- 발표 대본
- Q&A
- 리허설
- 제출본/offline backup

기술 구현 상태와 발표 산출물 준비 상태를 혼동하지 않는다.
