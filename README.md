# Apache Logs-Only LLM Intrusion Analysis Pipeline

Apache 웹 로그를 MariaDB에 적재하고, Web UI에서 등록한 `analysis_jobs`를 Analysis Job Worker가 가져와 `full_report` 분석을 실행한 뒤 결과를 확인하는 DB-backed LLM 침입 로그 분석 플랫폼입니다.

현재 canonical architecture overview는 [docs/00_current_architecture.md](docs/00_current_architecture.md)입니다. 처음 구조를 확인할 때 이 문서를 먼저 읽습니다.

핵심 원칙은 `logs-only`와 보수적 해석입니다. Apache 로그에 직접 보이지 않는 raw POST body, response body 원문, DB 결과, 브라우저 실행 여부는 사용하지 않으며, `status_code`, `response_body_bytes`, `resp_content_type`만으로 성공, 침해, 유출을 단정하지 않습니다.

## 프로젝트 개요

- Apache 웹 로그 기반 분석
- DB-backed MVP 상위 흐름: `Apache logs -> MariaDB -> analysis_jobs -> Analysis Job Worker -> full_report artifacts -> Web UI`
- `full_report` 내부 분석 흐름: `export -> prepare -> stage1 -> stage2 -> viewer_payload`
- `sliding_window / rollup / operator_queue` 기반 흐름은 후속 `analysis_mode=windowed_triage`로 분리
- `prepare_llm_input.py`에서 후보와 context-only 문맥을 선별
- `src/prepare/` 하위 모듈에서 decoder, hint, context summary, constants owner 일부를 분리 관리
- `llm_stage1_classifier.py`에서 후보별 1차 분류
- `llm_stage2_reporter.py`에서 Markdown / JSON 보고서 생성
- `scripts/check_stage2_report_quality.py`로 Stage2 report JSON wording risk를 warning-only lint
- `run_analysis_pipeline.py --dry-run`으로 실제 LLM API 호출 없이 구조 검증 가능
- 문서 허브는 [docs/README.md](docs/README.md)에서 관리

## Pipeline

```text
Apache logs
  -> apache_log_shipper.py
  -> MariaDB web_logs
  -> Web UI analysis_jobs registration
  -> Analysis Job Worker full_report
  -> export_db_logs_cli.py
  -> run_analysis_pipeline.py direct path
  -> prepare_llm_input.py
  -> llm_stage1_classifier.py
  -> llm_stage2_reporter.py
  -> viewer_payload.json
  -> analysis_reports / job_events
  -> Web UI result view
  -> optional: check_stage2_report_quality.py
```

`analysis_jobs` queue는 MariaDB table 기반의 실행 queue입니다. `operator queue`는 sliding window / rollup 결과를 사람이 검토하기 위한 artifact queue이며, 실행 lifecycle queue가 아닙니다.

Web UI의 read-only 원칙은 보안 결과 해석에 적용됩니다. DB-backed MVP에서는 Web UI가 `analysis_jobs` 등록/조회와 job lifecycle 표시를 위해 DB write/read를 수행할 수 있습니다.

MVP의 기본 `analysis_mode`는 `full_report`입니다. `SUCCEEDED`는 Stage1, Stage2, `viewer_payload`, report/artifact 저장까지 완료되어 Web UI에서 결과를 확인할 수 있는 상태를 뜻합니다. 2026-05-31 실제 smoke 기준으로 Web UI job 등록, Analysis Job Worker `--run-pipeline`, direct pipeline 실행, `analysis_reports` 저장, `/job/{id}/viewer` dashboard 표시까지 확인했습니다.

## Supported Signals

- SQLi
- XSS
- traversal
- CMDI
- HPP
- PHP wrapper / file disclosure attempt
- Log4Shell-style JNDI lookup
- SSRF-like internal / metadata target
- SSTI expression
- webshell-like access pattern
- Auth/Login abuse context
- HTTP method behavior context
- HTTP protocol anomaly context
- Static / health / normal browse baseline context
- Crawler-like baseline context
- Scanner-like sensitive path context
- Mixed benign + scanner-like context
- `supporting_events`
- `probing_sequence_summaries`
- `ip_behavior_aggregates`
- `auth_behavior_summaries`
- `method_behavior_summaries`
- `protocol_anomaly_summaries`
- `static_baseline_summaries`
- `crawler_baseline_summaries`
- `sensitive_path_probe_summaries`
- `mixed_baseline_scanner_summaries`

위 context-only 항목은 성공/침해 단정 근거가 아니라 문맥 보존용입니다.

## Prepare Module Structure

`src/prepare_llm_input.py`는 여전히 prepare 단계의 coordinator 역할을 유지합니다. 세부 helper와 pattern/context builder는 `src/prepare/` 하위 모듈로 분리되어 있습니다.

```text
src/prepare/decoders.py
src/prepare/l3_hints.py
src/prepare/models.py
src/prepare/method_summaries.py
src/prepare/protocol_anomalies.py
src/prepare/auth_behavior.py
src/prepare/static_baseline.py
src/prepare/crawler_baseline.py
src/prepare/sensitive_path_probe.py
src/prepare/ip_behavior.py
src/prepare/probing_sequence.py
src/prepare/mixed_baseline_scanner.py
src/prepare/sqli_hints.py
src/prepare/xss_hints.py
src/prepare/file_disclosure_hints.py
src/prepare/traversal_cmdi_hints.py
```

세부 역할과 분리 원칙은 [src/prepare/README.md](src/prepare/README.md)를 기준으로 확인합니다.

분리 원칙:

- mechanical refactor 우선
- `prepare_llm_input.py` wrapper 유지
- output key / policy_notes / counts 의미 유지
- expected fixture와 Stage2 reporter는 refactor 커밋에서 수정하지 않음
- Apache logs-only 해석 한계 유지

## Current Stability Baseline

현재 기준은 post-refactor stable 상태입니다.

- prepare module split round1/round2 완료
- constants mini-move 1차 완료
- SQLi/XSS/file disclosure/traversal-CMDI hint split 완료
- Stage2 prompt compaction 완료
- Stage2 report quality lint 추가 및 tuning 완료
- B/C/E/H dry-run spot check 통과
- H R4, E R2B actual LLM spot check 통과
- 최신 actual report 2건 quality lint PASS
- 추가 코드 분리는 보류하고 실제 LLM 출력 관찰 중심으로 관리

## Regression Checks

```bash
python3 scripts/check_prepare_regression.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py
python3 scripts/check_stage_dryrun_regression.py --strict
python3 scripts/check_stage2_report_quality.py --input path/to/stage2_report.json --pretty
```

현재 기준:

- prepare regression: 18 fixtures, `warn=0 fail=0`
- stage dry-run regression: 12 fixtures, `warn=0 fail=0`
- Stage2 quality lint tests: 14 passed
- 주요 Python 파일 `py_compile` 통과

최신 상태는 [docs/진행상황.md](docs/진행상황.md)를 기준으로 확인합니다.

## Limitations

- no raw POST body
- no response body content
- no DB result
- no browser execution validation
- no login success / account takeover / credential stuffing success assertion from Apache logs alone
- no file exposure / source disclosure / server compromise assertion from status/bytes/content-type alone
- no real crawler identity or site structure assertion from User-Agent/path pattern alone
- Apache logs-only visibility can produce blind spots

## Safety Principles

- no `lab-*` UA rule
- no specific IP rule
- no response size hard-code
- no product-name hard-code
- no route-specific exception as core detection logic
- hint/category/context-based analysis
- avoid environment-specific overfitting

## Documentation Layout

- `docs/00_current_architecture.md`: 현재 canonical architecture overview
- `docs/README.md`: 전체 문서 허브
- `src/`: 분석 파이프라인의 주요 Python 코드
- `src/prepare/README.md`: prepare 하위 모듈 역할과 분리 원칙
- `scripts/`: 회귀 검증, dry-run 검증, Stage2 quality lint, 보조 점검 스크립트
- `docs/operations/`: 실행 가이드, 환경 구축, 로그 구조, `export/prepare/stage1/stage2` 운영 문서
- `docs/standards/`: 비교 실험 표준, 결과 기록 템플릿, 품질 기준
- `docs/experiments/`: A~H 세트별 실험 설계/실행 요청 문서
- `docs/design/`: 파이프라인 설계, regression 설계, prepare split, constants/hints evidence boundary, Stage2 prompt/lint 설계 문서
- `docs/reviews/`: 중간정리, LLM 샘플 검증, post-refactor dry-run/actual LLM spot check
- `docs/planning/`: 후속 작업 TODO와 우선순위
- `lab/`: 실험 산출물, 비교 결과, 실행 결과 보관

자세한 문서 인덱스는 [docs/README.md](docs/README.md)를 기준으로 확인합니다.

## Documentation

- 현재 canonical architecture overview: [docs/00_current_architecture.md](docs/00_current_architecture.md)
- 문서 허브: [docs/README.md](docs/README.md)
- 현재 상태 대시보드: [docs/진행상황.md](docs/진행상황.md)
- 운영/실행: [docs/operations/01_운영_기준_실행_가이드.md](docs/operations/01_운영_기준_실행_가이드.md)
- 전체 흐름: [docs/operations/00_전체_흐름_요약_가이드.md](docs/operations/00_전체_흐름_요약_가이드.md)
- 실험 표준: [docs/standards/98_비교_실험_요청_세트_표준.md](docs/standards/98_비교_실험_요청_세트_표준.md)
- 회귀 검증 설계: [docs/design/99_prepare_regression_fixture_설계.md](docs/design/99_prepare_regression_fixture_설계.md), [docs/design/99_stage_dryrun_regression_설계.md](docs/design/99_stage_dryrun_regression_설계.md)
- prepare split 인덱스: [docs/design/README.md](docs/design/README.md), [src/prepare/README.md](src/prepare/README.md)
- Stage2 prompt/lint 설계: [docs/design/99_stage2_prompt_compaction_plan.md](docs/design/99_stage2_prompt_compaction_plan.md), [docs/design/99_stage2_report_quality_lint_candidate_review.md](docs/design/99_stage2_report_quality_lint_candidate_review.md), [docs/design/99_stage2_report_quality_lint_tuning_plan.md](docs/design/99_stage2_report_quality_lint_tuning_plan.md)
- post-refactor actual LLM spot check: [docs/reviews/99_post_refactor_LLM_output_spot_check.md](docs/reviews/99_post_refactor_LLM_output_spot_check.md)
- 후속 작업: [docs/planning/99_비교실험_후속개선_TODO.md](docs/planning/99_비교실험_후속개선_TODO.md)
