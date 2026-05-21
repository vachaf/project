# 99_document_cleanup_plan

- 기준 시점: 2026-05-21
- 목적: `docs/design/` 과 주변 요약/기록 문서의 역할을 재정렬하고, 중복되거나 완료된 임시 문서를 통합/archive/delete하기 전에 근거를 먼저 고정한다.
- 강한 제약:
  - Apache logs-only 판단 원칙은 약화하지 않는다.
  - `status_code=200`, `response_body_bytes`, `resp_content_type`, route 이름, product/category 이름, 특정 UA/IP만으로 공격 성공/계정 탈취/서버 침해/업로드 저장/파일 존재/정적 리소스 노출/admin 접근 성공을 단정하지 않는다.
  - Web UI는 read-only이며 새 보안 판단, 새 관계, 새 severity/category/verdict/incident를 만들지 않는다.

## 분류 기준

- `active`: 현재 기준 문서로 계속 읽히는 문서
- `historical`: 과거 판단/실험/완료 기록으로 보존 가치가 있는 문서
- `duplicate`: 다른 문서에 거의 흡수 가능한 중복 문서
- `completed-plan`: 완료된 작업 계획/체크리스트
- `obsolete`: 현재 기준과 맞지 않거나 superseded 된 문서
- `run-artifact`: 특정 관찰 run의 원본 summary
- `index-needed`: 상위 색인/종합 문서가 필요한 영역

## 이번 정리에서 새로 둘 기준 문서

| 문서 | 역할 |
|---|---|
| `docs/design/99_prepare_module_split_summary.md` | prepare module split 완료 범위와 남은 보류 항목의 기준 요약 |
| `docs/design/99_prepare_candidate_policy.md` | prepare candidate policy의 현재 기준과 실제 반영 범위 정리 |
| `docs/design/99_prepare_candidate_policy_distribution_history.md` | candidate policy 관찰/분포/history 분리 문서 |
| `docs/design/99_observability_run_summary_index.md` | observability run summary 상위 색인 |
| `docs/planning/99_비교실험_후속개선_history.md` | TODO에서 걷어낸 완료 기록 요약 |

## `docs/design/` 인벤토리 및 결정

| 문서 경로 | 현재 역할 | 유지/통합/archive/delete 결정 | 통합 대상 문서 | 이유 |
|---|---|---|---|---|
| `docs/design/99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md` | `active` 보류 결정 메모 | 유지 | - | 현재도 기준 guardrail 문서다. |
| `docs/design/99_POST_body_visibility_한계와_해석_기준.md` | `active` 해석 한계 기준 | 유지 | - | Apache logs-only 경계를 직접 고정한다. |
| `docs/design/99_apache_app_observability_comparison_plan.md` | `active` observability 설계 | 유지 | - | 앱 topology 비교 기준으로 계속 필요하다. |
| `docs/design/99_apache_log_collection_expansion_plan.md` | `active` 수집 확장 설계 | 유지 | - | current scope 문서다. |
| `docs/design/99_apache_log_collection_expansion_scope_correction.md` | `historical` 범위 정정 | 유지 | - | 상위 문서의 의미를 바로잡는 정정 기록이다. |
| `docs/design/99_apache_security_io_v2_candidate.md` | `active` v2 후보 계약 | 유지 | - | v1 유지, v2 후보 검토 문서로 필요하다. |
| `docs/design/99_design_docs_cleanup_candidate_review.md` | `historical` 초기 cleanup 검토 메모 | archive | `docs/design/99_document_cleanup_plan.md` | 이번 정리 계획서가 기준 문서가 되고, 기존 문서는 과거 검토 기록으로 충분하다. |
| `docs/design/99_file_disclosure_verdict_taxonomy_검토.md` | `active` taxonomy 검토 | 유지 | - | file disclosure wording/guardrail 근거다. |
| `docs/design/99_output_cleanup_script_설계.md` | `active` cleanup 설계 | 유지 | - | output retention 정책과 쌍으로 계속 필요하다. |
| `docs/design/99_pipeline_run_dir_output_layout_plan.md` | `active` run_dir 설계 역사+기준 | 유지 | - | run_dir 판단 근거가 남아 있다. |
| `docs/design/99_pipeline_run_dir_phase1b_phase2_candidate_review.md` | `historical` run_dir 후보 비교 | 유지 | - | 구현 경과 메모 성격이지만 후속 판단 근거가 남아 있다. |
| `docs/design/99_prepare_apache_observability_context_feature_review.md` | `active` prepare observability context review | 유지 | - | topology context 도입 근거 문서다. |
| `docs/design/99_prepare_api_key_secret_probe_coverage_plan.md` | `active` coverage 후보 | 유지 | - | 완료 여부가 불명확해 유지한다. |
| `docs/design/99_prepare_attack_hints_shared_policy_candidate_review.md` | `historical` 후보 비교 초안 | 유지 | `docs/design/99_prepare_module_split_summary.md`에서 링크 | 중복 요소가 있으나 shared policy 경계 검토의 초기 판단 기록으로 보존 가치가 있다. |
| `docs/design/99_prepare_candidate_policy_distribution_review.md` | `historical` distribution review | archive | `docs/design/99_prepare_candidate_policy_distribution_history.md` | 새 history 문서가 기준이 되고, 원문은 관찰 기록으로 archive가 적절하다. |
| `docs/design/99_prepare_constants_mini_move_summary.md` | `active` 완료 요약 | 유지 | - | 현재 ownership 판단의 기준 축이다. |
| `docs/design/99_prepare_constants_ownership_map.md` | `active` ownership map | 유지 | - | 남은 split 판단의 기준 문서다. |
| `docs/design/99_prepare_context_summary_contract.md` | `active` contract | 유지 | - | 분리 완료 후에도 계약 문서로 의미가 있다. |
| `docs/design/99_prepare_context_summary_split_candidate.md` | `historical` 분리 후보 검토 | 유지 | - | contract와 round2 사이 판단 근거가 남아 있다. |
| `docs/design/99_prepare_deferred_split_items.md` | `active` 보류 항목 기준 | 유지 | - | 아직 남은 TODO와 직결된다. |
| `docs/design/99_prepare_deferred_split_reentry_review.md` | `active` 재진입 기준 | 유지 | - | 보류 원칙을 현재도 고정한다. |
| `docs/design/99_prepare_graphql_introspection_coverage_plan.md` | `active` coverage 후보 | 유지 | - | 완료 여부가 불명확하다. |
| `docs/design/99_prepare_graphql_introspection_fixture_plan.md` | `active` fixture 후보 | 유지 | - | 완료 여부가 불명확하다. |
| `docs/design/99_prepare_hints_split_summary.md` | `active` hints split 기준 요약 | 유지 | - | split 결과 기준 문서다. |
| `docs/design/99_prepare_ip_behavior_aggregates_split_plan.md` | `completed-plan` 세부 split 완료 기록 | delete | `docs/design/99_prepare_module_split_summary.md` | 세부 완료 범위가 신규 종합 문서와 round2 summary에 흡수 가능하고, 독립 유지 가치가 낮다. |
| `docs/design/99_prepare_llm_input_inventory.md` | `active` inventory | 유지 | - | 다음 분리 판단의 출발점 문서다. |
| `docs/design/99_prepare_mixed_baseline_scanner_split_plan.md` | `completed-plan` 세부 split 완료 기록 | delete | `docs/design/99_prepare_module_split_summary.md` | 세부 완료 기록만 남아 있어 종합 문서 흡수 후 삭제 가능하다. |
| `docs/design/99_prepare_module_split_plan.md` | `historical` umbrella plan | 유지 | `docs/design/99_prepare_module_split_summary.md`에서 링크 | 초기 계획/원칙 문서로 역사적 가치가 있다. |
| `docs/design/99_prepare_module_split_round1_summary.md` | `historical` round1 완료 요약 | 유지 | `docs/design/99_prepare_module_split_summary.md`에서 링크 | 새 종합 문서가 active 기준이 되더라도 round1 세부 기록은 보존 가치가 있다. |
| `docs/design/99_prepare_module_split_round2_summary.md` | `historical` round2 완료 요약 | 유지 | `docs/design/99_prepare_module_split_summary.md`에서 링크 | round2 세부 기록과 회귀 결과는 남겨둔다. |
| `docs/design/99_prepare_new_attack_coverage_candidate_review.md` | `active` coverage roadmap | 유지 | - | coverage 후보 비교의 기준점이다. |
| `docs/design/99_prepare_new_attack_coverage_round2_candidate_review.md` | `active` coverage round2 후보 | 유지 | - | 후속 우선순위 근거가 남아 있다. |
| `docs/design/99_prepare_new_attack_coverage_round_summary.md` | `historical` coverage 완료 요약 | 유지 | - | round summary 성격이라 보존한다. |
| `docs/design/99_prepare_open_redirect_coverage_plan.md` | `active` coverage 후보 | 유지 | - | 완료 여부가 불명확하다. |
| `docs/design/99_prepare_open_redirect_fixture_plan.md` | `active` fixture 후보 | 유지 | - | 완료 여부가 불명확하다. |
| `docs/design/99_prepare_p2_attack_coverage_candidate_review.md` | `active` P2 coverage review | 유지 | - | coverage 분류 기준으로 필요하다. |
| `docs/design/99_prepare_php_sample_candidate_policy_review.md` | `historical` PHP sample policy review | archive | `docs/design/99_prepare_candidate_policy.md` | 현재 기준 정책과 관찰 history를 분리하기 위해 archive로 내린다. |
| `docs/design/99_prepare_probing_sequence_split_plan.md` | `completed-plan` 세부 split 완료 기록 | delete | `docs/design/99_prepare_module_split_summary.md` | 종합 문서에 흡수 가능하고 개별 유지 가치가 낮다. |
| `docs/design/99_prepare_regression_fixture_설계.md` | `active` regression 설계 | 유지 | - | 현재도 기준 문서다. |
| `docs/design/99_prepare_scanner_probe_context_candidate_demotion_review.md` | `historical` scanner/probe demotion review | archive | `docs/design/99_prepare_candidate_policy_distribution_history.md` | 실제 로직 반영 문서가 아니라 review artifact다. |
| `docs/design/99_prepare_search_false_positive_policy_reentry_review.md` | `active` re-entry review | 유지 | - | deferred split 판단에 계속 필요하다. |
| `docs/design/99_prepare_sensitive_path_probe_split_plan.md` | `completed-plan` 세부 split 완료 기록 | delete | `docs/design/99_prepare_module_split_summary.md` | 종합 문서로 완전 흡수 가능하다. |
| `docs/design/99_prepare_shared_attack_policy_boundary_review.md` | `active` shared policy boundary | 유지 | - | logs-only guardrail과 linked 된다. |
| `docs/design/99_prepare_shared_attack_policy_reentry_review.md` | `active` re-entry review | 유지 | - | 현재도 보류 기준 문서다. |
| `docs/design/99_prepare_ssrf_log4shell_coverage_plan.md` | `active` coverage plan | 유지 | - | round summary와 연결되는 기준 문서다. |
| `docs/design/99_prepare_ssrf_log4shell_fixture_plan.md` | `historical` fixture 반영 기록 포함 | 유지 | - | 완료 일부가 기록되어 있어 archive보다 유지가 안전하다. |
| `docs/design/99_prepare_ssti_coverage_plan.md` | `historical/active` 1차 반영 완료 후 후속 후보 | 유지 | - | 일부 완료 후속 판단 문서다. |
| `docs/design/99_prepare_ssti_fixture_plan.md` | `historical/active` 1차 반영 완료 후 후속 후보 | 유지 | - | 후속 보강 판단 근거가 남아 있다. |
| `docs/design/99_prepare_status_error_only_candidate_demotion_review.md` | `historical` status/error-only review | archive | `docs/design/99_prepare_candidate_policy_distribution_history.md` | 실제 prepare 반영이 아니라 review-only artifact다. |
| `docs/design/99_prepare_upload_multipart_sql_comment_false_positive_review.md` | `historical` narrow guard review | archive | `docs/design/99_prepare_candidate_policy.md` | 실제 반영 범위는 기준 정책 문서에 흡수하고, 세부 검토는 archive로 유지한다. |
| `docs/design/99_prepare_webshell_command_query_coverage_plan.md` | `active` coverage 후보 | 유지 | - | fixture 분기 전 기준 문서다. |
| `docs/design/99_prepare_webshell_probe_coverage_plan.md` | `active` coverage 후보 | 유지 | - | 아직 독립 가치가 있다. |
| `docs/design/99_prepare_webshell_probe_fixture_plan.md` | `active` fixture 후보 | 유지 | - | 완료 여부가 불명확하다. |
| `docs/design/99_prepare_xxe_coverage_plan.md` | `historical/active` 1차 반영 완료 후 후속 후보 | 유지 | - | 후속 보강 판단 문서다. |
| `docs/design/99_prepare_xxe_fixture_plan.md` | `historical/active` 1차 반영 완료 후 후속 후보 | 유지 | - | 후속 보강 판단 문서다. |
| `docs/design/99_run_analysis_pipeline_user_runner_ux_review.md` | `active` runner UX review | 유지 | - | run_dir/Web UI 경계에 계속 연결된다. |
| `docs/design/99_sensitive_path_probe_context_category_검토.md` | `active` category review | 유지 | - | path probe context 의미를 직접 고정한다. |
| `docs/design/99_stage2_prompt_compaction_plan.md` | `historical/active` 완료 기록 포함 | 유지 | - | Stage2 wording guardrail 근거다. |
| `docs/design/99_stage2_report_quality_lint_candidate_review.md` | `historical` lint 도입 검토 | 유지 | - | tuning 문서와 함께 품질 경로를 보여준다. |
| `docs/design/99_stage2_report_quality_lint_tuning_plan.md` | `historical/active` tuning 기록 | 유지 | - | warning-only 정착 근거가 남아 있다. |
| `docs/design/99_stage_dryrun_regression_설계.md` | `active` regression 설계 | 유지 | - | 현재도 기준 문서다. |
| `docs/design/99_web_ui_loader_phase2a_input_model_review.md` | `historical/active` 구현 전 조사 | 유지 | - | run_dir loader 설계 근거가 남아 있다. |
| `docs/design/99_web_ui_loader_phase2b_fixture_plan.md` | `historical/active` fixture 설계 | 유지 | - | 구현 전 테스트 근거다. |
| `docs/design/99_web_ui_loader_phase2c_test_plan.md` | `historical/active` test plan + 결과 업데이트 | 유지 | - | 결과 업데이트가 있어 유지가 안전하다. |
| `docs/design/99_web_ui_report_viewer_execution_scope_review.md` | `active` read-only scope 기준 | 유지 | - | Web UI 비권한 원칙을 직접 고정한다. |
| `docs/design/99_web_ui_report_viewer_phase1a_plan.md` | `historical` 구현 phase plan | 유지 | - | Phase 경계 기록이다. |
| `docs/design/99_web_ui_report_viewer_phase1a_template_contract.md` | `active` template contract | 유지 | - | contract 성격이 남아 있다. |
| `docs/design/99_web_ui_report_viewer_phase1b_plan.md` | `historical` compare view plan | 유지 | - | Phase 경계 기록이다. |
| `docs/design/99_web_ui_report_viewer_phase2_candidate_review.md` | `historical/active` 후보 비교 | 유지 | - | execution console 금지 근거가 남아 있다. |
| `docs/design/99_web_ui_report_viewer_phase2a_filter_plan.md` | `historical/active` filter plan | 유지 | - | read-only 확장 기준이 남아 있다. |
| `docs/design/99_web_ui_report_viewer_plan.md` | `active` 상위 기준 문서 | 유지 | - | Web UI 기준 문서다. |
| `docs/design/99_web_ui_report_viewer_ui_polish_plan.md` | `historical/active` polish 후보 | 유지 | - | 후속 UI polish 판단에 필요하다. |
| `docs/design/99_web_ui_run_dir_loader_phase2_plan.md` | `active` run_dir loader 기준 | 유지 | - | 현재 backend scan 기준과 연결된다. |
| `docs/design/99_web_ui_viewer_payload_display_plan.md` | `active` payload display 설계 | 유지 | - | read-only payload 표시 기준이다. |
| `docs/design/README.md` | `index-needed` design 색인 | 유지 후 갱신 | `docs/design/99_prepare_module_split_summary.md`, `docs/design/99_prepare_candidate_policy.md` | active 기준 문서를 앞으로 세우고 archive/delete 반영이 필요하다. |

## `docs/planning/`, `docs/operations/`, `docs/진행상황.md`, `작업일지/` 인벤토리 및 결정

| 문서 경로 | 현재 역할 | 유지/통합/archive/delete 결정 | 통합 대상 문서 | 이유 |
|---|---|---|---|---|
| `docs/planning/99_비교실험_후속개선_TODO.md` | `active` TODO | 유지 후 축약 | `docs/planning/99_비교실험_후속개선_history.md` | 완료 기록을 history로 분리하고 남은 TODO만 남긴다. |
| `docs/planning/README.md` | `index-needed` planning 색인 | 유지 후 갱신 | `docs/planning/99_비교실험_후속개선_history.md` | TODO/history 2단 구조를 반영해야 한다. |
| `docs/operations/00_전체_흐름_요약_가이드.md` | `active` 운영 요약 | 유지 | - | 기준 문서다. |
| `docs/operations/01_운영_기준_실행_가이드.md` | `active` single source of truth | 유지 | - | 절대 유지 대상이다. |
| `docs/operations/01_프로젝트_방향과_실험대상.md` | `active` 상위 방향 문서 | 유지 | - | 기준 문서다. |
| `docs/operations/02_Juice_shop_환경_구축_및_설치.md` | `active` 환경 구축 | 유지 | - | 운영 문서다. |
| `docs/operations/02_LLM_환경_구축_및_설치.md` | `active` 환경 구축 | 유지 | - | 운영 문서다. |
| `docs/operations/02_MariaDB_환경_구축_및_설치.md` | `active` 환경 구축 | 유지 | - | 운영 문서다. |
| `docs/operations/02_OpenCart_환경_구축_및_설치.md` | `active` 환경 구축 | 유지 | - | 운영 문서다. |
| `docs/operations/03_로그_표준과_DB_구조.md` | `active` 로그/DB 기준 | 유지 | - | 기준 문서다. |
| `docs/operations/04_로그_적재_및_운영.md` | `active` 운영 정책 | 유지 | - | 기준 문서다. |
| `docs/operations/05_Export_LLM_분석_전략.md` | `active` 분석 기준 | 유지 | - | logs-only 해석 기준과 직접 연결된다. |
| `docs/operations/06_통합_스크립트_설명_정리본.md` | `active` 스크립트 참조 | 유지 | - | 운영 참조 문서다. |
| `docs/operations/99_apache_custom_log_format_contract.md` | `active` logformat contract | 유지 | - | 절대 유지 대상이다. |
| `docs/operations/99_output_retention_policy.md` | `active` retention 기준 | 유지 | - | cleanup 설계와 직접 연결된다. |
| `docs/operations/README.md` | `index-needed` operations 색인 | 유지 | - | 현재 구조로 충분하다. |
| `docs/진행상황.md` | `active` 대시보드 | 유지 후 갱신 | 새 기준 문서 링크 | 새로운 summary/history 링크로 정리할 필요가 있다. |
| `작업일지/README.md` | `index-needed` 작업일지 형식 | 유지 | - | 템플릿 성격이다. |
| `작업일지/0430.md` | `historical` 일지 | 유지 | - | 일지는 archive 대상이 아니라 원본 보존이 적절하다. |
| `작업일지/0502.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0503.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0504.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0505.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0506.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0507.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0508.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0509.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0510.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0514.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0515.md` | `historical` 일지 | 유지 | - | 같은 이유로 유지한다. |
| `작업일지/0521.md` | `active/historical` 최신 일지 | 유지 | - | 최신 기록으로 유지한다. |

## `lab/observability/runs/*/summary.md` 인벤토리 및 결정

| 문서 경로 | 현재 역할 | 유지/통합/archive/delete 결정 | 통합 대상 문서 | 이유 |
|---|---|---|---|---|
| `lab/observability/runs/obs_php_sample_002/summary.md` | `run-artifact` v1 direct PHP baseline | 유지 | `docs/design/99_observability_run_summary_index.md` | 원본 run summary는 보존한다. |
| `lab/observability/runs/obs_php_sample_v2_001/summary.md` | `run-artifact` v2 direct PHP baseline | 유지 | `docs/design/99_observability_run_summary_index.md` | 원본 run summary는 보존한다. |
| `lab/observability/runs/obs_php_sample_v2_error_heavy_001/summary.md` | `run-artifact` error-heavy skeleton | 유지 | `docs/design/99_observability_run_summary_index.md` | 미완성 run summary라도 artifact 원본으로 유지한다. |
| `lab/observability/runs/obs_opencart_002/summary.md` | `run-artifact` v1 OpenCart | 유지 | `docs/design/99_observability_run_summary_index.md` | 원본 run summary는 보존한다. |
| `lab/observability/runs/obs_opencart_v2_001/summary.md` | `run-artifact` v2 OpenCart | 유지 | `docs/design/99_observability_run_summary_index.md` | 원본 run summary는 보존한다. |
| `lab/observability/runs/obs_juiceshop_proxy_v2_001/summary.md` | `run-artifact` v2 Juice Shop normal | 유지 | `docs/design/99_observability_run_summary_index.md` | 원본 run summary는 보존한다. |
| `lab/observability/runs/obs_juiceshop_proxy_v2_error_check_001/summary.md` | `run-artifact` v2 proxy error check | 유지 | `docs/design/99_observability_run_summary_index.md` | 원본 run summary는 보존한다. |
| `docs/design/99_observability_run_summary_index.md` | `index-needed` 상위 run index | 생성 | - | 분산된 summary를 한눈에 보는 색인이 필요하다. |

## 실행 순서

1. 기준 문서 생성: module split summary, candidate policy, candidate policy distribution history, observability runs index, planning history.
2. `docs/design/README.md`, `docs/README.md`, `docs/planning/README.md`, `docs/진행상황.md`, `docs/planning/99_비교실험_후속개선_TODO.md`를 새 기준 문서 기준으로 갱신.
3. 완전 흡수 가능한 completed-plan 4건은 delete.
4. 기준 문서에서 밀려난 candidate-policy review / cleanup candidate review는 `docs/archive/design/`으로 이동.
5. `rg`로 이동/삭제 경로 참조를 다시 점검하고 archive/new summary 링크로 치환.

## 삭제/이동 예정 문서의 근거 메모

- delete 예정 4건은 모두 “세부 split 완료 기록” 문서이며, 현재 정책/계약/남은 TODO를 새 종합 문서와 round summary가 충분히 설명할 수 있다.
- archive 예정 candidate policy review 묶음은 “실제 로직에 반영된 현재 기준” 문서가 아니라 특정 시점의 review/distribution note이므로, 기준 문서에서 분리해 historical로 남기는 편이 혼동을 줄인다.
- run summary 원본은 삭제하지 않는다. 관찰 세부와 당시 wording을 회귀 근거로 다시 봐야 할 수 있기 때문이다.
