# reviews

## 목적

- `reviews/`는 완료·평가성 문서와 품질 검토 문서를 둔다.
- 실제 LLM 샘플 검증 계획과 Stage2 표현 품질 점검도 이 폴더에서 관리한다.
- review 문서는 현재 기준 설계 문서가 아니라 품질 검토, 완료 검토, 사후 판단 근거로 읽는다.
- 현재 기준은 필요할 때 [../00_current_architecture.md](../00_current_architecture.md), [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md), [../design/README.md](../design/README.md)에서 확인한다.

## 문서 목록

- [99_A-H세트_중간정리.md](./99_A-H세트_중간정리.md): A~H 실험 세트 중간 정리
- [99_A-F세트_대표샘플_6선.md](./99_A-F세트_대표샘플_6선.md): A~F 대표 샘플 6선과 분석 품질 대조 기준
- [99_llm_sample_review_plan.md](./99_llm_sample_review_plan.md): 실제 LLM 샘플 검증 계획
- [99_llm_sample_validation_review.md](./99_llm_sample_validation_review.md): lab LLM sample validation 원문을 docs에서 읽을 수 있게 요약한 수동 품질 검토
- [99_observability_topology_comparison_review.md](./99_observability_topology_comparison_review.md): lab observability comparison의 PHP sample/OpenCart/Juice Shop topology 비교 요약
- [99_observability_run_summaries.md](./99_observability_run_summaries.md): lab observability run summary 8개를 docs에서 읽을 수 있게 모은 관찰 요약
- [99_post_refactor_dry_run_spot_check.md](./99_post_refactor_dry_run_spot_check.md): post-refactor dry-run spot check
- [99_post_refactor_LLM_output_spot_check.md](./99_post_refactor_LLM_output_spot_check.md): post-refactor actual LLM output spot check
- [99_stage2_wording_quality_review.md](./99_stage2_wording_quality_review.md): Stage2 wording 품질 검토

## 읽는 순서

1. 전체 실험 상태는 [99_A-H세트_중간정리.md](./99_A-H세트_중간정리.md)
2. 대표 케이스 대조는 [99_A-F세트_대표샘플_6선.md](./99_A-F세트_대표샘플_6선.md)
3. 실제 LLM 샘플 검증은 docs-side summary인 [99_llm_sample_validation_review.md](./99_llm_sample_validation_review.md)를 우선 보고, 검증 계획은 [99_llm_sample_review_plan.md](./99_llm_sample_review_plan.md)를 본다.
4. Apache observability topology 비교는 [99_observability_topology_comparison_review.md](./99_observability_topology_comparison_review.md)
5. observability run별 결론은 [99_observability_run_summaries.md](./99_observability_run_summaries.md)
6. post-refactor 회귀 확인은 [99_post_refactor_dry_run_spot_check.md](./99_post_refactor_dry_run_spot_check.md), [99_post_refactor_LLM_output_spot_check.md](./99_post_refactor_LLM_output_spot_check.md)
7. Stage2 표현 품질은 [99_stage2_wording_quality_review.md](./99_stage2_wording_quality_review.md)
8. 후속 작업은 [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

Observability review 문서는 run별 결론과 topology 비교를 다루며, scenario catalog와 matrix template의 docs-side 설계 요약은 [../design/99_observability_run_summary_index.md](../design/99_observability_run_summary_index.md)에서 연결한다.

## 관리 원칙

- 평가, 검토, 품질 리뷰 문서는 `reviews/`에 둔다.
- 구현 설계와 보류 결정은 `design/`에 둔다.
- 해야 할 일 목록과 우선순위는 `planning/`에 둔다.
- 오래된 review도 이번 단계에서는 삭제/archive하지 않고 historical 참고 문서로 둔다.
