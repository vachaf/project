# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-05-24
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
- Sliding Window adoption review: [../design/99_sliding_window_adoption_review.md](../design/99_sliding_window_adoption_review.md)
- Rollup input review: [../design/99_sliding_window_rollup_input_review.md](../design/99_sliding_window_rollup_input_review.md)
- Rollup input format: [../design/99_sliding_window_rollup_input_format.md](../design/99_sliding_window_rollup_input_format.md)
- Rollup pipeline integration: [../design/99_sliding_window_rollup_pipeline_integration.md](../design/99_sliding_window_rollup_pipeline_integration.md)
- Rollup quick reference: [../design/99_sliding_window_rollup_quick_reference.md](../design/99_sliding_window_rollup_quick_reference.md)
- Rollup implementation guide: [../design/99_sliding_window_rollup_implementation_guide.md](../design/99_sliding_window_rollup_implementation_guide.md)
- Operator Queue design: [../design/99_sliding_window_operator_queue_design.md](../design/99_sliding_window_operator_queue_design.md)

## P0. Sliding Window / Rollup / Operator Queue 후속 작업

- [x] Sliding Window 문서 세트 repo 수용 범위 검토
- [x] Sliding Window 예시 명령과 현재 CLI 옵션 호환성 확인
- [x] Sliding Window dry-run 검증 범위 확정
- [x] Sliding Window planner mode 구현 및 검증
  - `src/sliding_window_scheduler.py` planner mode 추가 완료.
  - 검증: `tests/test_sliding_window_scheduler.py` → 5 passed.
  - 검증: sliding window + candidate policy quick regression set → 29 passed.
- [x] Sliding Window Level 1 export mode 구현 및 검증
  - `src/sliding_window_scheduler.py --mode export` 추가 완료.
  - `data/windowed/<date>/<window_id>/export.json`만 생성한다.
  - prepare/stage1/stage2는 제외한다.
  - `runs/`는 생성하지 않는다.
  - 검증: scheduler test → 8 passed.
  - 검증: sliding window + candidate policy quick regression set → 32 passed.
- [x] prepare flat output names 추가 및 검증
  - `src/prepare_llm_input.py --flat-output-names` 추가 완료.
  - 기본 `<base>_llm_input.json` naming은 유지한다.
  - `--flat-output-names` 사용 시 `llm_input.json`, `analysis_candidates.json`, `noise_summary.json`을 out-dir에 직접 생성한다.
  - `--flat-output-names`와 `--base-name`은 argparse 상호배타로 막는다.
  - 검증: `tests/test_prepare_llm_input_output_names.py` → 4 passed.
  - 검증: prepare regression → `pass=25 warn=0 fail=0`.
  - 검증: stage dry-run regression → `pass=19 warn=0 fail=0`.
- [x] Sliding Window Level 2 prepare mode 구현 및 검증
  - `src/sliding_window_scheduler.py --mode prepare` 추가 완료.
  - 일부 window의 `export.json`을 입력으로 `prepare_llm_input.py --flat-output-names`만 실행한다.
  - `data/windowed/<date>/<window_id>/`에 `llm_input.json`, `analysis_candidates.json`, `noise_summary.json`을 직접 생성한다.
  - `prepared/` 하위 디렉터리 생성 후 copy/symlink하는 구조는 기본안에서 제외했다.
  - stage1/stage2/viewer_payload는 실행하지 않는다.
  - `runs/`는 생성하지 않는다.
  - 검증: scheduler test → 13 passed.
  - 검증: sliding window + prepare output + candidate policy quick bundle → 41 passed.
- [x] `window_summary.json` v1 생성 및 검증
  - `src/sliding_window_summary.py` 추가 완료.
  - `src/sliding_window_scheduler.py --mode prepare`에서 prepare 성공 후 `window_summary.json`을 자동 생성한다.
  - prepare output 3종이 이미 있어 `skipped_existing`인 경우에도 `window_summary.json`이 없으면 생성한다.
  - `window_summary.json`이 이미 있고 `--overwrite`가 없으면 유지한다.
  - `artifact_status.window_summary.exists=true`로 저장되는지 확인했다.
  - `candidate_index`에는 `request_id`, `src_ip`, `method`, `uri`, `status_code`, `score`, `verdict_hint`, `reason_hint_prefixes`만 넣는다.
  - `raw_log`, `raw_request`, `user_agent`, `referer`는 복제하지 않는다.
  - `policy_distribution`, severity/category/final verdict/success 판단은 넣지 않는다.
  - 검증: summary/scheduler tests → 18 passed.
  - 검증: sliding window summary + scheduler + prepare output + candidate policy quick bundle → 46 passed.
- [x] Rollup input 문서 세트 repo 기준 정렬
  - `99_sliding_window_rollup_input_review.md` 작성 완료.
  - `99_sliding_window_rollup_input_format.md`, `99_sliding_window_rollup_pipeline_integration.md`, `99_sliding_window_rollup_quick_reference.md`, `99_sliding_window_rollup_implementation_guide.md`를 v1.0 최소 구현 기준으로 축소했다.
  - v1.0: `window_summary.json` 수집, missing/invalid window 상태 기록, request_id dedup, candidate_index/distribution merge, rollup artifact 3종 생성.
  - v1.1: `uri_family_hints`, `low_and_slow_hints` 후보.
  - v1.5: Stage1 호환 `analysis_candidates` projection 후보.
- [x] Rollup v1.0 최소 구현 및 검증
  - `src/sliding_window_rollup.py` 추가 완료.
  - `tests/test_sliding_window_rollup.py` 추가 완료.
  - 구현 범위: window_summary path 계산, summary 로드, missing/invalid window 기록, request_id dedup, missing request_id 보존, fallback duplicate 표시, candidate_index merge, distributions merge, `rollup_input.json` / `dedup_candidates.json` / `rollup_summary.json` 생성.
  - 제외 범위: Stage1/Stage2 실행, `runs/` 생성, `uri_family_hints`, `low_and_slow_hints`, Stage1 projection, confidence/threat_level/final verdict, 새 score/verdict_hint 생성, raw_log/raw_request/user_agent 복제.
  - 검증: `tests/test_sliding_window_rollup.py` → 7 passed.
  - 검증: sliding window rollup + summary + scheduler + candidate policy quick bundle → 53 passed.
  - single-window smoke: `rollup_20260524_0200_0300`, windows_loaded=1, candidate_rows_total=5, candidate_index_count=5, dedup_removed_by_request_id=0.
  - missing-window smoke: `rollup_20260524_0200_0400`, window_count=2, windows_successfully_loaded=1, windows_missing_or_failed=1, incomplete_analysis=true, missing reason=`window_summary_not_found`.
  - 3-window overlap smoke: `sw_0200_0300`, `sw_0230_0330`, `sw_0300_0400` 모두 loaded, candidate_rows_total=5, candidate_index_count=5, dedup_removed_by_request_id=0.
  - 실제 overlap smoke에서 중복 request_id는 발생하지 않았다. 중복 후보가 있는 window가 하나뿐이므로 정상이며, cross-window request_id dedup은 unit test로 검증했다.
- [x] Rollup v1.0 output reuse policy 구현 및 검증
  - `src/sliding_window_rollup.py --overwrite` 추가 완료.
  - output 3종(`rollup_input.json`, `dedup_candidates.json`, `rollup_summary.json`)이 모두 있으면 기본 `skipped_existing` 처리한다.
  - 일부만 있으면 `PartialExistingRollupArtifactsError`로 실패한다.
  - `--overwrite` 지정 시 모두 있음/일부 있음과 무관하게 재생성한다.
  - CLI text/json summary에 `status`, `existing_outputs`, `missing_outputs`, `counts`를 포함한다.
  - 검증: `tests/test_sliding_window_rollup.py` → 10 passed.
  - 검증: sliding window rollup + summary + scheduler + candidate policy quick bundle → 56 passed.
  - smoke: 기존 `rollup_20260524_0200_0400` artifact 3종 존재 시 `status=skipped_existing` 확인.
- [x] Operator Queue v1 설계 및 구현
  - `docs/design/99_sliding_window_operator_queue_design.md` 작성 및 v1 구현 기준으로 보강 완료.
  - `src/sliding_window_operator_queue.py` 추가 완료.
  - `tests/test_sliding_window_operator_queue.py` 추가 완료.
  - 입력: `data/rollups/<date>/rollup_*/rollup_input.json`, `rollup_summary.json`.
  - 출력: `data/operator_queue/<date>/queue_items.json`, `queue_summary.json`.
  - 구현 범위: quiet/needs_review/data_quality_check routing, data_quality_status 파생, llm_eligible 파생, llm_required=false 고정, top_observed distribution 생성, payload-like reason hint allowlist 상수화, atomic write, output reuse policy.
  - 제외 범위: Stage1/Stage2 실행, LLM reporter 실행, Web UI 변경, DB/API, 보안 verdict/confidence/threat_level/success 판단 생성.
  - 검증: `tests/test_sliding_window_operator_queue.py` → 11 passed.
  - 검증: sliding window/operator/rollup/scheduler/candidate policy quick bundle → 67 passed.
  - smoke: `python3 src/sliding_window_operator_queue.py --work-dir /opt/web_log_analysis --date 2026-05-24 --pretty` → `status=written`, `rollup_items_total=2`, `needs_review=2`, `llm_eligible=2`, `llm_required=0`.
  - 생성 artifact: `data/operator_queue/2026-05-24/queue_items.json`, `queue_summary.json`.
- [x] Operator Queue allowlist 보정 및 검증
  - actual smoke의 `candidate_reason_hint_prefix` 분포에서 `sqli`, `xss`가 관찰되어 `PAYLOAD_LIKE_REASON_HINTS`에 `sqli`, `xss`를 추가했다.
  - 기존 `sqli_hint`, `xss_hint`는 유지했다.
  - `upload`, `login_endpoint`, `auth_payload_content_type`, `error_linked`, `error_status`는 payload-like allowlist에 추가하지 않았다.
  - 이는 queue routing signal 정렬일 뿐이며 score/verdict_hint/candidate visibility/LLM required는 변경하지 않는다.
  - 검증: `tests/test_sliding_window_operator_queue.py` → 13 passed.
  - 검증: sliding window/operator/rollup/scheduler/candidate policy quick bundle → 69 passed.
  - smoke: `--overwrite`로 queue 재생성 후 두 rollup 모두 `has_payload_like_reason_hint=true`, `llm_eligible=true`, `recommended_action=review_before_optional_briefing` 확인.
- [ ] Operator Queue smoke/운영 rollup cadence 분리 여부 판단
  - 같은 날짜 아래 `rollup_0200_0300`과 `rollup_0200_0400` 같은 실험성 cadence가 함께 잡히면 queue에 중복처럼 보일 수 있다.
  - 필요 시 `--rollup-pattern`, `--rollup-id-prefix`, 또는 별도 rollup root 사용을 검토한다.
- [ ] Single Rollup Reporter 설계 여부 판단
  - operator queue 이후 optional briefing으로 설계한다.
  - detection engine이 아니라 observation briefing으로 제한한다.
- [ ] Rollup v1.0 smoke 보강 여부 판단
  - 실제 로그에서 request_id 중복이 발생하는 overlap 구간을 추가로 찾을지 판단한다.
  - 현재는 unit test로 cross-window request_id dedup을 검증했고, 실제 smoke에서는 window load/merge/missing handling/output reuse policy를 확인했다.
- [ ] Rollup v1.1 hint 설계 여부 판단
  - `uri_family_hints`
  - `low_and_slow_hints`
  - repeated src_ip / repeated uri / repeated reason_hint_prefix
  - v1.1에서도 hint를 `candidate_index`나 Stage1 후보로 승격하지 않는다.
- [ ] Rollup v1.5 Stage1 projection 검토
  - Stage1 호환 `analysis_candidates` projection은 별도 fixture/test 전까지 보류한다.
  - projection 과정에서 score/verdict_hint/severity/confidence를 새로 만들지 않는다.
- [ ] rollup stage2와 daily summary의 역할 분리
- [ ] token/cost 추정 재측정 항목 정리
  - 팀원 문서의 token/cost 값은 근사치로 두고, 실제 모델 단가와 현재 run artifact 기준으로 재측정할 항목을 표시한다.

## P1. observability 후속 판단

- [ ] `proxy_error_check`를 정식 scenario catalog extension으로 뺄지 검토
  - 검토 문서: [../design/99_proxy_error_check_scenario_extension_review.md](../design/99_proxy_error_check_scenario_extension_review.md)
  - 현재는 backend availability context 관찰용 별도 run으로 유지한다.
  - 정규 S01~S15 편입, catalog/runner/prepare 변경, label detector 확장은 모두 보류한다.
  - 공격/침해 시나리오처럼 서술하지 않는다.
- [ ] external client 기반 reverse proxy topology run 필요성 판단
  - direct PHP external error-heavy run은 완료됐다.
  - 다음 proxy topology run은 direct app 결과와 현재 표본의 충분성을 보고 별도 판단한다.
- [ ] OpenCart v2 추가 진행 여부 검토
  - 현재 표본으로 충분한지, 추가 run이 필요한지만 판단한다.
- [ ] `mod_remoteip`/remoteIP 환경 구성 여부 검토
  - external client error-heavy run과 분리해서 별도 설계 후 진행한다.
  - 실제 공격자 신원 판정이 아니라 관찰 필드 차이 검토 목적에 한정한다.

## P2. candidate policy 관찰

- [x] `obs_php_sample_v2_error_heavy_external_001` EH01~EH12 전체 external run을 수행하고 `explain_prepare_candidates.py` 결과를 baseline과 비교
  - 결과: local/internal baseline과 같은 `payload 3 / probe 4 / status-error 3 / auth 1 / upload 1` shape 유지
  - controlled external client identity: `client_ip_source=direct`, `src_ip=192.168.56.114`, `peer_ip=192.168.56.114`
  - stale explanation artifact를 최신 `/opt/web_log_analysis` 기준으로 재생성한 뒤 EH01~EH12 label이 정상 표시됨
  - prepare/scoring/filtering 변경 없음
- [ ] upload/sql-comment narrow guard가 실제 strong SQLi를 과소탐지하지 않는지 계속 관찰
- [ ] broad status/error-only demotion은 계속 보류 유지
- [ ] scanner/probe broad demotion은 계속 보류 유지
- [ ] proxy error context의 정식 prepare 반영 여부는 별도 검토 전까지 보류

## P3. Web UI read-only 관찰

- [ ] Interpretation Aid와 context badge가 과도하게 findings처럼 보이지 않는지 관찰
- [ ] Related Contexts / Supporting Events 표시가 새 관계 추론처럼 보이지 않는지 점검
- [ ] backend unavailable / proxy error badge는 scenario 정식화 여부가 정리된 뒤 다시 검토

## P4. wording / taxonomy guard

- [ ] actual LLM 출력에서 context-only 과승격이 반복되는지 관찰
- [ ] file disclosure 성공, admin 접근 성공, upload 저장 성공 같은 과해석이 재발하는지 관찰
- [ ] 필요 시 lint warning 분포만 확인하고, review-only lint라는 기본 성격은 유지

## P5. run_dir / archive / retention

- [ ] `--run-id` 필요성 관찰
- [ ] legacy/lab archive opt-in scan 정책 후속 검토
- [ ] raw observability log의 보관/커밋 정책을 계속 보수적으로 유지할지 점검
- [ ] output cleanup의 실제 삭제 기능은 별도 승인 전까지 계속 보류

## P6. 새 coverage 후보

- [ ] API key / secret token probe fixture plan 작성 여부 판단
- [ ] Webshell command query fixture plan 작성 여부 판단
- [ ] request smuggling / header anomaly 로그 가시성 검토
- [ ] deserialization / object injection, LDAP / NoSQL injection-like payload는 계속 보류할지 재확인
