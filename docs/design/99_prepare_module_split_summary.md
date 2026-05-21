# 99_prepare_module_split_summary

- 기준 시점: 2026-05-21
- 문서 역할: prepare module split의 현재 기준 요약
- 관련 historical 문서:
  - [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
  - [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
  - [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
  - [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
  - [99_prepare_deferred_split_reentry_review.md](./99_prepare_deferred_split_reentry_review.md)

## 1. 현재 결론

prepare module split은 현재 stable 상태로 본다.

- round1/round2에서 mechanical refactor 범위의 분리는 완료됐다.
- candidate/scoring/filtering, supporting_events 생성/연결, Stage1/Stage2 schema/wording, output key 의미는 이 작업으로 바꾸지 않았다.
- Apache logs-only 해석 원칙은 유지한다.
- 추가 분리는 구조 정리 목적만으로 재개하지 않고, `99_prepare_deferred_split_items.md`, `99_prepare_deferred_split_reentry_review.md` 기준으로만 다시 연다.

## 2. 완료 범위

### 2.1 round1에서 고정된 모듈

```text
src/prepare/decoders.py
src/prepare/l3_hints.py
src/prepare/models.py
src/prepare/method_summaries.py
src/prepare/protocol_anomalies.py
src/prepare/auth_behavior.py
src/prepare/static_baseline.py
src/prepare/crawler_baseline.py
src/prepare/sensitive_path_probe.py
```

핵심 유지 조건:

- decoded payload reconstruction을 execution/success proof로 쓰지 않는다.
- method/protocol/auth/static/crawler/sensitive-path 관찰은 context 또는 request-pattern signal이지 성공 단정 근거가 아니다.
- `status_code=200`, `response_body_bytes`, `resp_content_type`, UA/IP만으로 성공/노출/침해를 단정하지 않는다.

### 2.2 round2에서 고정된 모듈

```text
src/prepare/ip_behavior.py
src/prepare/probing_sequence.py
src/prepare/mixed_baseline_scanner.py
```

핵심 유지 조건:

- IP 집계는 신원 판정이 아니다.
- probing/scanner burst는 context 요약이지 성공/노출/침해 확정이 아니다.
- static/not-found/admin/.env/server-status 계열은 requested path 관찰일 뿐 실제 파일 존재나 admin 접근 성공을 뜻하지 않는다.

## 3. 현재 기준 문서와 historical 문서의 역할 분리

### 3.1 현재 기준으로 읽을 문서

- 이 문서: 전체 split 범위와 현재 상태 요약
- [99_prepare_llm_input_inventory.md](./99_prepare_llm_input_inventory.md): 남은 책임 inventory
- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md): constants ownership
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md): summary contract
- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md): 남은 보류 항목
- [99_prepare_deferred_split_reentry_review.md](./99_prepare_deferred_split_reentry_review.md): 재진입 기준

### 3.2 세부 historical 문서

- `99_prepare_module_split_plan.md`: 초기 umbrella plan
- `99_prepare_module_split_round1_summary.md`: round1 세부 완료 기록
- `99_prepare_module_split_round2_summary.md`: round2 세부 완료 기록

## 4. 이번에 종합 문서로 흡수한 세부 split 기록

이번 cleanup에서 아래 문서의 “독립 active 문서” 역할은 종료한다.

```text
docs/design/99_prepare_sensitive_path_probe_split_plan.md
docs/design/99_prepare_ip_behavior_aggregates_split_plan.md
docs/design/99_prepare_probing_sequence_split_plan.md
docs/design/99_prepare_mixed_baseline_scanner_split_plan.md
```

삭제 가능한 이유:

- 모두 완료된 단일 split 범위만 다루는 세부 기록이다.
- 유지해야 할 핵심 정보는 이미 round summary와 이 종합 문서에 남는다.
- 남은 TODO나 정책 변화가 따로 남아 있지 않다.
- 링크 대상이 분산되어 `docs/design/` 가독성을 떨어뜨리므로, 종합 문서 하나로 읽는 편이 낫다.

## 5. 의도적으로 남겨둔 비분리 영역

아래는 “아직 안 했음”이 아니라 “지금은 하지 않음”으로 고정된 항목이다.

- shared attack/search policy constants
- `detect_decoded_attack_hints`
- supporting_events 생성/연결 로직
- candidate/scoring/filtering 로직
- normal search false-positive handling
- large `constants.py` bulk split
- Stage2 reporter 구조 변경
- expected/test fixture 변경

관련 기준 문서:

- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [99_prepare_shared_attack_policy_reentry_review.md](./99_prepare_shared_attack_policy_reentry_review.md)
- [99_prepare_search_false_positive_policy_reentry_review.md](./99_prepare_search_false_positive_policy_reentry_review.md)
- [99_prepare_deferred_split_reentry_review.md](./99_prepare_deferred_split_reentry_review.md)

## 6. 검증 상태

split 문서 전반에서 유지한 공통 전제:

```text
- mechanical refactor only
- behavior change 없음
- output JSON key/meaning 유지
- reason_hints 이름 유지
- Apache logs-only evidence boundary 유지
```

현재는 추가 split보다 관찰/유지 단계가 우선이다.
