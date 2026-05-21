# 99_비교실험_후속개선_history

- 기준 시점: 2026-05-21
- 문서 역할: `99_비교실험_후속개선_TODO.md`에서 걷어낸 완료 기록의 축약 history
- 현재 TODO: [99_비교실험_후속개선_TODO.md](./99_비교실험_후속개선_TODO.md)

## 1. 목적

이 문서는 “이미 끝난 항목의 짧은 요약 + 기준 문서 링크”만 남긴다.

- 상세 근거는 `docs/진행상황.md`, 개별 설계 문서, 작업일지, run summary 원문에 둔다.
- TODO 문서는 앞으로 해야 할 일만 유지한다.

## 2. 완료 요약

| 완료 축 | 요약 | 관련 문서 |
|---|---|---|
| prepare module split | round1/round2 mechanical split 완료, 현재는 stable 유지 단계 | [../design/99_prepare_module_split_summary.md](../design/99_prepare_module_split_summary.md) |
| constants mini-move / hints split | safe constants mini-move, hints split, deferred split 기준 정리 완료 | [../design/99_prepare_constants_mini_move_summary.md](../design/99_prepare_constants_mini_move_summary.md), [../design/99_prepare_hints_split_summary.md](../design/99_prepare_hints_split_summary.md), [../design/99_prepare_deferred_split_reentry_review.md](../design/99_prepare_deferred_split_reentry_review.md) |
| Stage2 wording/lint | prompt compaction, report quality lint 도입/튜닝 완료 | [../design/99_stage2_prompt_compaction_plan.md](../design/99_stage2_prompt_compaction_plan.md), [../design/99_stage2_report_quality_lint_tuning_plan.md](../design/99_stage2_report_quality_lint_tuning_plan.md) |
| Web UI read-only viewer | report viewer, payload display, run_dir loader backend 전환 완료 | [../design/99_web_ui_report_viewer_plan.md](../design/99_web_ui_report_viewer_plan.md), [../design/99_web_ui_report_viewer_execution_scope_review.md](../design/99_web_ui_report_viewer_execution_scope_review.md), [../design/99_web_ui_run_dir_loader_phase2_plan.md](../design/99_web_ui_run_dir_loader_phase2_plan.md) |
| observability baseline | PHP sample / OpenCart / Juice Shop topology 비교와 v1/v2 logformat 관찰 완료 | [../design/99_observability_run_summary_index.md](../design/99_observability_run_summary_index.md), [../design/99_apache_app_observability_comparison_plan.md](../design/99_apache_app_observability_comparison_plan.md), [../operations/99_apache_custom_log_format_contract.md](../operations/99_apache_custom_log_format_contract.md) |
| candidate policy review | upload/sql-comment narrow guard 반영, distribution/history 분리 문서화 완료 | [../design/99_prepare_candidate_policy.md](../design/99_prepare_candidate_policy.md), [../design/99_prepare_candidate_policy_distribution_history.md](../design/99_prepare_candidate_policy_distribution_history.md) |
| topology context / viewer interpretation aid | prepare observability context와 Web UI display-only aid 반영 완료 | [../design/99_prepare_apache_observability_context_feature_review.md](../design/99_prepare_apache_observability_context_feature_review.md), [../진행상황.md](../진행상황.md) |

## 3. 유지하는 guardrail

- Apache logs-only evidence boundary를 유지한다.
- `status_code=200`, `response_body_bytes`, `resp_content_type`, `handler`, `x_forwarded_for`만으로 공격 성공/침해/유출/업로드 저장/admin 접근 성공을 단정하지 않는다.
- Web UI는 read-only이며 새 보안 판단/관계를 만들지 않는다.
