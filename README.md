# Apache 로그 기반 보안 분석 지원 시스템

> **Apache Log-Based Security Analysis Support System**

Apache 웹 서버 로그를 수집하고, 분석 입력을 구성한 뒤 **deterministic 전처리, AI 기반 분류·보고서 생성, 보안 표준 연계**를 거쳐 사람이 근거와 한계를 함께 검토할 수 있는 결과로 제공하는 로그 기반 보안 분석 지원 시스템입니다.

이 프로젝트는 트래픽을 실시간 차단하거나 Apache 로그만으로 공격 성공을 확정하는 것을 목표로 하지 않습니다. 대신 다음 질문에 답하는 것을 목표로 합니다.

> **쌓여 있는 웹 로그에서 무엇을 검토해야 하는지, 왜 검토해야 하는지, 그리고 어디까지 판단할 수 있는지를 어떻게 근거와 함께 보여줄 것인가?**

---

## 1. 왜 만들었는가

웹 서버에는 많은 로그가 지속적으로 쌓이지만, HTTP 상태 코드나 특정 문자열 하나만으로 보안 의미를 바로 판단하기는 어렵습니다.

실제 검토 과정에서는 다음 질문이 함께 필요합니다.

- 어떤 요청을 우선 검토해야 하는가
- 어떤 근거 때문에 검토 대상이 되었는가
- 주변 요청이나 행동 문맥은 어떤 의미가 있는가
- 분석 결과는 어떤 표준과 관련되는가
- 로그만으로 확인할 수 없는 부분은 무엇인가

이 프로젝트는 **원천 로그, 분석 대상, 해석 문맥, 분석 결과, 해석 한계**를 구분해 추적할 수 있도록 분석 흐름을 구성했습니다.

원시 로그 전체의 판단을 AI에 바로 맡기기보다, 먼저 deterministic 전처리에서 후보·문맥·근거를 구조화하고 이후 AI가 그 근거를 바탕으로 분류와 보고서 종합을 수행하도록 설계했습니다.

---

## 2. 전체 구조

~~~text
Apache access / security / error logs
                |
                v
          Log Shipper
                |
                v
             MariaDB
                |
        +-------+-------------------+
        |                           |
        |                           v
        |                    Live Monitoring
        |                  apache_security_logs
        |                           |
        |                     선택 로그 ID
        |                           |
        |                           v
        +---- 시간 범위 입력 ----> Analysis Job
                                    full_report
                                        |
                                        v
                               Analysis Job Worker
                                        |
                                        v
                                      Export
                                        |
                                        v
                                     Prepare
                                        |
                                        v
                              Stage1 Classification
                                        |
                                        v
                         Security Standards Mapping
                                        |
                                        v
                            Stage2 Report Synthesis
                                        |
                                        v
                         Security Standards Summary
                                        |
                                        v
                          Job-scoped Artifacts
                                        |
                         +--------------+-------------+
                         |                            |
                         v                            v
                    Job Detail                Analysis Viewer
~~~

현재 full_report 분석 작업에는 두 가지 대표 입력 경로가 있습니다.

1. **시간 범위 기반 입력**  
   Web UI에서 분석 시간 범위를 지정해 Analysis Job을 생성합니다.

2. **Live 선택 기반 입력**  
   Live Monitoring에서 apache_security_logs의 행을 선택하면, 선택한 DB 행 ID를 정확한 입력으로 보존하는 Analysis Job을 생성합니다.

두 경우 모두 기존 Analysis Job / Worker lifecycle을 사용합니다. Live Monitoring이 Prepare, Stage1, Stage2를 직접 호출하지 않습니다.

---

## 3. 사용자 관점의 흐름

전체 사용 흐름은 다음 네 단계로 볼 수 있습니다.

~~~text
관찰
  ↓
선택
  ↓
분석
  ↓
검토
~~~

### 관찰

Live Monitoring에서 MariaDB의 apache_security_logs에 수집된 최근 원천 로그와 보안 관찰 정보를 확인합니다.

### 선택

분석할 로그를 선택하거나, 새 분석 작업에서 시간 범위를 지정합니다.

### 분석

Analysis Job Worker가 full_report 파이프라인을 실행합니다.

~~~text
Export
→ Prepare
→ Stage1
→ Security Standards Mapping
→ Stage2
→ Security Standards Summary
→ Viewer Payload / Artifacts
~~~

### 검토

Job Detail에서 작업 상태와 단계별 산출물을 추적하고, Analysis Viewer에서 최종 결과와 근거·한계를 확인합니다.

---

## 4. 왜 이런 구조로 만들었는가

### 4.1 원천 로그와 분석 결과를 구분

로그에 실제로 기록된 값과 분석 과정에서 만들어진 해석을 같은 사실로 취급하지 않습니다.

~~~text
Observed Log
≠
Analysis Result
~~~

HTTP status, URI, 응답 크기, Content-Type 같은 값은 관찰 근거이며, 그 자체로 공격 성공이나 침해를 의미하지 않습니다.

### 4.2 AI 이전에 근거를 구조화

Prepare는 deterministic preprocessing 단계입니다.

주요 역할은 다음과 같습니다.

- 입력 정규화와 decoding
- candidate 구성
- candidate 제외 사유 기록
- context 구성
- supporting evidence 구성
- 분석 근거 hint 생성

Prepare에서 후보로 선택되지 않은 행은 **안전하거나 정상이라고 판정된 것이 아닙니다.**

### 4.3 후보별 분류와 보고서 종합을 분리

Stage1은 Prepare candidate별 evidence 기반 LLM classification을 수행합니다.

Stage2는 Stage1 결과와 구조화된 문맥을 바탕으로 사람이 읽을 수 있는 보고서를 종합합니다.

~~~text
Prepare
후보·문맥·근거 구조화
        ↓
Stage1
후보별 근거 기반 분류
        ↓
Stage2
결과 종합과 보고서 생성
~~~

이렇게 단계를 나누어 결과가 어떤 입력과 근거에서 시작되었는지 추적할 수 있도록 했습니다.

---

## 5. 분석 정보의 역할 구분

Viewer에서는 정보를 같은 의미로 섞지 않고 역할별로 구분합니다.

| 역할 | 의미 |
| --- | --- |
| **주요 탐지 요청 (Finding)** | 직접 검토 대상으로 선택된 요청 |
| **해석 정보 (Context)** | Finding을 이해하기 위한 문맥·집계 정보 |
| **주변 참고 요청 (Supporting Event)** | Finding 주변의 참고 요청 |

다음 경계를 유지합니다.

~~~text
Finding ≠ 공격 성공
Context ≠ 새로운 Finding
Supporting Event ≠ Finding
candidate-excluded ≠ safe
~~~

즉 **무엇을 관찰했는가**와 **그것을 어떻게 해석했는가**를 분리하는 것이 핵심 설계 원칙입니다.

---

## 6. 주요 구성 요소

### Live Monitoring

MariaDB의 apache_security_logs에 수집된 최근 로그를 조회하고 분석 입력을 선택하는 화면입니다.

주요 기능:

- 최근 로그 조회
- 기간 / HTTP status / Method / IP / Request Target 필터
- 원천 로그 상세 확인
- Security Observation 확인
- 분석 입력 로그 선택
- 선택한 로그로 기존 full_report Analysis Job 생성

Live Monitoring은 최근 로그를 주기적으로 갱신해 확인하는 화면이며 WebSocket 기반 실시간 스트리밍을 의미하지 않습니다.

Security Observation의 review_required 같은 값 역시 공격 성공 판정이 아니라 추가 검토가 필요한 관찰 상태를 나타냅니다.

### Analysis Job / Worker

분석 작업은 MariaDB의 analysis_jobs를 중심으로 관리합니다.

대표 lifecycle:

~~~text
PENDING
  ↓
RUNNING
  ↓
SUCCEEDED / FAILED
~~~

Worker는 Job을 claim하고 Job별 artifact root를 사용해 Export부터 Viewer payload 생성까지 기존 full_report 파이프라인을 실행합니다.

단계별 lifecycle과 실행 기록은 job_events에 남기며, 결과 artifact 경로와 요약은 analysis_reports에서 추적합니다.

### Security Standards Mapping / Summary

Security Standards Mapping은 Stage1 결과와 Prepare evidence를 바탕으로 OWASP Top 10, CWE, WSTG 관계를 deterministic하게 보강합니다.

Security Standards Summary는 이미 정리된 finding의 mapping을 집계합니다.

~~~text
Security Standards Mapping / Summary
= taxonomy enrichment / aggregate

!= detector
!= vulnerability confirmation
!= exploit success confirmation
~~~

### Analysis Viewer

Analysis Viewer는 viewer_payload.v1과 관련 artifact를 읽어 사람이 검토하기 쉬운 형태로 보여주는 **read-only interpretation layer**입니다.

Viewer는 다음을 새로 판정하거나 재계산하지 않습니다.

- Finding 생성
- Context의 Finding 승격
- Stage1 verdict 변경
- severity / confidence 재계산
- Standards Mapping 재계산
- 공격 성공 여부 추론

대신 분석 결과와 근거, 정보 역할, 표준 연계, 해석 한계를 한 화면에서 검토할 수 있도록 구성합니다.

---

## 7. Prepare가 다루는 대표 신호와 문맥

현재 분석 정책은 여러 웹 보안 관련 signal과 context를 다룹니다. 다만 모든 signal이나 hint가 독립적인 공격 판정 또는 전용 Stage1 verdict를 의미하는 것은 아닙니다.

### 주요 후보화·분류 예시

- SQL Injection
- Cross-Site Scripting
- Path Traversal
- Command Injection
- File Disclosure / PHP Wrapper 관련 패턴
- Authentication abuse / brute-force-like behavior
- Scanner-like behavior

### 추가 hint·context 예시

- SSRF-like target
- SSTI expression
- JNDI lookup pattern
- HTTP Parameter Pollution
- HTTP method / protocol behavior
- sensitive path probing
- static / crawler / scanner baseline context
- IP behavior / probing sequence context

각 신호는 현재 정의된 bounded grammar와 분석 정책 범위 안에서 사용됩니다.

신호가 관찰되었다는 사실만으로 취약점 존재, 공격 성공, 침해 성공을 의미하지 않습니다.

---

## 8. Apache logs-only Evidence Boundary

이 프로젝트의 분석 범위는 Apache 로그에서 관찰 가능한 정보에 제한됩니다.

대표적으로 다음 정보를 근거로 사용할 수 있습니다.

- 요청 시각
- 출발지 IP
- HTTP Method
- URI / Request Target
- HTTP status
- 응답 크기
- Content-Type
- User-Agent
- 반복 요청 및 주변 요청 패턴

하지만 Apache 로그만으로 다음을 확정하지 않습니다.

~~~text
실제 OS command 실행
DB query 실행 결과
실제 파일 내용 노출
브라우저 JavaScript 실행
외부 callback 성공
취약점 존재
서버 침해
데이터 유출
~~~

따라서 결과에서는 **관찰된 정황**, **분석 결과**, **확인할 수 없는 영역**을 구분해 표현합니다.

세부 기준은 [Apache logs-only Evidence Boundary](docs/00_apache_logs_only_evidence_boundary.md)를 참고합니다.

---

## 9. Job Artifacts

full_report 분석은 Job별 artifact root를 사용합니다.

대표 산출물 예시는 다음과 같습니다.

~~~text
export.json
llm_input.json
analysis_candidates.json
noise_summary.json
filtered_reasons.json
stage1_results.json
stage2_report_input.json
stage2_report.json
stage2_report.md
viewer_payload.json
manifest.json
~~~

Job Detail은 이러한 산출물과 실행 lifecycle을 추적하는 화면이고, Analysis Viewer는 최종 결과를 읽고 검토하는 화면입니다.

---

## 10. 기술 구성

| 영역 | 기술 / 역할 |
| --- | --- |
| Web | FastAPI / Jinja2 / JavaScript |
| Data | Apache Logs / MariaDB |
| Ingest | Apache Log Shipper |
| Job | DB-backed Analysis Job / Worker |
| Preprocessing | deterministic Prepare pipeline |
| AI | Stage1 Classification / Stage2 Report Synthesis |
| Standards | OWASP Top 10 / CWE / WSTG Mapping & Summary |
| Output | Job Artifacts / viewer_payload.v1 / Analysis Viewer |

---

## 11. 검증 원칙

프로젝트는 **구현 존재**와 **실제 검증 PASS**를 구분합니다.

검증 상태는 다음 기준을 사용합니다.

~~~text
PASS
FAIL
BLOCKED
NOT RUN
~~~

소스나 테스트가 존재한다는 사실만으로 runtime PASS로 취급하지 않습니다.

주요 검증 범위에는 다음이 포함됩니다.

- Apache → Shipper → MariaDB ingest
- Live Monitoring
- Live selected logs → Analysis Job
- Analysis Job Worker lifecycle
- Export / Prepare
- Stage1 / Stage2
- Security Standards Mapping / Summary
- Job-scoped artifacts
- Job Detail / Analysis Viewer
- Prepare regression
- Stage dry-run regression
- Web regression
- Apache logs-only wording boundary

대표 regression command:

~~~bash
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
~~~

revision별 최종 검증 결과는 Final verification 문서와 evidence record에서 관리합니다. Main README에는 쉽게 오래될 수 있는 고정 테스트 개수나 과거 smoke 결과를 기준값으로 두지 않습니다.

---

## 12. 현재 한계

현재 시스템은 Apache 웹 로그를 주요 근거로 사용합니다.

따라서 로그에 존재하지 않는 다음 정보에는 직접 접근할 수 없습니다.

- raw POST body
- 실제 response body 내용
- DB 실행 결과
- 파일 시스템 내부 결과
- 브라우저 실행 결과
- OS command 실행 결과
- 외부 callback 결과

외부 LLM Provider를 사용하는 분석 작업은 네트워크와 Provider 응답 상태의 영향을 받을 수 있습니다.

또한 현재 정의한 signal, candidate policy, logs-only evidence boundary 범위 안에서 분석하므로 모든 보안 이벤트를 탐지하거나 실제 취약점 존재를 보장하는 시스템이 아닙니다.

---

## 13. 문서 안내

Main README는 프로젝트의 현재 목적과 상위 흐름을 설명합니다. 세부 설계와 운영·검증 근거는 docs 아래에서 관리합니다.

### 먼저 볼 문서

- [Architecture Reference](docs/00_current_architecture.md)
- [Apache logs-only Evidence Boundary](docs/00_apache_logs_only_evidence_boundary.md)
- [Documentation Hub](docs/README.md)
- [Final Scope](docs/final/final-scope.md)
- [Final Status & Freeze Criteria](docs/final/final-status-and-freeze-criteria.md)
- [Final Demo Casebook](docs/final/final-demo-casebook.md)
- [Final Known Limitations](docs/final/final-known-limitations.md)

### 영역별 문서

- docs/design/ — 시스템 및 분석 설계
- docs/operations/ — 실행 환경, DB, Worker 운영
- docs/reviews/ — 검토 및 검증 기록
- docs/standards/ — 실험·검증 기준
- docs/experiments/ — 실험 설계와 결과
- docs/planning/ — 후속 작업과 계획
- src/prepare/README.md — Prepare 하위 모듈 구조

전체 문서 색인은 [docs/README.md](docs/README.md)를 참고합니다.

---

## 14. 프로젝트가 최종적으로 제공하는 것

~~~text
원천 웹 로그
    ↓
분석 대상과 문맥 구조화
    ↓
근거 기반 AI 분류
    ↓
보안 표준 연계
    ↓
보고서 종합
    ↓
사람이 근거와 한계를 함께 검토할 수 있는 결과
~~~

> **어떤 요청을 왜 검토해야 하는지, 어떤 근거가 있으며 어디까지 판단할 수 있는지를 함께 보여주는 로그 기반 보안 분석 지원 시스템을 구현하는 것이 이 프로젝트의 핵심입니다.**
