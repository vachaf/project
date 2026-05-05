# 99_prepare_deferred_split_items

- 문서 상태: prepare 미분리/보류 항목 정리
- 기준 시점: 2026-05-05
- 목적: prepare module split, constants mini-move, hint split 이후 의도적으로 남겨둔 항목과 보류 이유, 재검토 조건을 정리한다.

관련 문서:

- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [99_stage2_prompt_compaction_plan.md](./99_stage2_prompt_compaction_plan.md)
- [99_stage2_report_quality_lint_candidate_review.md](./99_stage2_report_quality_lint_candidate_review.md)
- [99_stage2_report_quality_lint_tuning_plan.md](./99_stage2_report_quality_lint_tuning_plan.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

현재 prepare 관련 구조 분리 작업은 stable 상태다.

완료한 범위:

```text
- prepare module split round1/round2
- safe constants mini-move
- SQLi/XSS/file disclosure/traversal-CMDI topic hint pattern split
- Stage2 prompt compaction
- Stage2 report quality lint 추가 및 튜닝
- B/C/E/H dry-run spot check
- H/E actual LLM spot check
```

아래 항목들은 실수로 빠진 것이 아니라 의도적으로 보류한 영역이다.

보류 원칙:

```text
- behavior 변경 위험이 큰 영역은 남겨둔다.
- candidate/scoring/filtering, supporting_events, Stage2 reporter, expected fixture를 mechanical refactor와 섞지 않는다.
- Apache logs-only evidence boundary가 흔들릴 수 있는 항목은 별도 split plan 없이는 이동하지 않는다.
- 반복 문제가 실제 LLM 출력이나 regression에서 확인될 때만 다시 연다.
```

## 2. 보류 항목 요약

| 항목 | 현재 판단 | 주요 보류 이유 | 재검토 조건 |
|---|---|---|---|
| `AUTOMATION_UA_PATTERNS` | 보류 | lab-* / tool UA 과해석 방지와 연결 | Stage1/Stage2 UA wording 문제가 반복될 때 |
| `detect_decoded_attack_hints` | 보류 | SQLi/XSS/file disclosure/traversal/CMDI와 모두 연결 | decoded reconstruction boundary 문서 작성 후 |
| shared attack/search policy constants | 보류 | false-positive suppression / candidate preservation 경계 | shared policy contract 문서 작성 후 |
| supporting_events 생성/연결 로직 | 보류 | incident/context 연결 핵심 계약 | supporting_events contract 문서 작성 후 |
| candidate/scoring/filtering 로직 | 보류 | behavior 변경 위험이 가장 큼 | detection 품질 문제가 반복될 때 |
| normal search false-positive handling | 보류 | FP suppression과 strong hint preservation 경계 | search FP policy split plan 작성 후 |
| `STANDARD_HTTP_METHODS` | 보류 | method/protocol anomaly 공유 | shared method/protocol ownership 확정 후 |
| static path/classification constants | 보류 | static/crawler/mixed/health 경계 | path classification ownership 확정 후 |
| probing/sensitive/mixed scanner constants | 보류 | path category 공유, file disclosure 경계 | path/probing ownership map 작성 후 |
| Stage2 reporter 구조 변경 | 보류 | output schema/report wording 영향 | 반복 report 품질 문제가 확인될 때 |
| expected/test fixture 변경 | 보류 | behavior contract 변경 위험 | 명시적 behavior change 작업에서만 |
| `constants.py` 대량 분리 | 보류 | import cycle / 원인 추적성 저하 | 충분한 ownership map과 소규모 이동 완료 후에도 필요할 때 |

## 3. 항목별 상세

### 3.1 `AUTOMATION_UA_PATTERNS`

현재 위치:

```text
src/prepare_llm_input.py
```

보류 이유:

```text
- sqlmap/nikto/nmap/python-requests/curl/wget 같은 User-Agent는 trace aid일 수 있지만 공격 성공 근거가 아니다.
- lab-* / experiment-like UA guard와 직접 연결된다.
- tool-like UA를 분리하면 자동화 UA가 공격 증거처럼 보일 위험이 있다.
```

재검토 조건:

```text
- 실제 LLM 출력에서 tool UA 또는 lab-* UA가 공격 근거로 반복 사용됨
- Stage1/Stage2 prompt guard만으로 해결되지 않음
- UA policy를 별도 module로 둬도 scoring/wording 의미가 변하지 않음
```

확인 명령:

```bash
grep -n "AUTOMATION_UA_PATTERNS\|automation:ua\|sqlmap\|nikto\|nmap\|python-requests\|curl\|wget" src/prepare_llm_input.py src/prepare/*.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py
```

가능한 문서:

```text
docs/design/99_prepare_automation_ua_hints_split_plan.md
```

## 3.2 `detect_decoded_attack_hints`

현재 위치:

```text
src/prepare_llm_input.py
```

보류 이유:

```text
- SQLi, XSS, file disclosure, traversal, CMDI와 모두 연결된다.
- decoders.py의 decoded variants와도 연결된다.
- encoding descriptors와 hint generation을 동시에 다룬다.
- topic-specific module로 옮기면 경계가 흐려진다.
```

위험:

```text
- decoded payload reconstruction이 exploit success처럼 해석될 수 있음
- encoding:* hint 의미가 regression expected와 연결될 수 있음
- SQLi/XSS/file disclosure/traversal/CMDI pattern import 방향이 복잡해질 수 있음
```

재검토 조건:

```text
- decoders.py와 decoded hint generation의 역할 경계를 별도 문서로 고정
- encoding:* reason_hints expected가 유지되는지 확인
- pattern dependency import cycle이 없는지 확인
```

확인 명령:

```bash
grep -n "def detect_decoded_attack_hints\|detect_decoded_attack_hints\|encoding:double_decoded\|encoding:html_entity\|decoded_depth" src/prepare_llm_input.py src/prepare/*.py tests/expected -R
```

가능한 문서:

```text
docs/design/99_prepare_decoded_attack_hints_split_plan.md
```

## 3.3 shared attack/search policy constants

현재 위치:

```text
src/prepare_llm_input.py
```

대상:

```text
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
STRONG_ATTACK_HINT_PREFIXES
STRONG_ATTACK_HINTS
ATTACK_ENCODED_PAYLOAD_RE
```

보류 이유:

```text
- SQLi/XSS/file disclosure/traversal/CMDI 등 여러 hint 계열이 공유할 수 있다.
- false positive suppression과 candidate preservation의 경계에 있다.
- shared module을 만들면 import 방향과 ownership 문제가 커질 수 있다.
```

재검토 조건:

```text
- normal search false-positive 판단과 strong hint preservation 계약을 문서화
- candidate_rows / filtered_out 변화 없이 분리 가능함을 확인
- shared policy module의 import 방향이 단방향으로 유지됨
```

확인 명령:

```bash
grep -n "SEARCH_PARAM_NAMES\|NORMAL_SEARCH_VALUE_RE\|NORMAL_SEARCH_ATTACK_TEXT_RE\|STRONG_ATTACK_HINT_PREFIXES\|STRONG_ATTACK_HINTS\|ATTACK_ENCODED_PAYLOAD_RE" src/prepare_llm_input.py src/prepare/*.py
```

가능한 문서:

```text
docs/design/99_prepare_shared_attack_policy_split_plan.md
```

## 3.4 supporting_events 생성/연결 로직

현재 위치:

```text
src/prepare_llm_input.py
```

보류 이유:

```text
- incident와 context를 연결하는 핵심 계약이다.
- supporting_events는 여러 공격군과 baseline/context summary가 공유한다.
- row별 reason_hints 오염, supporting_role 변화, supporting_event_count 변화 위험이 크다.
```

재검토 조건:

```text
- supporting_events input/output contract 문서 작성
- supporting_role별 expected fixture 검토
- Stage2 reporter가 소비하는 supporting_events 의미 확인
- prepare/stage regression이 충분히 고정한 뒤 mechanical split 검토
```

확인 명령:

```bash
grep -n "supporting_events\|supporting_role\|supporting_reason\|build_.*supporting_event\|covered_by_" src/prepare_llm_input.py src/prepare/*.py src/llm_stage2_reporter.py tests/expected -R
```

가능한 문서:

```text
docs/design/99_prepare_supporting_events_split_plan.md
```

## 3.5 candidate/scoring/filtering 로직

현재 위치:

```text
src/prepare_llm_input.py
```

보류 이유:

```text
- behavior 변경 위험이 가장 크다.
- candidate_rows, filtered_out, false_positive_review_candidates, verdict_hint, reason_hints, score에 직접 영향을 준다.
- regression expected 전체가 흔들릴 수 있다.
```

재검토 조건:

```text
- 반복 detection 품질 문제가 확인됨
- 단순 구조 분리보다 behavior change가 필요한 작업으로 명시됨
- 새 expected fixture 또는 regression 기준을 먼저 설계함
```

확인 명령:

```bash
grep -n "score \+=\|score =\|verdict_hint\|filtered_out\|analysis_candidates\|false_positive_review_candidates\|candidate_rows" src/prepare_llm_input.py tests/expected -R
```

가능한 문서:

```text
docs/design/99_prepare_candidate_scoring_filtering_review.md
```

## 3.6 normal search false-positive handling

현재 위치:

```text
src/prepare_llm_input.py
```

보류 이유:

```text
- benign_normal_search, normal_search_baseline, educational SQL/XSS search, strong hint preservation과 연결된다.
- false positive suppression이 과하면 실제 공격 후보가 빠질 수 있고, 약하면 오탐이 늘 수 있다.
```

재검토 조건:

```text
- 실제 LLM 또는 regression에서 normal search FP 문제가 반복됨
- SEARCH_PARAM_NAMES / NORMAL_SEARCH_* / strong hint preservation 계약을 별도 문서로 고정
```

확인 명령:

```bash
grep -n "benign_normal_search\|normal_search_baseline\|educational.*search\|NORMAL_SEARCH\|SEARCH_PARAM_NAMES\|false_positive" src/prepare_llm_input.py src/prepare/*.py tests/expected -R
```

가능한 문서:

```text
docs/design/99_prepare_search_false_positive_policy_split_plan.md
```

## 3.7 `STANDARD_HTTP_METHODS`

현재 위치:

```text
src/prepare_llm_input.py
```

보류 이유:

```text
- method behavior와 protocol anomaly가 공유한다.
- method_summaries.py 단독 owner로 보기 어렵다.
- protocol_anomalies.py와의 공유 경계를 흐릴 수 있다.
```

재검토 조건:

```text
- shared method/protocol ownership이 명확해짐
- method/protocol modules가 직접 공유 constants를 안전하게 import할 수 있음
```

확인 명령:

```bash
grep -n "STANDARD_HTTP_METHODS" src/prepare_llm_input.py src/prepare/*.py
```

가능한 문서:

```text
docs/design/99_prepare_method_protocol_shared_constants_plan.md
```

## 3.8 static path/classification constants

현재 위치:

```text
src/prepare_llm_input.py
```

대상:

```text
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
```

보류 이유:

```text
- 일반 static row 판별과 health-like path 판단에 연결된다.
- crawler baseline, mixed scanner와 경계가 있을 수 있다.
- static file 존재, JS 실행, health 정상 여부 단정 금지와 연결된다.
```

재검토 조건:

```text
- static/crawler/mixed path classification ownership을 별도 문서로 고정
- movement가 classification behavior를 바꾸지 않음
```

확인 명령:

```bash
grep -n "STATIC_EXTENSIONS\|STATIC_PREFIXES\|STATIC_BASELINE_IMAGE_EXTENSIONS\|HEALTH_LIKE_PATHS" src/prepare_llm_input.py src/prepare/*.py
```

가능한 문서:

```text
docs/design/99_prepare_static_path_classification_constants_plan.md
```

## 3.9 probing/sensitive/mixed scanner 공유 constants

현재 위치:

```text
src/prepare_llm_input.py
```

대상:

```text
PROBING_SEQUENCE_*
SENSITIVE_PATH_PROBE_*
DIR_PROBE_*
MIXED_BASELINE_SCANNER_*
```

보류 이유:

```text
- sensitive path, probing sequence, mixed scanner가 path/category 판단을 공유할 수 있다.
- file disclosure와 의미 경계가 겹친다.
- context-only summary를 candidate/incident로 과승격하지 않도록 경계를 유지해야 한다.
```

재검토 조건:

```text
- path/probing ownership map 작성
- sensitive/probing/mixed/file disclosure 경계가 더 명확해짐
- expected fixture가 output key와 reason_hints를 충분히 고정
```

확인 명령:

```bash
grep -n "PROBING_SEQUENCE_\|SENSITIVE_PATH_PROBE_\|DIR_PROBE_\|MIXED_BASELINE_SCANNER_" src/prepare_llm_input.py src/prepare/*.py tests/expected -R
```

가능한 문서:

```text
docs/design/99_prepare_path_probe_shared_constants_plan.md
```

## 3.10 Stage2 reporter 구조 변경

현재 위치:

```text
src/llm_stage2_reporter.py
```

보류 이유:

```text
- output schema와 report wording에 직접 영향을 준다.
- Stage2 prompt compaction은 완료했지만, 구조 변경은 별도 작업으로 다뤄야 한다.
- report quality lint는 review-only tool로 도입했으며 Stage2 reporter 구조와 분리되어 있다.
```

재검토 조건:

```text
- 실제 LLM 출력에서 반복 wording 문제가 확인됨
- prompt/lint만으로 해결되지 않음
- output schema 변경이 필요하면 별도 migration 문서 작성
```

가능한 문서:

```text
docs/design/99_stage2_reporter_structure_review.md
```

## 3.11 expected/test fixture 변경

보류 이유:

```text
- mechanical refactor와 behavior change를 분리하기 위함
- expected fixture는 현재 behavior contract다.
- 실제 동작 의미를 바꿀 때만 변경한다.
```

재검토 조건:

```text
- 의도적 behavior change가 승인됨
- 새/변경된 expected 기준이 문서화됨
```

## 3.12 `constants.py` 대량 분리

보류 이유:

```text
- import cycle 위험이 크다.
- owner가 명확하지 않은 shared constants가 아직 남아 있다.
- 소규모 mini-move 이후에도 shared policy/path/scoring 계열은 보류 상태다.
```

재검토 조건:

```text
- shared ownership 문서가 충분히 쌓임
- 단일 constants.py가 실제로 import 방향을 단순화한다는 근거가 있음
- 소규모 이동보다 유지보수성이 좋아진다는 판단이 선행됨
```

현재 결론:

```text
DO_NOT_MOVE_IN_BULK
```

## 4. 다음에 다시 작업할 때 순서

권장 순서:

```text
1. 실제 반복 문제 확인
2. grep으로 사용 위치 확인
3. split/review plan 작성
4. mechanical refactor 범위 확정
5. py_compile 실행
6. prepare regression strict 실행
7. stage dry-run regression strict 실행
8. 필요 시 dry-run / actual LLM spot check
9. 완료 문서와 TODO 갱신
```

## 5. 현재 권장 상태

현재는 추가 코드 분리를 하지 않는다.

권장 관리 방식:

```text
- stable 상태 유지
- 실제 LLM 출력과 lint warning/blocker를 관찰
- 반복 문제가 발생할 때만 해당 보류 항목을 다시 연다
- 문서/README/TODO 동기화를 우선 관리한다
```

문서 전용 커밋 후보:

```text
docs: document deferred prepare split items
```
