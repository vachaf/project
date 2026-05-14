# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-05-14
- 문서 역할: 앞으로 해야 할 일만 남기는 TODO
- 원칙:
  - 완료된 항목은 이 문서에 길게 유지하지 않는다.
  - 상세 완료 이력은 `docs/진행상황.md`, 개별 설계 문서, 작업일지로 이관한다.
  - Apache logs-only evidence boundary를 유지한다.
  - `status_code=200`, `text/html`, `response_body_bytes`, `handler`, `x_forwarded_for`만으로 공격 성공/유출/내부 결과를 단정하지 않는다.

---

## 최근 완료 상태

- 기존 A~H 비교 실험/standards/reviews 정리 및 기준 문서 반영 완료
- prepare split round1/round2, constants mini-move, hints split(SQLi/XSS/file disclosure/traversal-CMDI) 완료
- Stage2 prompt compaction + report quality lint 추가/튜닝 완료
- Web UI loader run_dir manifest scan backend 전환 완료
- Web UI read-only viewer/payload dashboard 및 layout/search/filter polish 완료
- Apache app observability 비교 기반 추가 완료:
  - `docs/operations/99_apache_custom_log_format_contract.md`
  - `docs/operations/examples/apache_security_logformat_v1.conf`
  - `docs/design/99_apache_app_observability_comparison_plan.md`
  - `lab/observability/scenario_catalog.md`
  - `lab/observability/observation_matrix_template.md`
  - `scripts/run_observability_scenarios.sh`
  - `scripts/init_observability_run_notes.sh`
  - `scripts/collect_observability_server_logs.sh`
  - `scripts/summarize_observability_run.sh`
  - `scripts/update_observation_matrix_from_run.sh`
- Apache observability 3-way run 완료:
  - PHP sample baseline: `obs_php_sample_002`
  - OpenCart: `obs_opencart_002`
  - Juice Shop reverse proxy: `obs_juiceshop_proxy_001`
- 비교 문서 작성 완료:
  - `lab/observability/comparison_php_sample_vs_opencart.md`
  - `lab/observability/comparison_php_sample_vs_opencart_vs_juiceshop.md`
- `summarize_observability_run.sh` 개선 완료:
  - notice/warn/error 분리
  - redirect-follow/double-request 후보 note 자동 반영
  - logical scenario count와 actual Apache request count 차이 표시
- 확인된 핵심 결론:
  - `apache_security_io_v1`은 direct PHP, real PHP rewrite/front-controller, reverse proxy 배치 모두에서 동작
  - `status_code=200`은 topology-dependent weak signal이며 성공/노출/침해 근거로 사용 금지
  - `handler`, `_route_=`, redirect-follow, `proxy-server`, proxy error context는 interpretation context로만 사용

---

## P0. Apache app observability 다음 작업

- [ ] 3-way 비교 결과를 prepare feature candidate review 문서로 승격할지 판단
  - 후보 파일: `docs/design/99_prepare_apache_observability_context_feature_review.md`
  - 포함 후보:
    - `front-controller/fallback candidate`
    - `reverse-proxy/backend-response candidate`
    - `redirect-follow candidate`
    - `backend unavailable/proxy error context`
- [ ] `proxy_error_check`를 정식 scenario catalog extension으로 분리할지 판단
  - 현재는 정규 S01~S15와 별도 backend availability 관찰로 유지
  - 정식화 시 공격/침해 시나리오가 아니라 backend availability context로 명시
- [ ] `lab/observability/runs/*/raw/` 커밋/보관 정책 점검
  - raw log는 민감정보 가능성이 있으므로 기본 커밋 금지 후보
  - 필요 시 `.gitignore` 또는 sanitization policy 검토
- [ ] 추가 앱 topology가 필요할 때만 후속 run 수행
  - 예: PHP-FPM 분리형, WAF-fronted Apache, TLS/HTTP2, 앞단 LB + mod_remoteip

---

## P1. prepare / LLM input 반영 후보

- [ ] OpenCart-like rewrite/front-controller behavior를 prepare context feature 후보로 검토
  - `has_route_param`
  - `route_param_value`
  - `is_front_controller_candidate`
  - `is_fallback_200_candidate`
  - `redirect_follow_candidate`
- [ ] reverse proxy/backend behavior를 prepare context feature 후보로 검토
  - `is_reverse_proxy_candidate`
  - `handler=proxy-server`
  - `backend_response_candidate`
  - `backend_unavailable_context`
  - `proxy_error_context`
- [ ] `status_code=200` guardrail 강화 필요 여부 검토
  - OpenCart/Juice Shop run에서 probe-like path도 200 fallback 가능함을 확인
  - Stage1/Stage2 prompt 또는 prepare context에서 topology hint를 명시할지 검토
- [ ] handler 기반 해석 feature 검토
  - `application/x-httpd-php`
  - `redirect-handler`
  - `httpd/unix-directory`
  - `proxy-server`
  - `server-status`
  - `-`
- [ ] query string rewrite marker 처리 검토
  - `_route_=`가 있는 경우 원 요청 target과 routed/fallback behavior를 분리
- [ ] request body 미수집 guardrail 유지
  - S08/S09는 Apache metadata로 요청만 관찰 가능
  - 로그인 성공/업로드 저장 성공은 app/DB/backend audit 없이는 판단 금지

---

## P2. Stage1/Stage2 wording/taxonomy guard 관찰

- [ ] actual LLM 출력에서 context-only 과승격을 계속 관찰
- [ ] actual LLM 출력에서 file disclosure 성공 단정 등 과해석을 계속 관찰
- [ ] lint warning/blocker 분포를 필요 시 확인
- [ ] `suspicious_file_disclosure` 실제 LLM 재검증은 필요 시점에만 수행
- 주의:
  - Apache logs-only 한계를 유지한다.
  - status/bytes/content-type만으로 성공을 단정하지 않는다.
  - `lab-*` 또는 `obs-test/*` User-Agent를 공격 근거로 일반화하지 않는다.
  - `check_stage2_report_quality.py`는 review-only lint이며 기본 모드는 CI를 깨지 않는다.

---

## P3. Web UI / viewer 후속 후보

- [ ] display-only topology/context badge 후보 검토
  - `front-controller/fallback candidate`
  - `reverse-proxy/backend-response candidate`
  - `redirect-follow candidate`
  - `backend unavailable / proxy error context`
  - 단, badge는 severity/category/verdict 변경 근거가 아님
- [ ] Related Contexts matching 과잉/누락 관찰
  - Web UI에서 새 관계를 추론해 연결을 보정하는 방식은 금지
  - context-only 승격, severity/category/verdict 재계산 금지
- [ ] Supporting Events 생성 조건 관찰
  - 항상 생성되는 필드가 아니라 조건부 context-only 보조 이벤트로 유지
  - 억지 생성하거나 UI에서 새 관계를 추론하지 않음
- [ ] viewer_payload_builder.py 최소 단위 테스트 추가 여부 검토
- [ ] Context graph / advanced relationship view는 장기 후보로 보류
- [ ] viewer_payload compare/history 후보 검토
- [ ] Web UI layout regression fixture 후보 검토
- [ ] Stage2 산출물 field completeness 관찰
- [ ] provider 비교 구조 일반화(openai/anthropic 고정 -> N-provider)는 장기 후보로 유지

---

## P4. run_dir / archive / runner 후속 후보

- [ ] `--run-id` 필요성 관찰
- [ ] `--overwrite` 정책 보류(필요 시점에만 확정)
- [ ] legacy/lab archive opt-in scan 정책/구현 여부 후속 검토
- [ ] flat/run_dir dedupe는 archive opt-in 필요가 확인될 때만 검토
- [ ] canonical_report_key는 후속 후보로 보류
- [ ] `run_analysis_pipeline.py --help` 예시의 table auto resolution 안내 보강 필요 여부 검토

---

## P5. retention / output cleanup

- 현재 동작:
  - 삭제 기능 없음
  - `--apply`는 NOT IMPLEMENTED로 종료
  - `KEEP` / `REVIEW` / `CLEANUP_CANDIDATE` / `DO_NOT_AUTO_DELETE` 분류 출력
  - `lab/`, `docs/`, `src/`, `tests/fixtures`, `tests/expected`, `.git` 보호
  - `/tmp/stage-dryrun-regression` 하위는 cleanup 후보로 분류
- 남은 후보:
  - [ ] 실제 필요 시점에만 JSONL 로그 출력 검토
  - [ ] 실제 필요 시점에만 `--kind temp-dryrun`, `--older-than-days` 필터 검토
  - [ ] `--apply` 또는 실제 삭제 기능은 별도 승인 전까지 보류

---

## P6. 새 공격/시나리오 coverage 검토

- 현재 방향:
  - 추가 prepare split은 당장 진행하지 않음
  - 새 공격/시나리오 coverage는 Apache logs-only evidence boundary를 먼저 고정하고 fixture/regression 적합성부터 판단
- 남은 TODO:
  - [ ] API key / secret token probe fixture plan 작성 여부 판단
  - [ ] Webshell command query fixture plan 작성 여부 판단
  - [ ] request smuggling / header anomaly 로그 가시성 검토
  - [ ] Deserialization / object injection-like payload 보류
  - [ ] LDAP / NoSQL injection-like payload 보류
  - [ ] scanner / tool behavior 확장 보류
  - [ ] prepare split 추가 분리는 계속 보류

---

## 장기 후보

- execution console 확장 후보(New Analysis / pipeline run / live progress / regression run / scheduling/alert/dashboard)
- run 구조 전환 후보(`data/runs/<run_id>/`, `data/latest`, manifest 기반 full run_dir 빌더)
- provider selection
- report search/filter
- SQLite history
- alert/dashboard
- comparison history trend
- 모바일 전용 UX
- dark/light theme toggle

주의:

- 위 항목은 read-only viewer 범위 검토 이후에만 장기 후보로 유지한다.
- 현재는 Phase 2 문서 신규 생성 및 execution TODO 승격을 하지 않는다.
- Phase 2를 시작하려면 read-only viewer 범위를 실행/운영 콘솔로 확장할지 먼저 별도 판단한다.
- `lab/`는 비교실험/fixture/archive 용도로 유지하며 일반 운영 출력과 섞지 않는다.
