# 99_prepare_search_false_positive_policy_reentry_review

- 문서 상태: prepare deferred split re-entry review (normal search false-positive handling)
- 기준 시점: 2026-05-07
- 목적: deferred split P1 후보 중 normal search false-positive handling을 split plan이 아닌 re-entry review 관점에서 상세 검토하고, 현재 경계 판단을 고정한다.

관련 문서:

- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [99_prepare_deferred_split_reentry_review.md](./99_prepare_deferred_split_reentry_review.md)
- [99_prepare_shared_attack_policy_reentry_review.md](./99_prepare_shared_attack_policy_reentry_review.md)
- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

## 1. 목적

- normal search false-positive handling을 지금 다시 열지 검토한다.
- 이번 문서는 코드 분리 계획 문서가 아니라 re-entry 판단 문서다.
- 기본 결론은 "즉시 코드 분리 보류"로 고정한다.

명시적 범위:

```text
- split plan 작성/확정 범위가 아님
- 코드 이동 실행 문서가 아님
- 정책 경계와 재검토 조건을 고정하는 review 문서임
```

## 2. 현재 상태

현재 prepare 계열은 안정 상태이며, normal search FP 정책도 의도적으로 coordinator 영역에 남겨둔 상태다.

현재 상태 요약:

```text
- SQLi/XSS/file disclosure/traversal-CMDI hint split 완료
- shared attack/search policy re-entry review 완료
- normal search FP 관련 로직은 src/prepare_llm_input.py에 의도적으로 유지
- prepare regression stable (pass=18 warn=0 fail=0)
- stage dry-run regression stable (pass=12 warn=0 fail=0)
- Stage2 quality tests stable (14 passed)
```

## 3. 검토 대상

이번 re-entry review의 직접 대상은 아래 항목이다.

```text
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
benign_normal_search
normal_search_baseline
educational SQL/XSS search context
false_positive_review_candidates
STRONG_ATTACK_HINT_PREFIXES / STRONG_ATTACK_HINTS와의 관계
```

검토 관점:

- `SEARCH_PARAM_NAMES`: query-like 요청을 normal search 맥락으로 진입시킬지 판단하는 시작 경계
- `NORMAL_SEARCH_VALUE_RE`: 정상 검색어 패턴으로 suppression 진입 조건을 제한하는 경계
- `NORMAL_SEARCH_ATTACK_TEXT_RE`: 검색값 내 공격성 텍스트를 재검사해 과도 suppression을 막는 경계
- `benign_normal_search`: filtered baseline category로서 과승격 방지 역할
- `normal_search_baseline`: 주변 문맥 비교군(reference baseline) 유지 역할
- educational SQL/XSS search context: 학습/검색 맥락을 공격 후보와 분리하는 보수 처리 경계
- `false_positive_review_candidates`: context-only review 후보로 남기는 완충 지점
- `STRONG_ATTACK_HINT_PREFIXES` / `STRONG_ATTACK_HINTS`: suppression 중에도 강한 공격 신호를 보존하는 역보정 경계

## 4. 정책 경계

본 정책은 suppression과 preservation을 동시에 만족해야 하며, 아래 경계를 유지한다.

- 정상 검색어를 공격 후보로 과승격하지 않는다.
- educational SQL/XSS search를 실제 공격으로 단정하지 않는다.
- strong attack hint가 있는 요청은 과도하게 `filtered_out` 처리하지 않는다.
- Apache logs-only 원칙을 유지한다.

정책 해석 원칙:

```text
- normal search suppression은 over-promotion 억제 목적이다.
- strong hint preservation은 under-detection 억제 목적이다.
- 둘 중 하나만 강화하면 candidate/scoring/filtering 균형이 깨질 수 있다.
```

## 5. 위험 분석

주요 위험은 FP suppression 강도 조절 실패에서 발생한다.

- suppression이 강하면 실제 공격 후보 누락 위험이 커진다.
- suppression이 약하면 benign search가 공격 후보로 과승격될 수 있다.
- shared policy constants와 candidate/scoring/filtering 경계가 강하게 결합되어 있어 mechanical move라도 간접 영향 위험이 있다.
- `supporting_events`와 `reference_baseline`의 문맥 역할에도 파급 가능성이 있다.
- `tests/expected` fixture 계약이 민감해 예기치 않은 변화 위험이 있다.

## 6. 지금 분리 가능 여부

결론:

```text
- 지금 즉시 코드 분리하지 않음
- split plan 작성도 보류
- 실제 LLM 출력 또는 regression에서 normal search FP 문제가 반복될 때 재검토
```

현재 판단 근거:

- 해당 로직은 shared attack/search policy와 candidate preservation 경계에 직접 연결되어 있다.
- 안정 상태에서 구조 정리 목적만으로 재진입할 근거가 부족하다.

## 7. 재검토 조건

아래 조건이 확인될 때만 re-entry를 다시 연다.

- benign normal search가 실제 LLM output에서 반복적으로 오탐을 만든다.
- educational SQL/XSS search가 공격 후보로 반복 과승격된다.
- strong hint preservation 약화로 실제 공격 후보가 빠진다.
- candidate/scoring/filtering 변화 없이 mechanical refactor 가능함을 확인한다.
- search FP policy contract를 별도 문서로 먼저 고정한다.

게이트 규칙:

```text
- 위 조건이 누적 확인되기 전에는 코드 분리 및 split plan 작성을 시작하지 않는다.
```

## 8. 가능한 후속 문서

재검토 조건 충족 시 아래 문서를 순차 후보로 둔다.

- `docs/design/99_prepare_search_false_positive_policy_split_plan.md`
- `docs/design/99_prepare_shared_attack_policy_split_plan.md`
- `docs/design/99_prepare_decoded_attack_hints_reentry_review.md`

## 9. 결론

최종 결론:

```text
- normal search false-positive handling은 P1 review-only 후보로 유지
- 코드 분리는 보류
- shared attack/search policy와 함께 관찰 대상으로 유지
```

본 결론은 2026-05-07 기준 stable regression 상태와 Apache logs-only 원칙을 유지하기 위한 보수적 re-entry 판단이다.
