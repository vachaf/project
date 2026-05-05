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
  - 현재는 coordinator 역할을 유지하며, 세부 helper와 pattern/context builder는 `src/prepare/` 하위 모듈로 분리되어 있다.
- `llm_stage1_classifier.py`
  - prepare 결과의 후보를 대상으로 1차 LLM 분류를 수행한다.
- `llm_stage2_reporter.py`
  - Stage1 결과와 문맥을 바탕으로 JSON / Markdown 보고서를 생성한다.
- `run_analysis_pipeline.py`
  - `export/prepare/stage1/stage2` 흐름을 통합 실행한다.

## prepare 하위 모듈

`src/prepare/` 하위에는 prepare 단계의 세부 helper가 topic별로 분리되어 있다.

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

분리 원칙:

- `prepare_llm_input.py`의 기존 공개 함수명 wrapper를 유지한다.
- output key, counts, policy_notes 의미를 바꾸지 않는다.
- candidate/scoring/filtering과 supporting_events 의미를 refactor 커밋에서 바꾸지 않는다.
- expected/test fixture와 Stage2 reporter는 mechanical refactor 커밋에서 수정하지 않는다.
- Apache logs-only 해석 한계를 유지한다.

## 운영 원칙

- Apache 로그 표면에 직접 남는 신호를 기준으로 분석한다.
- raw POST body, response body 원문, DB 결과, 브라우저 실행 여부는 기본 근거로 사용하지 않는다.
- `status_code`, `response_body_bytes`, `resp_content_type`만으로 성공, 침해, 유출을 단정하지 않는다.
- 로그인 성공, 계정 탈취, file exposure, command execution, browser execution, server compromise는 Apache 로그만으로 단정하지 않는다.
- 실험환경 특화 rule, 특정 IP, 특정 UA, 특정 response size에 과적합하지 않는다.

## 회귀 검증

prepare 관련 구조 변경 후에는 아래 검증을 기준으로 한다.

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

현재 기준:

```text
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
```

## 관련 문서

- 전체 문서 허브: `../docs/README.md`
- 현재 상태: `../docs/진행상황.md`
- 운영/실행 가이드: `../docs/operations/01_운영_기준_실행_가이드.md`
- 회귀 검증 설계: `../docs/design/99_prepare_regression_fixture_설계.md`, `../docs/design/99_stage_dryrun_regression_설계.md`
- prepare split 인덱스: `../docs/design/README.md`
- 후속 TODO: `../docs/planning/99_비교실험_후속개선_TODO.md`
