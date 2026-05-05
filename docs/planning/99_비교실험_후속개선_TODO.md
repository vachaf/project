# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-05-05
- 문서 역할: 앞으로 해야 할 일만 남기는 TODO
- 원칙: 완료된 항목은 이 문서에 길게 유지하지 않는다.

## 최근 완료 상태

- A~H 실험 문서, operations/design/reviews/standards/planning 문서 구조 정리 완료
- 폴더별 README와 루트 README 정비 완료
- A~H 실험 세트의 주요 context-only 문맥은 현재 regression/docs 기준에 반영 완료
- 실제 LLM 샘플 검증 1차 완료
  - F/G/H 5개 샘플 수동 리뷰 완료
  - B/C/E 3개 샘플 수동 리뷰 완료
  - 누적 8개 샘플, 72/80 = 90%
- 분석 품질 기준/체크리스트 정리 완료
  - `docs/standards/99_analysis_quality_criteria.md`
  - `docs/standards/99_LLM분석_품질평가_체크리스트.md`
  - `docs/reviews/99_A-F세트_대표샘플_6선.md`
- file disclosure verdict taxonomy 검토 완료
  - `suspicious_file_disclosure` verdict는 이미 존재하며 새 verdict 추가는 현재 필요 없음
- Stage1/Stage2 `lab-*` / experiment-like User-Agent wording guard 1차 보강 완료
  - Stage1 prompt guard 추가
  - Stage2 `stage1_carryover_rule` 추가
  - `e_r2_php_wrapper.expected.json` 보강
- retention/output cleanup 정책과 cleanup script 설계 문서 작성 완료
  - `docs/operations/99_output_retention_policy.md`
  - `docs/design/99_output_cleanup_script_설계.md`
  - `scripts/cleanup_outputs.py` list-only prototype 추가 완료
  - `tests/test_cleanup_outputs.py` 단위 테스트 15개 통과
- prepare module split 1차/2차 진행 완료
  - round1: `decoders.py`, `l3_hints.py`, `models.py`, `method_summaries.py`, `protocol_anomalies.py`, `auth_behavior.py`, `static_baseline.py`, `crawler_baseline.py`, `sensitive_path_probe.py`
  - round2: `ip_behavior.py`, `probing_sequence.py`, `mixed_baseline_scanner.py`
  - `docs/design/99_prepare_module_split_round1_summary.md` 작성 완료
  - `docs/design/99_prepare_module_split_round2_summary.md` 작성 완료
- prepare constants ownership / mini-move 정리 완료
  - `docs/design/99_prepare_constants_ownership_map.md` 작성 완료
  - `docs/design/99_prepare_constants_mini_move_candidate_review.md` 작성 완료
  - `docs/design/99_prepare_constants_mini_move_summary.md` 작성 및 crawler baseline까지 갱신 완료
  - `PROTOCOL_ANOMALY_*` constants 3개를 `src/prepare/protocol_anomalies.py`로 이동 완료
  - `IP_BEHAVIOR_*` constants 3개를 `src/prepare/ip_behavior.py`로 이동 완료
  - method behavior constants 5개를 `src/prepare/method_summaries.py`로 이동 완료
  - static baseline constants 3개를 `src/prepare/static_baseline.py`로 이동 완료
  - auth behavior constants/patterns 7개를 `src/prepare/auth_behavior.py`로 이동 완료
  - crawler baseline constants/patterns 6개를 `src/prepare/crawler_baseline.py`로 이동 완료
- prepare hints split 1차 정리 완료
  - `docs/design/99_prepare_hints_split_candidate_review.md` 작성 완료
  - `docs/design/99_prepare_hints_split_summary.md` 작성 및 traversal/CMDI까지 갱신 완료
  - `docs/design/99_prepare_shared_attack_policy_boundary_review.md` 작성 완료
  - `src/prepare/sqli_hints.py` 분리 완료
  - `src/prepare/xss_hints.py` 분리 완료
  - `src/prepare/file_disclosure_hints.py` 분리 완료
  - `src/prepare/traversal_cmdi_hints.py` 분리 완료
  - shared attack/search policy, automation UA, decoded attack hints는 보류로 고정
- Stage2 prompt / report lint 정리 완료
  - `docs/design/99_stage2_prompt_compaction_plan.md` 작성 완료
  - `src/llm_stage2_reporter.py`의 `build_messages()` system prompt를 섹션화/압축 완료
  - `docs/design/99_stage2_report_quality_lint_candidate_review.md` 작성 완료
  - `scripts/check_stage2_report_quality.py` 추가 완료
  - `tests/test_stage2_report_quality.py`: 14 passed
  - `docs/design/99_stage2_report_quality_lint_tuning_plan.md` 작성 및 튜닝 완료 반영
  - safe negation blocker 과잉탐지 완화 완료
  - H R4 / E R2B actual report lint 결과 PASS, blocker=0 warning=0
- post-refactor dry-run / actual LLM spot check 완료
  - `docs/reviews/99_post_refactor_dry_run_spot_check.md` 작성 완료
  - `docs/reviews/99_post_refactor_LLM_output_spot_check.md` 작성 완료
  - B R2B, C, E R2B, H R4 dry-run spot check 통과
  - H R4 actual LLM spot check 통과
  - E R2B actual LLM spot check 통과
  - context-only 과승격, file disclosure 성공 단정, server-status 노출 단정은 spot check 기준 발견하지 않음
- 최종 검증 재확인 완료
  - `python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py` 통과
  - `python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py` 통과
  - `python3 scripts/check_prepare_regression.py --strict`: pass=18 warn=0 fail=0
  - `python3 scripts/check_stage_dryrun_regression.py --strict`: pass=12 warn=0 fail=0
  - `git status --short`: clean
- Web UI Report Viewer 문서/구현 흐름 반영 완료
  - Phase 1A plan/contract, Phase 1B plan 기준 구현 흐름 반영
  - UI polish 계획 문서 작성 완료: `docs/design/99_web_ui_report_viewer_ui_polish_plan.md`

## P1. 실제 LLM 샘플 검증 체계 관리 — stable

- 완료:
  - F/G/H 5개 샘플 수동 리뷰 완료
  - B/C/E 3개 샘플 수동 리뷰 완료
  - post-refactor actual LLM spot check 2건 완료
- 남은 관리:
  - 새 샘플은 반복 문제나 발표/보고 필요 시점에만 추가
  - provider별 비교는 필요할 때만 선택 수행
  - 실제 LLM 샘플 검증은 regression 통과 여부와 같은 의미가 아님

## P2. Stage1/Stage2 wording/taxonomy guard 관리 — 관찰 단계

- 완료:
  - `suspicious_file_disclosure` taxonomy 검토
  - Stage1 `lab-*` / experiment-like UA guard 추가
  - Stage2 `stage1_carryover_rule` 추가
  - Stage2 report prompt compaction 완료
  - Stage2 report quality lint 추가 및 safe-negation tuning 완료
  - `e_r2_php_wrapper.expected.json` 보강
  - H R4 actual LLM: context-only 과승격 없음
  - E R2B actual LLM: file disclosure 성공/유출 단정 없음
- 남은 후보:
  - 실제 LLM 출력에서 context-only 문맥이 과승격되는지 계속 관찰
  - lint warning/blocker 분포를 필요 시 확인
  - `suspicious_file_disclosure` 실제 LLM 재검증은 필요 시점에만 수행
- 주의:
  - Apache logs-only 한계를 유지한다.
  - status/bytes/content-type만으로 성공을 단정하지 않는다.
  - `lab-*` UA를 공격 근거로 일반화하지 않는다.
  - `check_stage2_report_quality.py`는 review-only lint이며 기본 모드는 CI를 깨지 않는다.

## P3. retention / output cleanup — list-only prototype 완료

- 완료:
  - output retention policy 작성
  - cleanup script 설계 문서 작성
  - `scripts/cleanup_outputs.py` list-only inventory prototype 추가
  - `tests/test_cleanup_outputs.py` 단위 테스트 15개 통과
- 현재 동작:
  - 삭제 기능 없음
  - `--apply`는 NOT IMPLEMENTED로 종료
  - `KEEP` / `REVIEW` / `CLEANUP_CANDIDATE` / `DO_NOT_AUTO_DELETE` 분류 출력
  - `lab/`, `docs/`, `src/`, `tests/fixtures`, `tests/expected`, `.git` 보호
  - `/tmp/stage-dryrun-regression` 하위는 cleanup 후보로 분류
- 남은 후보:
  - 실제 필요 시점에만 JSONL 로그 출력 검토
  - 실제 필요 시점에만 `--kind temp-dryrun`, `--older-than-days` 필터 검토
  - `--apply` 또는 실제 삭제 기능은 별도 승인 전까지 보류

## P4. prepare 모듈 분리 — stable / 추가 코드 분리 보류

- 완료:
  - round1/round2 prepare module split 완료
  - constants mini-move 1차 완료
  - topic hint pattern split 1차 완료
  - shared attack/search policy boundary review 작성 완료
  - dry-run spot check: B R2B, C, E R2B, H R4 통과
  - actual LLM spot check: H R4, E R2B 통과
  - Stage2 prompt compaction 후 stage dry-run regression 통과
  - Stage2 report lint tuning 후 sample lint PASS
  - 최종 py_compile / prepare regression / stage dry-run regression 통과
- 보류:
  - `AUTOMATION_UA_PATTERNS`
  - `detect_decoded_attack_hints`
  - shared attack/search policy constants
  - normal search false-positive handling
  - candidate preservation/scoring/filtering
  - supporting_events 생성/연결 로직
  - Stage1/Stage2 reporter 구조 변경
  - expected/test fixture 변경
  - `constants.py` 대량 분리
- 다음 후보:
  - 바로 추가 코드 분리하지 않음
  - 실제 LLM 출력 관찰 후 반복 문제에 맞춰 report lint, Stage2 wording, 또는 보류 후보 재검토
- 조건:
  - 전면 리팩터링 금지
  - 작은 커밋 유지
  - prepare regression, stage dry-run regression, py_compile 통과 유지
  - 기존 behavior 변경 없이 구조 분리 우선
  - Apache logs-only 해석 한계 유지

## P5. docs 유지보수

- 할 일:
  - 문서 구조가 바뀌면 루트 README와 docs/README.md 동기화
  - operations 문서와 코드 옵션 정합성 주기 점검
  - 새 standards/reviews 문서가 생기면 해당 README 인덱스를 먼저 갱신
  - 오래된 문서는 archive 후보로 검토하되, 직접 참조 중인 문서는 이동하지 않음
- 현재 우선 후보:
  - Web UI README/인덱스 동기화(viewer 원칙, lint 연계 명령, read-only 범위)
  - docs 인덱스에서 Web UI/Stage2 lint/prepare split 최근 문서 가시성 유지
  - archive 후보 조사
  - 절대 경로 링크의 단계적 상대 경로 전환

## 장기 후보

- known asset 운영 가이드 정리
- Threat intelligence 연동 검토
- 알림, 대시보드, 자동 대응 검토
- 보류/비권장: 프레임워크 전환(React/Vue/Svelte/Angular, Streamlit, Tailwind/Bootstrap, Docker)
  - 현재는 FastAPI + Jinja2 + Plain CSS 유지가 우선
  - htmx/Alpine.js는 작은 인터랙션 필요 시에만 후보

## 다음 실행 후보

- UI polish 구현(template/CSS 중심)
  - 우선 파일: `web/templates/index.html`, `web/templates/compare.html`, `web/templates/detail.html`, `web/static/style.css`
  - 원칙: Python logic 변경 최소화, report read-only 유지, Stage2 보안 판정 의미 변경 금지

장기 후보 주의:

- Apache 로그 표면만으로 성공/침해를 단정하지 않으므로 자동 차단은 가장 나중이다.
- 실시간 Slack/email 알림, 웹 대시보드, 자동 대응은 현재 범위 밖이다.
