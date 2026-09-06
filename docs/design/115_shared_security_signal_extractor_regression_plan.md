# 115 Shared Security Signal Extractor 후속 회귀 계획

- 작성일: 2026-09-06
- compatibility 기준 revision: `f25cc0fbd65a628ad62129b4ba477f9cc2726807`
- 상위 설계: [114 설계](./114_shared_security_signal_extractor_design.md)
- 선행 계획: [104 회귀 계획](./104_shared_security_signal_extractor_regression_plan.md)
- harness 명세: [116 B2-A 명세](./116_prepare_full_output_comparison_harness_spec.md)
- 상태: 104의 승인 의미와 116의 full-output 계약을 승계한 문서 갱신. 구현과 실행은 모두 미승인이고 `NOT RUN`이다.

## 1. 목적과 family 분리

과거 사용자 HEAD와 최신 main의 역사적 차이는 extractor regression으로 집계하지 않는다. `compatibility`는 동일한 최신 기준 source에서 공용화 전후 전체 반환값 차이 0을 뜻한다.

| family | 기준 | PASS 의미 |
| --- | --- | --- |
| `compatibility` | `f25cc0f...`의 공용화 전 출력 | 같은 입력과 parameter의 blocking 타입, 값, 순서와 중복 차이 0 |
| `corrected` | 별도 승인 decision ID와 허용 diff | 승인된 의미 변경만 발생하고 나머지는 compatibility 유지 |
| `live_adoption` | 제한 allowlist, provenance, 처리 상태와 표시 | 공격 verdict 없이 승인된 관찰 계약만 제공 |

한 family의 PASS는 다른 family의 실행 또는 승인이 아니다. corrected로 compatibility baseline을 덮지 않고 Live 기대를 Prepare corrected에 복사하지 않는다. traversal의 Live 채택은 비활성이다.

## 2. `build_outputs()` 전체 비교

다음 5-tuple 전체를 capture한다.

1. `llm_input`
2. `candidate_payload`
3. `noise_payload`
4. `filtered_reasons_payload`
5. `filtered_payload`

### 2.1 compatibility blocking 조건

- 반환 타입, tuple 길이와 slot 타입
- dict key 존재, 추가와 누락, value와 value type
- NULL, 빈 문자열, 빈 list, 0과 false의 구분
- list와 tuple의 타입, 길이, 순서와 중복 횟수
- `reason_hints`와 모든 reason의 내용, 공백, `(+N)`, 위치, 순서와 중복
- candidate, filtered, noise, 모든 summary, aggregate와 supporting event
- 대표 candidate, incident group, merged ID, source와 count
- metadata와 명시하지 않은 신규 field
- 호출 전후 input mutation
- 명시된 오류 case가 아닌 예외 발생, 타입 또는 메시지 변화

list와 tuple 및 reason 순서와 중복은 blocking이다. 정렬, set, whitespace 정규화 또는 dedup으로 차이를 숨기지 않는다.

### 2.2 dict insertion order

dict key 존재, value와 type 동일성은 compatibility blocking이다. insertion order 차이는 typed capture와 diff에 `dict_order_changed`로 반드시 남기되 바로 blocking으로 확정하지 않는다.

- 별도 `serialization-order` gate에서 우선 검토한다.
- 실제 직렬화 산출물 또는 소비자가 key order에 의존한다는 근거가 있으면 별도 승인으로 blocking 여부를 정한다.
- 차이를 조용히 무시하거나 정렬로 제거하지 않는다.
- `serialization-order`가 `NOT RUN`, `BLOCKED` 또는 미승인이어도 compatibility 값 동등성 `PASS`와 혼동하지 않는다.
- 값 동등성 보고에는 serialization-order 상태를 함께 표시한다.

## 3. typed capture와 diff

`null`, `bool`, `int`, `float`, `str`, `list`, `tuple`, `dict`를 구분한다. dict는 순서 있는 key와 value node로 저장한다. 큰 int, 음수 0과 float를 손실 없이 보존하고 unsupported object를 문자열로 바꾸지 않는다. tuple 길이와 slot 타입 위반은 계약 위반이다.

diff에는 family, corpus와 case 및 parameter ID, slot, 경로, 차이 종류, 양쪽 존재 여부, 타입과 typed value를 둔다. type, value, missing, added, length, sequence, dict order, mutation과 exception을 구분한다. 전체 diff는 artifact에 보존하고 terminal에는 raw 원문 없이 ID, 경로와 개수만 표시한다.

## 4. 다섯 corpus

| corpus | inventory | identity와 실행 조건 |
| --- | --- | --- |
| Prepare regression | fixture 25개 전체와 대응 expected 25개 | fixture bytes, path, revision, payload hash와 parameter ID |
| CRS path/file-access | 36개 전체, direct 27개, partial 3개, body 제외 6개 | CRS revision, source checksum, rule와 test ID, adapter digest |
| multi-family CRS | path/file 36, CMDi 18, XSS 19, SQLi 20의 93개 | 중복 실행 identity는 하나, 모든 suite membership 보존 |
| CSIC reviewed subset | reviewed identity 222개와 validation 상태 | 원문 3개, source file, index, raw request hash, parser와 projection digest |
| Live 합성 경계 | SQLi, XSS, CMDi, PHP filter, 상태와 cap, traversal 후보 | body 합성 금지, 별도 `live_adoption` 기대 |

CRS source revision은 `96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a`로 고정한다. byte가 같아도 source identity가 다르면 합치지 않으며 component와 suite 중복 membership은 모두 기록한다. 누락 corpus나 case를 자동 skip하지 않는다.

CSIC 원문 size와 checksum, source file, index와 raw request hash가 검증되지 않으면 CSIC gate와 다섯 corpus 전체 판정은 `BLOCKED`다. 자동 다운로드, 다른 mirror 대체, 자동 재주석 또는 provisional identity 승격을 금지한다.

## 5. case와 parameter matrix

- 기본은 `min_score=4`, `min_repeat_aggregate=3`; CRS와 CSIC는 `source_tables=['security']`.
- score 3, 4, 5, 6과 필요한 기존 score 전후 경계를 둔다.
- 같은 group 2, 3, 4행과 aggregation threshold 2, 3, 4를 둔다.
- access, security, error 개별과 혼합 및 혼합 역순을 둔다.
- 빈 payload와 행, 누락 field, NULL, 빈 문자열, 숫자형과 문자열 ID, naive와 offset time을 둔다.
- raw, URL decode 1과 2, HTML entity, plus, 잘못된 escape, Unicode, 중복 variant와 4095, 4096, 4097 경계를 둔다.
- 동일 timestamp, 중복 request ID, 다른 source의 동일 ID, 반복 원문과 입력 역순을 둔다.
- Live는 0, 1, 50행, missing target와 URI, derived query, cap 초과, 미착수와 detector 오류를 둔다. 51행은 서비스 제한 case다.

각 행은 고유 parameter ID를 갖고 before와 after가 같은 matrix를 사용한다. CLI default에 의존하거나 다른 parameter 결과를 비교하지 않는다.

## 6. semantic 및 false-positive 경계

최신 기준의 bounded traversal, 직접 OS resource 분리, CMDi grammar 확대, XSS executable context, browser-data exfil 경계와 substantive candidate gate는 compatibility에 포함한다.

- traversal은 경계가 있는 `../`, backslash, triple-dot, embedded `foo../bar`와 `foo.../bar`를 분리한다.
- 직접 `/etc/passwd`와 경계가 맞는 `win.ini`는 resource이며 traversal 또는 CWE-22가 아니다.
- CRS `930100.3`의 현재 source 결과와 corrected 의미는 다른 family에서 관리한다.
- CMDi pipe와 semicolon 확대 어휘를 보존하되 `and_exec`, `subshell`, `shell_invocation`은 별도 Live 승인 전 비활성이다.
- XSS는 실행 가능한 event handler와 JavaScript context, browser-data와 exfiltration 결합을 구분한다.
- `;environment`, bare `document.cookie`, bare `url(javascript:alert())`, SQL `;INSERT`, command 유사 일반 문자열과 generic context score-only 입력을 negative 경계로 둔다.

최신 main에 detector가 있다는 사실이나 Prepare candidate 여부를 Live 채택 승인으로 사용하지 않는다.

## 7. 결정성, 격리와 mutation

- fixed clock은 `2026-01-01T00:00:00+09:00`, timezone은 `Asia/Seoul`이다.
- production에 test option을 넣지 않고 격리 process에서 `prepared_at`을 통제한다.
- before-1, before-2와 after는 독립 process 및 별도 source root에서 실행한다.
- 실제 import origin과 source SHA를 확인하고 다른 tree module 혼입 시 중단한다.
- 매 호출에 fresh deep copy를 사용하고 호출 전후 typed capture로 mutation을 검사한다.
- before-1과 before-2의 전체 결과와 inventory가 같아야 한다.
- same-process 연속 호출과 case 순서 역전을 보조 검사하여 상태 누출을 찾는다.
- 입력 time field를 삭제하거나 mask하지 않는다. 다른 wall-clock 의존은 통제 전 `BLOCKED`다.

## 8. artifact와 안전

before-1, before-2, after와 comparison은 모두 서로 다른 새 run directory를 사용한다. 기존 artifact나 baseline이 있으면 실패하고 덮어쓰기, `--force`, symlink와 before와 after 동일 경로를 거부한다. completion marker는 checksum 완성 뒤 마지막에 기록한다. 실패 run은 incomplete이며 baseline으로 승격하지 않는다.

source, harness, adapter와 input identity, clock, timezone, parameter, inventory 및 비밀이 아닌 환경만 기록한다. 환경 전체, 비밀 변수, 인증정보를 artifact에 기록하거나 raw 원문을 terminal에 출력하지 않는다.

실행 구간 DB, LLM, network, Stage1, Mapping, Stage2, Worker와 Job 호출은 각각 0회이고 source 수정과 source tree artifact 쓰기도 0회여야 한다. 기존 parser와 input projection은 digest를 고정해 재사용할 수 있으나 축약 evaluator, metric writer, Stage runner의 결과는 full-output baseline으로 재사용하지 않는다.

## 9. 구현과 실행의 분리 순서

1. typed capture와 strict comparator 자체 검증
2. source, adapter, raw와 projection identity
3. fixed clock, timezone, process isolation과 import origin
4. mutation, inventory 및 case 누락 검사
5. before-1 capture
6. 별도 process의 before-2 capture와 반복 동등성
7. 별도 승인 source의 after capture
8. family별 비교와 `serialization-order` gate
9. diff, summary, checksum과 completion marker

B2-B 구현, 자체 검증, source 준비, before baseline, after 비교, corrected expectation, Live adoption과 성능은 각각 별도 승인한다. 구현과 baseline 실행을 결합하지 않는다.

## 10. 판정

| 상태 | 의미 |
| --- | --- |
| `PASS` | 해당 gate의 승인 입력과 조건 전부 충족 |
| `FAIL` | 전제가 완전한 실제 비교에서 승인되지 않은 차이나 위반 발생 |
| `BLOCKED` | source, identity, clock, harness 또는 승인 전제가 부족해 유효한 판정 불가 |
| `NOT RUN` | 실행하지 않음. PASS가 아님 |

같은 최신 source의 blocking 차이는 `FAIL`이다. CSIC identity 누락, source SHA나 import origin 불명, fixed clock 실패, 누락 inventory, mutation, incomplete artifact와 harness 자체 검증 미완료는 `BLOCKED`다. 명시하지 않은 예외 변화는 전제가 완전하면 `FAIL`이다. `serialization-order`는 독립 상태를 보고한다.

## 11. Live 상태 회귀

| `processing_status` | `assessment` | 조건 |
| --- | --- | --- |
| `complete` | `review_required` | 완료 관찰에 승인 신호 있음 |
| `complete` | `no_signal` | 완료 관찰에 승인 신호 없음 |
| `partial` | `review_required` | 부분 관찰에 확인된 신호 있음 |
| `partial` | `undetermined` | 절단 또는 처리 budget이며 신호 없음 |
| `unavailable` | `undetermined` | surface 없음 또는 page budget 미착수 |
| `error` | `undetermined` | detector 예외, 중간 signal 비공개 |

미관찰, cap, budget, 예외와 미착수를 `no_signal`로 바꾸면 실패다. observation을 제거한 기존 Live response는 SQL, filter, sort, pagination, cursor, NULL과 오류까지 전체 동등해야 한다. Live가 공격, 성공, 정상, severity와 침해 verdict를 만들거나 Mapping verdict를 호출하면 실패다.

## 12. correctness와 성능

전체 반환값, provenance, 상태, mutation과 안전은 correctness gate다. 성능은 그 뒤 별도 승인으로 측정한다. `10ms/행`, `250ms/페이지`, p95, p99와 메모리 수치는 provisional target이며 현재 acceptance가 아니다. 환경, 표본, warm-up과 최종 기준 승인 전에는 성능 PASS 또는 FAIL을 선언하지 않는다.

## 13. rollback과 중단

rollback은 승인된 구현 hunk만 대상으로 하며 현재 사용자 Live 변경이나 기존 dirty tree를 되돌리지 않는다. 사용자 hunk와 겹치면 자동 복원하지 않고 중단한다. 실패 diff, source와 input identity, 명령, 환경과 artifact를 보존하고 기대값을 통과용으로 바꾸지 않는다.

compatibility 차이, source 또는 provenance 불명, corpus 누락, before 비결정성, mutation, 금지 호출이나 쓰기, 불확실성을 정상으로 표시, traversal 자동 활성화, resource의 CWE-22 오염, 실패 artifact 승격과 미승인 성능 수치 사용은 중단 조건이다.

## 14. 현재 상태

104의 D1, D3, D4와 D5 구조 승인, D2 traversal 보류, Prepare와 Live 경계, rollback 원칙을 그대로 승계했다. 116의 다섯 corpus, typed capture, identity, fixed clock, 반복 비교, artifact와 판정 계약을 반영했다. 현재 A 문서 갱신만 수행됐으며 B2-B harness 골격과 모든 실행은 `NOT RUN`이다.
