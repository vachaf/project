# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-05-21
- 문서 역할: 앞으로 해야 할 일만 남기는 TODO
- 완료 이력: [99_비교실험_후속개선_history.md](./99_비교실험_후속개선_history.md)
- 관련 대시보드: [../진행상황.md](../진행상황.md)

## 원칙

- 이 문서는 남은 TODO만 유지한다.
- 완료 기록은 [99_비교실험_후속개선_history.md](./99_비교실험_후속개선_history.md), `docs/진행상황.md`, 개별 설계 문서, 작업일지로 이관한다.
- Apache logs-only evidence boundary를 유지한다.
- `status_code=200`, `text/html`, `response_body_bytes`, `handler`, `x_forwarded_for`만으로 공격 성공/유출/내부 결과를 단정하지 않는다.
- Web UI는 read-only이며 새 보안 판단/관계/incident를 만들지 않는다.

## 현재 기준 문서

- prepare split 기준: [../design/99_prepare_module_split_summary.md](../design/99_prepare_module_split_summary.md)
- candidate policy 기준: [../design/99_prepare_candidate_policy.md](../design/99_prepare_candidate_policy.md)
- candidate policy history: [../design/99_prepare_candidate_policy_distribution_history.md](../design/99_prepare_candidate_policy_distribution_history.md)
- observability run index: [../design/99_observability_run_summary_index.md](../design/99_observability_run_summary_index.md)

## P0. observability 후속 판단

- [ ] 외부 client 기반 error-heavy run 수행 여부 판단
  - 설계 문서: [../design/99_external_client_error_heavy_run_plan.md](../design/99_external_client_error_heavy_run_plan.md)
  - EH01~EH12 lab-only runner: `scripts/run_error_heavy_observability_scenarios.sh`
  - 목적은 distribution 표본 확장에 한정한다.
  - 현재 상태는 설계 문서와 runner 추가까지이며, 실제 전체 run 수행은 다음 단계다.
  - prepare/scoring/filtering 변경을 전제로 하지 않는다.
- [ ] `proxy_error_check`를 정식 scenario catalog extension으로 뺄지 검토
  - 검토 문서: [../design/99_proxy_error_check_scenario_extension_review.md](../design/99_proxy_error_check_scenario_extension_review.md)
  - 현재는 backend availability context 관찰용 별도 run으로 유지한다.
  - 정규 S01~S15 편입, catalog/runner/prepare 변경, label detector 확장은 모두 보류한다.
  - 공격/침해 시나리오처럼 서술하지 않는다.
- [ ] OpenCart v2 추가 진행 여부 검토
  - 현재 표본으로 충분한지, 추가 run이 필요한지만 판단한다.
- [ ] `mod_remoteip`/remoteIP 환경 구성 여부 검토
  - external client error-heavy run과 분리해서 별도 설계 후 진행한다.
  - 실제 공격자 신원 판정이 아니라 관찰 필드 차이 검토 목적에 한정한다.

## P1. candidate policy 관찰

- [ ] `obs_php_sample_v2_error_heavy_external_001` EH01~EH12 전체 external run을 수행하고 `explain_prepare_candidates.py` 결과를 baseline과 비교
- [ ] upload/sql-comment narrow guard가 실제 strong SQLi를 과소탐지하지 않는지 계속 관찰
- [ ] broad status/error-only demotion은 계속 보류 유지
- [ ] scanner/probe broad demotion은 계속 보류 유지
- [ ] proxy error context의 정식 prepare 반영 여부는 별도 검토 전까지 보류

## P2. Web UI read-only 관찰

- [ ] Interpretation Aid와 context badge가 과도하게 findings처럼 보이지 않는지 관찰
- [ ] Related Contexts / Supporting Events 표시가 새 관계 추론처럼 보이지 않는지 점검
- [ ] backend unavailable / proxy error badge는 scenario 정식화 여부가 정리된 뒤 다시 검토

## P3. wording / taxonomy guard

- [ ] actual LLM 출력에서 context-only 과승격이 반복되는지 관찰
- [ ] file disclosure 성공, admin 접근 성공, upload 저장 성공 같은 과해석이 재발하는지 관찰
- [ ] 필요 시 lint warning 분포만 확인하고, review-only lint라는 기본 성격은 유지

## P4. run_dir / archive / retention

- [ ] `--run-id` 필요성 관찰
- [ ] legacy/lab archive opt-in scan 정책 후속 검토
- [ ] raw observability log의 보관/커밋 정책을 계속 보수적으로 유지할지 점검
- [ ] output cleanup의 실제 삭제 기능은 별도 승인 전까지 계속 보류

## P5. 새 coverage 후보

- [ ] API key / secret token probe fixture plan 작성 여부 판단
- [ ] Webshell command query fixture plan 작성 여부 판단
- [ ] request smuggling / header anomaly 로그 가시성 검토
- [ ] deserialization / object injection, LDAP / NoSQL injection-like payload는 계속 보류할지 재확인
