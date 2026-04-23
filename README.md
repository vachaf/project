# LLM 기반 침입로그 분석 시스템

Apache 웹 로그를 MariaDB에 적재한 뒤, export → 전처리 → LLM 1차 분류 → LLM 2차 보고서 생성까지 수행하는 로그 분석 파이프라인입니다.

## 디렉터리

- `docs/`: 구축, 운영, 분석 기준 문서
- `src/`: 실행 스크립트

## 현재 파이프라인

```text
Apache 로그 생성
  ↓
apache_log_shipper.py
  ↓
MariaDB(web_logs)
  ↓
export_db_logs_cli.py
  ↓
prepare_llm_input.py
  ↓
llm_stage1_classifier.py
  ↓
llm_stage2_reporter.py
```

`run_analysis_pipeline.py`는 export 이후 단계를 한 번에 실행하거나, 중간 산출물에서 재개하는 엔트리포인트입니다.

## 핵심 원칙

- 기본 분석 입력은 `security` 로그입니다.
- `error` 로그는 예외, 5xx, `request_id`/`error_link_id` 연계 확인용 보조 입력입니다.
- `access` 로그는 운영 확인과 기준선 비교용입니다.
- DB 저장 시각 기준은 UTC, 사용자 입력과 export 출력 기준은 KST입니다.
- LLM provider는 `openai`와 `anthropic`을 지원하며, 미지정 시 기존처럼 OpenAI를 사용합니다.
- `resp_html_*` fingerprint 계열은 현재 보류 또는 선택 항목입니다.
- 현재 보수 해석의 핵심은 `resp_content_type`, `response_body_bytes`, `raw_request_target`, `path_normalized_from_raw_request`, `likely_html_fallback_response`입니다.

## 빠른 시작

### 1. DB export

```bash
python3 ./src/export_db_logs_cli.py \
  --host 192.168.35.223 \
  --user log_reader \
  --password 'reader_password' \
  --date 2026-04-02 \
  --table security \
  --pretty
```

### 2. 전처리

```bash
python3 ./src/prepare_llm_input.py \
  --input ./data/raw/security_2026-04-02_kst.json \
  --out-dir ./processed \
  --pretty \
  --write-filtered-out
```

### 3. 통합 실행

```bash
python3 ./src/run_analysis_pipeline.py \
  --export-input ./data/raw/security_2026-04-02_kst.json \
  --work-dir . \
  --mode routine \
  --pretty
```

Claude를 사용할 때는 `ANTHROPIC_API_KEY`와 모델명을 설정하고 provider를 지정합니다.

```bash
python3 ./src/run_analysis_pipeline.py \
  --llm-provider anthropic \
  --stage1-model "$ANTHROPIC_MODEL" \
  --stage2-model "$ANTHROPIC_MODEL" \
  --export-input ./data/raw/security_2026-04-02_kst.json \
  --work-dir . \
  --mode routine \
  --pretty
```

## 주요 산출물

- export: `data/raw/{table}_{date}_kst.json` 또는 `data/raw/{table}_{start}_to_{end}_kst.json`
- prepare: `<base>_llm_input.json`
- stage1: `<base>_stage1_results.json`
- stage2: `<base>_stage2_report.md`
- manifest: `<work-dir>/pipeline_manifest.json`

## 문서 읽는 순서

- 전체 구조 요약: `docs/00_전체_흐름_요약_가이드.md`
- 구축 문서: `docs/02_*`
- DB 및 로그 표준: `docs/03_로그_표준과_DB_구조.md`
- 운영 기준: `docs/04_로그_적재_및_운영.md`
- 분석 전략: `docs/05_Export_LLM_분석_전략.md`
- fingerprint 보류 결정: `docs/99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md`

## 보조 설명 문서

스크립트별 역할과 입력·출력 관계를 빠르게 확인하려면 아래 문서를 참고합니다.

- `docs/06_통합_스크립트_설명.md`
