# 05_Export_LLM_분석_전략

- 문서 상태: 정리본
- 버전: v1.5
- 작성일: 2026-04-09
- 기준 코드:
  - `src/export_db_logs_cli.py`
  - `src/prepare_llm_input.py`
  - `src/llm_stage1_classifier.py`
  - `src/llm_stage2_reporter.py`
  - `src/run_analysis_pipeline.py`

## 1. 목적

현재 `src` 코드 기준으로 DB export, 전처리, stage1 분류, stage2 보고서 생성 흐름을 짧게 정리한다. 이 문서는 설계안이 아니라 현재 동작 기준 문서다.

## 2. 현재 파이프라인

```text
MariaDB(web_logs)
  ↓
export_db_logs_cli.py
  ↓
<base>.json
  ↓
prepare_llm_input.py
  ↓
<base>_llm_input.json
  ↓
llm_stage1_classifier.py
  ↓
<base>_stage1_results.json
  ↓
llm_stage2_reporter.py
  ↓
<base>_stage2_report.md / .json
```

`run_analysis_pipeline.py` 는 위 흐름을 한 번에 실행한다.

## 3. 로그 역할

- `security`: 분석 기본 입력
- `error`: 5xx 또는 `request_id`/`error_link_id` 연계 확인용 보조 입력
- `access`: 운영 확인과 기준선 비교용 보조 입력

routine 분석의 기본 입력은 `security` 다.

## 4. export 기준

### 4.1 시간 처리

- DB 저장 시각은 UTC 기준으로 가정한다.
- 사용자는 KST(`Asia/Seoul`) 기준으로 조회 범위를 입력한다.
- 조회 시 KST 범위를 UTC로 변환해 DB를 조회한다.
- 출력 JSON의 시간 필드는 KST ISO-8601 문자열로 변환된다.

### 4.2 기본 테이블과 옵션

- 기본 `--table`: `security`
- 지원 테이블: `access`, `security`, `error`, `all`
- 지원 시간 옵션:
  - `--today`
  - `--date YYYY-MM-DD`
  - `--start ... --end ...`

### 4.3 export 출력 구조

`export_db_logs_cli.py` 결과 JSON 상위 키:

- `meta`
- `counts`
- `data`

`meta` 주요 필드:

- `database`
- `exported_at`
- `query_timezone`
- `db_timezone`
- `range_mode`
- `start`
- `end_exclusive`
- `start_db_query`
- `end_exclusive_db_query`
- `table_option`
- `limit_per_table`
- `total_count`

`data` 는 항상 `access`, `security`, `error` 배열을 가진다.

### 4.4 export 파일명

- 출력 경로는 작업 루트 기준 `data/raw/` 고정
- 날짜 단위 export: `{table}_{date}_kst.json`
- 시간 범위 export: `{table}_{start}_to_{end}_kst.json`
- 동일 파일명이 있으면 그대로 덮어쓴다.

예시:

```bash
python3 ./src/export_db_logs_cli.py \
  --host 192.168.35.223 \
  --user log_reader \
  --date 2026-04-02 \
  --table security \
  --pretty
```

## 5. prepare 기준

### 5.1 기본값

- 입력: export JSON
- 기본 `--include-source-tables`: `security`
- 기본 `--min-score`: `4`
- 기본 `--min-repeat-aggregate`: `3`

### 5.2 출력 파일

- `<base>_llm_input.json`
- `<base>_analysis_candidates.json`
- `<base>_noise_summary.json`
- `<base>_filtered_out_rows.json` (`--write-filtered-out` 사용 시)

### 5.3 `<base>_llm_input.json` 구조

상위 키:

- `meta`
- `noise_summary`
- `candidate_group_summary`
- `analysis_candidates`

`meta` 주요 필드:

- `query_timezone`
- `analysis_window`
- `source_database`
- `source_table_option`
- `selected_source_tables`
- `analysis_primary_table`
- `exported_at`
- `prepared_at`
- `model_usage_policy`
- `pipeline_policy`
- `thresholds`
- `counts`
- `filtered_out_breakdown`

### 5.4 `analysis_candidates` 실제 핵심 필드

- `source_table`
- `log_id`
- `log_time`
- `src_ip`
- `method`
- `uri`
- `query_string`
- `status_code`
- `score`
- `verdict_hint`
- `reason_hints`
- `request_id`
- `error_link_id`
- `raw_request`
- `user_agent`
- `referer`
- `duration_us`
- `ttfb_us`
- `raw_log`
- `response_body_bytes`
- `resp_content_type`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`
- `hpp_detected`
- `hpp_param_names`
- `embedded_attack_hint`
- `incident_group_key`
- `merged_row_count`
- `merged_source_tables`
- `merged_log_ids`

### 5.5 현재 사용 중인 필드와 보류 필드

현재 분석 파이프라인에서 유지하는 핵심:

- `resp_content_type`
- `response_body_bytes`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`

현재 보류 또는 비핵심:

- `resp_html_norm_fingerprint`
- `resp_html_fingerprint_version`
- `resp_html_baseline_name`
- `resp_html_baseline_match`
- `resp_html_baseline_confidence`
- `resp_html_features_json`

`resp_html_*` 계열은 현재 분석 파이프라인의 핵심 기준이 아니다.

## 6. stage1 기준

### 6.1 기본값

- 기본 `--mode`: `routine`
- `routine`: `gpt-5.4-mini`
- `milestone`: `gpt-5.4`
- `presentation`: `gpt-5.4`
- 기본 `--reasoning-effort`: `none`
- 기본 `--candidate-limit`: `0`
- 기본 `--max-evidence-items`: `8`

### 6.2 출력 파일

- `<base>_stage1_results.json`
- `<base>_stage1_errors.json`

### 6.3 verdict / severity / confidence 스키마

`verdict`:

- `benign_normal`
- `likely_false_positive`
- `suspicious_scan`
- `suspicious_bruteforce`
- `suspicious_sqli`
- `suspicious_xss`
- `suspicious_path_traversal`
- `suspicious_command_injection`
- `suspicious_auth_abuse`
- `server_error_probe`
- `inconclusive`

`severity`:

- `info`
- `low`
- `medium`
- `high`
- `critical`

`confidence`:

- `low`
- `medium`
- `high`

`recommended_actions`:

- `ignore`
- `watch`
- `review_raw_log`
- `review_error_log`
- `correlate_request_id`
- `correlate_src_ip`
- `rate_limit_or_block`
- `investigate_immediately`

## 7. stage2 기준

### 7.1 기본값

- 기본 `--mode`: `routine`
- `routine`: `gpt-5.4-mini`
- `milestone`: `gpt-5.4`
- `presentation`: `gpt-5.4`
- 기본 `--top-incidents`: `12`
- 기본 `--top-noise-groups`: `8`
- 기본 `--top-ips`: `8`
- 기본 `--reasoning-effort`: `none`

### 7.2 출력 파일

- `<base>_stage2_report_input.json`
- `<base>_stage2_report.json`
- `<base>_stage2_report.md`
- `<base>_stage2_report_error.json`

### 7.3 stage2 입력 구조

`<base>_stage2_report_input.json` 상위 키:

- `analysis_context`
- `pipeline_counts`
- `distributions`
- `top_incidents`
- `top_src_ips`
- `top_noise_groups`
- `top_filtered_categories`
- `top_out_of_candidate_recon`
- `stage1_errors_excerpt`
- `asset_context`
- `policy_notes`

stage2는 `request_id` 우선, 없으면 `src_ip + method + uri + status_code + 1초 단위 시각` 기준으로 incident를 묶는다.

## 8. run_analysis_pipeline 기준

### 8.1 시작점

- `--export-input`
- `--llm-input`
- `--stage1-results`

### 8.2 기본 디렉터리

- 기본 `--work-dir`: `.`
- 기본 `--processed-dir`: `<work-dir>/processed`
- 기본 `--reports-dir`: `<work-dir>/reports`
- manifest: `<work-dir>/pipeline_manifest.json`

### 8.3 prepare 기본 전달값

- `--prepare-min-score`: `4`
- `--prepare-min-repeat-aggregate`: `3`
- `--prepare-source-tables`: `security`

예시:

```bash
python3 ./src/run_analysis_pipeline.py \
  --export-input ./data/raw/security_2026-04-02_kst.json \
  --work-dir . \
  --mode routine \
  --pretty
```

## 9. 현재 보수 해석 기준

path traversal 계열에서 현재 문서 기준 보수 해석은 다음 순서로 본다.

1. `resp_content_type`
2. `response_body_bytes`
3. `raw_request_target`
4. `path_normalized_from_raw_request`
5. `likely_html_fallback_response`

`likely_html_fallback_response == true` 이고 `resp_content_type == text/html` 인 경우, fallback HTML 가능성을 우선 검토한다.

`resp_html_*` 는 현재 보류 기능이므로, 값이 있더라도 보조 참고용으로만 본다.

## 10. 현재 미구현 또는 비기본 항목

- HTML fallback fingerprint 값 생성
- `resp_html_*` 기반 분석 주 흐름
- 별도 `bin/` wrapper 스크립트
- `rule_candidate_filter.py`

이 항목들은 현재 표준 운영 기준에서 제외한다.
