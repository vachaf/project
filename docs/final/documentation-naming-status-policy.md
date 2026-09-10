# Documentation Naming & Status Policy v0.2

- 작성일: 2026-09-10
- 목적: 2026년 9월 Final 마크업을 앞두고 `docs/design/` 전체 문서의 **이름, 상태, 권위, 기술 결정 상태, Final 역할, 후속 문서 관계**를 일관되게 관리한다.
- 적용 범위: `docs/design/` 전체와 Final 제출/발표에서 직접 참조하는 관련 문서
- 상태: **채택 후보 — design 문서 전체 적용 기준**
- 적용 원칙: 모든 문서를 지금 rename하거나 병합하지 않는다. 먼저 상태와 권위 관계를 정리하고, rename은 Final-reference active 문서에 제한한다.

> **핵심 원칙:** 문서가 `Active`라는 사실과 구현·검증이 완료되었다는 사실은 서로 다르다.  
> 문서의 사용 상태와 기술/결정 상태를 반드시 분리한다.

---

## 1. 관리 축

모든 design 문서는 가능하면 아래 여섯 축으로 관리한다.

### 1.1 문서 분류

```text
Active
Historical
Superseded
```

- **Active**: 현재 Final architecture·운영·검증·발표에서 읽어야 하는 문서
- **Historical**: 당시 결정·실험·검토 기록. 현재 기준 문서는 아님
- **Superseded**: 후속 문서가 의미·계약을 승계한 문서

### 1.2 현재 권위

```text
canonical
supporting
record only
```

- **canonical**: 해당 주제의 현재 기준 문서
- **supporting**: canonical을 뒷받침하는 세부 설계·검토 근거
- **record only**: 역사적 증적 또는 당시 판단 기록

### 1.3 결정 상태

```text
adopted
proposed
deferred
blocked
not run
```

- **adopted**: 현재 프로젝트 기준으로 채택된 계약/정책
- **proposed**: 아직 최종 승인되지 않은 제안
- **deferred**: Post-final로 의도적으로 연기
- **blocked**: 선행조건 부족으로 진행 불가
- **not run**: 실행/검증이 수행되지 않음

### 1.4 Final 역할

```text
runtime
verification
appendix
deferred evidence
```

- **runtime**: 실제 Final 실행 흐름을 설명
- **verification**: regression/harness/benchmark 등 검증 근거
- **appendix**: 발표·논문 부록 근거
- **deferred evidence**: 이번 Final에서는 제외된 후속 기능의 기록

### 1.5 최신 후속 문서

Superseded 또는 Historical 문서가 현재 무엇으로 이어지는지 명시한다.

예:

```text
docs/design/103_shared_security_signal_extractor_design.md
→ docs/design/114_shared_security_signal_extractor_design.md
```

### 1.6 기준 시점

가능하면 다음 중 하나 이상을 기록한다.

```text
기준 revision
기준 commit
기준 date
검증 revision
```

과거 PASS나 당시 구현 상태를 현재 Final 상태로 오해하지 않게 하기 위함이다.

---

## 2. 모든 design 문서에 적용할 수 있는가

### 결론

**상태·권위·후속 관계 정책은 모든 `docs/design/` 문서에 적용한다.**

다만 다음은 구분한다.

```text
전체 design 문서
→ 상태/권위/결정 상태/Final 역할 분류 적용

Phase가 명확한 active 문서
→ Phase naming 적용 후보

99_* 및 오래된 planning/review 문서
→ 이번 Final에서는 rename하지 않고 상태만 관리
```

---

## 3. 문서군별 기본 처리 원칙

| 문서군 | 기본 분류 | 권위 | Final 역할 | 통합 원칙 |
| --- | --- | --- | --- | --- |
| DB-backed Job / Worker / Web safety | Active | supporting | runtime | `00_current_architecture`에서 요약, 세부 문서는 유지 |
| Prepare candidate policy | Active | canonical | runtime | `99_prepare_candidate_policy.md` 유지 |
| Prepare split/constants/hints | Historical 또는 Active supporting | supporting/record only | runtime evidence | summary만 active, round별 문서는 historical |
| Standards Mapping | Active | canonical/supporting | runtime | Summary와 병합하지 않음 |
| Standards Summary | Active | canonical/supporting | runtime | Mapping과 목적이 다르므로 분리 |
| External benchmark 101~113 | Historical 또는 appendix-active | supporting/record only | verification/appendix | 상세 provenance 문서는 병합 금지 |
| Shared extractor 103/104 | Superseded | record only | deferred evidence/history | 114/115 후속 링크 명시 |
| Shared extractor 114/115/116 | Active | canonical/supporting | verification / conditional runtime | design/regression/harness 역할 분리 유지 |
| Web Viewer phase 계획 | Historical | record only | runtime evidence | Final용 canonical web summary 신설 |
| Sliding Window / Rollup / Operator Queue | Historical / Deferred supporting | supporting/record only | deferred evidence | Final runtime 본편에서 제외 |
| Observability 실험 / capability matrix | Historical supporting | supporting | appendix/deferred evidence | 필요한 부분만 Final 근거로 참조 |
| Coverage / fixture plan | Historical supporting | record only | verification | 실제 fixture casebook으로 Final 통합 |

---

## 4. 즉시 Superseded 처리할 문서

### 4.1 Shared Extractor

```text
docs/design/103_shared_security_signal_extractor_design.md
→ Superseded
→ 최신 후속: docs/design/114_shared_security_signal_extractor_design.md
```

```text
docs/design/104_shared_security_signal_extractor_regression_plan.md
→ Superseded
→ 최신 후속:
   docs/design/115_shared_security_signal_extractor_regression_plan.md
   docs/design/116_prepare_full_output_comparison_harness_spec.md
```

103/104는 삭제하지 않는다. Final active index에서는 제외하고 historical/superseded reference로 보존한다.

---

## 5. 통합해야 하는 곳

통합은 **원문 파일 병합·삭제**가 아니라 **canonical summary 신설**을 기본으로 한다.

### 5.1 Job Architecture

세부 근거:

```text
99_db_backed_log_collection_and_analysis_job_design.md
99_db_backed_web_ui_api_safety_addendum.md
99_analysis_job_modes_and_sliding_window_integration.md
99_analysis_job_stage_events_design.md
99_analysis_job_stale_running_recovery_policy.md
```

Final 기준:

```text
docs/00_current_architecture.md
```

또는 추후:

```text
core-current-architecture.md
```

를 canonical summary로 사용한다.

세부 문서는 supporting/historical로 유지한다.

### 5.2 Report Viewer

여러 phase 계획·loader·UI polish 문서를 하나로 합치지 않는다.

Final canonical 후보:

```text
web-report-viewer-architecture.md
```

여기에 다음만 정리한다.

- 현재 사용자 흐름
- Viewer payload 역할
- Standards Mapping/Summary 표시 경계
- read-only 결과 해석 경계
- Job detail → Viewer 연결

기존 phase 문서는 Historical로 유지한다.

### 5.3 Final 검증 문서

다음 신규 문서는 기존 design/review 자료를 대체하지 않고 Final 관점에서 요약한다.

```text
final-scope.md
final-status-and-freeze-criteria.md
final-demo-casebook.md
final-verification-record.md
final-known-limitations.md
```

---

## 6. 통합하면 안 되는 곳

### 6.1 Standards Mapping / Standards Summary

분리 유지.

```text
Mapping
= finding-level deterministic enrichment

Summary
= deduplicated finding aggregate
```

### 6.2 Shared Extractor 114 / 115 / 116

분리 유지.

```text
114 = design
115 = regression plan
116 = harness specification
```

승인 단위가 다르므로 합치지 않는다.

### 6.3 CRS / CSIC 상세 benchmark 문서

분리 유지.

```text
source integrity
annotation
prepare baseline
semantic validation
controlled review
```

이 연쇄 자체가 provenance다.

---

## 7. Rename 적용 범위

### 7.1 우선 rename 후보

1. `114~116`
2. `100`
3. `101~113`은 Final appendix에서 실제로 적극 참조할 경우
4. `99_*`는 이번 Final에서는 rename하지 않음

### 7.2 권장 이름

```text
100_security_standards_coverage_summary_design.md
→ phase4b-01_security_standards_summary_design.md

114_shared_security_signal_extractor_design.md
→ phase7-01_shared_security_signal_extractor_design.md

115_shared_security_signal_extractor_regression_plan.md
→ phase7-02_shared_security_signal_extractor_regression_plan.md

116_prepare_full_output_comparison_harness_spec.md
→ phase7-03_prepare_full_output_harness_spec.md
```

101~113은 appendix 정책 확정 후 별도 mapping을 적용한다.

---

## 8. 99_* 문서 처리

`99_*`는 이번 Final에서 일괄 rename하지 않는다.

이유:

- 작성 시점과 phase가 뒤섞여 있음
- 내부 link와 history reference가 넓음
- 일부는 현재 코드의 세부 역사적 근거
- Final 직전 대규모 rename의 이득보다 위험이 큼

대신:

```text
docs/design/README.md
```

에서 상태·권위·Final 역할을 분명히 한다.

---

## 9. docs/design/README.md 권장 구조

```text
# Design Documentation Index

## Canonical / Active
현재 Final에서 직접 참조하는 설계

## Active Supporting
현재 canonical을 뒷받침하는 세부 설계

## Verification / Appendix
benchmark, regression, harness, provenance

## Superseded
후속 문서가 의미를 승계한 문서

## Historical
과거 phase/검토/실험 기록

## Deferred / Post-final
현재 Final 범위 밖이지만 후속 작업 근거로 보존
```

각 행에는 가능하면 다음 열을 둔다.

| Document | Classification | Authority | Decision Status | Final Role | Successor / Notes |
| --- | --- | --- | --- | --- | --- |

---

## 10. 실제 적용 순서

```text
1. v0.2 정책 승인
2. docs/design 전체 파일 inventory 생성
3. 각 문서에 Classification / Authority / Decision Status / Final Role 부여
4. 103/104 즉시 Superseded 처리
5. 114/115/116 Active 등록
6. canonical summary가 필요한 문서군 표시
7. docs/design/README.md index 개편
8. active Final-reference 문서 rename 대상 확정
9. git mv + 내부 link 갱신
10. broken-link 검사
11. 9/15 이후 대규모 rename 금지
```

---

## 11. 현재 권장 결론

```text
전체 design 문서
→ 상태·권위·후속 관계 분류 적용

Active 문서
→ Final index에서 우선 연결

Superseded 문서
→ 후속 문서 링크를 명시하고 보존

Historical 문서
→ 삭제·병합하지 않고 reference-only로 격하

Rename
→ active phase 문서부터 최소 범위로 적용

Integration
→ 원문 병합이 아니라 canonical summary 신설
```

가장 먼저 수행할 실제 작업은:

```text
docs/design/README.md에
Active / Historical / Superseded / Deferred 구조를 만들고

103/104 → Superseded
114/115/116 → Active

로 올리는 것
```

이다.
