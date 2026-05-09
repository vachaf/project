# 99_prepare_shared_attack_policy_reentry_review

- 문서 상태: prepare deferred split re-entry review (shared attack/search policy constants)
- 기준 시점: 2026-05-07
- 목적: deferred split P1 후보였던 shared attack/search policy constants를 split plan이 아닌 re-entry review 관점에서 다시 검토하고, 지금 시점의 경계 판단을 고정한다.

관련 문서:

- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [99_prepare_deferred_split_reentry_review.md](./99_prepare_deferred_split_reentry_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

## 1. 목적

이번 문서는 shared attack/search policy constants를 지금 다시 열지 검토하는 re-entry 판단 문서다.

명시적 범위:

```text
- split plan 문서가 아님
- 코드 분리 실행 문서가 아님
- 경계/계약 재확인 문서임
- 기본 결론은 "즉시 코드 분리 보류"
```

## 2. 현재 상태

prepare 계열은 현재 stable 상태를 유지 중이며, 이번 검토는 안정 상태에서의 보수적 재진입 판단으로 본다.

현재 상태 요약:

```text
- SQLi/XSS/file disclosure/traversal-CMDI topic hint split 완료
- shared policy constants는 의도적으로 src/prepare_llm_input.py에 유지
- prepare regression stable
- stage dry-run regression stable
- Stage2 quality tests stable
```

해석 경계 유지:

```text
- Apache logs-only evidence boundary 유지
- 구조 정리 목적만으로 candidate/scoring/filtering 의미를 건드리지 않음
```

## 3. 대상 constants별 역할

검토 대상:

```text
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
STRONG_ATTACK_HINT_PREFIXES
STRONG_ATTACK_HINTS
ATTACK_ENCODED_PAYLOAD_RE
```

각 constant의 정책 경계 역할:

- `SEARCH_PARAM_NAMES`: search/query parameter detection 경계. query-like 요청을 일반 검색 맥락으로 분류할지의 첫 관문이다.
- `NORMAL_SEARCH_VALUE_RE`: 정상 검색어/저위험 검색값 판단 경계. false-positive suppression 진입 조건과 연결된다.
- `NORMAL_SEARCH_ATTACK_TEXT_RE`: 검색값 내부 공격성 텍스트 판단 경계. 정상 검색 baseline과 공격성 텍스트를 구분하는 보강 규칙이다.
- `STRONG_ATTACK_HINT_PREFIXES`: strong hint preservation 경계. suppression 중에도 보존해야 하는 강한 공격 힌트 prefix 판단에 연결된다.
- `STRONG_ATTACK_HINTS`: strong attack hint 판단 경계. 개별 강신호 힌트의 보존 여부를 고정한다.
- `ATTACK_ENCODED_PAYLOAD_RE`: encoded payload signal 경계. 인코딩된 공격 페이로드 흔적을 포착하되, 이는 reconstruction signal이지 실행/성공 근거가 아님을 전제로 한다.

## 4. 연결된 정책 경계

shared constants는 단일 topic 내부 상수가 아니라 아래 경계를 가로지르는 shared policy 계약이다.

```text
- normal search false-positive suppression
- educational SQL/XSS search context
- strong hint preservation
- candidate preservation
- filtered_out / false_positive_review_candidates
- SQLi/XSS/file disclosure/traversal-CMDI hint split 경계
- Apache logs-only evidence boundary
```

핵심은 suppression과 preservation의 균형이며, 어느 한쪽으로만 치우친 이동은 regression 민감도를 높일 수 있다.

## 5. 위험 분석

지금 시점에서 분리를 재개할 때 주요 위험은 다음과 같다.

- shared module로 분리 시 owner가 모호해질 수 있다.
- false-positive suppression이 과도해지면 실제 공격 후보가 누락될 수 있다.
- strong hint preservation이 과도해지면 정상 검색이 후보로 과잉 보존될 수 있다.
- topic hint module들이 shared module을 import하면서 import direction이 복잡해질 수 있다.
- candidate/scoring/filtering behavior가 간접 변경될 위험이 있다.

추가로, split 자체가 mechanical이어도 정책 경계 해석이 흔들리면 `filtered_out`, `false_positive_review_candidates`, candidate 구성 결과에 영향이 날 수 있다.

## 6. 지금 분리 가능 여부

결론:

```text
- 지금 즉시 코드 분리하지 않음
- shared policy contract 문서화만 수행
- 반복 문제 또는 regression/LLM output 이슈가 실제 확인될 때 split plan 작성
```

이번 문서는 re-entry review이며 split 확정 문서가 아니다.

## 7. 재검토 조건

아래 조건이 누적 확인될 때만 다음 단계(별도 split plan)를 연다.

- normal search FP 문제가 실제 LLM 출력에서 반복됨
- strong hint preservation 문제로 candidate 누락/과잉 보존이 반복됨
- shared policy constants의 단일 owner를 확정할 수 있음
- candidate/scoring/filtering 변화 없이 mechanical refactor 가능함을 확인
- import direction이 단방향으로 유지됨

게이트 규칙:

```text
- 위 조건이 불충분하면 분리 보류 유지
- 구조 정리 필요성만으로는 재진입 불가
```

## 8. 가능한 후속 문서

재검토 조건 충족 시 다음 review/split 후보 문서를 순차 검토한다.

- `docs/design/99_prepare_shared_attack_policy_split_plan.md`
- `docs/design/99_prepare_search_false_positive_policy_reentry_review.md`
- `docs/design/99_prepare_decoded_attack_hints_reentry_review.md`

## 9. 결론

최종 판단:

```text
- shared attack/search policy constants는 P1 review-only 후보로 유지
- 코드 분리는 보류
- 다음 단계는 normal search FP 또는 decoded hints를 즉시 여는 것이 아니라
  실제 반복 문제 여부를 먼저 확인
```

본 결론은 stable regression 상태와 Apache logs-only evidence boundary를 유지하기 위한 보수적 판단으로 적용한다.
