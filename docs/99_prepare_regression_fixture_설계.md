# Prepare Regression Fixture 설계

## 목적

- `src/prepare_llm_input.py`의 prepare 단계만 빠르게 회귀 검증한다.
- Stage1/Stage2 LLM 호출 없이 synthetic export JSON을 넣고 `analysis_candidates`, `supporting_events`, `false_positive_review_candidates`, `probing_sequence_summaries`, `sensitive_path_probe_summaries`, `ip_behavior_aggregates`, `filtered_out_rows`의 분류 결과를 확인한다.
- Apache 로그 표면 지표만 사용한 현재 규칙 기반 prepare 동작이 의도와 크게 벗어나지 않는지 smoke 수준으로 확인한다.

## 비목표

- Stage1/Stage2 모델 품질 검증
- response body 원문, DB 조회 결과, 브라우저 실행 여부 기반 성공 판정
- 대규모 탐지 규칙 개편
- 특정 실험 환경 이름이나 라우트 재현에 기대는 fixture 검증

## Synthetic Fixture 우선 이유

- lab 데이터에 포함된 실험 전용 User-Agent, IP, 경로 이름에 회귀 검증이 종속되지 않게 하기 위함이다.
- fixture를 최소 입력으로 통제하면 prepare 단계의 일반화 가능한 신호만 검증하기 쉽다.
- 회귀 실패 시 원인을 규칙 로직과 기대조건 수준에서 바로 파악할 수 있다.

## Fixture 목록

- `b_r2b_double_encoded_sqli`
- `b_r2b_educational_sql_fp`
- `c_html_entity_xss`
- `c_xss_fp_review`
- `d_r3_directory_probing`
- `e_r2_php_wrapper`
- `e_r2_direct_config_path`
- `e_r3_search_attack_and_baseline`
- `f_r1_auth_behavior_context`
- `g_r1_method_behavior_context`
- `g_r2_protocol_anomaly_context`
- `ip_behavior_multi_signal_context`
- `h_r1_static_baseline_context`
- `h_r2_crawler_baseline_context`
- `h_r3_sensitive_path_probe_context`
- `l3_log4shell_ssrf_context`
- `l3_ssti_webshell_context`

## 최소 Row 필드

fixture row는 현재 `prepare_llm_input.py`가 실제로 읽는 필드명에 맞춘다.

- `id`
- `request_id`
- `timestamp` 대신 현재 코드가 읽는 `log_time`, `created_at`
- `src_ip`
- `method`
- `host`, `vhost`
- `uri`
- `query_string`
- `status_code`
- `response_body_bytes`
- `resp_content_type`
- `duration_us`
- `ttfb_us`
- `referer`
- `user_agent`
- `raw_request`
- `raw_log`

## Assert 정책

- 전체 출력 snapshot 비교는 하지 않는다.
- expected JSON은 조건 기반 규칙으로 유지한다.
- 레벨은 `MUST`, `SHOULD`, `MUST_NOT`, `KNOWN_LIMITATION`을 사용한다.
- `MUST` / `MUST_NOT`는 실패를 만든다.
- `SHOULD`와 `KNOWN_LIMITATION`은 경고를 만든다.
- 규칙은 다음 종류를 지원한다.
  - 특정 `request_id`가 특정 컬렉션에 존재하는지
  - 특정 `request_id`가 특정 컬렉션에 존재하지 않는지
  - 특정 항목의 `reason_hints`, `review_reason`, `supporting_role` 등에 일반화된 hint/category substring이 있는지
  - 복수 컬렉션 중 하나에 존재하는지

## 실험환경 특화 금지 원칙

- `lab-*` User-Agent 기반 탐지 금지
- 실제 실험 IP 기반 탐지 금지
- 특정 response size 값 하드코딩 금지
- OpenCart/Juice Shop 이름 기반 하드코딩 금지
- `route=product/search` 같은 전체 endpoint 문자열 기반 assert 금지

fixture는 다음 값을 사용한다.

- 문서용 IP: `198.51.100.x`, `203.0.113.x`
- 일반 UA: `Mozilla/5.0 regression-fixture`
- example.test 계열 host/vhost

## Hint / Category 중심 Assert 원칙

- endpoint 전체 문자열보다 `reason_hints`, `review_reason`, `supporting_role`, `noise_category`, `probing_sequence_summaries`, `ip_behavior_aggregates` 중심으로 검증한다.
- 예시:
  - `encoding:decoded_depth_2`
  - `encoding:double_decoded_sqli`
  - `encoding:html_entity_decoded_xss`
  - `sqli:*`
  - `xss:*`
  - `file_disclosure:php_filter_wrapper`
  - `file_disclosure:base64_source_intent`
  - `file_disclosure:resource_parameter`
  - `benign_normal_search`
  - `supporting_role=reference_baseline`
  - `dir_probe:*`
- `ip_behavior:*`
- `auth_abuse:*`
  - `l3:log4shell`
  - `log4shell:*`
  - `l3:ssrf`
  - `ssrf:*`
  - `l3:ssti`
  - `ssti:*`
  - `l3:webshell_probe`
  - `webshell:*`

## 일반화된 Path / Query 구조 사용 원칙

- OpenCart/Juice Shop route를 재현하지 않는다.
- `/search?q=...`, `/file?target=...`, `/config.php`, `/admin/`, `/backup/` 같은 일반화된 path/query 구조를 사용한다.
- 검색형 시나리오는 `search`, `q`, `query` 계열 파라미터를 사용한다.
- PHP wrapper 시나리오는 `file`, `resource`, `target` 계열 파라미터를 사용한다.

## Prepare CLI 확인 원칙

check 스크립트는 `src/prepare_llm_input.py`의 실제 CLI를 기준으로 작성한다.

- 확인한 옵션:
  - `--input`
  - `--out-dir`
  - `--base-name`
  - `--min-score`
  - `--min-repeat-aggregate`
  - `--include-source-tables`
  - `--write-filtered-out`
  - `--pretty`
- 확인한 출력 파일명 규칙:
  - `<base>_llm_input.json`
  - `<base>_analysis_candidates.json`
  - `<base>_noise_summary.json`
  - `<base>_filtered_out_rows.json`

check 스크립트는 이 규칙을 함수로 해석해서 산출물을 찾는다. 임의의 파일명을 가정하지 않는다.

## Known Limitation

- 2026-04-30 기준 normal search baseline row의 `dir_probe:*` hint 잔존 문제는 해결되었다.
- `e_r3_search_attack_and_baseline` fixture에서는 해당 조건을 `MUST_NOT`으로 회귀 검증한다.
- 2026-04-30 기준 `ip_behavior_aggregates`는 prepare top-level context-only 출력과 Stage2 report input/prompt 반영까지 완료되었다.
- 2026-05-02 기준 `auth_behavior_summaries`는 prepare top-level context-only 출력과 Stage2 dry-run report input 반영까지 완료되었다.
- 2026-05-03 기준 `method_behavior_summaries`는 prepare top-level context-only 출력과 Stage2 dry-run report input 최소 반영까지 완료되었다.
- 2026-05-03 기준 `protocol_anomaly_summaries`는 prepare top-level context-only 출력과 Stage2 dry-run report input 최소 반영까지 완료되었다.
- 2026-05-03 기준 `h_r1_static_baseline_context` fixture 는 `static_baseline_summaries` 생성, `baseline:*` filtered hint 치환, candidate 비승격을 검증한다.
- 2026-05-03 기준 `h_r2_crawler_baseline_context` fixture 는 `crawler_baseline_summaries` 생성, `crawler_like:*` filtered hint 치환, candidate 비승격을 검증한다.
- 2026-05-03 기준 `h_r3_sensitive_path_probe_context` fixture 는 `sensitive_path_probe_summaries` 생성, `sensitive_path:*` filtered hint 치환, `/server-status` representative candidate 축소를 검증한다.
- 2026-04-30 기준 `b_r2b_double_encoded_sqli` expected 는 `encoding:decoded_depth_2` 외에 `sqli:boolean_true_condition` 및 일부 구조 hint(`quote_termination`, `parenthesis_termination`, `comment_sequence`, `xclose_pattern`)를 함께 확인한다.

## `h_r1_static_baseline_context` expected 기준

- 같은 `src_ip`의 300초 window 안에서 `/favicon.ico`, `/robots.txt`, `/sitemap.xml`, `.js`, `.css`, image asset, health-like endpoint, `GET /` baseline 이 함께 관찰되면 `static_baseline_summaries`가 생성되어야 한다.
- summary 는 `context_role=static_baseline_context`, `aggregate_scope=same_src_ip_static_baseline_time_window`, `should_promote_to_candidate=false`를 유지해야 한다.
- `reason_hints`에는 `baseline:favicon`, `baseline:robots_txt`, `baseline:sitemap_xml`, `baseline:static_js`, `baseline:static_css`, `baseline:static_image`, `baseline:health_check`, `baseline:normal_get`, `baseline:no_static_content_inference`가 포함되어야 한다.
- `interpretation_limit`은 `static_content_not_visible_no_attack_inference`를 유지해야 한다.
- `asset_categories_observed`에는 `favicon`, `robots_txt`, `sitemap_xml`, `javascript_asset`, `css_asset`, `image_asset`, `health_check`, `normal_get`가 반영되어야 한다.
- fixture 전체를 개별 `analysis_candidates`로 승격하지 않아야 한다.
- static baseline context 로 덮인 filtered row 는 `dir_probe:*` 단독 hint 대신 `baseline:*` 중심 hint 를 가져야 한다.

## `g_r1_method_behavior_context` expected 기준

- 같은 `src_ip`의 300초 window 안에서 `OPTIONS`, `TRACE`, `PUT`, `DELETE` 같은 risky method 2종 이상이거나 risky method 와 `HEAD`/`GET` baseline 이 함께 관찰되면 `method_behavior_summaries`가 생성되어야 한다.
- summary 는 `context_role=method_behavior_context`, `aggregate_scope=same_src_ip_method_time_window`, `should_promote_to_candidate=false`를 유지해야 한다.
- `reason_hints`에는 `method_probe:options`, `method_probe:trace`, `method_probe:put`, `method_probe:delete`, `baseline:normal_head`, `baseline:normal_get`, `method_probe:mixed_method_sequence`, `method_probe:no_method_success_inference`가 포함되어야 한다.
- `interpretation_limit`은 `no_method_success_inference_from_apache_logs`를 유지해야 한다.
- `method_counts`에는 `OPTIONS`, `TRACE`, `PUT`, `DELETE`, `HEAD`, `GET`가 반영되어야 한다.
- `risky_methods_observed`에는 `OPTIONS`, `TRACE`, `PUT`, `DELETE`가, `baseline_methods_observed`에는 `HEAD`, `GET`가 포함되어야 한다.
- fixture 전체를 개별 `analysis_candidates`로 승격하지 않아야 하며, `HEAD`/`GET` baseline row 는 특히 candidate 로 과승격되면 안 된다.
- method behavior context 로 덮인 filtered row 는 `dir_probe:*` 단독 hint 대신 `method_probe:*` 또는 `baseline:*` hint 를 가져야 한다.

## `h_r2_crawler_baseline_context` expected 기준

- 같은 `src_ip`의 300초 window 안에서 crawler-like `User-Agent`가 2건 이상 관찰되거나, crawler-like `User-Agent`와 함께 `robots.txt`, `sitemap.xml`, product/category browse, normal `GET /` baseline 이 함께 관찰되면 `crawler_baseline_summaries`가 생성되어야 한다.
- summary 는 `context_role=crawler_baseline_context`, `aggregate_scope=same_src_ip_crawler_like_time_window`, `should_promote_to_candidate=false`를 유지해야 한다.
- `reason_hints`에는 `crawler_like:googlebot_like_ua`, `crawler_like:generic_crawler_ua`, `crawler_like:robots_txt`, `crawler_like:sitemap_xml`, `crawler_like:product_browse`, `crawler_like:category_browse`, `crawler_like:ua_spoofable`, `crawler_like:no_crawler_authenticity_inference`, `crawler_like:no_site_structure_inference`, `crawler_like:no_page_existence_inference` 같은 보수적 힌트가 포함되어야 한다.
- `interpretation_limit`은 `crawler_ua_spoofable_no_content_or_page_existence_inference`를 유지해야 한다.
- `crawler_like_user_agent_families`에는 `googlebot_like`, `generic_crawler`가 반영되어야 하며, `path_categories_observed`에는 `robots_txt`, `sitemap_xml`, `product_browse`, `category_browse`, `normal_get`가 반영되어야 한다.
- fixture 전체를 개별 `analysis_candidates`로 승격하지 않아야 한다.
- crawler baseline context 로 덮인 filtered row 는 `/products/`, `/category/` 같은 browse row 에서 `dir_probe:*` 단독 hint 대신 `crawler_like:*` 중심 hint 를 가져야 한다.

## `h_r3_sensitive_path_probe_context` expected 기준

- 같은 `src_ip`의 300초 window 안에서 `/wp-login.php`, `/wp-admin/`, `/.env`, `/phpinfo.php`, `/server-status`, `/backup.zip` 같은 scanner-like sensitive path family 가 2종 이상 관찰되거나 같은 path 가 반복되면 `sensitive_path_probe_summaries`가 생성되어야 한다.
- summary 는 `context_role=sensitive_path_probe_context`, `aggregate_scope=same_src_ip_sensitive_path_time_window`, `should_promote_to_candidate=false`를 유지해야 한다.
- `reason_hints`에는 `sensitive_path:wp_login`, `sensitive_path:wp_admin`, `sensitive_path:env_file`, `sensitive_path:phpinfo`, `sensitive_path:server_status`, `sensitive_path:backup_artifact`, `sensitive_path:no_file_exposure_inference`, `sensitive_path:no_server_status_exposure_inference`, `sensitive_path:no_success_inference` 같은 보수적 힌트가 포함되어야 한다.
- `interpretation_limit`은 `sensitive_path_probe_no_file_or_app_exposure_inference`를 유지해야 한다.
- `path_categories_observed`에는 `wp_login`, `wp_admin`, `env_file`, `phpinfo`, `server_status`, `backup_artifact`가 반영되어야 한다.
- `wp-login`, `/.env`, `/backup.zip` 같은 low-signal sensitive path row 는 개별 `analysis_candidates`로 과승격되면 안 된다.
- repeated `/server-status` candidate 가 남더라도 1개 대표 이하로 유지하고, summary/context 힌트가 함께 반영되어야 한다.
- sensitive path context 로 덮인 filtered row 는 `dir_probe:*` 단독 hint 대신 `sensitive_path:*` 중심 hint 를 가져야 한다.

## `g_r2_protocol_anomaly_context` expected 기준

- 같은 `src_ip`의 300초 window 안에서 invalid method, `HTTP/1.0`, bad protocol version, missing Host, odd Host, long path 중 하나 이상이 관찰되면 `protocol_anomaly_summaries`가 생성되어야 한다.
- summary 는 `context_role=protocol_anomaly_context`, `aggregate_scope=same_src_ip_protocol_anomaly_time_window`, `should_promote_to_candidate=false`를 유지해야 한다.
- `reason_hints`에는 `protocol_anomaly:unsupported_method`, `protocol_anomaly:http10_request`, `protocol_anomaly:legacy_protocol_observation`, `protocol_anomaly:bad_protocol_version`, `protocol_anomaly:missing_host`, `protocol_anomaly:odd_host`, `protocol_anomaly:long_path`, `protocol_anomaly:no_success_inference` 같은 보수적 힌트가 포함되어야 한다.
- `interpretation_limit`은 `protocol_anomaly_context_only_no_success_inference`를 유지해야 한다.
- `anomaly_types_observed`에는 `unsupported_method`, `http10_request`, `bad_protocol_version`, `missing_host`, `odd_host`, `long_path`가 반영되어야 한다.
- fixture 전체를 개별 `analysis_candidates`로 승격하지 않아야 한다.
- protocol anomaly context 로 덮인 filtered row 는 `baseline:normal_get` 단독 hint 대신 `protocol_anomaly:*` 또는 `method_probe:unsupported_method` hint 를 가져야 한다.

## `f_r1_auth_behavior_context` expected 기준

- 같은 `src_ip`와 auth endpoint family 의 300초 window 안에서 `POST` auth 요청이 3건 이상이거나 `401` 반복, `401/200` 혼재가 있으면 `auth_behavior_summaries`가 생성되어야 한다.
- summary 는 `context_role=auth_behavior_context`, `aggregate_scope=same_src_ip_auth_endpoint_time_window`, `should_promote_to_candidate=false`를 유지해야 한다.
- `reason_hints`에는 `auth_abuse:repeated_auth_endpoint`, `auth_abuse:repeated_401`, `auth_abuse:mixed_401_200_sequence`, `auth_abuse:post_body_not_visible`, `auth_abuse:no_auth_success_inference` 같은 보수적 힌트가 포함되어야 한다.
- `interpretation_limit`은 `post_body_not_visible_no_auth_success_inference`를 유지해야 한다.
- 반복 `401` auth row 전체를 개별 incident 로 유지하지 않고 representative candidate 수를 줄여야 한다.
- representative candidate 는 최소 1개 이상 남아야 하며, 나머지 반복 `401` row 중 일부는 `supporting_role=auth_behavior_support`, `supporting_reason=covered_by_auth_behavior_summary` 형태의 context-only `supporting_events`로 내려가야 한다.
- 해당 supporting event 는 `auth_abuse:covered_by_auth_behavior_summary` hint 를 포함해야 한다.
- `200` auth filtered row 는 candidate 로 과승격되면 안 되고 `dir_probe:*` hint 를 유지하면 안 된다.
- 일반 browse `GET` row 는 auth abuse candidate 로 과승격되면 안 된다.

## `ip_behavior_multi_signal_context` expected 기준

- 같은 `src_ip`의 300초 window 안에서 다중 path, 높은 4xx 비율, 혼합 공격 category, 민감 경로 접근이 함께 관찰되면 `ip_behavior_aggregates`가 생성되어야 한다.
- aggregate 는 `context_role=ip_behavior_context`, `aggregate_scope=same_src_ip_time_window`, `should_promote_to_candidate=false`를 유지해야 한다.
- `reason_hints`에는 `ip_behavior:*` 계열이 포함되어야 한다.
- `attack_categories_attempted`에는 `sqli`, `xss`, `dir_probe` 같은 요약 category 가 반영되어야 한다.
- `/admin/`, `/backup/`, `/config.php` 같은 low-signal probe row는 개별 `analysis_candidates`로 과승격되면 안 된다.
- 같은 fixture 안의 SQLi/XSS payload row는 기존 규칙대로 candidate 로 유지될 수 있다.

## L3 fixture 기준

### `l3_log4shell_ssrf_context`

- `${jndi:ldap://...}` 구조는 `analysis_candidates`에 남아야 한다.
- `reason_hints`에는 `l3:log4shell`, `log4shell:jndi_lookup`, `log4shell:ldap_callback`이 포함되어야 한다.
- metadata target URL 파라미터 요청은 `analysis_candidates`에 남아야 한다.
- `reason_hints`에는 `l3:ssrf`, `ssrf:url_parameter`, `ssrf:metadata_ip`, `ssrf:cloud_metadata_target`이 포함되어야 한다.

### `l3_ssti_webshell_context`

- `{{7*7}}` 구조는 `analysis_candidates`에 남아야 한다.
- `reason_hints`에는 `l3:ssti`, `ssti:template_expression`, `ssti:jinja_expression`이 포함되어야 한다.
- `/upload/shell.php?cmd=id` 구조는 `analysis_candidates`에 남아야 한다.
- `reason_hints`에는 `l3:webshell_probe`, `webshell:script_filename`, `webshell:cmd_parameter`이 포함되어야 한다.
