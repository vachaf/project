# src/

## 목적

`src/`는 Apache 로그 기반 LLM 침입 로그 분석 파이프라인의 주요 Python 코드가 있는 폴더다.

기본 흐름은 다음과 같다.

```text
export -> prepare -> stage1 -> stage2
```

## 주요 entrypoint

- `export_db_logs_cli.py`
  - MariaDB에 적재된 Apache 로그를 시간 구간 기준으로 export한다.
- `prepare_llm_input.py`
  - export JSON을 정제하고 분석 후보, noise summary, context-only 문맥을 만든다.
- `llm_stage1_classifier.py`
  - prepare 결과의 후보를 대상으로 1차 LLM 분류를 수행한다.
- `llm_stage2_reporter.py`
  - Stage1 결과와 문맥을 바탕으로 JSON / Markdown 보고서를 생성한다.
- `run_analysis_pipeline.py`
  - `export/prepare/stage1/stage2` 흐름을 통합 실행한다.

## 운영 원칙

- Apache 로그 표면에 직접 남는 신호를 기준으로 분석한다.
- raw POST body, response body 원문, DB 결과, 브라우저 실행 여부는 기본 근거로 사용하지 않는다.
- `status_code`, `response_body_bytes`, `resp_content_type`만으로 성공, 침해, 유출을 단정하지 않는다.
- 실험환경 특화 rule, 특정 IP, 특정 UA, 특정 response size에 과적합하지 않는다.

## 관련 문서

- 전체 문서 허브: `../docs/README.md`
- 운영/실행 가이드: `../docs/operations/01_운영_기준_실행_가이드.md`
- 회귀 검증 설계: `../docs/design/99_prepare_regression_fixture_설계.md`, `../docs/design/99_stage_dryrun_regression_설계.md`
