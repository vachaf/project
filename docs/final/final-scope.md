# Final Scope v1.0

- 작성일: 2026-09-10
- 대상 프로젝트: Apache 기반 Web Log Analysis / Security Log Monitoring
- 문서 목적: 2026년 9월 말 최종 마크업 및 Code Freeze를 앞두고, 프로젝트 기능과 검증 항목을 **Final / Conditional Final / Deferred**로 명확히 구분하고 각 항목의 최종 포함 기준을 고정한다.

> **Scope Freeze 원칙:** 본 문서는 기능 구현 명세가 아니라 2026년 9월 Final 범위와 승격 기준을 고정하기 위한 관리 문서이다. 새로운 기능 아이디어가 생겼다는 이유만으로 Final 범위를 확대하지 않는다.
- 목표 시점:
  - Conditional Final 승격 판단: 2026-09-20 전후부터 순차 진행
  - Demo fixture freeze: 2026-09-26
  - Code Freeze: 2026-09-27
  - 최종 문서·화면·발표자료 마크업: 2026-09-28 ~ 2026-09-30

---

## 1. 범위 분류 원칙

### 1.1 Final

현재 프로젝트의 실제 제품/운영 흐름에 포함되어 있고, 최종본의 핵심 기능으로 확정할 수 있는 항목이다.

```text
Final
= 현재 제품의 일부로 확정
= 최종 architecture와 발표 본편에 포함
= 최종 freeze revision에서 상태를 다시 검증
```

### 1.2 Conditional Final

구현 자산 또는 설계·검증 기반이 존재하지만, 최종 통합·회귀·E2E 또는 compatibility 검증이 아직 완료되지 않은 항목이다.

```text
Conditional Final
= 구현 또는 검증 자산 존재
= 최종 승격 조건이 남아 있음
= 조건 충족 시 Final로 승격
= 조건 미충족 시 진행 중 또는 후속 항목으로 정확히 표기
```

Conditional Final은 “거의 Final”이라는 의미가 아니다. 각 항목의 승격 gate를 실제로 통과해야 Final로 변경한다.

### 1.3 Deferred

프로젝트상 유효한 후속 후보이지만, 2026년 9월 최종본 범위에는 포함하지 않는 항목이다.

```text
Deferred
= 이번 Final 범위 밖
= 삭제된 TODO가 아님
= Post-final 작업으로 명시적 이관
```

---

# 2. Final 확정 범위

| 영역 | Final 포함 항목 | 최종본에서의 역할 |
| --- | --- | --- |
| Log Source | Apache 로그 수집 구조 | 분석 근거가 되는 원천 로그 |
| Storage | MariaDB 원천 로그 저장 | 분석 및 조회의 데이터 기반 |
| Job | DB-backed `full_report` Job 생성 | 사용자가 분석 작업을 등록하는 운영 진입점 |
| Worker | Analysis Job Worker / lifecycle | `PENDING → RUNNING → SUCCEEDED/FAILED` 실행 관리 |
| Prepare | Prepare deterministic preprocessing | 분석 후보 구성 및 기존 deterministic preprocessing |
| Stage1 | Stage1 LLM Classification | 후보 로그의 evidence 기반 1차 분류 |
| Standards | Security Standards Mapping | Stage1 결과에 대한 deterministic standards enrichment |
| Stage2 | Stage2 Report Synthesis | finding 종합 및 report 생성 |
| Standards Summary | Security Standards Summary | deduplicated finding 기준 deterministic summary |
| Viewer | Report Viewer | 최종 분석 결과 확인 화면 |
| Evidence Boundary | Apache logs-only evidence boundary | 로그만으로 공격 성공·침해·취약점 존재를 과장하지 않는 핵심 원칙 |
| Regression | 대표 regression/demo fixture | 최종 시연 및 회귀 근거 |
| Verification | 최종 regression/freeze 결과 기록 | freeze revision 기준 상태 증적 |

## 2.1 Final Runtime 기본 흐름

```text
Apache Logs
    ↓
Shipper / Ingest
    ↓
MariaDB
    ↓
Web UI
    ↓
full_report Job
    ↓
Analysis Job Worker
    ↓
Export
    ↓
Prepare
    ↓
Stage1
    ↓
Deterministic Security Standards Mapping
    ↓
Stage2
    ↓
Deterministic Security Standards Summary
    ↓
Report Viewer
```

## 2.2 Final에 포함되는 핵심 의미 경계

다음 표현을 최종 문서·UI·발표에서 유지한다.

```text
관찰 신호 없음
≠ 정상
≠ 안전

분석 구간에 로그 없음
≠ 관찰 신호 없음

candidate-excluded
= 분석 후보에서 제외됨
≠ benign / normal / safe

Security Standards Mapping
= deterministic enrichment
≠ 공격 탐지기
≠ 취약점 존재 확인
≠ 공격 성공 확인

context-only
= 문맥 정보
≠ finding 자동 승격
≠ incident 자동 승격
```

---

# 3. Conditional Final

## 3.1 Shared Security Signal Extractor

### 현재 상태

- shared deterministic security observation extractor 설계가 존재한다.
- Prepare와 Live가 deterministic signal facts만 공유하고, score/verdict/severity는 공유하지 않는 구조로 설계되어 있다.
- compatibility / corrected / live_adoption expectation family를 분리한다.
- 현재 최종 승격을 위해서는 compatibility 및 회귀 검증 근거가 필요하다.

### Final 승격 조건

```text
C harness self-validation
    ↓
D corpus/source identity gate
    ↓
E before compatibility baseline
    ↓
Shared extractor 구현
    ↓
After comparison
    ↓
Prepare full-output compatibility PASS
    ↓
Final 승격 판단
```

### Final 승격 기준

- Prepare 기존 전체 반환값 compatibility가 승인된 기준에서 유지될 것
- corrected expectation과 compatibility expectation을 섞지 않을 것
- live_adoption을 별도 gate로 유지할 것
- extractor가 DB/file/network I/O, score, severity, verdict, candidate selection을 수행하지 않을 것

---

## 3.2 Prepare Full-output Comparison Harness

### 현재 상태

- harness building block과 관련 테스트 자산이 존재한다.
- B harness 정적 구현은 PASS로 판단되었다.
- end-to-end capture, corpus/source identity, before baseline, after comparison은 별도 단계다.

### Final 승격 조건

```text
B static implementation PASS
    ↓
C self-validation PASS
    ↓
D source/corpus identity PASS
    ↓
E before baseline 확보
    ↓
After comparison
    ↓
비교 결과 기록
```

### Final 승격 기준

- 5개 `build_outputs()` 반환값 전체 비교
- typed value strict comparison
- exception exact type/message 비교
- input mutation 검증
- baseline completion/checksum/hash/path/symlink 검증
- source/input identity 검증
- PASS / FAIL / BLOCKED / NOT RUN 상태를 구분

Harness code 존재와 compatibility 검증 완료는 같은 의미로 사용하지 않는다.

---

## 3.3 Live Monitoring v3.1

> **Live / Shared Extractor 의존 관계:** 기본 **Live Monitoring v3.1**은 shared security signal extractor 없이도 독립적으로 Final 승격할 수 있다. 반면 **Live Security Observation**은 shared extractor의 compatibility 검증과 `live_adoption` gate를 선행조건으로 한다.

### 현재 상태

Live v3.1은 현재 별도 작업트리에 구현·테스트 자산이 존재한다.

현재 확인된 구현 자산 범위:

- `/live`
- `/api/live/snapshot`
- Live 전용 `LOG_DB_*`
- MariaDB `apache_security_logs` SELECT-only 조회
- 기본 최신 50건
- 기간 / Status / Method / IP / URI·Request Target 조건 검색
- `(log_time, id)` cursor pagination
- 5초 polling 기반 신규 로그 확인
- KST 표시
- 원문 IP / Request Target / User-Agent 표시
- `textContent` / escaping 기반 안전 출력
- Live repository / service / route tests

현재 main에는 아직 통합되지 않은 별도 작업 자산으로 취급한다.

### Final 승격 조건

```text
Live checkpoint 생성
    ↓
remote 보존 확인
    ↓
최신 origin/main 기준 통합
    ↓
Live regression PASS
    ↓
기존 Web regression PASS
    ↓
DB read-only integration 확인
    ↓
E2E 확인
    ↓
Final 승격
```

### Final 승격 기준

- Live source/test가 main 기준 작업공간에 안전하게 통합될 것
- 기존 FastAPI Web 기능을 깨뜨리지 않을 것
- DB 접근이 `log_reader` / SELECT-only 경계를 유지할 것
- Prepare / Stage1 / Mapping / Stage2 / Worker를 Live 조회 경로에서 직접 호출하지 않을 것
- raw data 렌더링 시 HTML 실행을 방지할 것
- 최신 로그 age를 장애/지연으로 자동 판정하지 않을 것
- 실제 E2E에서 Apache → Shipper → MariaDB → Live 신규 행 표시가 확인될 것

### 현재 Final 문서에서의 표현

> **Live Monitoring v3.1은 별도 작업트리에 구현·테스트 자산이 존재하며, 현재 main 통합 및 최종 회귀/E2E 검증 전 단계이다. 최종 통합 결과에 따라 Final 범위 승격 여부를 결정한다.**

---

## 3.4 Live Security Observation

### 현재 상태

- Live 자체 공격 verdict를 만들지 않는 원칙은 유지한다.
- shared extractor를 사용한 observation은 shared extractor compatibility 이후에만 진행한다.

### Final 승격 조건

- shared extractor compatibility PASS
- Live adoption expectation PASS
- `processing_status`와 `assessment`의 2축 표현 유지
- `관찰 신호 없음 ≠ 정상 확정` 문구 유지
- severity / exploit success / incident verdict를 Live에서 생성하지 않음

조건 미충족 시 Live Monitoring 자체가 Final이어도 security observation은 별도 Deferred 또는 진행 중 항목으로 남길 수 있다.

---

## 3.5 Live → Analysis Job 사용자 흐름

### 현재 상태

기존 Final runtime의 분석 진입점은 시간 범위 기반 `full_report` Job이다.

Live에서 선택한 DB row를 기존 analysis job으로 전달하는 최종 계약은 아직 확정 대상이다.

### Final 승격 조건

- 기존 Job lifecycle 재사용
- Live가 직접 Prepare/Stage1/Stage2를 호출하지 않음
- 선택 로그 전달 계약 또는 시간 범위 전달 계약 확정
- Job 생성 후 기존 Job detail / Viewer 흐름과 연결
- E2E regression 완료

---

# 4. 가능하면 Final에 포함할 항목

아래 항목은 새 기능 개발보다 설명·측정 정리 중심이므로 일정이 허용하면 포함한다.

| 항목 | 판단 |
| --- | --- |
| filtered reasons 설명 | 가능하면 포함 |
| token usage 설명 | 가능하면 포함 |
| D5 성능 측정 결과 | 실제 측정값 확보 시 포함 |
| shared extractor compatibility 결과 요약 | PASS 근거 확보 시 포함 |
| Live observation | 관련 gate 완료 시 포함 |

---

# 5. Offline Validation / Appendix

OWASP CRS와 CSIC는 runtime 제품 흐름에 포함하지 않는다.

```text
Runtime
= 실제 사용자 Job / Worker / Viewer 흐름

Offline Validation
= benchmark / fixture / regression / harness
```

## 5.1 OWASP CRS

- detector semantic boundary
- false-positive regression
- mapping expectation 검증
- 대표 발표 본편보다는 검증 부록에 배치

## 5.2 CSIC

- source provenance와 review 범위를 명확히 기록
- 실행하지 않은 범위는 `NOT RUN`
- source/identity blocker가 있으면 `BLOCKED`
- 과거 결과를 freeze revision의 현재 PASS처럼 표현하지 않음

---

# 6. Deferred / Post-final

다음 항목은 이번 Final에서 구현·통합하지 않는다.

| Deferred 항목 | 결정 |
| --- | --- |
| Sliding Window / `windowed_triage` 사용자 UI 통합 | Post-final |
| operator queue 확대 | Post-final |
| cancel / requeue / retry UX | Post-final |
| worker health dashboard 확대 | Post-final |
| Viewer compare/history | Post-final |
| Context graph / advanced relationship view | Post-final |
| Standards drill-down/filter/dashboard badge 확대 | Post-final |
| deterministic Markdown 추가 | Post-final |
| observability capability matrix | Post-final |
| incident sibling mapping union | Post-final |
| WebSocket/SSE Live | Post-final |
| Live duplicate collapse | Post-final |
| Live masking | 현재 의도적으로 제외 |
| 신규 공격 유형 coverage | Post-final |
| SSTI / XXE / LDAP / NoSQL / deserialization 등 신규 family | Post-final |
| API key / secret token 신규 coverage | Post-final |
| Webshell command query 신규 fixture | Post-final |
| request smuggling / header anomaly | Post-final |
| coverage round 2 | Post-final |
| CRS 930120 전체 resource coverage 추종 | Post-final |
| 6B-5 반복성 추가 실험 | 기존 skip 결정 유지 |
| `--run-id` 확장 | Post-final |
| `--overwrite` 정책 | Post-final |
| archive opt-in scan | Post-final |
| flat/run_dir dedupe | Post-final |
| canonical_report_key | Post-final |

Deferred는 삭제된 TODO가 아니라 9월 Final 이후 후속 작업이다.

---

# 7. 최종 Demo / Regression 범위

발표 본편은 많은 benchmark 수치보다 대표적인 의미 경계를 보여주는 fixture를 우선한다.

## 7.1 기본 Demo 후보 6개

1. Double-encoded SQLi
2. HTML entity XSS
3. XSS false-positive boundary
4. PHP wrapper / file-resource
5. Traversal vs direct resource
6. CMDi bounded grammar

## 7.2 보조 후보

- Directory probe / context-only
- Static / crawler baseline

## 7.3 Demo 원칙

각 사례마다 다음 세 가지를 고정한다.

```text
1. 무엇이 관찰되었는가
2. 시스템이 무엇을 판단했는가
3. 무엇을 확정하지 않는가
```

예:

```text
php://filter 관련 요청 패턴 관찰
→ 분석 대상 및 관련 표준 enrichment 가능

그러나
→ 파일 내용이 실제 노출되었다는 의미 아님
→ 서버 침해가 성공했다는 의미 아님
```

---

# 8. 최종 문서 구조 원칙

## 8.1 Active / Historical / Superseded

문서를 삭제하기보다 다음 세 상태로 관리한다.

```text
Active
= 최종본에서 실제 참조

Historical
= 당시 결정·검토 기록

Superseded
= 최신 문서가 의미를 승계함
```

Shared extractor의 기존 103/104 문서는 114/115가 의미를 승계한 경우 `Superseded`로 표시한다.

## 8.2 Phase 기반 naming

신규 또는 active 문서는 global serial number보다 Phase 기반 이름을 우선한다.

예:

```text
phase4b-01_security_standards_summary_design.md

phase5b-02_external_benchmark_prepare_baseline_review.md

phase6b-04_external_benchmark_multifamily_live_baseline_review.md

phase6c-02_csic2010_prepare_baseline_review.md

phase7-01_shared_security_signal_extractor_design.md
phase7-02_shared_security_signal_extractor_regression_plan.md
phase7-03_prepare_full_output_harness_spec.md
```

Phase에 속하지 않는 횡단 문서는 다음 prefix를 사용할 수 있다.

```text
core-*
web-*
ops-*
final-*
```

---

# 9. Code Freeze 상태 표기

최종 freeze revision에서 모든 주요 검증은 다음 네 상태 중 하나로 기록한다.

| 상태 | 의미 |
| --- | --- |
| `PASS` | 승인된 검증을 실행했고 합격 |
| `FAIL` | 검증을 실행했고 계약 차이 또는 오류 확인 |
| `BLOCKED` | 실행 전제 또는 identity/source 조건 미충족 |
| `NOT RUN` | 해당 검증을 실행하지 않음 |

다음 표현은 사용하지 않는다.

```text
아마 통과
사실상 완료
문제 없어 보임
이전에도 통과했음
```

과거 PASS는 historical evidence이며, freeze revision에서 다시 실행하지 않았다면 현재 PASS로 재사용하지 않는다.

---

# 10. 9월 Final Gate

## Gate 1 — Scope Freeze

- Final / Conditional / Deferred 분류 승인
- Conditional 승격 조건 승인
- 신규 P0 기능 추가 중단

## Gate 2 — Technical Integration

- Live checkpoint remote 보존
- 최신 main 기준 작업공간 확보
- C / D / E 및 shared extractor critical path 진행
- Live integration 진행

## Gate 3 — Conditional Promotion

각 Conditional Final 항목을 독립적으로 판단한다.

```text
Shared extractor
→ compatibility PASS 여부

Harness
→ C/D/E 및 comparison evidence 확보 여부

Live Monitoring
→ main integration + regression + E2E 여부

Live observation
→ shared extractor + live_adoption 여부

Live → Job
→ 기존 lifecycle 재사용 + E2E 여부
```

## Gate 4 — Demo Fixture Freeze

- 2026-09-26
- 발표 입력과 대표 사례 고정
- 이후 fixture 의미 변경 금지

## Gate 5 — Code Freeze

- 2026-09-27
- P0 외 신규 기능 수정 중단
- freeze revision 기록
- verification status 기록
- known limitation 기록

## Gate 6 — Final Markup

- 2026-09-28 ~ 2026-09-30
- 문구
- architecture
- README
- 화면 캡처
- 발표 자료
- 부록
- limitations
- regression evidence 고정

---

# 11. 변경 관리 원칙

이 문서 v1.0 이후 Final 범위를 변경하려면 다음 중 하나가 필요하다.

1. 새로운 P0 blocker가 발견됨
2. Conditional Final의 승격 또는 강등
3. 현재 Final 항목이 실제 regression에서 FAIL/BLOCKED로 확인됨
4. 9월 일정상 명확히 수행 불가능한 항목이 확인됨

새 기능 아이디어가 생겼다는 이유만으로 Final 범위를 확대하지 않는다.

---

# 12. 최종 결정 요약

```text
FINAL
────────────────────────────────────
Apache / MariaDB
DB-backed full_report Job
Analysis Job Worker
Prepare
Stage1
Security Standards Mapping
Stage2
Security Standards Summary
Report Viewer
Apache logs-only evidence boundary
대표 fixture / regression
최종 verification record


CONDITIONAL FINAL
────────────────────────────────────
Shared Security Signal Extractor
Prepare full-output comparison harness
Live Monitoring v3.1
Live Security Observation
Live → Analysis Job workflow


DEFERRED
────────────────────────────────────
Sliding Window / operator queue 확대
cancel / retry / requeue UX
worker health dashboard 확대
advanced Viewer / graph / history
추가 Standards UI 확장
WebSocket / SSE Live
Live duplicate collapse
Live masking
신규 공격 family / coverage round 2
기타 post-final 연구·운영 확장
```

---

# 13. 현재 문서 상태

- 문서 버전: **Final Scope v1.0**
- 상태: **Scope Freeze — v1.0 확정**
- 다음 변경 사유:
  - Conditional Final 승격/강등
  - freeze regression 결과 반영
  - Final scope blocker 발견

이 문서는 기능 구현 명세가 아니라 **2026년 9월 최종본의 범위와 승격 gate를 관리하는 기준 문서**다.
