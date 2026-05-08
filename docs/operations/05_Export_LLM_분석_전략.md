# 05_Export_LLM_분석_전략

- 문서 상태: 분석 기준 문서
- 목적: export, prepare, stage1, stage2의 데이터 구조와 해석 기준을 정리한다.

실제 운영 명령은 [01_운영_기준_실행_가이드.md](./01_운영_기준_실행_가이드.md)를 본다.
스크립트별 역할과 입출력 개요는 [06_통합_스크립트_설명_정리본.md](./06_통합_스크립트_설명_정리본.md)를 본다.
설계 결정과 해석 한계는 [99_POST_body_visibility_한계와_해석_기준.md](../design/99_POST_body_visibility_한계와_해석_기준.md), [99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md](../design/99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md)를 본다.

## 1. 현재 파이프라인

수동 흐름:

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

통합 실행:

- `run_analysis_pipeline.py`는 prepare -> stage1 -> stage2를 묶는 통합 실행 입구다.
- `run_analysis_pipeline.py`는 `--export-input`, `--llm-input`, `--stage1-results`에서 시작할 수 있다.
- `--export-input` one-shot 실행에서는 `--prepare-source-tables=auto`가 기본이다.
  - `meta.table_option=security/access/error`이면 해당 table로 고정
  - `meta.table_option=all`이면 `counts > 0` 우선, 없으면 `data` row 존재 기준으로 포함 table을 자동 선택
  - resume 시작점 또는 export JSON read 실패 시 `security` fallback
  - 사용자가 `--prepare-source-tables`를 명시하면 explicit override가 우선
- `--dry-run`으로 실제 LLM API 호출 없이 구조 검증이 가능하다.
- 실행 후 `pipeline_manifest.json`을 생성한다.

## 2. 로그 역할

- `security`: 기본 prepare 입력, 분석 기본 입력
- `error`: 5xx 또는 `request_id`/`error_link_id` 연계 확인용 보조 입력
- `access`: 운영 확인과 기준선 비교용 보조 입력

- 수동 `prepare_llm_input.py` 기준 기본 prepare 입력은 `security`다.
- `run_analysis_pipeline.py --export-input` 경로에서는 `--prepare-source-tables=auto`가 기본이며 export JSON `meta.table_option/counts/data`로 prepare 포함 table을 결정한다.
- `error`와 `access`는 수동 prepare에서는 `--include-source-tables`, pipeline에서는 `--prepare-source-tables`(explicit override)로 포함 범위를 조정할 수 있다.
- `access`를 현재 주 입력처럼 보지 않는다.

## 3. export 기준

- 입력 시간: KST
- DB 조회: UTC로 변환 후 수행
- 출력 시간: KST ISO-8601 문자열
- 기본 `--table`: `security`
- 상위 키: `meta`, `counts`, `data`

주요 옵션:

- `--table`
- `--today`
- `--date`
- `--start`
- `--end`
- `--out`
- `--out-dir`
- `--test-connection`

파일명 기준:

- `{table}_{date}_kst.json`
- `{table}_{start}_to_{end}_kst.json`

실제 명령은 [01_운영_기준_실행_가이드.md](./01_운영_기준_실행_가이드.md)를 우선한다.

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

추가 기준:

- `--include-source-tables`로 `security,error` 등 포함 범위를 조정할 수 있다.
- `--write-filtered-out` 사용 시 `<base>_filtered_out_rows.json`을 저장한다.
- 같은 incident 중복 row를 dedup 한다.
- context-only 문맥을 보존한다.
- context-only 문맥은 성공/침해 단정 근거가 아니라 후보 밖, 저신호, 반복 행위 문맥을 Stage2에 전달하기 위한 구조다.

`<base>_llm_input.json`의 주요 상위 키 예시:

- `meta`
- `noise_summary`
- `candidate_group_summary`
- `analysis_candidates`
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

위 context summary 계열은 현재 코드 기준의 주요 예시이며, 완전한 고정 schema 전체 목록으로 단정하지 않는다.

### 4.1 로그 가시성 한계와 POST body blind spot

현재 파이프라인은 Apache 공통/security 로그 표면에 직접 남는 신호를 우선 사용한다. 따라서 아래와 같은 신호에는 비교적 강하다.

- `query_string`
- `raw_request_target`
- `status_code`
- `response_body_bytes`
- `resp_content_type`
- `500` 오류
- `UNION`, `SELECT`, SQL 주석 같은 공격 토큰이 요청 라인이나 쿼리스트링에 직접 남는 경우

반대로 공격 신호가 `POST` JSON body 내부에만 있고, Apache 공통/security 로그 표면에는 직접 드러나지 않는 경우는 현재 구조의 blind spot이 될 수 있다. 특히 auth bypass 성공형 요청처럼 로그에 `POST /rest/user/login`, `200`, `application/json`, 일반적인 응답 크기 정도만 남고 payload 자체가 보이지 않는 경우에는 prepare 단계에서 후보화가 누락될 수 있다.

이 한계는 모델이 payload 의미를 해석하지 못해서라기보다, LLM에 전달되기 전 단계에서 확보 가능한 데이터 가시성 범위가 좁기 때문에 발생한다. 즉 현재 baseline은 "Apache 공통/security 로그를 기반으로 어디까지 분류·요약할 수 있는가"를 평가하는 구조이며, 상류에서 body-derived signal을 추가하면 평가 질문 자체가 달라진다.

자세한 기준은 [99_POST_body_visibility_한계와_해석_기준.md](../design/99_POST_body_visibility_한계와_해석_기준.md)를 본다.

## 5. `analysis_candidates` 핵심 필드

대표 필드:

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

실제 전체 필드는 prepare 코드 기준을 따르며, 위 목록은 현재 운영 해석에 자주 쓰는 대표 필드다.

## 6. stage1 기준

기본값:

- 기본 `--mode`: `routine`
- `routine`: `gpt-5.4-mini`
- `milestone`: `gpt-5.4`
- `presentation`: `gpt-5.4`
- 기본 `--reasoning-effort`: `none`
- 기본 `--candidate-limit`: `0`
- 기본 `--max-evidence-items`: `8`

주요 옵션:

- `--provider`
- `--model`
- `--candidate-limit`
- `--max-evidence-items`
- `--reasoning-effort`
- `--dry-run`
- `--store`

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

dry-run 주의:

- `llm_stage1_classifier.py --dry-run`은 실제 API 호출 없이 요청 계획/preview 성격의 결과를 만든다.
- 실제 실행 예시는 [01_운영_기준_실행_가이드.md](./01_운영_기준_실행_가이드.md)를 본다.

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

일반 출력:

- `<base>_stage2_report_input.json`
- `<base>_stage2_report.json`
- `<base>_stage2_report.md`

실패 또는 parse error 시 생성될 수 있는 진단 출력:

- `<base>_stage2_report_error.json`
- `<base>_stage2_report_raw_error.json`

`<base>_stage2_report_input.json`의 주요 상위 키 예시:

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
- `supporting_events`

필요 시 아래 context summary 계열이 함께 포함될 수 있다.

- `static_baseline_summaries`
- `crawler_baseline_summaries`
- `sensitive_path_probe_summaries`
- `mixed_baseline_scanner_summaries`
- `ip_behavior_aggregates`
- `auth_behavior_summaries`
- `method_behavior_summaries`
- `protocol_anomaly_summaries`

현재 운영 기준에서는 `KNOWN_ASSET_IPS`를 기본 필수로 보지 않는다.

해석 기준:

- prepare와 stage1은 `raw_request`, `raw_request_target`, `raw_log`, `request_id` 같은 raw evidence를 더 직접적으로 사용한다.
- stage2는 사건 요약형 입력을 바탕으로 운영자용 보고서를 생성한다.
- stage2는 raw evidence 원문 뷰어가 아니라 사건형 요약 보고서다.
- 따라서 stage2 입력에는 전체 raw 원문 대신 최소 evidence만 제한적으로 포함한다.
- 현재 stage2 incident brief에는 기존 사건 요약 필드에 더해 `reason_hints`, `user_agent`, `raw_request`, 짧은 `raw_log_excerpt`가 최소 보강될 수 있다.
- 따라서 stage2 결과는 최종 증거가 아니라 운영자 의사결정용 요약 보고서로 해석한다.
- suspicious/high incident는 `request_id` 기반 raw log 대조 절차와 함께 해석한다.
- 운영자는 `request_id`로 `apache_security_logs.raw_log` 원문을 조회하고, 같은 시간대 `apache_error_logs` 및 앱 로그를 대조해 payload 정황, 도구 사용 정황, 서버 반응, 성공 정황을 구분해야 한다.
- Anthropic 경로에서는 JSON 출력이 길어지면 `stop_reason=max_tokens`로 truncation이 날 수 있으므로 stop reason 확인이 중요하다.
- error/raw_error 진단 출력은 실패 또는 parse error 상황에서만 생성될 수 있으며, 일반 성공 출력의 고정 산출물로 보지 않는다.

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
- `--stop-after`로 prepare/stage1/stage2 중단이 가능하다.
- `--dry-run`으로 실제 LLM API 호출 없이 구조 검증이 가능하다.
- `--keep-going`으로 오류가 나도 가능한 범위에서 manifest를 남길 수 있다.
- `pipeline_manifest.json`이 생성된다.
- manifest에는 입력, 단계별 command, 산출물 경로, provider, known asset IP 등이 기록된다.

## 9. 현재 보수 해석 기준

path traversal 계열에서는 아래 순서로 본다.

1. `resp_content_type`
2. `response_body_bytes`
3. `raw_request_target`
4. `path_normalized_from_raw_request`
5. `likely_html_fallback_response`

`resp_html_*`는 현재 보류 또는 선택 항목이다.

핵심 근거처럼 사용하지 않는다. 자세한 기준은 [99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md](../design/99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md)를 본다.

## 10. 문서 역할 경계

- 이 문서는 데이터 구조와 분석 기준을 설명한다.
- 실제 운영 명령 복붙은 [01_운영_기준_실행_가이드.md](./01_운영_기준_실행_가이드.md)로 모은다.
- 스크립트별 역할, 입력, 출력 개요는 [06_통합_스크립트_설명_정리본.md](./06_통합_스크립트_설명_정리본.md)를 본다.
- 설계 결정과 해석 한계는 [99_POST_body_visibility_한계와_해석_기준.md](../design/99_POST_body_visibility_한계와_해석_기준.md), [99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md](../design/99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md)를 본다.
