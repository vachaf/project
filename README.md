# Apache Logs-Only LLM Intrusion Analysis Pipeline

Apache 웹 로그를 MariaDB에 적재한 뒤 `export -> prepare -> stage1 -> stage2` 순서로 분석하는 LLM 기반 침입 로그 분석 파이프라인입니다.

핵심 원칙은 `logs-only`와 보수적 해석입니다. Apache 로그에 직접 보이지 않는 raw POST body, response body 원문, DB 결과, 브라우저 실행 여부는 사용하지 않으며, `status_code`, `response_body_bytes`, `resp_content_type`만으로 성공, 침해, 유출을 단정하지 않습니다.

## 프로젝트 개요

- Apache 웹 로그 기반 분석
- `export -> prepare -> stage1 -> stage2` 구조로 동작
- `prepare_llm_input.py`에서 후보와 context-only 문맥을 선별
- `llm_stage1_classifier.py`에서 후보별 1차 분류
- `llm_stage2_reporter.py`에서 Markdown / JSON 보고서 생성
- `run_analysis_pipeline.py --dry-run`으로 실제 LLM API 호출 없이 구조 검증 가능
- 문서 허브는 [docs/README.md](docs/README.md)에서 관리

## Pipeline

```text
Apache logs
  -> apache_log_shipper.py
  -> MariaDB web_logs
  -> export_db_logs_cli.py
  -> prepare_llm_input.py
  -> llm_stage1_classifier.py
  -> llm_stage2_reporter.py
  -> run_analysis_pipeline.py
```

## Supported Signals

- SQLi
- XSS
- traversal
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

## Regression Checks

```bash
python3 scripts/check_prepare_regression.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py
python3 scripts/check_stage_dryrun_regression.py --strict
```

현재 기준:

- prepare regression: 18 fixtures, `warn=0 fail=0`
- stage dry-run regression: 12 fixtures, `warn=0 fail=0`

최신 상태는 [docs/진행상황.md](docs/진행상황.md)를 기준으로 확인합니다.

## Limitations

- no raw POST body
- no response body content
- no DB result
- no browser execution validation
- no success / exfiltration / compromise assertion from status/bytes/content-type alone
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

- `docs/README.md`: 전체 문서 허브
- `docs/operations/`: 실행 가이드, 환경 구축, 로그 구조, `export/prepare/stage1/stage2` 운영 문서
- `docs/standards/`: 비교 실험 표준, 결과 기록 템플릿
- `docs/experiments/`: A~H 세트별 실험 설계/실행 요청 문서
- `docs/design/`: 파이프라인 설계, regression 설계, 해석 한계, 보류 결정
- `docs/reviews/`: 중간정리, LLM 샘플 검증, Stage2 wording 품질 검토
- `docs/planning/`: 후속 작업 TODO와 우선순위
- `lab/`: 실험 산출물, 비교 결과, 실행 결과 보관

자세한 문서 인덱스는 [docs/README.md](docs/README.md)를 기준으로 확인합니다.

## Documentation

- 문서 허브: [docs/README.md](docs/README.md)
- 현재 상태 대시보드: [docs/진행상황.md](docs/진행상황.md)
- 운영/실행: [docs/operations/01_운영_기준_실행_가이드.md](docs/operations/01_운영_기준_실행_가이드.md)
- 전체 흐름: [docs/operations/00_전체_흐름_요약_가이드.md](docs/operations/00_전체_흐름_요약_가이드.md)
- 실험 표준: [docs/standards/98_비교_실험_요청_세트_표준.md](docs/standards/98_비교_실험_요청_세트_표준.md)
- 실험 문서 인덱스: [docs/experiments/README.md](docs/experiments/README.md)
- 회귀 검증 설계: [docs/design/99_prepare_regression_fixture_설계.md](docs/design/99_prepare_regression_fixture_설계.md), [docs/design/99_stage_dryrun_regression_설계.md](docs/design/99_stage_dryrun_regression_설계.md)
- 후속 작업: [docs/planning/99_비교실험_후속개선_TODO.md](docs/planning/99_비교실험_후속개선_TODO.md)
