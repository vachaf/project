# 99_design_docs_cleanup_candidate_review

- 기준 시점: 2026-05-09
- 검토 범위: `docs/design/*.md` 중 완료된 prepare split / constants move / hints split plan 성격 문서 중심
- 근거 문서:
  - `docs/design/README.md`
  - `docs/진행상황.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`

## 1. 검토 목적

`docs/design/` 내 완료된 작업 계획서/체크리스트 문서를 정리 후보로 분류해, 이후 문서 슬림화(삭제/요약 통합) 시 안전한 1차 판단 근거를 제공한다.

이번 문서는 검토 전용이며 실제 삭제는 수행하지 않는다.

## 2. 삭제 판단 기준

- 삭제 후보
  - 완료된 지시서/체크리스트 성격이고 현재 TODO/진행상황에서 직접 참조되지 않음
  - 동일 주제의 상위 summary 문서에 완료 맥락이 이미 흡수됨
- 보존 후보
  - Apache logs-only, evidence boundary, 성공 단정 금지, Web UI read-only 범위, 계약(contract)/fixture 같은 운영 판단 근거를 담음
  - 현재 TODO/진행상황/README에서 직접 참조되거나 재검토 가능성이 높음
- 요약 후 삭제 후보
  - 개별 파일 삭제는 가능하나, 삭제 전 README/진행상황에 1~3줄 요약을 남기면 안전
- 판단 보류
  - split 기록 문서이지만 supporting_events/context-only 경계 등 현재 운영 판단과 연결되어 즉시 삭제 판단이 위험

## 3. 삭제 후보 목록

1. `docs/design/99_prepare_module_split_round2_candidate_review.md`
- 이유: 후보 비교 문서이며 결과가 `99_prepare_module_split_round2_summary.md`와 진행상황 요약으로 흡수됨.
- 완료 요약 위치: `docs/design/99_prepare_module_split_round2_summary.md`, `docs/진행상황.md`.

2. `docs/design/99_prepare_constants_mini_move_candidate_review.md`
- 이유: 후보 비교 성격, 완료 결과가 `99_prepare_constants_mini_move_summary.md`로 정리됨.
- 완료 요약 위치: `docs/design/99_prepare_constants_mini_move_summary.md`, `docs/진행상황.md`.

3. `docs/design/99_prepare_hints_split_candidate_review.md`
- 이유: 후보 비교 문서이며 완료 상태가 `99_prepare_hints_split_summary.md`와 진행상황에 반영됨.
- 완료 요약 위치: `docs/design/99_prepare_hints_split_summary.md`, `docs/진행상황.md`.

## 4. 요약 후 삭제 후보 목록

1. `docs/design/99_prepare_method_summary_split_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md` prepare module split 섹션에 “method summary split 완료 + contract 불변조건 유지” 1줄.

2. `docs/design/99_prepare_protocol_anomaly_split_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md`에 “protocol anomaly split 완료, output key/fixture 계약 유지” 1줄.

3. `docs/design/99_prepare_auth_behavior_split_plan.md`
- 삭제 전 요약 제안: `docs/진행상황.md`에 “auth behavior split 완료, POST body 미가시성 해석 제한 유지” 1줄.

4. `docs/design/99_prepare_static_baseline_split_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md`에 “static baseline split 완료, context-only 유지” 1줄.

5. `docs/design/99_prepare_crawler_baseline_split_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md`에 “crawler baseline split 완료 및 fixture 계약 유지” 1줄.

6. `docs/design/99_prepare_sqli_hints_split_plan.md`
- 삭제 전 요약 제안: `docs/진행상황.md`에 “SQLi hints split 완료, DB 성공 단정 금지 유지” 1줄.

7. `docs/design/99_prepare_xss_hints_split_plan.md`
- 삭제 전 요약 제안: `docs/진행상황.md`에 “XSS hints split 완료, browser execution 단정 금지 유지” 1줄.

8. `docs/design/99_prepare_file_disclosure_hints_split_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md`에 “file disclosure hints split 완료, suspicious verdict 경계 유지” 1줄.

9. `docs/design/99_prepare_traversal_cmdi_hints_split_plan.md`
- 삭제 전 요약 제안: `docs/진행상황.md`에 “traversal/CMDI hints split 완료, execution/success 단정 금지 유지” 1줄.

10. `docs/design/99_prepare_protocol_anomaly_constants_move_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md` constants 섹션에 “PROTOCOL_ANOMALY 상수 mini-move 완료” 1줄.

11. `docs/design/99_prepare_ip_behavior_constants_move_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md` constants 섹션에 “IP_BEHAVIOR 상수 mini-move 완료” 1줄.

12. `docs/design/99_prepare_method_behavior_constants_move_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md` constants 섹션에 “method constants 부분 이동, STANDARD_HTTP_METHODS 보류” 1줄.

13. `docs/design/99_prepare_static_baseline_constants_move_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md` constants 섹션에 “static constants 부분 이동, path/classification 상수 보류” 1줄.

14. `docs/design/99_prepare_auth_behavior_constants_move_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md` constants 섹션에 “auth constants/patterns 이동 완료” 1줄.

15. `docs/design/99_prepare_crawler_baseline_constants_move_plan.md`
- 삭제 전 요약 제안: `docs/design/README.md` constants 섹션에 “crawler constants/patterns 이동 완료” 1줄.

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

- 1차 삭제 커밋 후보
  - 우선 `삭제 후보 3건`만 단일 커밋으로 정리

- README 정리 후보
  - `요약 후 삭제 후보` 삭제 전, `docs/design/README.md`에 split/mini-move 완료 이력을 1~3줄 집약 문장으로 통합

- TODO/진행상황 축소 후보
  - `docs/진행상황.md`의 완료 이력 중 split/mini-move/hints 항목을 “완료 묶음 요약”으로 축약
  - `docs/planning/99_비교실험_후속개선_TODO.md`는 완료 이력 나열을 더 줄이고 실제 미완료 TODO만 유지

## 8. 비고

- 본 문서는 검토 결과만 기록한다.
- 이번 작업에서 파일 삭제/이동/수정(코드/테스트/파이프라인)은 수행하지 않았다.
