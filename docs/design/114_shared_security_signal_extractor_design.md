# 114 Shared Security Signal Extractor 후속 설계 명세

- 작성일: 2026-09-06
- 기준 revision: `f25cc0fbd65a628ad62129b4ba477f9cc2726807`
- 선행 문서: [103 설계 명세](./103_shared_security_signal_extractor_design.md)
- 회귀 계획: [115 회귀 계획](./115_shared_security_signal_extractor_regression_plan.md)
- 전체 반환값 명세: [116 B2-A 명세](./116_prepare_full_output_comparison_harness_spec.md)
- 상태: 103의 D1부터 D5까지 승인 의미를 승계한 최신 기준 설계. D2 traversal의 Live 채택은 비활성이고 재검토 대상이며 D5 성능 수치는 미승인이다.

이 문서의 승인은 설계 문서 갱신 승인일 뿐 구현, 시험, baseline, Live 활성화 또는 배포 승인이 아니다. B2-B harness 구현은 별도 승인이 필요하다.

## 1. 목적과 불변 원칙

Prepare와 Live가 공유하는 범위는 단일 요청에서 결정적으로 관찰한 사실과 provenance뿐이다. 공용화는 탐지 중복을 줄이되 Prepare의 기존 결과와 Live의 읽기 전용 관찰 한계를 보존한다.

- 새 공격 계열, transform, wordlist, score 조정은 범위 밖이다.
- 공용화와 의미상 오류 정정은 별도 변경으로 진행한다.
- Prepare score, threshold, filter, aggregation과 Mapping verdict를 Live에 연결하지 않는다.
- Live는 공격 여부, 성공 여부, 정상 여부, severity, 침해 또는 취약점 verdict를 생성하지 않는다.
- body, 임의 header 또는 서버 내부 상태를 합성하지 않는다.

D1, D3, D4와 D5의 cap 및 초과 처리 구조를 그대로 유지한다. D2의 좁은 최초 allowlist 의미도 유지하지만 traversal은 후보 검증 뒤 별도 승인을 받아야 하며 현재 `live_adoption`은 비활성이다.

## 2. 최신 기준 semantic

장기 compatibility 기준은 `f25cc0fbd65a628ad62129b4ba477f9cc2726807`이다. traversal과 resource 변경 `c2092e925fd526ace1b653784fb8207f9ee54a76`, CMDi와 XSS 및 substantive candidate gate 변경 `9d299641195edee738f21b50d542c938b4bf3273`은 이 기준에 이미 포함된다.

| 영역 | compatibility에 포함되는 최신 의미 | Live 정책 |
| --- | --- | --- |
| traversal | 경계가 있는 `../`, backslash와 encoded 형태, 명시적 triple-dot, embedded dot-dot 억제 | 자동 채택 금지 |
| resource | 직접 `/etc/passwd`와 경계가 맞는 `win.ini`를 민감 OS resource로 분리 | traversal 또는 CWE-22 승격 금지 |
| CMDi | Unix와 Windows command, pipe, semicolon, subshell, `&&`, shell invocation grammar 확대 | 별도 승인 없이 allowlist 확대 금지 |
| XSS | executable event handler와 JavaScript context, browser-data access와 exfiltration 결합 경계 | 제한 구조만 별도 채택 |
| candidate | generic context score만으로 candidate가 되지 않도록 substantive security signal 요구 | Prepare 정책이며 Live verdict가 아님 |

과거 사용자 HEAD와 최신 main 사이 변화는 역사적 source 차이이며 extractor regression이 아니다. 최신 main에 있다는 사실도 Live adoption 승인이 아니다.

## 3. 세 계층의 책임

| 계층 | 책임 | 금지 |
| --- | --- | --- |
| extractor core | bounded transformation, 규칙 일치, 구조 관찰 사실, provenance와 처리 범위 | DB, 파일, 네트워크, 현재 시각, score, threshold, severity, verdict, candidate 결정 |
| Prepare compatibility layer | 기존 입력 조합과 실행 순서 재현, facts를 기존 hint와 score로 변환, threshold, filter, aggregation 계약 보존 | Live import, hint 정렬 또는 중복 제거, corrected 변경 혼합 |
| Live adapter | 실제 관찰 surface 투영, 승인된 제한 allowlist, 상태와 안전한 표시 계약 | Prepare 평가와 Mapping verdict 호출, 없는 surface 합성, 공격 또는 정상 판정 |

`evaluate_row`의 score와 verdict branch, strong SQLi, 교육용 감산, noise, 반복 집계, dedup, summary와 supporting event는 Prepare 소유다. 기존 `(int, List[str])` detector 반환형은 compatibility layer가 유지하며 core 계약으로 옮기지 않는다. Live 참고 정보는 별도 승인된 정적 registry와 Live 전용 연결만 사용한다.

## 4. 입력과 transformation

- Prepare profile은 `build_analysis_texts`의 raw 및 normalized 조합, query와 request-target variant, 호출 횟수, 공백과 중복 처리 순서를 그대로 재현한다.
- combined text match는 compatibility에 보존하되 특정 원본 field의 provenance로 꾸미지 않는다.
- Live profile은 실제 `request_target` 우선, `uri` 보조다. 제한된 target의 첫 literal `?`에서만 derived query를 만든다.
- `%3F`를 separator로 먼저 decode하거나 target과 URI를 합쳐 가상 요청을 만들지 않는다.
- SELECT에 없는 raw request, query column, body와 header를 합성하지 않는다.
- 입력 row와 문자열을 수정하지 않는다.

Prepare와 Live는 profile과 scope가 다르므로 전체 결과 동일성을 요구하지 않고 동일 surface와 transformation에서 얻은 사실의 의미만 공유한다.

## 5. provenance와 version 축

| 항목 | 계약 |
| --- | --- |
| `signal_id` | 관찰 사실의 안정적 의미 ID. verdict나 severity가 아니며 다른 의미로 재사용하지 않음 |
| `rule_id` | match를 생성한 구체 규칙 ID |
| rule revision | match 범위, 경계 또는 transformation 의미가 바뀔 때 증가 |
| `adoption_rule_id` | Live가 facts를 제한 조합으로 채택한 별도 규칙 ID |
| adoption policy version | allowlist, 조합, 제외 또는 표시 정책이 바뀔 때 증가 |
| schema revision | envelope, field, 타입 또는 serialization 계약이 바뀔 때 증가 |
| source surface | 실제 `uri`, `request_target`, `query_string`, `raw_request`, `raw_log` 또는 compatibility `combined_text` |
| derived surface | query와 decode 결과를 부모 source 및 `derived_from`과 함께 표시 |
| variant chain | `variant_id`, 부모, transform 순서 |
| decode type와 depth | raw, URL decode, HTML entity와 해당 chain의 깊이 구분 |
| span 좌표계 | 원문과 decoded offset 구분. 불확실한 원문 좌표를 만들지 않음 |
| truncation과 budget | 원래 길이, 관찰 길이, input, variant, output 절단과 미실행 사유 |

규칙 의미와 Live 채택 정책은 서로 다른 version 축이다. rule revision은 adoption policy를 자동 변경하지 않고 반대도 마찬가지다. schema revision도 두 축을 대체하지 않는다.

match 순서는 rule, surface, variant 생성, 위치 순서다. 같은 rule, surface, variant, 위치만 중복 제거하고 다른 provenance는 보존한다. Prepare hint 순서와 중복은 compatibility layer가 기존 실행 순서로 재현한다.

## 6. Prepare compatibility

최신 기준 source에서 다음은 공용화 전후 차이 0이어야 한다.

- `sqli:*`, `xss:*`, `traversal:*`, `cmdi:*`, `(+N)` 및 모든 reason 문자열
- encoding, file disclosure, context, false-positive와 no-inference hint
- append와 extend의 순서, 최초 등장 보존과 중복 의미
- score, 감산, threshold, candidate, filtered row와 noise
- aggregation, 대표 candidate, incident group, merged IDs와 source
- summary, supporting event와 downstream 결과
- substantive security signal gate와 upload SQL comment 예외

최신 traversal, resource, CMDi, XSS 변경은 이미 compatibility 일부이므로 공용화 중 되돌리거나 corrected 변화로 집계하지 않는다.

## 7. D2 제한 allowlist와 traversal

최초 후보 구조는 같은 source와 variant 내부의 SQL quote 종료와 boolean true, SQL quote 종료와 UNION SELECT 및 열 열거, 승인된 태그 event handler, 승인된 separator와 command, PHP filter wrapper와 base64 filter 및 resource 결합이다. 다른 surface, variant 또는 parameter의 조각을 합치지 않는다.

`;environment`, bare `document.cookie`, bare `url(javascript:alert())`, SQL `;INSERT`, generic context score와 단독 resource token은 채택하지 않는다. 최신 CMDi의 `and_exec`, `subshell`, `shell_invocation`과 확대 command도 자동 편입하지 않는다.

| traversal 후보 | 구분과 현재 상태 |
| --- | --- |
| `../` | 경계가 있는 명시 escape 후보. Live 비활성 |
| backslash | 경계가 있는 `..\` 계열을 독립 검증. Live 비활성 |
| triple-dot | 명시 triple-dot과 inner dot-dot 오인을 분리. Live 비활성 |
| embedded dot-dot | `foo../bar`, `foo.../bar`를 escape와 구분. Live 비활성 |
| 직접 `/etc/passwd` | 민감 OS resource이며 traversal이 아님. CWE-22 승격 금지 |
| 직접 `win.ini` | 경계가 맞는 민감 OS resource이며 traversal이 아님. CWE-22 승격 금지 |
| CRS `930100.3` | 현재 source 결과와 corrected 의미를 다른 family로 관리. Live 비활성 |

traversal 보류는 최종 미지원 결정이 아니다. compatibility 보존, corrected 후보 승인, 별도 `live_adoption` 승인 순서로만 활성화한다.

## 8. 처리 상태와 평가 상태

| `processing_status` | 신호 | `assessment` | 의미 |
| --- | --- | --- | --- |
| `complete` | 있음 | `review_required` | 완료 관찰에 채택 신호 있음 |
| `complete` | 없음 | `no_signal` | 승인 범위에서 신호 없음. 정상 판정이 아님 |
| `partial` | 있음 | `review_required` | 부분 관찰에서 확인된 신호 있음 |
| `partial` | 없음 | `undetermined` | 절단 또는 budget 때문에 확정 불가 |
| `unavailable` | 해당 없음 | `undetermined` | surface 없음 또는 page budget 미착수 |
| `error` | 해당 없음 | `undetermined` | detector 오류, 중간 signal 비공개 |

`no_signal`은 처리 완료일 때만 허용한다. 일부 surface 미관찰과 input, variant, time, output budget 초과는 `partial`, 미착수는 `unavailable`, 예외는 `error`다. 이를 신호 없음으로 바꾸지 않고 reason code와 scope에 기록한다.

## 9. D4 additive Live 계약

기존 `items[]` 행에는 versioned observation만 추가한다. 이를 제거한 기존 response projection은 전체 동등해야 한다. SQL, 계정, WHERE, 정렬, LIMIT, cursor, NULL, ID와 원문을 바꾸지 않는다. 관찰로 행을 제거하거나 정렬하지 않고 추가 SELECT, DB 쓰기, 파일 쓰기 또는 Job을 만들지 않는다.

observation에는 schema와 detector 및 adoption policy version, 두 상태 축, reason code, scope와 승인 signal만 둔다. score, severity, confidence, verdict와 candidate 여부를 넣지 않는다. 원문 또는 decoded 전문을 복제하지 않는다.

## 10. D5 cap과 성능 상태

Live 추가 관찰에만 다음 구조를 유지한다. request target과 URI 각각 4096 Unicode code point, 최대 세 surface, raw와 URL decode 1 및 2, 각 variant의 HTML entity 1개, surface당 6개와 행당 18개 variant, 총 73,728 code point, signal 16종과 signal당 evidence 4개, observation 행당 16KiB와 50행 800KiB다. 기존 50행과 5초 polling을 유지한다.

Prepare 입력과 원래 Live 원문에는 이 cap을 적용하지 않는다. 절단 끝에서 생긴 인위적 경계를 채택하지 않는다. `10ms/행`, `250ms/페이지`, p95, p99와 메모리 수치는 provisional target일 뿐 acceptance가 아니다. correctness와 성능을 분리 측정한 뒤 별도 승인한다.

## 11. 103 승인 이력 승계표

| 기존 항목 | 기존 승인 의미 | 최신 main 반영 사항 | 114의 대응 절 | 현재 승인 상태 | 추후 승인 필요사항 |
| --- | --- | --- | --- | --- | --- |
| 103 1절 | 관찰 사실만 공유, Prepare 판단과 Live 분리 | 기준 revision 갱신 | 1, 2절 | 유지 | 없음 |
| 103 2절 | Live read-only와 실제 surface 한계 | 사용자 Live 변경 보존 | 1, 9절 | 유지 | Live 구현 승인 |
| 103 3, 4절 | 계층별 책임과 정책 경계 | 최신 detector 위치와 semantic 반영 | 2, 3절 | 유지 및 구체화 | package와 API 승인 |
| D1, 103 5, 6절 | versioned 입력과 출력, ID, provenance, 순서 | 세 version 축 명시 | 4, 5절 | 승인 유지 | 실제 ID와 schema 승인 |
| 103 7절 | Prepare hint와 결과 전체 호환 | substantive gate 포함 | 6절 | 승인 유지 | B2-B와 baseline 승인 |
| D2, 103 8.2절 | 좁은 allowlist, traversal 임시 보류 | bounded traversal, resource 분리, CMDi와 XSS 최신 경계 | 7절 | 승인 유지, traversal 비활성 | corrected와 adoption 승인 |
| D3, 103 8.1절 | 처리와 평가 두 축 | budget과 오류 상태 명확화 | 8절 | 승인 유지 | 구현 및 시험 승인 |
| 103 9절 | Mapping은 Prepare와 Stage 소유 | resource의 CWE-22 오염 금지 | 3, 7절 | 승인 유지 | reference 연결 승인 |
| D4, 103 10.1절 | 행별 additive observation | 최신 Live 계약 유지 | 9절 | 승인 유지 | 구현과 활성화 승인 |
| D5, 103 10.2, 10.3절 | cap과 초과 상태 승인, 성능 수치 미승인 | 최신 semantic과 독립 유지 | 8, 10절 | 구조 승인, 수치 미승인 | benchmark와 acceptance 승인 |
| 103 11, 12절 | 단계별 중단과 blocker | benchmark 경로는 B1.5에서 확인, B2-B 미승인 | 12절 | 문서만 갱신 | 후속 단계별 승인 |

## 12. 현재 상태와 중단 조건

B2-B harness, extractor, test, corpus, baseline, corrected expectation, Live adoption과 성능 benchmark는 모두 미승인이고 `NOT RUN`이다. 기준 source와 import origin 불명, compatibility 차이 은폐, provenance가 다른 fact 결합, traversal 자동 활성화, 직접 resource의 CWE-22 승격, 불확실 상태의 `no_signal` 전환, Prepare 또는 Mapping verdict의 Live 호출, 사용자 변경 역변경이 필요하면 후속 단계를 중단한다.
