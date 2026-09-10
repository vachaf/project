# Final Known Limitations & Terminology

- 기준일: 2026-09-10
- 기준 revision: `24133088907c9a53cc3c86b130b297544cb2283b` (`docs: add final demo casebook`)
- 범위 결정: [Final Scope](./final-scope.md)
- 현재 runtime: [Current Architecture](../00_current_architecture.md)
- 증거 해석의 canonical 기준: [Apache logs-only evidence boundary](../00_apache_logs_only_evidence_boundary.md)

## 1. 목적과 기준 revision

이 문서는 Final에서 **무엇을 할 수 없는지, 그 이유와 허용되는 표현**을 고정한다. 구현 TODO 목록이나 취약점 목록이 아니다. 범위 포함 여부와 승격 gate는 Final Scope를, 사례별 관찰과 비확정 경계는 [Final Demo Casebook](./final-demo-casebook.md)을 따른다.

## 2. Limitation 분류 원칙

| 분류 | 뜻 | Final에서의 처리 |
| --- | --- | --- |
| Evidence / Observability | Apache logs-only 원천으로 구조적으로 알 수 없는 사실 | 기능 미구현으로 표현하지 않고 증거 경계로 유지 |
| Final Runtime Product | 현재 확정 runtime이 의도적으로 제공하지 않는 기능 | 이번 Final의 제품 제한으로 명시 |
| Conditional Final | 자산은 있으나 통합·호환성·회귀·E2E gate가 남은 항목 | 현재 완료나 Final로 주장하지 않음 |
| Deferred / Post-final | 가치가 있으나 이번 Final 범위 밖인 확장 | 실패가 아니라 명시적 후속 이관 |

다음은 서로 바꿔 쓸 수 없다.

```text
limitation ≠ bug
deferred ≠ failed
NOT RUN ≠ FAIL
candidate-excluded ≠ benign
no-data ≠ no-signal
no-signal ≠ normal
HTTP status ≠ exploit success verdict
Standards Mapping ≠ vulnerability confirmation
Standards Summary ≠ compliance score
```

## 3. Apache Logs-only Evidence / Observability Limitations

Apache access/security/error log는 요청·응답 metadata와 로그에 남은 메시지를 관찰하는 원천이다. URI, query string, method, status, byte count, content type, User-Agent, 시간상 반복은 말할 수 있지만, 다음은 원천적으로 확정할 수 없다.

- 실제 response body 내용, 반환된 파일·비밀·개인정보의 내용
- raw POST body가 Apache log에 없을 때 그 body의 payload, 인증 정보 또는 의도
- DB query 실행 결과와 데이터 변경·조회 결과
- 애플리케이션 내부의 인증/인가 성공 상태
- browser JavaScript 실행, reflection, cookie 접근·전송
- OS command 실행 결과, RCE/침해 성공 여부
- file system의 실제 파일 존재, 읽기·업로드·삭제 성공 또는 노출 내용
- outbound callback, 실제 사용자 계정 탈취, crawler의 실제 정체

따라서 HTTP `200`, `text/html`, response byte 수, route 이름, IP, User-Agent는 관찰 evidence 또는 보조 context일 뿐 성공 판정이 아니다. `401/403/404/500`도 각각 기록된 HTTP 응답일 뿐 공격 실패·파일 부재·침해 성공을 확정하지 않는다.

POST body만이 신호인 요청은 현 baseline의 blind spot이다. raw body를 저장하거나 body-derived hint를 넣으면 Apache 공통/security 로그만의 baseline과 다른 별도 augmented mode가 된다. 자세한 근거는 [POST body visibility 한계](../design/99_POST_body_visibility_한계와_해석_기준.md)를 따른다.

`likely_html_fallback_response`는 현재의 보수적 response-surface 해석이다. 반면 `resp_html_*` fingerprint는 상류 생성 경로가 확정된 runtime evidence가 아니므로 Final 근거로 사용하지 않는다. [HTML fallback 보류 결정](../design/99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md)을 따른다.

file/resource 요청은 intent 또는 request pattern을 말할 수 있다. PHP wrapper, traversal syntax, direct sensitive-path probe는 서로 다른 관찰 신호이며, 어느 경우도 파일 존재·내용 반환·취약점 존재를 증명하지 않는다. [file disclosure taxonomy 검토](../design/99_file_disclosure_verdict_taxonomy_검토.md)를 따른다.

## 4. Final Runtime Product Limitations

확정 Final runtime은 시간 범위 `full_report` Job 등록, Worker lifecycle, 분석 pipeline, report/viewer 조회에 집중한다. 다음은 현재 의도적으로 제공하지 않는다.

- cancel, requeue, retry UX 및 확대된 worker health dashboard
- Viewer history, compare, 고급 filter/polish, context graph 및 relationship view
- sliding-window / `windowed_triage` 사용자 흐름과 operator queue
- WebSocket/SSE 기반 Live, Live duplicate collapse, Live masking
- standards drill-down/filter/dashboard badge 확대와 deterministic Markdown 추가

이는 고장이나 누락된 성공 조건이 아니라 현재 Final 제품 범위다. Viewer는 분석 의미를 재계산·변경하지 않는 **read-only interpretation layer**다. 반면 Web UI는 Job 생성과 상태/결과 조회를 수행할 수 있으므로 “Web UI 전체가 read-only”라고 쓰지 않는다.

## 5. Conditional Final Limitations

아래는 구현·설계·검증 자산이 존재해도 아직 Final runtime으로 승격하지 않는 항목이다. 상태와 세부 gate는 [Final Scope의 Conditional Final](./final-scope.md#3-conditional-final)을 우선한다.

| 항목 | 아직 확정할 수 없는 이유 / 승격 조건 |
| --- | --- |
| Shared Security Signal Extractor | C self-validation, D source/corpus identity, E before baseline, after comparison 및 Prepare full-output compatibility PASS가 필요하다. extractor 존재는 compatibility 완료가 아니다. |
| Prepare full-output compatibility | static harness PASS와 실제 전체 반환값 compatibility PASS는 다르다. typed value, exception, input mutation, baseline integrity, source identity를 포함한 gate가 남아 있다. |
| Live Monitoring v3.1 | 별도 작업 자산이며 main 통합, Live/기존 Web regression, SELECT-only DB integration, Apache→Shipper→MariaDB→Live E2E가 필요하다. |
| Live Security Observation | shared extractor compatibility와 `live_adoption` PASS, `processing_status`/assessment 2축, no-success-inference를 모두 유지해야 한다. |
| Live → Analysis Job integration | 기존 lifecycle 재사용, 전달 계약 확정, Live의 직접 pipeline 호출 금지 및 Job detail/Viewer E2E가 필요하다. |

특히 Live observation의 assessment 용어는 아래 7절에서 **Conditional Final terminology**로만 정의한다. 현재 Final runtime 결과에 이미 존재하는 상태처럼 표시하지 않는다.

## 6. Deferred / Post-final

다음은 이번 Final에서 의도적으로 범위 밖으로 둔다: 신규 attack family 및 coverage round 2, SSTI/XXE/LDAP/NoSQL/deserialization, API key·secret token, webshell command-query fixture, request smuggling/header anomaly, CRS resource coverage 확대, Sliding Window/operator queue 확대, run-id/overwrite/archive/dedupe 정책 확장이다.

Deferred는 “failed”나 버려진 TODO가 아니다. Final Scope에 기록된 Post-final backlog이며, 새 기능 자산이 있다는 사실만으로 이번 Final claim으로 승격하지 않는다.

## 7. Canonical Terminology

| 용어 | Final에서의 정확한 뜻 |
| --- | --- |
| analysis candidate | Prepare가 관찰 evidence를 근거로 후속 Stage1 분석 대상으로 구성한 요청/단위. 공격 성공 판정이 아니다. |
| candidate-excluded | candidate selection에서 제외된 행. benign, normal, safe 판정이 아니다. |
| filtered reason | 제외 또는 저신호 처리의 policy 설명 artifact. 대상의 안전성·무해성을 판정하지 않는다. |
| context-only | 보존할 문맥 정보이지만 finding/incident로 자동 승격하거나 severity를 단독으로 높이지 않는 신호. |
| finding | Stage1 분류 뒤 Stage2 입력에서 deduplicate된 분석 finding. 관찰 evidence 기반 분석 결과이며 취약점 확인이 아니다. |
| incident | report/Viewer가 finding 중심으로 제시하는 조사 단위 또는 요약 명칭. 침해사고 확정·성공 공격을 뜻하지 않는다. 가능하면 `finding` 또는 `incident candidate`로 범위를 함께 밝힌다. |
| observation | 로그에 실제로 기록되어 관찰된 metadata, request pattern 또는 context. 그 자체는 success verdict가 아니다. |
| standards_mapping | finding-level deterministic taxonomy/test-scenario enrichment. 새 detector, CWE 확인 또는 OWASP 위반 판정이 아니다. |
| standards_summary | deduplicated finding aggregate. compliance score 또는 전체 환경 coverage가 아니다. |
| processing_status | **Conditional Final terminology.** Live row/flow의 처리 가능·불완전 상태 축이며 보안 assessment가 아니다. |
| review_required | **Conditional Final terminology.** 관찰 signal의 추가 검토가 필요하다는 assessment. 성공·incident 확정이 아니다. |
| no_signal | **Conditional Final terminology.** 로그는 있으나 adopted observation signal이 없다는 assessment. normal/safe가 아니다. |
| undetermined | **Conditional Final terminology.** 처리 불완전, 입력/상태 불충분 또는 사용 불가로 assessment를 정할 수 없음. no_signal과 다르다. |

## 8. Claim / Wording Boundary

최종 UI, README, 발표에서 아래 대체 표현을 사용한다.

| 피해야 할 표현 | 권장 표현 |
| --- | --- |
| 정상 / 안전 | 관찰 신호 없음, candidate-excluded, context-only, baseline-like 등 실제 상태 |
| 공격 성공 | 관련 공격 패턴 또는 시도 정황 관찰 |
| SQL Injection 성공 | SQLi 관련 request pattern 관찰 |
| XSS 성공 | XSS-like request pattern 관찰 |
| CMDi/RCE 성공 | CMDi-like grammar와 command context 관찰 |
| 파일 유출 성공 | file/resource disclosure intent 또는 관련 request 관찰 |
| 취약점 확인 | 관련 taxonomy relationship/enrichment |
| OWASP 위반 | 관련 OWASP category relationship |
| CWE 발생 | 관련 CWE relationship |
| 탐지됨 | candidate, classified finding, observation 중 실제 단계에 맞는 표현 |

`detected`는 detector가 실제로 확정한 범위를 넓게 암시할 수 있다. UI label이나 발표에서는 `observed`, `analysis candidate`, `classified finding`, `mapping assigned` 중 데이터 단계에 맞는 말을 선택한다. `attack`도 공격자 신원·성공을 뜻하는 명사로 단독 사용하지 말고 `attack-like request pattern`, `attempt context`, `analysis candidate`처럼 evidence 범위를 붙인다.

## 9. Security Standards Interpretation Boundary

```text
Security Standards Mapping = finding-level deterministic enrichment
Security Standards Summary = deduplicated finding aggregate
```

Mapping은 Stage1 finding과 Prepare evidence를 OWASP Top 10, CWE, WSTG 관계로 보수적으로 보강한다. Summary는 그 mapping을 deduplicated finding 단위로 집계한다. 하나의 finding이 여러 category와 관계될 수 있으므로 category count를 incident 총수로 합산하지 않는다.

다음 표현은 금지한다: `vulnerability scanner`, `compliance checker`, `confirmed CWE`, `OWASP violation detector`, `exploit success evidence`.

`attempt_only`, `behavior_only`, `partial`, `not_applicable` 같은 observability relationship은 관찰 범위의 관계 label이다. `partial`은 부분적으로 관찰 가능한 evidence를 뜻할 뿐 부분 성공, exploit success 또는 vulnerability confirmation이 아니다. mapping이 없거나 unmapped여도 finding/target이 safe라는 뜻이 아니다.

## 10. No-data / No-signal / Undetermined

```text
분석 구간에 로그 없음 = no-data
로그는 있으나 adopted observation signal 없음 = no_signal
처리 불완전·입력 부족·사용 불가 = undetermined 가능

no-data ≠ no-signal ≠ normal ≠ safe
```

현재 Final runtime의 `No data` Job은 요청 구간 export에 로그가 없어서 pipeline을 진행하지 않은 결과다. 이는 no-signal assessment나 안전 판정이 아니다. `no_signal`과 `undetermined`는 Live Security Observation이 승격될 때 사용할 Conditional Final terminology이므로, 현재 runtime 화면에 존재하는 사실로 소급하지 않는다.

## 11. Verification Status Terminology

Final verification 증적에는 다음 상태만 사용한다.

| 상태 | 뜻 |
| --- | --- |
| PASS | freeze revision에서 해당 검증이 성공했다는 기록 |
| FAIL | 실행되어 검증 조건을 충족하지 못했다는 기록 |
| BLOCKED | 실행/판정에 필요한 외부 조건이나 identity가 막혀 진행할 수 없다는 기록 |
| NOT RUN | 해당 freeze revision에서 실행하지 않았다는 기록 |

“아마 통과”, “사실상 완료”, “문제 없어 보임”, “예전에 통과함”은 Final 증적 상태가 아니다. historical PASS는 과거 revision/환경에서의 기록이고, freeze revision PASS는 이 Final 기준 revision에서 다시 확인한 기록이다. 전자는 후자를 대체하지 않는다.

## 12. UI / Documentation Wording Notes

현재 Web/README에서 다음 표현은 Final 설명 시 아래처럼 한정한다.

| 현재 표현 또는 표면 | Final 해석/설명 |
| --- | --- |
| `Potentially stale` | RUNNING Job의 heartbeat가 stale threshold보다 오래되었다는 warning이다. worker 장애나 Job 실패 확정이 아니며 상태 확인 뒤 조치한다. |
| `No data` | 요청 시간 범위에서 로그를 찾지 못한 Job 결과다. `no_signal`, normal, safe가 아니다. |
| `incident candidates` / `notable_incidents` | 조사·표시를 위한 finding 중심 단위다. 실제 침해사고 또는 성공 공격 확정으로 발표하지 않는다. |
| `read-only` | Viewer가 Stage1/Stage2 의미·verdict·severity·mapping을 재계산하거나 변경하지 않는다는 뜻이다. Web UI는 Job 생성과 상태 조회를 수행할 수 있다. |
| `Detected` / `attack` | 가능한 경우 observed pattern, analysis candidate, classified finding처럼 실제 단계로 바꾼다. |
| `normal` / `safe` | baseline-like 또는 관찰 상태로 바꾸며, candidate-excluded/no-data/no-signal에 붙이지 않는다. |
| `safe` in implementation | redaction, escaping, path validation 등 UI/운영 안전성의 기술 용어일 수 있다. 보안 분석 verdict의 safe와 혼동하지 않는다. |

Viewer의 `Security Standards Summary` boundary 문구처럼, standards 관계는 vulnerability, weakness, compliance, successful exploitation을 확인하지 않는다고 명시한다. legacy file-based viewer와 DB-backed Job viewer도 이 해석 경계를 공유한다.

## 13. 발표 질문 대응용 요약

**Q. 이 시스템은 공격 성공을 탐지합니까?**
A. Apache 로그에서 관찰 가능한 요청 패턴과 문맥을 분석합니다. response body, DB 결과, browser 실행 같은 별도 증거 없이 성공 여부는 확정하지 않습니다.

**Q. HTTP 200이면 성공 아닌가요?**
A. HTTP 응답이 기록됐다는 뜻입니다. fallback HTML, route 처리, 파일 노출, 로그인 또는 exploit 성공을 증명하지는 않습니다.

**Q. SQLi/XSS/CMDi를 찾았다고 말할 수 있나요?**
A. 해당 문법이나 request pattern을 observation/candidate/finding 단계에서 말할 수 있습니다. SQLi DB 성공, XSS 실행, command 실행 성공으로 표현하지 않습니다.

**Q. candidate-excluded면 정상 트래픽인가요?**
A. 아닙니다. 현재 candidate selection policy에서 제외됐다는 뜻이며 benign·normal·safe 판정이 아닙니다.

**Q. No data는 안전하다는 뜻인가요?**
A. 아닙니다. 선택한 시간 구간에서 export할 로그가 없었다는 뜻입니다. no-signal과도 다릅니다.

**Q. OWASP/CWE가 표시되면 취약점이 확인된 것인가요?**
A. 아닙니다. finding-level deterministic standards relationship/enrichment이며 vulnerability confirmation이나 compliance score가 아닙니다.

**Q. Web UI는 read-only인가요?**
A. Viewer는 결과 의미를 바꾸지 않는 read-only interpretation layer입니다. Web UI는 Final runtime에서 full_report Job 생성과 상태 조회를 수행합니다.

**Q. Live 화면과 Live Security Observation은 Final인가요?**
A. 둘 다 현재는 Conditional Final이지만 승격 조건은 다릅니다. 기본 Live Monitoring은 main 통합, Web/Live regression, SELECT-only DB integration, E2E를 통과하면 shared extractor 없이도 독립적으로 Final 승격할 수 있습니다. Live Security Observation은 여기에 별도로 shared extractor compatibility와 live_adoption PASS가 필요합니다.
