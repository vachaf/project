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
- PHP sample baseline 완료:
  - run: `obs_php_sample_002`
  - S01~S15 전체 관측 성공
  - User-Agent canonical marker 기준 필터링 검증
  - request_id 기반 app_security/app_error 연결 확인
  - notice/warn/error 분리 반영
  - `/server-status`는 localhost 200, 외부 403 확인. 외부 노출로 판단하지 않음
- OpenCart observability run 완료:
  - run: `obs_opencart_002`
  - S01~S15 전체 관측 성공
  - `O0=0`, `O1=13`, `O1/O4=2`
  - OpenCart rewrite/front-controller behavior 확인
  - `_route_=` + `handler=redirect-handler` + `status_code=200` 조합을 fallback/routed response 후보로 정리
- PHP sample vs OpenCart 비교 문서 작성 완료:
  - `lab/observability/comparison_php_sample_vs_opencart.md`
- `summarize_observability_run.sh` 개선 완료:
  - notice/warn/error 분리
  - redirect-follow/double-request 후보 note 자동 반영
  - logical scenario count와 actual Apache request count 차이 표시

---

## P0. Apache app observability 다음 작업

- [ ] Juice Shop reverse proxy 환경에서 동일 `apache_security_io_v1` 포맷 적용
  - PHP sample/OpenCart와 동일한 LogFormat 유지
  - 앱별 포맷 분기 금지
  - reverse proxy 특성은 app_security.log가 아니라 context 해석에서 반영
- [ ] Juice Shop run 수행
  - 권장 run_id: `obs_juiceshop_proxy_001`
  - `scripts/init_observability_run_notes.sh`
  - `scripts/run_observability_scenarios.sh`
  - `scripts/collect_observability_server_logs.sh`
  - `scripts/update_observation_matrix_from_run.sh`
- [ ] Juice Shop run summary 작성
  - backend/proxy behavior
  - `mod_proxy`/backend error context 여부
  - request_id backend 전달 여부는 가능하면 별도 확인
- [ ] 3-way 비교 문서 작성
  - 후보 파일: `lab/observability/comparison_php_sample_vs_opencart_vs_juiceshop.md`
  - 비교 축:
    - direct PHP/static baseline
    - real PHP app rewrite/front-controller behavior
    - Apache reverse proxy/backend behavior
- [ ] `front-controller/fallback candidate` feature 후보 정리
  - `status_code=200`
  - `handler=redirect-handler`
  - `query_string` contains `_route_=`
  - unusual/probe-like request target
  - finding severity 상승 근거가 아니라 interpretation/context feature로만 취급
- [ ] redirect-follow/double-request 처리 기준 문서화
  - logical scenario count와 actual Apache request count는 다를 수 있음
  - `curl --location` 때문에 301/302 후속 요청이 같은 scenario에 추가될 수 있음
  - matrix의 `count`는 actual Apache request count로 해석

---

## P1. prepare / LLM input 반영 후보

- [ ] OpenCart-like rewrite/front-controller behavior를 prepare context feature 후보로 검토
  - `has_route_param`
  - `route_param_value`
  - `is_front_controller_candidate`
  - `is_fallback_200_candidate`
  - `redirect_follow_candidate`
- [ ] `status_code=200` guardrail 강화 필요 여부 검토
  - OpenCart run에서 probe-like path도 200 fallback 가능함을 확인
  - Stage1/Stage2 prompt 또는 prepare context에서 fallback 후보를 명시할지 검토
- [ ] handler 기반 해석 feature 검토
  - `application/x-httpd-php`
  - `redirect-handler`
  - `httpd/unix-directory`
  - `server-status`
  - `-`
- [ ] query string rewrite marker 처리 검토
  - `_route_=`가 있는 경우 원 요청 target과 routed/fallback behavior를 분리
- [ ] request body 미수집 guardrail 유지
  - S08/S09는 Apache metadata로 요청만 관찰 가능
  - 로그인 성공/업로드 저장 성공은 app/DB audit 없이는 판단 금지

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

- [ ] Related Contexts matching 과잉/누락 관찰
  - Web UI에서 새 관계를 추론해 연결을 보정하는 방식은 금지
  - context-only 승격, severity/category/verdict 재계산 금지
- [ ] Supporting Events 생성 조건 관찰
  - 항상 생성되는 필드가 아니라 조건부 context-only 보조 이벤트로 유지
  - 억지 생성하거나 UI에서 새 관계를 추론하지 않음
- [ ] viewer_payload_builder.py 최소 단위 테스트 추가 여부 검토
  - `context_id`, `linked_context_ids`, `sample_request_ids`, `request_id`, `incident_group_key` 보존
  - `supporting_events` top-level 보존 및 empty/missing fallback
  - context-only summary가 findings로 섞이지 않는지 확인
- [ ] Context graph / advanced relationship view는 장기 후보로 보류
- [ ] viewer_payload compare/history 후보 검토
- [ ] Web UI layout regression fixture 후보 검토
  - Event Timeline selected-only toggle
  - Contexts Preview 카드형
  - Report Detail 모바일 카드형
  - `notable_incidents.summary/request_count/recommended_action` 채움 fixture 필요성
- [ ] Stage2 산출물 field completeness 관찰
  - 필요 시 Stage2 reporter schema/field completeness 검토는 별도 후속 과제로 분리
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
