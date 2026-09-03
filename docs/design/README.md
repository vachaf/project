# design

## 목적

- `design/`은 파이프라인 구조 설계, regression 설계, 모듈 분리 계획을 둔다.
- 해석 한계, 기능 보류, 분류 기준 검토 같은 설계 판단 문서도 함께 관리한다.
- 현재 상위 구조와 문서 해석 기준은 [../00_current_architecture.md](../00_current_architecture.md)를 따른다.

## 빠른 읽기 원칙

- 전체 현재 구조는 [../00_current_architecture.md](../00_current_architecture.md)를 먼저 본다.
- Apache logs-only evidence boundary는 [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)를 single source of truth로 둔다.
- `full_report`는 DB-backed MVP의 direct pipeline mode다.
- Sliding Window, Rollup, Operator Queue는 `full_report`에 자동 포함되는 단계가 아니라 후속 `windowed_triage` 흐름이다.
- `analysis_jobs` queue는 DB-backed 분석 실행 queue이고, `operator_queue`는 rollup 결과를 사람이 검토하기 위한 queue다.

## 현재 기준 / Canonical

- [../00_current_architecture.md](../00_current_architecture.md): 현재 architecture, DB-backed MVP, mode/queue 경계
- [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md): Apache logs-only 판정 경계와 금지/권장 표현 기준
- [99_db_backed_log_collection_and_analysis_job_design.md](./99_db_backed_log_collection_and_analysis_job_design.md): DB-backed log collection과 analysis job 설계
- [99_db_backed_web_ui_api_safety_addendum.md](./99_db_backed_web_ui_api_safety_addendum.md): Web UI/API safety와 read-only 해석 기준
- [99_analysis_job_modes_and_sliding_window_integration.md](./99_analysis_job_modes_and_sliding_window_integration.md): `full_report`와 후속 `windowed_triage` mode 경계
- [99_observability_run_summary_index.md](./99_observability_run_summary_index.md): observability run summary canonical index
- [99_apache_app_observability_scenario_catalog.md](./99_apache_app_observability_scenario_catalog.md): Apache app observability scenario catalog docs-side summary
- [99_apache_app_observability_matrix_template.md](./99_apache_app_observability_matrix_template.md): Apache app observability matrix template docs-side summary
- [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md): 현재 prepare candidate policy 기준

## 분류 개요

| 분류 | 우선 문서 | 읽는 목적 |
| --- | --- | --- |
| DB-backed MVP / Web UI / Analysis Agent | `99_db_backed_*`, `99_analysis_job_modes_*` | 현재 job 등록, worker 실행, report/viewer 저장 흐름 |
| Apache logs-only / observability / candidate policy | `99_observability_run_summary_index.md`, `99_apache_app_observability_scenario_catalog.md`, `99_apache_app_observability_matrix_template.md`, `../reviews/99_observability_run_summaries.md`, `99_prepare_candidate_policy.md`, `99_prepare_candidate_policy_distribution_history.md` | 로그 관찰 한계, 후보 추출 정책, run summary 색인과 docs-side 관찰 요약 |
| prepare split / constants / hints | `99_prepare_module_split_summary.md`, `99_prepare_constants_ownership_map.md`, `99_prepare_hints_split_summary.md` | prepare 내부 구조와 보수적 분리 기준 |
| Sliding Window / rollup / operator queue | `99_analysis_job_modes_and_sliding_window_integration.md`, `99_sliding_window_*` | 후속 `windowed_triage`와 operator review queue |
| Stage2 / report quality | `99_stage2_*` | Stage2 prompt, report lint, wording quality |
| Historical review / 후보 검토 | `*_review.md`, phase plan, adoption review | 완료 검토, 보류 근거, archive/delete 전 판단 자료 |

## 세부 문서 목록

- 현재 DB-backed MVP / Web UI / Analysis Agent
  - [99_db_backed_log_collection_and_analysis_job_design.md](./99_db_backed_log_collection_and_analysis_job_design.md): Apache 로그 수집, MariaDB, Web UI `analysis_jobs` 등록, Analysis Agent 실행, 결과 표시까지의 DB-backed MVP 설계
  - [99_db_backed_web_ui_api_safety_addendum.md](./99_db_backed_web_ui_api_safety_addendum.md): Web UI/API safety, 보안 결과 해석 read-only, `analysis_jobs` 등록/조회 DB write/read 허용 범위
  - [99_run_analysis_pipeline_user_runner_ux_review.md](./99_run_analysis_pipeline_user_runner_ux_review.md): `run_analysis_pipeline.py` 사용자 실행 UX와 DB-backed job lifecycle 연결 기준
- 설계/회귀 검증
  - [104_external_benchmark_930100_3_classification_review.md](./104_external_benchmark_930100_3_classification_review.md): CRS 930100/3 raw encoded traversal semantics, current normalization gap, exact traversal annotation 유지 결정
  - [103_external_benchmark_mapping_boundary_review.md](./103_external_benchmark_mapping_boundary_review.md): traversal + direct-sensitive evidence의 CWE-552/WSTG-CONF-04 boundary, controlled Stage1 4건 conflict, case-specific manifest alignment 결론
  - [102_external_benchmark_prepare_baseline_review.md](./102_external_benchmark_prepare_baseline_review.md): OWASP CRS Prepare-only baseline 27 direct cases의 production path, miss/예상 밖 candidate 원인, P0~P3 우선순위와 Stage1 진입 결정
  - [101_external_security_benchmark_design.md](./101_external_security_benchmark_design.md): OWASP CRS 930100/930110/930120 기반 외부 security benchmark의 observability, case annotation, fixture/result schema, metric, Level 1/2 상세 설계
  - [99_document_cleanup_plan.md](./99_document_cleanup_plan.md): 문서 정리 계획과 유지/archive/delete 근거
  - [99_lab_runner_migration_plan.md](./99_lab_runner_migration_plan.md): `lab/*_set` runner code를 `scripts/lab_runners/{set}/`로 분리하기 위한 설계와 영향 범위
  - [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md): prepare 모듈 분리 계획
  - [99_prepare_module_split_summary.md](./99_prepare_module_split_summary.md): prepare module split 현재 기준 요약
  - [99_prepare_llm_input_inventory.md](./99_prepare_llm_input_inventory.md): prepare_llm_input.py 책임 영역 inventory와 다음 분리 후보 검토
  - [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md): context summary builder 분리 전 input/output 불변조건
  - [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md): context summary builder 후보별 분리 우선순위 검토
  - [99_prepare_regression_fixture_설계.md](./99_prepare_regression_fixture_설계.md): prepare regression fixture 설계
  - [99_stage_dryrun_regression_설계.md](./99_stage_dryrun_regression_설계.md): Stage dry-run regression 설계
  - [99_output_cleanup_script_설계.md](./99_output_cleanup_script_설계.md): output cleanup script 안전 설계 기준
  - [99_cleanup_outputs_lab_protection_policy_review.md](./99_cleanup_outputs_lab_protection_policy_review.md): runner migration 이후에도 `cleanup_outputs.py`의 `lab` 보호 정책을 유지할지 검토한 문서
  - [99_lab_artifact_fixture_selection_plan.md](./99_lab_artifact_fixture_selection_plan.md): `lab/*_산출물` 제거 전 보존할 대표 fixture 후보와 이관 기준을 정리한 계획
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
  - [99_proxy_error_check_scenario_extension_review.md](./99_proxy_error_check_scenario_extension_review.md): proxy error check를 정규 scenario가 아닌 availability extension 후보로 유지할지 검토
- prepare candidate policy / distribution
  - [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md): 현재 실제 prepare 로직에 반영된 candidate policy 기준
  - [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md): run 분포/history 정리. 새 policy가 아니라 관찰 기록이다.
  - [99_prepare_apache_observability_context_feature_review.md](./99_prepare_apache_observability_context_feature_review.md): Apache observability context feature review. 현재는 삭제/통합 대상이 아니라 design review/historical 참고 문서로 둔다.
  - 세부 review 원문 중 이미 이동된 문서는 `docs/archive/design/` 아래 historical 문서로 관리한다.
- Stage2 prompt / report quality
  - [99_stage2_prompt_compaction_plan.md](./99_stage2_prompt_compaction_plan.md): Stage2 report prompt 압축·섹션화 계획/완료 기록
  - [99_stage2_report_quality_lint_candidate_review.md](./99_stage2_report_quality_lint_candidate_review.md): Stage2 report quality lint 후보 검토와 warning-only 도입 기준
  - [99_stage2_report_quality_lint_tuning_plan.md](./99_stage2_report_quality_lint_tuning_plan.md): Stage2 report quality lint safe-negation tuning 계획/완료 기록
- Web UI / report viewer
  - 현재 기준: Web UI read-only는 보안 결과 해석 read-only를 뜻하며, DB-backed MVP의 `analysis_jobs` 등록/조회 DB write/read는 허용한다.
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
  - [99_owasp_security_standard_mapping_investigation.md](./99_owasp_security_standard_mapping_investigation.md): OWASP Top 10:2025 / CWE / WSTG 매핑 가능성과 Apache logs-only 경계 조사
  - [99_owasp_security_standard_mapping_design.md](./99_owasp_security_standard_mapping_design.md): OWASP Top 10:2025 / CWE / WSTG deterministic enrichment 상세 설계
  - [100_security_standards_coverage_summary_design.md](./100_security_standards_coverage_summary_design.md): deduplicated finding 기준 OWASP/CWE/WSTG 관찰 분포 summary semantics, artifact contract, Stage2/Viewer 통합 설계
  - [99_sensitive_path_probe_context_category_검토.md](./99_sensitive_path_probe_context_category_검토.md): sensitive path probe context category 도입 검토
  - [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md): file disclosure verdict taxonomy 상태와 후속 검증 조건 검토
  - [99_pipeline_run_dir_output_layout_plan.md](./99_pipeline_run_dir_output_layout_plan.md): run dir 검토 문서
  - [99_proxy_error_check_scenario_extension_review.md](./99_proxy_error_check_scenario_extension_review.md): proxy/backend unavailable 신호를 attack scenario로 승격하지 않기 위한 availability extension 검토
- observability / external client run
  - [99_observability_run_summary_index.md](./99_observability_run_summary_index.md): run summary 상위 색인. run별 docs-side 요약은 [../reviews/99_observability_run_summaries.md](../reviews/99_observability_run_summaries.md)를 우선 본다.
  - [99_apache_app_observability_scenario_catalog.md](./99_apache_app_observability_scenario_catalog.md): S01~S15 logical scenario와 evidence boundary 요약
  - [99_apache_app_observability_matrix_template.md](./99_apache_app_observability_matrix_template.md): run별 observation matrix 구조와 해석 기준 요약
  - [../reviews/99_observability_topology_comparison_review.md](../reviews/99_observability_topology_comparison_review.md): PHP sample/OpenCart/Juice Shop topology 비교 review
  - [99_external_client_error_heavy_run_plan.md](./99_external_client_error_heavy_run_plan.md): external client 기반 error-heavy distribution 비교와 identity/header guardrail 계획
  - `lab/observability` 원본은 장기 이관 대상이지만 현재 observability scripts input으로 남아 있다.
- 운영 자동화 / Sliding Window
  - [99_analysis_job_modes_and_sliding_window_integration.md](./99_analysis_job_modes_and_sliding_window_integration.md): `full_report` direct pipeline과 후속 `windowed_triage` mode 경계
  - [99_sliding_window_adoption_review.md](./99_sliding_window_adoption_review.md): 팀원 작성 Sliding Window 문서 세트의 repo 수용 범위, CLI 호환성, dry-run 검증 순서 검토
  - [99_sliding_window_operator_queue_design.md](./99_sliding_window_operator_queue_design.md): rollup 결과를 사람이 검토하기 위한 operator queue 설계
  - [99_sliding_window_operator_queue_item_detail.md](./99_sliding_window_operator_queue_item_detail.md): operator queue item detail CLI/schema/표시 기준
  - [99_sliding_window_single_rollup_observation_brief.md](./99_sliding_window_single_rollup_observation_brief.md): 단일 rollup observation brief 후보와 non-conclusion 기준
  - `analysis_jobs` queue는 DB-backed 실행 queue이고, operator queue는 rollup 결과 검토 queue다. 두 queue를 같은 개념으로 보지 않는다.

## 읽는 순서

1. 현재 상위 구조는 [../00_current_architecture.md](../00_current_architecture.md)
2. Apache logs-only 경계는 [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
3. DB-backed MVP는 [99_db_backed_log_collection_and_analysis_job_design.md](./99_db_backed_log_collection_and_analysis_job_design.md), [99_db_backed_web_ui_api_safety_addendum.md](./99_db_backed_web_ui_api_safety_addendum.md)
4. runner UX bridge/historical review는 [99_run_analysis_pipeline_user_runner_ux_review.md](./99_run_analysis_pipeline_user_runner_ux_review.md)
5. observability는 [99_observability_run_summary_index.md](./99_observability_run_summary_index.md), scenario 요약은 [99_apache_app_observability_scenario_catalog.md](./99_apache_app_observability_scenario_catalog.md), matrix 기준은 [99_apache_app_observability_matrix_template.md](./99_apache_app_observability_matrix_template.md), run별 docs-side 요약은 [../reviews/99_observability_run_summaries.md](../reviews/99_observability_run_summaries.md), topology 비교는 [../reviews/99_observability_topology_comparison_review.md](../reviews/99_observability_topology_comparison_review.md)
6. candidate policy 현재 기준은 [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md), 분포 이력은 [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md)
7. module split 현재 상태는 [99_prepare_module_split_summary.md](./99_prepare_module_split_summary.md)
8. constants 이동 또는 ownership 판단이면 prepare constants ownership / mini-move 문서
9. SQLi/XSS/file disclosure 등 hint 계열 분리나 evidence boundary 판단이면 prepare hints split / evidence boundary 문서
10. operator queue와 장시간 분석 routing은 [99_analysis_job_modes_and_sliding_window_integration.md](./99_analysis_job_modes_and_sliding_window_integration.md), [99_sliding_window_operator_queue_design.md](./99_sliding_window_operator_queue_design.md), [99_sliding_window_operator_queue_item_detail.md](./99_sliding_window_operator_queue_item_detail.md), [99_sliding_window_single_rollup_observation_brief.md](./99_sliding_window_single_rollup_observation_brief.md)
11. Stage2 prompt 정리나 report quality lint 검토면 Stage2 prompt / report quality 문서
12. 로그 가시성, 해석 한계, 보류 기능 판단이면 설계 결정/해석 한계 문서
13. 관련 평가는 [../reviews/README.md](../reviews/README.md)
14. 후속 작업은 [../planning/README.md](../planning/README.md)

## 관리 원칙

- 구현 여부, 한계, 보류 결정, regression 설계는 `design/`에 둔다.
- 평가, 품질 검토, 완료 리뷰는 `reviews/`에 둔다.
- 후속 작업 큐와 TODO는 `planning/`에 둔다.
