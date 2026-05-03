# Apache 웹 로그 사건형 분석 요약 (2026-05-03 19:59:11~19:59:39 KST)

- 생성 시각: 2026-05-03T20:18:02.295+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-05-03T19:59:11.000+09:00 ~ 2026-05-03T19:59:39.000+09:00
- known asset IP: 192.168.56.1, 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
해당 시간대에는 동일 출발지 IP에서 민감 경로를 빠르게 둘러보는 정찰성 패턴이 관찰되었습니다. 다만 제공된 Apache 로그 요약만으로 실제 파일 노출, 계정 탈취, 취약점 악용 성공은 확인되지 않았고, 특히 출발지 IP가 known asset 범위에 있어 내부 테스트나 운영 점검 가능성도 함께 고려해야 합니다.

## 2. 경영 요약
- 분석 구간 내 총 45개 행 중 후보로 승격된 사건은 1건이며, 나머지는 후보 밖 탐색성 요청 또는 정상 비교군으로 정리되었습니다.
- 핵심 사건은 `/server-status` 접근 시도로, `GenericScanner/1.0` UA와 403 응답이 함께 보여 Apache 상태 페이지를 겨냥한 정찰로 해석하는 것이 타당합니다.
- 같은 IP에서 `.env`, `backup.zip`, `wp-login.php` 등 민감 경로 접근이 짧은 시간에 반복되어 디렉터리/민감 경로 probing 정황이 뚜렷합니다.
- 그러나 200 응답이나 text/html 응답만으로 실제 파일 노출이나 서비스 존재를 단정할 수는 없으며, 본문 원문이 없어 성공 여부는 확정하지 않습니다.
- 출발지 IP `192.168.56.1`은 known asset 과 일치하므로 외부 공격자 단정 대신 내부 테스트, 자체 호출, 운영 점검 가능성을 반드시 병기해야 합니다.

## 3. 파이프라인 요약
- 전체 export row 수: 45
- 1차 후보 row 수: 1
- distinct incident 수: 1
- filtered out row 수: 21
- filtered out 비집계 row 수: 12
- noise 집계 그룹 수: 3
- static baseline summary 수: 1
- crawler baseline summary 수: 1
- sensitive path probe summary 수: 1
- mixed baseline/scanner summary 수: 1
- ip behavior aggregate 수: 1
- auth behavior summary 수: 0
- method behavior summary 수: 0
- protocol anomaly summary 수: 0
- stage1 성공/오류: 1 / 0
- verdict 분포: {"suspicious_scan": 1}
- severity 분포: {"low": 1}
- 대표 source table 분포: {"security": 1}
- filtered_out 세부 분포: {"benign_normal_search": 12, "low_signal_dir_probe": 6, "low_signal_fuzzing": 3}
- 후보 밖 주요 카테고리: benign_normal_search 12건 (57.1%), low_signal_dir_probe 6건 (28.6%), low_signal_fuzzing 3건 (14.3%)

## 4. 핵심 발견
- **민감 경로 정찰과 `/server-status` 탐색이 같은 출발지에서 관찰됨** [medium] - 동일 IP `192.168.56.1`에서 짧은 시간 구간 동안 `.env`, `backup.zip`, `wp-login.php`, `/server-status`가 함께 관찰되었습니다. 이는 단일 침해 체인이라기보다 여러 민감/관리 경로를 빠르게 훑는 reconnaissance 또는 directory probing 문맥에 가깝습니다.
- **실제 노출이나 악용 성공은 확인되지 않음** [info] - `/server-status`는 403으로 차단되었고, 다른 반복 경로의 200 응답도 Apache 로그 표면만으로 파일 노출이나 앱 내부 정보 노출 성공을 확정할 수 없습니다. 반복되는 `text/html` 응답은 fallback HTML 가능성도 배제할 수 없습니다.
- **known asset IP 이므로 내부성 트래픽 가능성 고려 필요** [low] - `192.168.56.1`은 known asset 목록과 일치합니다. 따라서 공격자 단정은 피해야 하며, 개발/운영 점검, 로컬 테스트, 자체 스캐너 실행 가능성을 함께 검토해야 합니다.

## 5. 주목할 사건
- request_id=afcqk19TYrFq3zXDH9-VqQAAAM4 | src_ip=192.168.56.1 | verdict=suspicious_scan | severity=low
  - 이유: `/server-status`는 Apache 상태 페이지 정찰의 전형적인 대상이며, `GenericScanner/1.0` UA와 403 응답 조합은 탐색 시도로 해석할 근거가 있습니다. 다만 차단 정황일 뿐이라 실제 취약점 악용이나 침해 성공으로는 볼 수 없고, known asset IP이므로 내부 테스트 가능성도 함께 고려해야 합니다.
  - uri=/server-status | method=GET | status=403 | score=5 | log_time=2026-05-03T19:59:31.089 09:00
  - incident_ref=request_id:afcqk19TYrFq3zXDH9-VqQAAAM4|table:security|log_id:31740|candidate:0 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: `/server-status`는 Apache 상태 페이지를 겨냥한 전형적인 정찰 대상이며, `GenericScanner/1.0` 사용자 에이전트와 403 응답이 함께 보여 탐색 시도로 보는 것이 타당합니다. 다만 제공된 정보만으로는 실제 취약점 악용이나 추가 진행을 확인할 수 없어 심각도는 낮게 부여합니다.

## 6. 주목할 출발지 IP
- 192.168.56.1: 유일한 후보 사건의 출발지이며, 동시에 `.env`, `backup.zip`, `wp-login.php`, `/server-status` 같은 민감 경로 접근과 정상 browse baseline 이 함께 관찰되었습니다. known asset IP 이므로 내부 테스트/운영 점검 가능성을 병기해야 합니다.

참고: 위 출발지 IP 중 일부는 known asset 목록과 일치하므로, 실제 공격자 IP 로 단정하지 말고 내부 테스트/자체 호출 여부를 먼저 확인해야 합니다.

## 7. 후보 밖 문맥 요청
필터링된 21건 중 `benign_normal_search` 12건은 정상 비교군 또는 reference baseline으로 해석하는 것이 적절합니다. `low_signal_dir_probe` 6건과 `low_signal_fuzzing` 3건은 후보 밖 탐색성 요청으로 보아야 하며, 같은 IP의 정찰성 흐름을 보조하는 문맥일 뿐 별도 침해 사건으로 승격할 근거는 약합니다. 특히 반복되는 200 text/html 응답은 fallback HTML 가능성을 우선 검토해야 하며, 200 응답만으로 민감 파일 노출이나 서비스 실재를 단정할 수 없습니다.

정책:
- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.
- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.
- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.
- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.

후보 밖 탐색성 요청 분포:
- low_signal_dir_probe: 6건 (28.6%)
- low_signal_fuzzing: 3건 (14.3%)

Context-only probing sequence 요약:
- src_ip=192.168.56.1 | window=2026-05-03T19:59:19.092 09:00 ~ 2026-05-03T19:59:37.059 09:00 | requests=9 | distinct_paths=4 | sample_paths=/.env, /wp-login.php, /backup.zip, /server-status
  - 반복 응답 힌트: dominant_response_body_bytes=75002 | dominant_count=8
  - 해석: Multiple low-signal directory probing paths from the same source in a short window. Context only; do not treat as confirmed compromise.

## 8. Static baseline context
- 아래 항목은 context-only 이며 개별 incident 승격이나 baseline outcome 확정 근거가 아닙니다.
- static_baseline_summaries 의 request 수는 같은 src_ip 와 static/health/browse baseline 시간창 기준 관찰 수입니다.
- src_ip=192.168.56.1 | window=2026-05-03T19:59:16.031 09:00 ~ 2026-05-03T19:59:34.061 09:00 | window_requests=12 | asset_categories=normal_get, javascript_asset, favicon, robots_txt, css_asset, sitemap_xml | status_counts={"200": 12}
  - reason_hints=baseline:normal_get, baseline:static_asset, baseline:static_js, baseline:no_js_execution_inference, baseline:favicon, baseline:robots_txt, baseline:no_crawler_policy_inference, baseline:static_css, baseline:sitemap_xml, baseline:no_site_structure_inference
  - 해석: static/health/browse baseline 관찰 문맥으로만 본다.
  - 제한: status, bytes, content_type 만으로 static file 존재, robots/sitemap 내용, JS 실행, file exposure, health 정상 여부를 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 9. Crawler baseline context
- 아래 항목은 context-only 이며 개별 incident 승격이나 crawler authenticity 확정 근거가 아닙니다.
- crawler_baseline_summaries 의 request 수는 같은 src_ip 와 crawler-like UA/browse baseline 시간창 기준 관찰 수입니다.
- src_ip=192.168.56.1 | window=2026-05-03T19:59:16.031 09:00 ~ 2026-05-03T19:59:35.066 09:00 | window_requests=8 | ua_families=googlebot_like, generic_crawler | path_categories=normal_get, robots_txt, sitemap_xml, product_browse | status_counts={"200": 8}
  - reason_hints=crawler_like:normal_browse, baseline:normal_get, crawler_like:robots_txt, crawler_like:no_crawler_policy_inference, crawler_like:googlebot_like_ua, crawler_like:ua_spoofable, crawler_like:no_crawler_authenticity_inference, crawler_like:sitemap_xml, crawler_like:no_site_structure_inference, crawler_like:generic_crawler_ua
  - 해석: crawler-like baseline 또는 low-signal crawl context 로만 본다.
  - 제한: User-Agent spoof 가능성, robots/sitemap 내용, site structure, page existence, attack success 를 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 10. Mixed baseline/scanner context
- 아래 항목은 context-only 이며 baseline/static/crawler-like 와 scanner-like 를 하나의 성공 공격으로 합치는 근거가 아닙니다.
- mixed_baseline_scanner_summaries 의 request 수는 같은 src_ip 와 mixed baseline/scanner 시간창 기준 관찰 수입니다.
- src_ip=192.168.56.1 | window=2026-05-03T19:59:16.031 09:00 ~ 2026-05-03T19:59:37.059 09:00 | window_requests=22 | baseline_contexts=normal_get, static_baseline, crawler_baseline | scanner_contexts=sensitive_path_probe | path_categories=normal_get, static_asset, favicon, sensitive_env_file, sensitive_wp_login, sensitive_backup_artifact, robots_txt, sensitive_server_status, crawler_robots_txt, sitemap_xml | status_counts={"200": 21, "403": 1}
  - reason_hints=mixed_context:benign_and_scanner_like, mixed_context:keep_baseline_and_scanner_separate, mixed_context:no_single_attack_inference, mixed_context:no_success_inference, mixed_context:no_file_exposure_inference, mixed_context:no_crawler_authenticity_inference, mixed_context:no_page_existence_inference, mixed_context:static_baseline_present, mixed_context:crawler_baseline_present, mixed_context:normal_browse_present
  - 해석: 같은 window 안에서 baseline/static/crawler-like 와 sensitive path probe 가 함께 관찰된 mixed context 로만 본다.
  - 제한: file exposure, app presence, crawler authenticity, page existence, attack success 를 단정하지 않고, 단일 성공 공격으로 합치지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 11. IP behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 severity 상향 근거가 아닙니다.
- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수이며, auth behavior count 와 직접 합산하지 않습니다.
- src_ip=192.168.56.1 | window=2026-05-03T19:59:16.031 09:00 ~ 2026-05-03T19:59:37.059 09:00 | window_requests=22 | distinct_paths=11 | 4xx_ratio=0.05 | 5xx_count=0
  - attempted_categories=dir_probe
  - sensitive_path_hits=/.env, /wp-login.php, /backup.zip, /server-status
  - reason_hints=ip_behavior:multi_path_burst, ip_behavior:sensitive_path_focus
  - 해석: 같은 src_ip 에서 scanning-like 또는 reconnaissance-like behavior 가 관찰된 문맥으로만 본다.
  - 제한: context_only_no_success_inference
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 12. Auth behavior context
- 관찰된 auth_behavior_summaries 없음

## 13. Method behavior context
- 관찰된 method_behavior_summaries 없음

## 14. Protocol anomaly context
- 관찰된 protocol_anomaly_summaries 없음

## 15. 권고 조치
- **P1** 동일 출발지 IP `192.168.56.1`의 트래픽을 내부 테스트/운영 점검 여부와 함께 즉시 대조하고, 해당 시점의 자동화 도구 실행 기록이나 변경 작업 이력을 확인한다.
  - 근거: known asset IP 이므로 외부 공격으로 단정하기보다 내부성 트래픽 가능성을 먼저 배제해야 하며, 정찰 패턴의 성격도 운영 맥락에 따라 달라질 수 있습니다.
- **P2** `/server-status`, `/.env`, `/backup.zip`, `/wp-login.php` 접근에 대해 원본 Apache 로그와 상위 애플리케이션 로그를 추가 상관분석하고, 실제 본문 노출 여부를 확인한다.
  - 근거: 현재 요약만으로는 200 응답의 의미를 확정할 수 없고, file disclosure 나 관리 페이지 노출 성공 여부는 원문 로그와 앱 로그가 있어야 판단할 수 있습니다.
- **P2** 같은 IP에서 반복 관찰된 민감 경로 접근에 대해 WAF/IDS 룰과 차단 정책을 점검하고, `/server-status` 같은 관리 경로는 접근제어를 재확인한다.
  - 근거: 정찰성 probing 이 확인되므로 관리·민감 경로의 외부/비인가 접근을 제한하는 기본 통제가 제대로 동작하는지 확인할 필요가 있습니다.
- **P3** 필터링된 `low_signal_dir_probe`와 `low_signal_fuzzing` 분포를 별도 보존해 추세를 관찰하고, 동일 출발지에서 재발하는지 주기적으로 모니터링한다.
  - 근거: 현재는 낮은 신호의 탐색성 요청 수준이지만, 같은 출발지에서 지속되면 후속 고신호 사건과 결합될 수 있기 때문입니다.

## 16. 신뢰도와 한계
- 이 보고서는 전처리 및 1차 분류된 요약 데이터만 기반으로 작성되었으며, raw POST body 나 응답 본문 원문은 확인할 수 없습니다.
- `200 text/html` 응답은 정상 라우팅, 빈 PHP 출력, 로그인/에러 템플릿, fallback HTML일 수 있어 파일 노출 성공 근거로 사용하지 않았습니다.
- `/server-status`의 403은 차단 정황을 보여주지만, 그것만으로 공격 성공이나 서버 취약점 존재를 입증하지는 않습니다.
- 출발지 IP가 known asset 범위에 있어 내부 테스트, 자체 호출, 운영 점검 가능성이 있습니다.
- 정찰성 요청과 정상 browse baseline 이 같은 시간대에 혼재하므로, 공격자 신원이나 실제 침해 여부는 추가 상관분석이 필요합니다.

## 17. 발표용 한 줄 정리
이번 구간의 핵심은 ‘성공한 침해’가 아니라 ‘known asset IP에서 관찰된 민감 경로 정찰’입니다. 발표에서는 `/server-status` 중심의 탐색 시도, `.env`·`backup.zip`·`wp-login.php` 반복 접근, 그리고 내부 테스트 가능성을 함께 균형 있게 설명하는 것이 적절합니다.
