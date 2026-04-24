# 05_Export_LLM_분석_전략

- 문서 상태: 분석 기준 문서
- 목적: export, prepare, stage1, stage2의 데이터 구조와 해석 기준을 정리한다.

실제 운영 명령은 [docs/01_운영_기준_실행_가이드.md](docs/01_운영_기준_실행_가이드.md)를 본다.

## 1. 현재 파이프라인

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

## 2. 로그 역할

- `security`: 분석 기본 입력
- `error`: 5xx 또는 `request_id`/`error_link_id` 연계 확인용 보조 입력
- `access`: 운영 확인과 기준선 비교용 보조 입력

## 3. export 기준

- 입력 시간: KST
- DB 조회: UTC로 변환 후 수행
- 출력 시간: KST ISO-8601 문자열
- 기본 `--table`: `security`
- 상위 키: `meta`, `counts`, `data`

파일명 기준:

- `{table}_{date}_kst.json`
- `{table}_{start}_to_{end}_kst.json`

운영 기준 경로는 `docs/01`을 우선한다.

## 4. prepare 기준

기본값:

- 기본 `--include-source-tables`: `security`
- 기본 `--min-score`: `4`
- 기본 `--min-repeat-aggregate`: `3`
- 로그인 계열은 기본적으로 `401/403` 실패 신호에 강하다. `POST /rest/user/login`의 `200 application/json` 성공은 일반 성공까지 과승격하지 않도록, JSON 응답 크기와 비브라우저/automation/공격성 힌트가 결합될 때만 별도 후보 점수를 준다.

출력 파일:

- `<base>_llm_input.json`
- `<base>_analysis_candidates.json`
- `<base>_noise_summary.json`
- `<base>_filtered_out_rows.json` 선택

`<base>_llm_input.json` 상위 키:

- `meta`
- `noise_summary`
- `candidate_group_summary`
- `analysis_candidates`

## 5. `analysis_candidates` 핵심 필드

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
- `incident_group_key`
- `merged_row_count`
- `merged_source_tables`
- `merged_log_ids`

## 6. stage1 기준

기본값:

- 기본 `--mode`: `routine`
- `routine`: `gpt-5.4-mini`
- `milestone`: `gpt-5.4`
- `presentation`: `gpt-5.4`
- 기본 `--reasoning-effort`: `none`
- 기본 `--candidate-limit`: `0`
- 기본 `--max-evidence-items`: `8`

출력 파일:

- `<base>_stage1_results.json`
- `<base>_stage1_errors.json`

주요 결과 필드:

- `verdict`
- `severity`
- `confidence`
- `false_positive_possible`
- `reasoning_summary`
- `evidence_fields`
- `recommended_actions`

## 7. stage2 기준

기본값:

- 기본 `--mode`: `routine`
- `routine`: `gpt-5.4-mini`
- `milestone`: `gpt-5.4`
- `presentation`: `gpt-5.4`
- 기본 `--top-incidents`: `12`
- 기본 `--top-noise-groups`: `8`
- 기본 `--top-ips`: `8`
- 기본 `--reasoning-effort`: `none`

출력 파일:

- `<base>_stage2_report_input.json`
- `<base>_stage2_report.json`
- `<base>_stage2_report.md`
- `<base>_stage2_report_error.json`

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

현재 운영 기준에서는 `KNOWN_ASSET_IPS`를 기본 필수로 보지 않는다.

해석 기준:

- prepare와 stage1은 `raw_request`, `raw_request_target`, `raw_log`, `request_id` 같은 raw evidence를 더 직접적으로 사용한다.
- stage2는 사건 요약형 입력을 바탕으로 운영자용 보고서를 생성한다.
- 따라서 stage2 결과는 최종 증거가 아니라 운영자 의사결정용 요약 보고서로 해석한다.
- suspicious/high incident는 `request_id` 기반 raw log 대조 절차와 함께 해석한다.
- Anthropic 경로에서는 JSON 출력이 길어지면 `stop_reason=max_tokens`로 truncation이 날 수 있으므로 stop reason 확인이 중요하다.

## 8. run_analysis_pipeline 기준

시작점:

- `--export-input`
- `--llm-input`
- `--stage1-results`

코드 기본 디렉터리:

- 기본 `--work-dir`: `.`
- 기본 `--processed-dir`: `<work-dir>/data/processed`
- 기본 `--reports-dir`: `<work-dir>/reports`

운영 기준:

- 현재 실제 운영 경로는 `/opt/web_log_analysis/data/processed`와 `/opt/web_log_analysis/reports`
- 따라서 `--work-dir /opt/web_log_analysis`만 지정해도 기본 산출물 경로가 운영 기준과 맞는다

## 9. 현재 보수 해석 기준

path traversal 계열에서는 아래 순서로 본다.

1. `resp_content_type`
2. `response_body_bytes`
3. `raw_request_target`
4. `path_normalized_from_raw_request`
5. `likely_html_fallback_response`

`resp_html_*`는 현재 보류 또는 선택 항목이다.

## 10. 문서 역할 경계

- 이 문서는 데이터 구조와 분석 기준을 설명한다.
- 실제 운영 명령 복붙은 [docs/01_운영_기준_실행_가이드.md](docs/01_운영_기준_실행_가이드.md)로 모은다.
