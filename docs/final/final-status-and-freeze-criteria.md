# Final Status & Freeze Criteria

- 기준일: 2026-09-10
- 이 문서의 작성 기준 revision: `71e8c90f9012ad98330e46280ddd7c011a64ad87`
- 대상: 2026년 9월 Final Code Freeze 및 이후 최종 마크업
- 문서 상태: **Active / canonical** — Final 범위의 상태 관리와 freeze 승인 기준
- 범위 기준: [Final Scope](./final-scope.md)
- runtime 기준: [Current Architecture](../00_current_architecture.md)
- demo 기준: [Final Demo Casebook](./final-demo-casebook.md)
- limitation 및 terminology 기준: [Final Known Limitations & Terminology](./final-known-limitations.md)
- 문서 상태·권위 정책: [Documentation Naming & Status Policy](./documentation-naming-status-policy.md), [Design Documentation Index](../design/README.md)

## 1. 목적과 기준

이 문서는 현재 기능을 다시 설명하는 구현 명세가 아니다. 2026년 9월 Final에서 무엇을 freeze 대상으로 삼는지, 실제 verification 결과를 어떻게 기록하는지, Conditional Final을 언제 승격하거나 강등하는지, 그리고 2026-09-27 Code Freeze를 어떤 근거로 승인하는지를 고정한다.

Final Scope가 **무엇을 Final / Conditional Final / Deferred로 분류하는가**를 정한다면, 이 문서는 해당 분류의 **검증 상태와 freeze 의사결정 규칙**을 정한다. source 또는 test가 존재한다는 사실, static review 결과, 과거 benchmark 결과는 이 문서에서 현재 freeze verification `PASS`가 아니다.

이 문서의 revision은 작성 시점 checkout만 가리킨다. 이후 main에 들어오는 technical commit의 존재·효과·검증 결과를 이 문서가 미리 추정하지 않는다.

## 2. 세 가지 상태 축

다음 세 축은 독립적이며 서로를 대체하지 않는다.

| 축 | 값 | 의미 |
| --- | --- | --- |
| Scope Status | `Final` / `Conditional Final` / `Deferred` | 2026년 9월 Final 범위에 포함되는 방식과 승격 필요 여부 |
| Verification Status | `PASS` / `FAIL` / `BLOCKED` / `NOT RUN` | 특정 revision에서 특정 check를 실제로 검증한 결과 |
| Document Status | `Active` / `Historical` / `Superseded` | 문서의 현재 참조·권위 관계 |

예를 들어 아래 조합은 정상이다.

```text
Shared Security Signal Extractor
Scope Status = Conditional Final
Document Status = Active
Verification Status = NOT RUN
```

따라서 다음 등식은 사용하지 않는다.

```text
Active = PASS
Final = 모든 테스트 PASS
Deferred = FAIL
```

`Final`은 freeze 대상이라는 뜻이며, 실제 freeze revision에서 요구된 check의 결과는 별도로 남겨야 한다. `Active`는 현재 읽을 문서라는 뜻일 뿐 구현·통합·runtime PASS를 뜻하지 않는다. `Deferred`는 이번 Final 범위 밖으로 의도적으로 이관한 항목이지 실패 판정이 아니다.

## 3. Final Scope Freeze 대상

아래는 [Final Scope](./final-scope.md)의 Final 확정 항목이다. `현재 구현/참조 상태` 열은 현재 architecture와 scope의 기준 위치를 보여줄 뿐 실행 결과가 아니다. freeze verification은 이번 문서 작성 중 실행하지 않았으므로 모두 `NOT RUN`으로 시작한다.

| Scope / Component | Scope Status | 현재 구현/참조 상태 | Freeze verification 결과 |
| --- | --- | --- | --- |
| Apache → MariaDB ingest 구조 | Final | canonical runtime architecture의 Apache logs → shipper/ingest → MariaDB 경로 | `NOT RUN` |
| DB-backed `full_report` Job | Final | 시간 범위 기반 Job 등록이 Final 운영 진입점으로 정의됨 | `NOT RUN` |
| Analysis Job Worker / lifecycle | Final | `PENDING → RUNNING → SUCCEEDED/FAILED` lifecycle이 canonical으로 정의됨 | `NOT RUN` |
| Export | Final | full_report pipeline의 시간 범위 export 단계 | `NOT RUN` |
| Prepare | Final | deterministic preprocessing 단계 | `NOT RUN` |
| Stage1 | Final | evidence 기반 LLM classification 단계 | `NOT RUN` |
| Security Standards Mapping | Final | Stage1 뒤 finding-level deterministic enrichment | `NOT RUN` |
| Stage2 | Final | finding 종합 및 report synthesis 단계 | `NOT RUN` |
| Security Standards Summary | Final | deduplicated finding aggregate | `NOT RUN` |
| Report Viewer | Final | 완료 report와 viewer payload의 read-only interpretation layer | `NOT RUN` |
| Apache logs-only evidence boundary | Final | UI·문서·발표 claim의 canonical 의미 경계 | `NOT RUN` (freeze wording review 필요) |
| 대표 demo/regression fixture | Final | casebook의 Primary/Supporting fixture 및 regression 근거 | `NOT RUN` |
| final verification record | Final | 실제 freeze evidence를 기록할 별도 record | `NOT RUN` (record 작성 전) |

이 표의 `NOT RUN`은 구현 부재 또는 실패를 뜻하지 않는다. 이 revision에서 freeze check를 실행·기록하지 않았다는 뜻이다. 반대로 source·test·design·historical PASS가 있어도 해당 check를 현재 revision에서 수행하지 않았다면 `PASS`로 채우지 않는다.

## 4. Verification Status

Verification Status는 각 Check ID마다 정확히 하나만 기록한다.

| 상태 | 정확한 의미 |
| --- | --- |
| `PASS` | 해당 revision에서 실제 검증을 실행했고, 미리 정한 expected/acceptance condition을 충족했다. |
| `FAIL` | 실제 검증을 실행했으나 expected/acceptance condition을 충족하지 못했다. |
| `BLOCKED` | 필요한 전제, source/fixture identity, 환경 또는 접근 조건이 없어 실행 또는 판정할 수 없다. |
| `NOT RUN` | 해당 revision에서 검증을 실행하지 않았다. |

다음은 Verification Status가 아니다.

```text
likely pass
static looks good
should work
historical pass
mostly done
```

static review는 runtime compatibility와 같은 check가 아니다. 예를 들어 Harness의 결과는 다음처럼 분리해 기록한다.

```text
B static review = PASS
C runtime self-validation = NOT RUN
```

첫 줄은 B라는 별도 static review check의 결과이고, 둘째 줄을 `PASS`로 추론하게 하지 않는다. 과거 revision의 `PASS`도 historical evidence일 뿐 freeze revision의 current `PASS`를 대신하지 않는다.

## 5. Conditional Promotion Matrix

각 Conditional Final은 독립된 승격 단위다. 하나의 항목의 `FAIL`, `BLOCKED`, `NOT RUN`이 다른 항목의 결과나 Final MVP 전체에 자동 전파되지 않는다.

| Conditional item | Scope Status | required promotion gates | 승격 시 필수 판정 |
| --- | --- | --- | --- |
| Prepare Full-output Harness | Conditional Final | B static implementation → C self-validation → D source/corpus identity → E before baseline → after comparison → comparison evidence record | 각 required gate `PASS`; static PASS만으로 runtime compatibility PASS를 주장하지 않음 |
| Shared Security Signal Extractor | Conditional Final | C PASS → D PASS → E before baseline 확보 → shared extractor implementation → after comparison → Prepare full-output compatibility PASS; expectation family 분리 유지 | 모든 gate `PASS`, compatibility / corrected / live_adoption을 섞지 않음 |
| Live Monitoring v3.1 | Conditional Final | remote-preserved checkpoint → main integration → Live regression → existing Web regression → SELECT-only DB integration → Apache → Shipper → MariaDB → Live E2E | 모든 gate `PASS`; Shared Extractor 없이도 독립 승격 가능 |
| Live Security Observation | Conditional Final | shared extractor compatibility PASS → live_adoption PASS → `processing_status` / `assessment` 2축 유지 → no-success-inference review | 모든 gate `PASS`; Live Monitoring과 별도 판정 |
| Live → Analysis Job | Conditional Final | existing Job lifecycle reuse → 전달 contract 확정 → Live가 Prepare/Stage1/Stage2를 직접 호출하지 않음 → Job detail / Viewer E2E | 모든 gate `PASS`; 기존 full_report Job 흐름에 연결 |

### 5.1 Prepare Full-output Harness

승격 sequence는 아래 순서를 유지한다.

```text
B static implementation PASS
    → C self-validation PASS
    → D source/corpus identity PASS
    → E before baseline 확보
    → after comparison
    → comparison evidence record
```

comparison evidence에는 `build_outputs()`의 전체 반환값, typed value strict comparison, exception exact type/message, input mutation, baseline completion/checksum/hash/path/symlink, source/input identity의 결과를 필요한 범위에서 남긴다. B static implementation `PASS`는 harness 구조의 검토 결과일 뿐 runtime capture 또는 compatibility `PASS`가 아니다.

### 5.2 Shared Security Signal Extractor

Shared Extractor는 C/D/E와 before/after comparison을 통과하고, 구현 후 Prepare full-output compatibility `PASS`가 확인되어야 Final로 승격할 수 있다. extractor는 deterministic signal facts만 공유하며 DB/file/network I/O, score, severity, verdict, candidate selection을 맡지 않는 계약을 유지한다.

다음 expectation family는 별도의 check family로 유지한다.

```text
compatibility  = 기존 승인 behavior와의 호환성
corrected      = 의도적으로 수정한 expectation의 정확성
live_adoption  = Live가 extractor를 채택할 때의 별도 contract
```

한 family의 `PASS`는 다른 family의 `PASS`가 아니다. 특히 corrected expectation은 compatibility 비교를 덮어쓰지 않으며, Live adoption은 Prepare compatibility를 대체하지 않는다.

### 5.3 Live Monitoring v3.1

기본 Live Monitoring은 Shared Extractor가 없어도 독립적으로 승격할 수 있다. remote에 보존된 checkpoint와 main integration을 확인한 뒤 Live regression, 기존 Web regression, `apache_security_logs`에 대한 SELECT-only DB integration, Apache → Shipper → MariaDB → Live 신규 행 표시 E2E를 각각 확인한다.

승격 후에도 Live 조회 경로는 Prepare, Stage1, Mapping, Stage2, Worker를 직접 호출하지 않고, raw data 출력은 escaping/안전한 text rendering 경계를 유지해야 한다. 최신 로그 age만으로 장애·지연을 자동 판정하지 않는다.

### 5.4 Live Security Observation

Live Security Observation은 Live Monitoring의 부속 라벨이 아니라 별도 Conditional Final이다. Shared Extractor compatibility와 `live_adoption`이 모두 `PASS`여야 하며, `processing_status`와 `assessment`를 다른 축으로 표시해야 한다. `no_signal`은 normal/safe가 아니고, observation은 severity, exploit success, incident verdict를 새로 만들지 않는다.

### 5.5 Live → Analysis Job

Live에서 분석을 시작하는 기능은 새 pipeline을 만들지 않는다. 기존 `full_report` Job lifecycle을 재사용하고, 선택 로그 또는 시간 범위 전달 contract를 명시적으로 확정해야 한다. Live 경로가 Prepare/Stage1/Stage2를 직접 호출하면 gate를 통과할 수 없다. Job 생성 뒤 기존 Job detail과 Viewer에서 결과를 읽을 수 있는 E2E가 필요하다.

## 6. Promotion / Demotion Rules

Conditional Final의 판정 규칙은 다음과 같다.

```text
Conditional Final + 모든 required gate PASS
→ Final 승격 가능

required gate FAIL
→ 승격 금지

required gate BLOCKED
→ 승격 금지; blocker 해소 전 Conditional Final 유지

required gate NOT RUN
→ 승격 금지

일정상 required gate 미완료
→ Conditional Final 유지 또는 Deferred / 진행 중 기술 항목으로 강등 가능
```

강등은 실패라는 수사적 표현이 아니라 Final claim을 정확히 맞추는 범위 조정이다. `Deferred`로 옮긴 항목은 Final 제품에 포함된 것처럼 UI·문서·발표에서 표현하지 않는다.

Conditional 하나의 승격 실패가 전체 Final 제품을 자동으로 `FAIL`하게 하지는 않는다. 예를 들어 Shared Extractor가 미완료여도 해당 항목만 Conditional Final 또는 Deferred로 남기고, 기본 Live Monitoring이 자신의 독립 gate를 모두 `PASS`하면 Live Monitoring은 Final로 승격할 수 있다. 반대로 Live Security Observation이 미완료여도 Live Monitoring의 독립 승격을 막지 않는다.

## 7. Core Freeze Blockers

### 7.1 전체 Final Freeze를 BLOCK하는 조건

다음은 Final MVP의 핵심 계약 또는 truthful Final claim을 훼손하므로, 영향이 해소·검증되기 전 2026-09-27 전체 Code Freeze를 승인할 수 없는 blocker 후보다.

- main branch와 freeze revision identity가 불명확하거나 dirty/staged 상태의 범위를 확정할 수 없음
- 핵심 DB-backed `full_report` Job 경로를 실행할 수 없음
- Analysis Job Worker가 정상 결과 또는 실패 결과를 포함해 정의된 terminal state에 도달하지 못함
- Export, Prepare, Stage1, deterministic Security Standards Mapping, Stage2, Security Standards Summary 중 핵심 runtime이 중단되어 정상 full_report 결과를 만들 수 없음
- Report Viewer가 완료 report / viewer payload를 표시할 수 없음
- freeze regression에서 Final의 핵심 기존 기능 regression이 확인됨
- Apache logs-only evidence boundary와 실제 Final UI·문서·발표 claim 사이에 exploit success, compromise, vulnerability confirmation 등을 심각하게 과장하는 충돌이 남아 있음
- 핵심 `BLOCKED` check의 영향 범위가 Final MVP까지인지 판단할 수 없어 승인 근거를 만들 수 없음

`FAILED` terminal state는 Worker가 오류를 truthfully 종료·기록한 결과일 수 있다. 이 문서에서 blocker는 Worker가 정상적으로 terminal lifecycle을 관리하지 못하는 경우 또는 Final acceptance condition을 충족하는 core path가 실패한 경우를 뜻한다.

### 7.2 해당 기능만 비승격·제외하는 조건

다음은 기존 Final MVP의 core checks가 충족되는 한 전체 freeze blocker가 아니라 해당 범위의 비승격 또는 Deferred 사유다.

- Live Monitoring v3.1이 main에 미통합이거나 자체 gate를 통과하지 못함
- Shared Security Signal Extractor가 미완료이거나 compatibility evidence가 없음
- Live Security Observation이 미완료이거나 `live_adoption` gate를 통과하지 못함
- Live → Analysis Job workflow가 미완료
- 명시된 Deferred 기능이 미구현
- non-core optional check 또는 historical benchmark가 `NOT RUN`

다만 이 항목이 이미 Final UI·문서·발표에서 Final로 claim되고 있거나 core path를 실제로 손상시키면, 단순 비승격 사유가 아니라 claim 정정 또는 core blocker로 재평가한다.

## 8. Verification Evidence Contract

향후 `final-verification-record.md`는 check 한 건마다 최소 아래 metadata를 보관한다. record는 실행 log를 무비판적으로 붙이는 장소가 아니라 revision별 판정과 재현 근거를 남기는 문서다.

| Field | 기록 기준 |
| --- | --- |
| Check ID | 이 문서의 ID convention에 따른 안정적인 식별자 |
| Scope / Component | 검증 대상 기능 또는 계약 |
| Required for Freeze? | `yes` 또는 `no` |
| Required for Promotion? | 해당 Conditional item의 이름 또는 `none` |
| Revision | 검증한 commit SHA와 필요한 경우 branch |
| Date/time | 실행 또는 판정 시각과 timezone |
| Environment | OS, runtime, dependency/provider, DB/fixture 등 판정에 필요한 비밀 없는 환경 요약 |
| Command / Procedure | 실제 실행 command 또는 수동 검토 절차 |
| Expected | 사전에 정한 acceptance condition |
| Actual | 관찰된 결과와 핵심 차이 |
| Status | `PASS` / `FAIL` / `BLOCKED` / `NOT RUN` 중 하나 |
| Evidence / artifact path | log, screenshot, artifact, checksum, fixture, issue 등 재검토 가능한 경로 |
| Notes / blocker | 제한, 재실행 조건, blocker owner/next action 등 |

record에는 secret, token, password, connection string, authorization/cookie, raw sensitive payload 또는 내부 민감정보를 저장하지 않는다. 필요한 경우 redacted artifact path와 재현에 충분한 비밀 없는 환경 설명만 남긴다.

## 9. Final Gates

### Gate 0 — Scope / Documentation Baseline

다음 Active documentation baseline의 존재와 연결을 확인한다.

- `final-scope.md`
- canonical current architecture
- `final-demo-casebook.md`
- `final-known-limitations.md`

Gate 0는 documentation baseline check이며 runtime `PASS`가 아니다. 문서가 `Active`라는 사실도 runtime verification 결과가 아니다.

### Gate 1 — Source Identity

- freeze revision과 branch/commit을 확정한다.
- dirty/staged 상태와 그 허용 여부를 기록한다.
- demo fixture, expected contract, source/corpus/baseline의 identity를 확인한다.
- comparison이 있으면 before/after artifact 및 checksum/hash/path 같은 identity evidence를 연결한다.

identity가 불명확하면 결과를 과거 evidence나 다른 checkout에서 가져와 `PASS`로 쓸 수 없으며 `BLOCKED` 또는 `FAIL`로 정확히 기록한다.

### Gate 2 — Core Runtime Verification

Final 확정 runtime의 실제 required checks를 수행한다. Apache → MariaDB ingest, DB-backed `full_report` Job, Worker lifecycle, Export → Prepare → Stage1 → Mapping → Stage2 → Summary, report/artifact 생성, Viewer 표시, core regression과 evidence-boundary wording review가 대상이다. 각 결과는 component별 Check ID와 evidence로 남긴다.

### Gate 3 — Conditional Promotion

Harness, Shared Extractor, Live Monitoring, Live Security Observation, Live → Analysis Job을 Section 5의 matrix대로 각각 독립 판정한다. Gate 3의 결과는 core Final MVP result와 분리해 기록한다.

### Gate 4 — Demo Fixture Freeze

- 날짜: **2026-09-26**
- 발표 입력, fixture/expected/test identity, 대표 사례와 의미 경계를 고정한다.
- 이후 fixture의 의미를 바꾸는 변경은 허용하지 않는다. 불가피한 수정은 revision을 새로 기록하고 관련 check를 재수행한다.

### Gate 5 — Code Freeze

- 날짜: **2026-09-27**
- 승인된 freeze revision을 기록한다.
- core required check, Conditional item 상태, known limitation, demo fixture identity, Final claim을 함께 검토한다.
- P0/critical fix 외 신규 기능 변경을 중단한다.

### Gate 6 — Final Markup

- 날짜: **2026-09-28 ~ 2026-09-30**
- architecture, README, UI wording, screenshot, 발표 자료, appendix, limitations, verification evidence를 freeze decision과 일치시킨다.
- Final/Conditional Final/Deferred 표기와 PASS/FAIL/BLOCKED/NOT RUN 결과를 혼동 없이 반영한다.

## 10. 2026-09-27 Code Freeze Decision

### Freeze 가능

다음이 모두 충족되면 freeze를 승인할 수 있다.

- Core Final runtime의 required checks가 `PASS`다.
- Section 7.1의 known core blocker가 없다.
- freeze revision과 source/fixture identity가 고정되어 있다.
- demo fixture가 Gate 4 기준으로 고정되고 재현 evidence가 있다.
- Conditional 항목별 Scope Status와 promotion check 결과가 정확히 기록되어 있다.
- known limitations가 기록되어 있으며, Deferred가 Final처럼 표시되지 않는다.
- UI·문서·발표 claim이 Apache logs-only evidence boundary를 지킨다.

### Freeze 불가

다음 중 하나라도 있으면 전체 freeze를 승인하지 않는다.

- core required check가 `FAIL`이다.
- 핵심 verification이 `BLOCKED`이고 Final MVP에 미치는 영향 범위를 확정할 수 없다.
- revision, source, fixture identity가 불명확하다.
- 고정한 demo가 재현되지 않는다.
- report 또는 Viewer의 핵심 경로가 깨졌다.
- Final UI·문서·발표에 evidence boundary를 넘는 잘못된 claim이 남아 있다.

### Freeze 가능하지만 Known Limitation 필요

다음은 core Final MVP가 `PASS`이고 정확한 비승격·limitation 표기가 있다는 조건에서 freeze를 막지 않는다.

- non-core optional check가 `NOT RUN`
- Conditional Final 기능이 승격되지 않음
- historical benchmark를 freeze revision에서 재실행하지 않음
- Post-final 기능이 미구현

이 경우 record에는 해당 항목의 Scope Status와 Verification Status를 그대로 쓰고, `PASS`처럼 보이도록 요약하거나 Final 본편 claim에 포함하지 않는다.

## 11. Check ID Convention

final verification record에서 관리 가능한 수준의 prefix를 사용한다. 번호는 각 prefix 안에서 2자리 또는 3자리로 증가시키며, Check ID는 revision이 바뀌어도 같은 계약이면 유지한다.

| Prefix | 대상 예시 |
| --- | --- |
| `DOC-*` | Gate 0 문서 baseline, wording/evidence-boundary review |
| `ID-*` | branch/commit, dirty state, fixture/source/corpus identity |
| `CORE-*` | `full_report` Job, Worker lifecycle, core pipeline terminal result |
| `PIPE-*` | Export, Prepare, Stage1, Stage2, artifact contract |
| `WEB-*` | Job detail, report route, Report Viewer |
| `STD-*` | Security Standards Mapping / Summary contract |
| `HARNESS-*` | B/C/D/E, before/after full-output comparison |
| `SHARED-*` | Shared Extractor implementation and compatibility family |
| `LIVE-*` | Live Monitoring / Observation checks |
| `E2E-*` | Apache→Shipper→MariaDB→Live, Live→Job→Viewer end-to-end |
| `DEMO-*` | fixture freeze, representative demo regression/reproduction |

예: `ID-01`, `CORE-02`, `HARNESS-C-01`, `SHARED-COMP-01`, `LIVE-REG-01`, `E2E-LIVE-01`, `DEMO-03`. 하나의 check가 Freeze와 Conditional promotion 양쪽에 관련되더라도 record의 `Required for Freeze?`와 `Required for Promotion?` 필드로 역할을 명시한다.

## 12. Initial Status Snapshot

이 snapshot은 위 기준 revision checkout의 문서·scope 위치를 기록한다. 이번 문서 작성에서는 test, benchmark, DB, LLM, network, production runtime을 실행하지 않았으므로 runtime/technical result를 `PASS`로 채우지 않는다.

| 대상 | Scope Status | Document / checkpoint 상태 | Verification Status at this snapshot |
| --- | --- | --- | --- |
| Final Scope document | n/a | present; Active canonical scope baseline | `NOT RUN` (runtime check 아님) |
| Canonical Architecture | n/a | present; Active canonical runtime description | `NOT RUN` (runtime check 아님) |
| Final Demo Casebook | n/a | present; Active demo/fixture baseline | `NOT RUN` (runtime reproduction 미실행) |
| Known Limitations | n/a | present; Active terminology/evidence-boundary baseline | `NOT RUN` (freeze wording review 미실행) |
| Prepare Full-output Harness | Conditional Final | B static implementation `PASS`가 scope에 별도 review result로 기록됨 | C onward pending / freeze runtime checks `NOT RUN` |
| Shared Security Signal Extractor | Conditional Final | Active Conditional design/regression assets; Final runtime 실선에는 미포함 | `NOT RUN` for required promotion verification |
| Live Monitoring v3.1 | Conditional Final | main integration pending으로 기록됨 | `NOT RUN` for integration/regression/E2E |
| Live Security Observation | Conditional Final | Live Monitoring과 독립된 Conditional scope | `NOT RUN` for compatibility/live_adoption/wording gates |
| Live → Analysis Job | Conditional Final | 전달 contract와 E2E가 승격 전 조건 | `NOT RUN` |
| Deferred / Post-final items | Deferred | Final 범위 밖으로 명시됨 | `NOT RUN`은 `FAIL` 또는 Final claim으로 바꾸지 않음 |

`present`는 documentation checkpoint의 존재만 뜻한다. 이 snapshot은 current source에 새 technical commit이 있는지, 작동하는지, 이전 결과가 재현되는지를 추정하지 않는다. 실제 결과는 freeze revision에서 실행 후 verification record에 추가한다.

## 13. Freeze 이후 변경 정책

2026-09-27 Code Freeze 이후에는 다음만 원칙적으로 허용한다.

- critical bug fix
- security/privacy fix
- broken documentation/link fix
- 명백한 사실 오류 수정

다음은 원칙적으로 금지한다.

- 신규 기능
- 새 attack family 또는 coverage 확대
- architecture 확대
- fixture 의미 변경
- UX 확장
- benchmark scope 확대

freeze 후 code, fixture, runtime contract, UI claim 또는 환경 의존성에 변경이 생기면 영향을 받은 check의 revision을 갱신하고 relevant verification을 다시 실행해야 한다. 이전 revision의 `PASS`를 변경 후 revision에 복사하지 않는다. 변경이 core Final contract를 바꾸면 Code Freeze 승인 자체를 재검토하고, Conditional 항목을 바꾸면 해당 항목의 promotion gate를 다시 판정한다.
