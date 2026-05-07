# design

## 목적

- `design/`은 파이프라인 구조 설계, regression 설계, 모듈 분리 계획을 둔다.
- 해석 한계, 기능 보류, 분류 기준 검토 같은 설계 판단 문서도 함께 관리한다.

## 문서 목록

- 설계/회귀 검증
  - [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md): prepare 모듈 분리 계획
  - [99_prepare_llm_input_inventory.md](./99_prepare_llm_input_inventory.md): prepare_llm_input.py 책임 영역 inventory와 다음 분리 후보 검토
  - [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md): context summary builder 분리 전 input/output 불변조건
  - [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md): context summary builder 후보별 분리 우선순위 검토
  - [99_prepare_regression_fixture_설계.md](./99_prepare_regression_fixture_설계.md): prepare regression fixture 설계
  - [99_stage_dryrun_regression_설계.md](./99_stage_dryrun_regression_설계.md): Stage dry-run regression 설계
  - [99_output_cleanup_script_설계.md](./99_output_cleanup_script_설계.md): output cleanup script 안전 설계 기준
- prepare module split
  - [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md): round1 prepare 모듈 분리 완료 요약
  - [99_prepare_module_split_round2_candidate_review.md](./99_prepare_module_split_round2_candidate_review.md): round2 후보 비교와 다음 후보 결정
  - [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md): round2 prepare 모듈 분리 완료 요약
  - [99_prepare_method_summary_split_plan.md](./99_prepare_method_summary_split_plan.md): method behavior summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_protocol_anomaly_split_plan.md](./99_prepare_protocol_anomaly_split_plan.md): protocol anomaly summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_auth_behavior_split_plan.md](./99_prepare_auth_behavior_split_plan.md): auth behavior summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_static_baseline_split_plan.md](./99_prepare_static_baseline_split_plan.md): static baseline summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_crawler_baseline_split_plan.md](./99_prepare_crawler_baseline_split_plan.md): crawler baseline summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md): sensitive path probe summary 분리 완료 기록
  - [99_prepare_ip_behavior_aggregates_split_plan.md](./99_prepare_ip_behavior_aggregates_split_plan.md): IP behavior aggregate split 계획/완료 기록
  - [99_prepare_probing_sequence_split_plan.md](./99_prepare_probing_sequence_split_plan.md): probing sequence summary split 계획/완료 기록
  - [99_prepare_mixed_baseline_scanner_split_plan.md](./99_prepare_mixed_baseline_scanner_split_plan.md): mixed baseline scanner summary split 계획/완료 기록
- prepare deferred split / re-entry review
  - [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md): prepare 분리 이후 의도적으로 남겨둔 보류 항목과 재검토 조건
  - [99_prepare_deferred_split_reentry_review.md](./99_prepare_deferred_split_reentry_review.md): stable 상태에서 deferred split 재진입 여부를 보수적으로 검토한 문서
  - [99_prepare_shared_attack_policy_reentry_review.md](./99_prepare_shared_attack_policy_reentry_review.md): shared attack/search policy constants 재진입 검토
  - [99_prepare_search_false_positive_policy_reentry_review.md](./99_prepare_search_false_positive_policy_reentry_review.md): normal search false-positive handling 재진입 검토
- prepare constants ownership / mini-move
  - [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md): prepare constants ownership과 이동 가능성 지도
  - [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md): safe constants mini-move 후보 검토
  - [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md): constants mini-move 완료 요약
  - [99_prepare_protocol_anomaly_constants_move_plan.md](./99_prepare_protocol_anomaly_constants_move_plan.md): protocol anomaly constants 이동 계획/완료 기록
  - [99_prepare_ip_behavior_constants_move_plan.md](./99_prepare_ip_behavior_constants_move_plan.md): IP behavior constants 이동 계획/완료 기록
  - [99_prepare_method_behavior_constants_move_plan.md](./99_prepare_method_behavior_constants_move_plan.md): method behavior constants 부분 이동 계획/완료 기록
  - [99_prepare_static_baseline_constants_move_plan.md](./99_prepare_static_baseline_constants_move_plan.md): static baseline constants 부분 이동 계획/완료 기록
  - [99_prepare_auth_behavior_constants_move_plan.md](./99_prepare_auth_behavior_constants_move_plan.md): auth behavior constants/patterns 이동 계획/완료 기록
  - [99_prepare_crawler_baseline_constants_move_plan.md](./99_prepare_crawler_baseline_constants_move_plan.md): crawler baseline constants/patterns 이동 계획/완료 기록
- prepare hints split / evidence boundary
  - [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md): SQLi/XSS/file disclosure 등 hint split 후보 비교
  - [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md): prepare hint split 완료 요약
  - [99_prepare_sqli_hints_split_plan.md](./99_prepare_sqli_hints_split_plan.md): SQLi hint split 계획/완료 기록
  - [99_prepare_xss_hints_split_plan.md](./99_prepare_xss_hints_split_plan.md): XSS hint split 계획/완료 기록
  - [99_prepare_file_disclosure_hints_split_plan.md](./99_prepare_file_disclosure_hints_split_plan.md): file disclosure hint split 계획/완료 기록
  - [99_prepare_traversal_cmdi_hints_split_plan.md](./99_prepare_traversal_cmdi_hints_split_plan.md): traversal/CMDI hint split 계획/완료 기록
  - [99_prepare_attack_hints_shared_policy_candidate_review.md](./99_prepare_attack_hints_shared_policy_candidate_review.md): attack hints와 shared policy 후보 비교
  - [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md): automation UA, shared attack/search policy, decoded hints 보류 경계 검토
  - [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md): 새 공격 커버리지 후보와 장기 roadmap 검토
- Stage2 prompt / report quality
  - [99_stage2_prompt_compaction_plan.md](./99_stage2_prompt_compaction_plan.md): Stage2 report prompt 압축·섹션화 계획/완료 기록
  - [99_stage2_report_quality_lint_candidate_review.md](./99_stage2_report_quality_lint_candidate_review.md): Stage2 report quality lint 후보 검토와 warning-only 도입 기준
  - [99_stage2_report_quality_lint_tuning_plan.md](./99_stage2_report_quality_lint_tuning_plan.md): Stage2 report quality lint safe-negation tuning 계획/완료 기록
- Web UI / report viewer
  - [99_web_ui_report_viewer_plan.md](./99_web_ui_report_viewer_plan.md): Stage2 report viewer 전체 설계와 phase 개요
  - [99_web_ui_report_viewer_phase1a_plan.md](./99_web_ui_report_viewer_phase1a_plan.md): Phase 1A report list/detail + Stage2 quality lint display 구현 체크리스트
  - [99_web_ui_report_viewer_phase1a_template_contract.md](./99_web_ui_report_viewer_phase1a_template_contract.md): Phase 1A 템플릿/뷰 컨텍스트 contract
  - [99_web_ui_report_viewer_phase1b_plan.md](./99_web_ui_report_viewer_phase1b_plan.md): Phase 1B compare view 설계와 구현 체크리스트
  - [99_web_ui_report_viewer_phase2_candidate_review.md](./99_web_ui_report_viewer_phase2_candidate_review.md): read-only viewer 확장과 execution console 확장 후보 비교
  - [99_web_ui_report_viewer_phase2a_filter_plan.md](./99_web_ui_report_viewer_phase2a_filter_plan.md): Phase 2A read-only filter/search/navigation MVP 설계
  - [99_web_ui_report_viewer_ui_polish_plan.md](./99_web_ui_report_viewer_ui_polish_plan.md): UI polish 우선순위와 프레임워크 보류 기준
- 설계 결정/해석 한계
  - [99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md](./99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md): HTML fallback fingerprint 기능 보류 결정
  - [99_POST_body_visibility_한계와_해석_기준.md](./99_POST_body_visibility_한계와_해석_기준.md): POST body visibility 한계와 해석 기준
  - [99_sensitive_path_probe_context_category_검토.md](./99_sensitive_path_probe_context_category_검토.md): sensitive path probe context category 도입 검토
  - [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md): file disclosure verdict taxonomy 상태와 후속 검증 조건 검토

## 읽는 순서

1. regression 또는 module split 작업이면 설계/회귀 검증 문서와 prepare module split 문서
2. constants 이동 또는 ownership 판단이면 prepare constants ownership / mini-move 문서
3. SQLi/XSS/file disclosure 등 hint 계열 분리나 evidence boundary 판단이면 prepare hints split / evidence boundary 문서
4. Stage2 prompt 정리나 report quality lint 검토면 Stage2 prompt / report quality 문서
5. 로그 가시성, 해석 한계, 보류 기능 판단이면 설계 결정/해석 한계 문서
6. 관련 평가는 [../reviews/README.md](../reviews/README.md)
7. 후속 작업은 [../planning/README.md](../planning/README.md)

## 관리 원칙

- 구현 여부, 한계, 보류 결정, regression 설계는 `design/`에 둔다.
- 평가, 품질 검토, 완료 리뷰는 `reviews/`에 둔다.
- 후속 작업 큐와 TODO는 `planning/`에 둔다.
