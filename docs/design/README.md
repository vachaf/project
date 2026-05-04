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
  - [99_prepare_method_summary_split_plan.md](./99_prepare_method_summary_split_plan.md): method behavior summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_protocol_anomaly_split_plan.md](./99_prepare_protocol_anomaly_split_plan.md): protocol anomaly summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_auth_behavior_split_plan.md](./99_prepare_auth_behavior_split_plan.md): auth behavior summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_static_baseline_split_plan.md](./99_prepare_static_baseline_split_plan.md): static baseline summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_crawler_baseline_split_plan.md](./99_prepare_crawler_baseline_split_plan.md): crawler baseline summary 분리 전 함수·출력·fixture 검토
  - [99_prepare_regression_fixture_설계.md](./99_prepare_regression_fixture_설계.md): prepare regression fixture 설계
  - [99_stage_dryrun_regression_설계.md](./99_stage_dryrun_regression_설계.md): Stage dry-run regression 설계
  - [99_output_cleanup_script_설계.md](./99_output_cleanup_script_설계.md): output cleanup script 안전 설계 기준
- 설계 결정/해석 한계
  - [99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md](./99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md): HTML fallback fingerprint 기능 보류 결정
  - [99_POST_body_visibility_한계와_해석_기준.md](./99_POST_body_visibility_한계와_해석_기준.md): POST body visibility 한계와 해석 기준
  - [99_sensitive_path_probe_context_category_검토.md](./99_sensitive_path_probe_context_category_검토.md): sensitive path probe context category 도입 검토
  - [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md): file disclosure verdict taxonomy 상태와 후속 검증 조건 검토

## 읽는 순서

1. regression 또는 module split 작업이면 설계/회귀 검증 문서
2. 로그 가시성, 해석 한계, 보류 기능 판단이면 설계 결정/해석 한계 문서
3. 관련 평가는 [../reviews/README.md](../reviews/README.md)
4. 후속 작업은 [../planning/README.md](../planning/README.md)

## 관리 원칙

- 구현 여부, 한계, 보류 결정, regression 설계는 `design/`에 둔다.
- 평가, 품질 검토, 완료 리뷰는 `reviews/`에 둔다.
- 후속 작업 큐와 TODO는 `planning/`에 둔다.
