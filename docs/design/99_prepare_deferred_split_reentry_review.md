# 99_prepare_deferred_split_reentry_review

- 문서 상태: prepare deferred split re-entry review
- 기준 시점: 2026-05-06
- 목적: prepare split 이후 의도적으로 보류한 항목을 stable 상태에서 다시 검토하되, 구조 정리만을 이유로 위험한 분리를 재개하지 않기 위한 재진입 기준을 고정한다.

관련 문서:

- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [../진행상황.md](../진행상황.md)

## 1. 목적

- prepare split 이후 보류 항목을 다시 열지 말지 검토한다.
- 바로 코드 분리를 진행하지 않는다.
- 현재 stable 상태에서 추가 분리가 필요한지, 보류 유지가 맞는지 판단한다.
- 반복 문제, regression 실패, actual LLM output 문제 없이 단순 구조 정리만으로 위험한 분리를 하지 않는다.

## 2. 현재 완료 상태

현재 상태는 분리 작업을 재개하기보다 유지/관찰이 우선인 stable 상태로 판단한다.

완료 요약:

```text
- prepare module split round1/round2 완료
- constants mini-move 완료
- SQLi/XSS/file disclosure/traversal-CMDI hint split 완료
- auth/crawler constants move 완료
- Stage2 prompt compaction / report quality lint 안정화 완료
- prepare regression pass=18 warn=0 fail=0
- stage dry-run regression pass=12 warn=0 fail=0
- Stage2 quality tests 14 passed
- Web UI Phase 1B/2A는 별도 축으로 마감 상태
```

해석 원칙 유지:

```text
- Apache logs-only evidence boundary 유지
- 구조 정리 refactor가 Stage1/Stage2 wording, schema, expected fixture를 흔들면 중단
```

## 3. 재진입 판단 기준

아래 기준을 모두 통과할 때만 re-entry 후보로 취급한다.

- 단일 owner가 명확한가
- mechanical refactor로 가능한가
- candidate/scoring/filtering에 영향을 주는가
- supporting_events 의미를 바꾸는가
- Stage1/Stage2 report schema나 wording에 영향을 주는가
- Apache logs-only evidence boundary를 흔들 위험이 있는가
- expected/test fixture 변경 없이 가능한가
- import cycle 위험이 있는가
- 반복 문제나 actual LLM output 문제로 재검토할 근거가 있는가

게이트 규칙:

```text
- 위 기준 중 하나라도 불명확하면 즉시 분리하지 않는다.
- split plan보다 review 문서(경계/계약) 고정이 선행되어야 한다.
```

## 4. 보류 항목별 재평가 표

| 항목 | 현 위치 | 위험도 | 지금 코드 분리 가능 여부 | 선행 문서 | 결론 |
|---|---|---|---|---|---|
| `AUTOMATION_UA_PATTERNS` | `src/prepare_llm_input.py` | 중간 | 아니오 | UA/wording 경계 review | 보류 유지, 반복 과해석 시만 재검토 |
| `detect_decoded_attack_hints` | `src/prepare_llm_input.py` | 높음 | 아니오 | decoded reconstruction boundary review | 지금 분리하지 않음 |
| shared attack/search policy constants (`SEARCH_PARAM_NAMES`, `NORMAL_SEARCH_VALUE_RE`, `NORMAL_SEARCH_ATTACK_TEXT_RE`, `STRONG_ATTACK_HINT_PREFIXES`, `STRONG_ATTACK_HINTS`, `ATTACK_ENCODED_PAYLOAD_RE`) | `src/prepare_llm_input.py` | 높음 | 아니오 | shared attack/search policy review | review-only 선행 |
| supporting_events 생성/연결 로직 | `src/prepare_llm_input.py` | 높음 | 아니오 | supporting_events contract review | 보류 유지 |
| candidate/scoring/filtering 로직 | `src/prepare_llm_input.py` | 매우 높음 | 아니오 | scoring/filtering contract review | 보류 유지 |
| normal search false-positive handling | `src/prepare_llm_input.py` | 높음 | 아니오 | normal search FP review | review-only 선행 |
| `STANDARD_HTTP_METHODS` | `src/prepare_llm_input.py` | 중간 | 아니오 | method/protocol ownership map | ownership map 선행 |
| static path/classification constants (`STATIC_EXTENSIONS`, `STATIC_PREFIXES`, `STATIC_BASELINE_IMAGE_EXTENSIONS`, `HEALTH_LIKE_PATHS`) | `src/prepare_llm_input.py` | 중간~높음 | 아니오 | static/path ownership map | ownership map 선행 |
| probing/sensitive/mixed scanner 공유 constants (`PROBING_SEQUENCE_*`, `SENSITIVE_PATH_PROBE_*`, `DIR_PROBE_*`, `MIXED_BASELINE_SCANNER_*`) | `src/prepare_llm_input.py` + `src/prepare/*.py` 경계 | 높음 | 아니오 | probing/path ownership map | ownership map 선행 |
| Stage2 reporter 구조 변경 | `src/llm_stage2_reporter.py` | 높음 | 아니오 | Stage2 schema/wording quality review | 보류 유지 |
| expected/test fixture 변경 | `tests/expected/*`, regression scripts | 매우 높음 | 아니오 | behavior change 명시 문서 | 보류 유지 |
| `constants.py` 대량 분리 | prepare 전반 | 높음 | 아니오 | constants ownership map 확장 | 보류 유지 |

## 5. 후보별 상세 메모

`AUTOMATION_UA_PATTERNS`
- `lab-*`/tool UA를 공격 근거로 오해할 위험이 남아 있다.
- 반복 과해석이 Stage1/Stage2 실제 출력에서 재발할 때만 재진입한다.

`detect_decoded_attack_hints`
- SQLi/XSS/file disclosure/traversal/CMDI와 동시 결합된 shared 경계다.
- decoded payload 복원과 공격 성공 해석을 분리하는 경계 문서가 먼저 필요하다.

shared attack/search policy constants
- false-positive suppression과 strong hint preservation의 계약 핵심이다.
- 분리 전 review 문서에서 preservation 규칙을 먼저 고정해야 한다.

normal search false-positive handling
- normal search 억제와 공격 신호 보존의 경계라 regression 민감도가 높다.
- split plan 이전에 review-only 문서로 재검토한다.

`STANDARD_HTTP_METHODS`
- method/protocol anomaly 양쪽에서 소비될 가능성이 높아 owner 단일화가 먼저다.
- 지금 이동하면 shared 경계가 더 불명확해질 수 있다.

static path/classification constants
- static/crawler/mixed/health 경계가 맞물려 단일 owner 미확정 상태다.
- ownership map 선행 없이는 안전한 mini-move가 어렵다.

probing/sensitive/mixed scanner 공유 constants
- path category와 scanner context가 얽혀 candidate/supporting 해석에 간접 영향이 있다.
- ownership map을 먼저 확정한 뒤에도 mechanical move만 허용한다.

supporting_events 생성/연결 로직
- incident-context 연결 계약이라 의미 변화 위험이 가장 크다.
- re-entry 대상이 아니라 계약 문서 보강 대상이다.

candidate/scoring/filtering 로직
- behavior 계약 핵심이며 expected fixture와 회귀에 직접 연동된다.
- 구조 정리 목적 분리는 금지한다.

Stage2 reporter 구조 변경
- schema/wording 변경 리스크가 높다.
- report quality 이슈가 반복되지 않는 현재 상태에서는 열지 않는다.

expected/test fixture 변경
- 명시적 behavior change 작업이 아닌 한 금지한다.
- 현 시점 re-entry 범위 밖이다.

`constants.py` 대량 분리
- import cycle과 추적성 저하 위험이 크다.
- mini-move 원칙 유지가 우선이다.

## 6. 추천 우선순위

P1: review-only 후보

- shared attack/search policy constants
- `detect_decoded_attack_hints`
- normal search false-positive handling

P2: ownership map 후보

- `STANDARD_HTTP_METHODS`
- static path/classification constants
- probing/sensitive/mixed scanner 공유 constants

P3: 계속 보류 후보

- supporting_events 생성/연결 로직
- candidate/scoring/filtering 로직
- Stage2 reporter 구조 변경
- expected/test fixture 변경
- `constants.py` 대량 분리
- `AUTOMATION_UA_PATTERNS` (단, `lab-*`/tool UA 과해석 반복 시에만 재검토)

## 7. 다음 액션

1. 코드 분리 작업은 시작하지 않는다.
2. P1 항목에 대해 split plan이 아닌 review 문서(경계/계약)만 작성한다.
3. P2 항목은 ownership map 갱신 전까지 이동 금지로 유지한다.
4. P3 항목은 반복 regression 실패 또는 actual LLM output 이슈가 확인될 때만 재진입한다.

## 8. 검증 명령

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python3 -m pytest tests/test_stage2_report_quality.py
```

## 9. 결론

현재 re-entry review 결론은 다음과 같다.

```text
- 지금 즉시 코드 분리하지 않음
- shared attack/search policy, decoded hints, normal search FP는 review 문서 선행
- path/static/probing/method constants는 ownership map 선행
- supporting_events/scoring/filtering/Stage2 reporter/expected fixture/constants.py bulk split은 보류 유지
- AUTOMATION_UA_PATTERNS는 lab-* / tool UA 과해석 문제가 반복될 때만 재검토
```

이 결론은 stable regression 상태(`prepare 18/0/0`, `stage dry-run 12/0/0`, `Stage2 quality tests 14 passed`)와 Apache logs-only evidence boundary를 유지하기 위한 보수적 재진입 기준으로 적용한다.
