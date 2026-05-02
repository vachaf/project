# Apache Logs-Only LLM Intrusion Analysis Pipeline

Apache 웹 로그를 MariaDB에 적재한 뒤 `export -> prepare -> stage1 -> stage2` 순서로 분석하는 LLM 기반 침입 로그 분석 파이프라인입니다.

핵심 원칙은 `logs-only`와 보수적 해석입니다. Apache 로그에 직접 보이지 않는 raw POST body, response body 원문, DB 결과, 브라우저 실행 여부는 사용하지 않으며, `status_code`, `response_body_bytes`, `resp_content_type`만으로 성공, 침해, 유출을 단정하지 않습니다.

## 프로젝트 개요

- Apache 웹 로그 기반 분석
- `prepare_llm_input.py`에서 후보와 문맥을 선별
- `llm_stage1_classifier.py`에서 후보별 1차 분류
- `llm_stage2_reporter.py`에서 Markdown / JSON 보고서 생성
- `run_analysis_pipeline.py --dry-run`으로 실제 LLM API 호출 없이 Stage1/Stage2 구조 검증 가능

## Pipeline

```text
Apache logs
  -> apache_log_shipper.py
  -> MariaDB web_logs
  -> export_db_logs_cli.py
  -> prepare_llm_input.py
  -> llm_stage1_classifier.py
  -> llm_stage2_reporter.py
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
- `supporting_events`
- `probing_sequence_summaries`
- `ip_behavior_aggregates` context-only

## Regression Checks

```bash
python3 scripts/check_prepare_regression.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py
python3 scripts/check_stage_dryrun_regression.py --strict
```

현재 기준:

- prepare regression: 11 fixtures, `0 fail`
- stage dry-run regression: 5 fixtures, `0 fail`

## Limitations

- no raw POST body
- no response body content
- no DB result
- no browser execution validation
- no success / exfiltration / compromise assertion from `status_code`, `response_body_bytes`, `resp_content_type` alone

## Safety Principles

- no `lab-*` UA rule
- no specific IP rule
- no response size hard-code
- no product-name hard-code
- hint/category-based analysis

## Key Docs

- 운영/실행: [docs/01_운영_기준_실행_가이드.md](docs/01_운영_기준_실행_가이드.md)
- 전체 흐름: [docs/00_전체_흐름_요약_가이드.md](docs/00_전체_흐름_요약_가이드.md)
- prepare regression 설계: [docs/99_prepare_regression_fixture_설계.md](docs/99_prepare_regression_fixture_설계.md)
- stage dry-run regression 설계: [docs/99_stage_dryrun_regression_설계.md](docs/99_stage_dryrun_regression_설계.md)
- 현재 상태 대시보드: [docs/진행상황.md](docs/진행상황.md)
- 남은 TODO: [docs/99_비교실험_후속개선_TODO.md](docs/99_비교실험_후속개선_TODO.md)
