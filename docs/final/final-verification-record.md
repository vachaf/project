# Final Verification Record

- 문서 기준일: 2026-09-19
- 현재 documentation HEAD: `3f9f5160b18981be5a342799e5649000905b024b`
- 최근 technical baseline: `2fab0fa8a5dd33fb0901b3d2dabceeb8c4c1a4af`
- 상태: **revision-scoped verification record**

이 문서는 특정 revision에서 실제 확인된 검증 결과와, 그 이후 문서-only 변경을 분리한다.

~~~text
source/test 존재
!= PASS

과거 PASS
!= 현재 HEAD에서 자동 재검증됨
~~~

현재 `3f9f5160...`까지의 최근 변경은 README/문서 정리 중심이며 application runtime 코드를 변경하지 않았다. 아래 technical 결과는 각 항목에 적힌 technical baseline에서 확인된 결과다.

## 1. Core runtime verification

최근 technical baseline에서 확인된 대표 결과:

| 영역 | 결과 | 의미 |
| --- | --- | --- |
| Prepare regression | PASS | deterministic Prepare contract 회귀 확인 |
| Stage dry-run regression | PASS | Stage1/Stage2 dry-run contract 확인 |
| Core/Web pytest | PASS | runtime/Web focused regression 확인 |
| Viewer route/payload | PASS | completed Job의 Viewer presentation 경로 확인 |

과거 고정 fixture 수나 pytest 개수를 이 문서의 영구 baseline으로 사용하지 않는다. 숫자는 실행 revision이 달라지면 다시 측정해야 한다.

## 2. Live Selected Logs → Analysis Job

현재 canonical selected-input 경로:

~~~text
Live row selection
  -> selected source IDs
  -> Analysis Job
  -> Worker
  -> exact-ID Export
  -> Prepare
  -> Stage1 + Standards Mapping
  -> Stage2 input + Standards Summary
  -> Stage2 synthesis
  -> Viewer Payload
~~~

이 경로는 구현 및 E2E 검증을 거쳤다.

핵심 acceptance boundary:

- 선택하지 않은 같은 시간대 row가 자동 포함되지 않는다.
- selected child ID와 exported source ID가 일치해야 한다.
- no-data는 safe/no-signal 판정이 아니다.
- Web request handler가 LLM pipeline을 직접 실행하지 않는다.

## 3. CASE-03

CASE-03은 traversal syntax와 direct sensitive-resource request를 구분하는 demo/evidence case다.

현재 상태:

~~~text
runtime / artifact identity: PASS / FROZEN
evidence freeze: PASS / FROZEN
~~~

핵심 의미:

- bounded traversal syntax와 direct resource token을 같은 signal로 합치지 않는다.
- direct sensitive-resource request만으로 traversal/CWE-22를 확정하지 않는다.
- Viewer는 candidate/context 구분을 presentation에서 유지한다.

## 4. CASE-06

CASE-06은 bounded Command Injection grammar를 보여주는 demo/evidence case다.

최근 verified runtime evidence:

~~~text
request shape:
  GET /search?cmd=%3Bps

Prepare:
  cmdi:semicolon_exec 계열 signal

Stage1:
  suspicious_command_injection

Standards:
  CWE-78
  WSTG-INPV-12
  OWASP Injection-related enrichment

Stage2 / Viewer:
  CMDi-like request
  command execution unverified
~~~

현재 상태:

~~~text
runtime / artifact identity: PASS / FROZEN
Viewer presentation: PASS
~~~

이 결과는 OS command 실행 성공을 의미하지 않는다.

## 5. Viewer presentation boundary

Viewer는 `viewer_payload.v1`의 의미를 재판정하지 않는다.

최근 technical baseline에서는 CASE-06 presentation correction 이후에도 source payload identity를 유지하면서 표시 category/label을 수정하는 presentation-only 경계가 확인됐다.

~~~text
Viewer presentation change
!= payload semantic rewrite
!= verdict recalculation
~~~

## 6. UI audit

최종 UI audit은 다음 사용자 화면을 대상으로 수행됐다.

- Job Dashboard
- New Job
- Job Detail
- Analysis Viewer
- Live Monitoring

검토 항목:

- Korean-first terminology
- 1366px 발표 화면 가독성
- table overflow / sticky header
- selected row/detail hierarchy
- Viewer finding/context/supporting-event 구분
- Job lifecycle / artifact 진입
- light-mode Live readability

이 audit은 UI/presentation 검토이며 분석 의미 계약을 변경하지 않았다.

## 7. External / offline verification

External benchmark와 Prepare full-output harness는 current user runtime과 구분한다.

~~~text
offline verification asset
!= runtime feature
!= current production PASS by existence
~~~

실행 결과를 주장할 때는 source/corpus/input identity와 해당 revision의 실제 실행 evidence를 함께 기록한다.

## 8. Demo / presentation readiness

현재 발표에서 사용하는 canonical 흐름:

~~~text
Dashboard
  -> Live Monitoring
  -> selected logs / Job
  -> Job Detail
  -> Analysis Viewer
~~~

새 provider-backed Job 실행이 발표 환경에서 불안정할 경우, 동일한 흐름으로 미리 완료·검증한 Job을 사용하는 것을 허용한다.

발표용 screenshot/video는 다음 경계를 지켜야 한다.

- secret/API key/DB credential 노출 금지
- 불필요한 실제 사용자 식별정보 최소화
- 공격 성공/침해 성공으로 과장 금지
- screenshot이 어떤 Job/revision을 기준으로 하는지 추적 가능해야 함

## 9. Verification terminology

| 값 | 의미 |
| --- | --- |
| PASS | 해당 revision에서 실제 확인된 검증이 acceptance condition을 충족 |
| FAIL | 실행했지만 acceptance condition을 충족하지 못함 |
| BLOCKED | 전제/환경/identity 부족으로 실행 또는 판정 불가 |
| NOT RUN | 해당 revision에서 실행하지 않음 |

Documentation-only commit이 뒤에 추가됐다는 이유만으로 technical baseline의 테스트를 current HEAD에서 다시 실행했다고 표현하지 않는다.

## 10. 현재 남은 발표 작업

기술 runtime 구현과 별개로 남은 작업은 발표 산출물 준비다.

- PPT 최종화
- demo 순서 확정
- fallback screenshot/video 정리
- 발표 스크립트/Q&A
- 최종 제출본 백업

현재 architecture는 [Current Architecture](../00_current_architecture.md), 의미 경계는 [Apache logs-only Evidence Boundary](../00_apache_logs_only_evidence_boundary.md)를 기준으로 한다.
