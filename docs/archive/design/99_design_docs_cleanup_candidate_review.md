# 99_design_docs_cleanup_candidate_review

- 기준 시점: 2026-05-09
- 검토 범위: `docs/design/*.md` 중 완료된 prepare split / constants move / hints split plan 성격 문서 중심
- 근거 문서:
  - `docs/design/README.md`
  - `docs/진행상황.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`

## 1. 검토 목적

`docs/design/` 내 완료된 작업 계획서/체크리스트 문서를 정리 후보로 분류하고, 요약 흡수 후 실제 삭제 반영 상태를 기록한다.

이번 문서는 검토 결과 + 삭제 완료 반영 상태 문서다.

## 2. 삭제 판단 기준

- 삭제 후보
  - 완료된 지시서/체크리스트 성격이고 현재 TODO/진행상황에서 직접 참조되지 않음
  - 동일 주제의 상위 summary 문서에 완료 맥락이 이미 흡수됨
- 보존 후보
  - Apache logs-only, evidence boundary, 성공 단정 금지, Web UI read-only 범위, 계약(contract)/fixture 같은 운영 판단 근거를 담음
  - 현재 TODO/진행상황/README에서 직접 참조되거나 재검토 가능성이 높음
- 요약 후 삭제
  - 개별 파일 삭제 전 README/진행상황/summary에 완료 요약을 흡수한 뒤 삭제
- 판단 보류
  - split 기록 문서이지만 supporting_events/context-only 경계 등 현재 운영 판단과 연결되어 즉시 삭제 판단이 위험

## 3. 삭제 후보 목록 (삭제 완료)

1. `docs/design/99_prepare_module_split_round2_candidate_review.md`
2. `docs/design/99_prepare_constants_mini_move_candidate_review.md`
3. `docs/design/99_prepare_hints_split_candidate_review.md`

## 4. 요약 후 삭제 완료 목록

- prepare summary split plan 5개 삭제 완료
  - `docs/design/99_prepare_method_summary_split_plan.md`
  - `docs/design/99_prepare_protocol_anomaly_split_plan.md`
  - `docs/design/99_prepare_auth_behavior_split_plan.md`
  - `docs/design/99_prepare_static_baseline_split_plan.md`
  - `docs/design/99_prepare_crawler_baseline_split_plan.md`
- prepare hints split plan 4개 삭제 완료
  - `docs/design/99_prepare_sqli_hints_split_plan.md`
  - `docs/design/99_prepare_xss_hints_split_plan.md`
  - `docs/design/99_prepare_file_disclosure_hints_split_plan.md`
  - `docs/design/99_prepare_traversal_cmdi_hints_split_plan.md`
- prepare constants move plan 6개 삭제 완료
  - `docs/design/99_prepare_protocol_anomaly_constants_move_plan.md`
  - `docs/design/99_prepare_ip_behavior_constants_move_plan.md`
  - `docs/design/99_prepare_method_behavior_constants_move_plan.md`
  - `docs/design/99_prepare_static_baseline_constants_move_plan.md`
  - `docs/design/99_prepare_auth_behavior_constants_move_plan.md`
  - `docs/design/99_prepare_crawler_baseline_constants_move_plan.md`
- 완료 요약 흡수 위치
  - `docs/design/README.md`
  - `docs/진행상황.md`
  - `docs/design/99_prepare_module_split_round1_summary.md`
  - `docs/design/99_prepare_module_split_round2_summary.md`
  - `docs/design/99_prepare_hints_split_summary.md`
  - `docs/design/99_prepare_constants_mini_move_summary.md`

## 5. 보존 후보 목록

1. `docs/design/99_prepare_context_summary_contract.md`
- 보존 이유: context summary input/output contract 및 context-only 불변조건 핵심 근거.

2. `docs/design/99_prepare_regression_fixture_설계.md`
- 보존 이유: regression fixture 설계 원칙/금지 규칙의 직접 기준 문서.

3. `docs/design/99_prepare_module_split_plan.md`
- 보존 이유: prepare 분리 작업의 상위 원칙(기계적 분리, Apache logs-only, 성공 단정 금지) 기준 문서.

4. `docs/design/99_prepare_module_split_round1_summary.md`
- 보존 이유: round1 결과의 상위 요약 문서로 추적 가치가 높음.

5. `docs/design/99_prepare_module_split_round2_summary.md`
- 보존 이유: round2 결과의 상위 요약 문서로 README/진행상황과 연결됨.

6. `docs/design/99_prepare_constants_ownership_map.md`
- 보존 이유: constants 대량 분리 보류 판단의 근거 문서.

7. `docs/design/99_prepare_constants_mini_move_summary.md`
- 보존 이유: constants mini-move 완료 상태를 집약하는 상위 요약.

8. `docs/design/99_prepare_hints_split_summary.md`
- 보존 이유: hints split 완료 상태를 집약하는 상위 요약.

9. `docs/design/99_prepare_shared_attack_policy_boundary_review.md`
- 보존 이유: shared policy/evidence boundary 보류 판단 근거.

10. `docs/design/99_POST_body_visibility_한계와_해석_기준.md`
- 보존 이유: Apache logs-only 가시성 한계와 blind spot 인정 원칙 문서.

11. `docs/design/99_web_ui_report_viewer_execution_scope_review.md`
- 보존 이유: Web UI read-only 원칙 및 execution console 보류 판단의 기준 문서.

## 6. 판단 보류 목록

1. `docs/design/99_prepare_sensitive_path_probe_split_plan.md`
- 보류 이유: supporting_events 연결/오염 방지 기준과 context-only 경계가 상세히 포함됨. 단순 완료 기록으로 보기 어려움.

2. `docs/design/99_prepare_ip_behavior_aggregates_split_plan.md`
- 보류 이유: IP 해석 한계(신원 단정 금지)와 output 계약이 함께 묶여 있어 정책 문서로도 사용됨.

3. `docs/design/99_prepare_probing_sequence_split_plan.md`
- 보류 이유: scanner-like sequence 해석 한계와 success 단정 금지 문구가 상세하여 정책 근거 성격이 큼.

4. `docs/design/99_prepare_mixed_baseline_scanner_split_plan.md`
- 보류 이유: context-only 유지 및 다중 baseline 신호 해석 경계가 현재 판단 근거로 사용될 가능성이 높음.

## 7. 권장 후속 작업

- 완료: 삭제 후보 3개 삭제
- 완료: 요약 후 삭제 후보 15개 삭제
- 남은 작업: 판단 보류 4개는 당분간 유지
- 남은 작업: `docs/design/README.md`와 `docs/진행상황.md`는 필요 시 추가 축약만 검토

## 8. 비고

- 본 문서는 검토 결과와 삭제 완료 반영 상태를 기록한다.
- 이번 정리에서 추가 파일 삭제/복구 및 코드/테스트/파이프라인 수정은 수행하지 않았다.
