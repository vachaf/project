# design

## 목적

- `design/`은 파이프라인 구조 설계, regression 설계, 모듈 분리 계획을 둔다.
- 해석 한계, 기능 보류, 분류 기준 검토 같은 설계 판단 문서도 함께 관리한다.

## 문서 목록

- 설계/회귀 검증
  - [99_document_cleanup_plan.md](./99_document_cleanup_plan.md): 문서 정리 계획과 유지/archive/delete 근거
  - [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md): prepare 모듈 분리 계획
  - [99_prepare_module_split_summary.md](./99_prepare_module_split_summary.md): prepare module split 현재 기준 요약
  - [99_prepare_llm_input_inventory.md](./99_prepare_llm_input_inventory.md): prepare_llm_input.py 책임 영역 inventory와 다음 분리 후보 검토
  - [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md): context summary builder 분리 전 input/output 불변조건
  - [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md): context summary builder 후보별 분리 우선순위 검토
  - [99_prepare_regression_fixture_설계.md](./99_prepare_regression_fixture_설계.md): prepare regression fixture 설계
  - [99_stage_dryrun_regression_설계.md](./99_stage_dryrun_regression_설계.md): Stage dry-run regression 설계
  - [99_output_cleanup_script_설계.md](./99_output_cleanup_script_설계.md): output cleanup script 안전 설계 기준
- prepare module split
  - [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md): round1 prepare 모듈 분리 완료 요약
  - [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md): round2 prepare 모듈 분리 완료 요약
  - method/protocol anomaly/auth/static baseline/crawler baseline summary split 완료: output key와 fixture/contract, Apache logs-only 해석 한계를 유지한 mechanical refactor로 반영
  - sensitive path probe / ip behavior / probing sequence / mixed baseline scanner 세부 split 기록은 [99_prepare_module_split_summary.md](./99_prepare_module_split_summary.md)에 흡수
- prepare deferred split / re-entry review
  - [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md): prepare 분리 이후 의도적으로 남겨둔 보류 항목과 재검토 조건
  - [99_prepare_deferred_split_reentry_review.md](./99_prepare_deferred_split_reentry_review.md): stable 상태에서 deferred split 재진입 여부를 보수적으로 검토한 문서
  - [99_prepare_shared_attack_policy_reentry_review.md](./99_prepare_shared_attack_policy_reentry_review.md): shared attack/search policy constants 재진입 검토
  - [99_prepare_search_false_positive_policy_reentry_review.md](./99_prepare_search_false_positive_policy_reentry_review.md): normal search false-positive handling 재진입 검토
- prepare constants ownership / mini-move
  - [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md): prepare constants ownership과 이동 가능성 지도
  - [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md): constants mini-move 완료 요약
  - protocol anomaly/IP behavior/method behavior 일부/static baseline 일부/auth behavior/crawler baseline constants mini-move 완료
  - shared attack/search policy, decoded hints, scoring/filtering, supporting_events, `constants.py` 대량 분리는 보류 유지
  - 완료된 세부 constants move plan 문서는 cleanup review 기준으로 요약 흡수 후 삭제 후보로 관리
- prepare hints split / evidence boundary
  - [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md): prepare hint split 완료 요약
  - SQLi/XSS/file disclosure/traversal-CMDI hints split 완료
  - SQLi DB 성공 단정 금지, XSS browser execution 단정 금지, file disclosure 실제 노출 단정 금지, CMDI execution/success 단정 금지 원칙 유지
  - [99_prepare_attack_hints_shared_policy_candidate_review.md](./99_prepare_attack_hints_shared_policy_candidate_review.md): attack hints와 shared policy 후보 비교
  - [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md): automation UA, shared attack/search policy, decoded hints 보류 경계 검토
  - [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md): 새 공격 커버리지 후보와 장기 roadmap 검토
  - [99_prepare_new_attack_coverage_round_summary.md](./99_prepare_new_attack_coverage_round_summary.md): 신규 공격 coverage 1라운드 완료 요약
  - [99_prepare_new_attack_coverage_round2_candidate_review.md](./99_prepare_new_attack_coverage_round2_candidate_review.md): 신규 공격 coverage 2라운드 후보 비교
  - [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md): P2 공격 커버리지 후보 우선순위와 완료/보류 상태 검토
  - [99_prepare_graphql_introspection_coverage_plan.md](./99_prepare_graphql_introspection_coverage_plan.md): GraphQL/API introspection 신호의 Apache logs-only 해석 경계와 coverage 계획
  - [99_prepare_graphql_introspection_fixture_plan.md](./99_prepare_graphql_introspection_fixture_plan.md): GraphQL/API introspection fixture/regression 구성 기준
  - [99_prepare_open_redirect_coverage_plan.md](./99_prepare_open_redirect_coverage_plan.md): redirect-like external URL parameter의 Apache logs-only 경계와 SSRF 구분 검토
  - [99_prepare_open_redirect_fixture_plan.md](./99_prepare_open_redirect_fixture_plan.md): `l3_open_redirect_external_url_context` fixture/regression 후보 설계
  - [99_prepare_api_key_secret_probe_coverage_plan.md](./99_prepare_api_key_secret_probe_coverage_plan.md): API key/secret token probe 신호의 Apache logs-only 경계와 false positive 위험 검토
  - [99_prepare_webshell_command_query_coverage_plan.md](./99_prepare_webshell_command_query_coverage_plan.md): webshell path + command-like query 결합 신호와 traversal/CMDI 경계 검토
  - [99_prepare_xxe_coverage_plan.md](./99_prepare_xxe_coverage_plan.md): XML parser abuse/XXE-like marker의 Apache logs-only 경계 검토
  - [99_prepare_xxe_fixture_plan.md](./99_prepare_xxe_fixture_plan.md): `l3_xxe_external_entity_context` fixture/regression 후보 설계
- prepare candidate policy / distribution
  - [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md): 현재 실제 prepare 로직에 반영된 candidate policy 기준
  - [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md): run 분포/history 정리
  - 세부 review 원문은 `docs/archive/design/` 아래 historical 문서로 이동
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
  - [99_pipeline_run_dir_output_layout_plan.md](./99_pipeline_run_dir_output_layout_plan.md): run dir 검토 문서
- observability summary index
  - [99_observability_run_summary_index.md](./99_observability_run_summary_index.md): run summary 상위 색인

## 읽는 순서

1. module split 현재 상태는 [99_prepare_module_split_summary.md](./99_prepare_module_split_summary.md)
2. candidate policy 현재 기준은 [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md)
3. constants 이동 또는 ownership 판단이면 prepare constants ownership / mini-move 문서
4. SQLi/XSS/file disclosure 등 hint 계열 분리나 evidence boundary 판단이면 prepare hints split / evidence boundary 문서
5. Stage2 prompt 정리나 report quality lint 검토면 Stage2 prompt / report quality 문서
6. 로그 가시성, 해석 한계, 보류 기능 판단이면 설계 결정/해석 한계 문서
7. 관련 평가는 [../reviews/README.md](../reviews/README.md)
8. 후속 작업은 [../planning/README.md](../planning/README.md)

## 관리 원칙

- 구현 여부, 한계, 보류 결정, regression 설계는 `design/`에 둔다.
- 평가, 품질 검토, 완료 리뷰는 `reviews/`에 둔다.
- 후속 작업 큐와 TODO는 `planning/`에 둔다.
