# Apache 로그 2차 분석 요약: 내부 자산 IP의 경량 정찰 및 민감 경로 탐색 정황

- 생성 시각: 2026-05-05T11:52:12.572+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-05-03T19:59:11.000+09:00 ~ 2026-05-03T19:59:39.000+09:00
- known asset IP: 192.168.56.1, 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
전체 분석 구간(2026-05-03 19:59:11 ~ 19:59:39 KST)에서 1건의 저위험 정찰성 incident와, 같은 출발지 IP에서 관찰된 후보 밖 탐색성 요청·기준선(baseline) 요청이 함께 보였습니다. 현재 근거만으로는 침해 성공이나 민감 정보 유출을 단정할 수 없고, known asset IP에서 발생했기 때문에 내부 테스트/운영 점검 가능성도 함께 열어두는 것이 적절합니다.

## 2. 경영 요약
- 분석 시간대에 192.168.56.1에서 `/server-status` 접근 시도 1건이 403으로 차단되었고, 정찰/탐색 성격으로 분류되었습니다.
- 같은 IP에서 `.env`, `backup.zip`, `wp-login.php` 등 민감 경로를 짧은 시간에 반복 조회한 정황이 있었지만, Apache 로그만으로 실제 파일 노출이나 로그인 성공은 확인되지 않았습니다.
- 또한 `/`, `/robots.txt`, `/favicon.ico`, `/assets/*`, `/sitemap.xml`, `/products/` 같은 일반/기준선 요청도 함께 보여, 정상 조회와 탐색성 요청이 섞인 혼합 문맥으로 보입니다.
- 출발지 IP가 known asset 목록과 일치하므로 외부 공격자 단정은 피하고, 내부 점검 또는 자동화된 테스트 가능성을 함께 고려해야 합니다.

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
- **관리자성 경로(`/server-status`)에 대한 저위험 정찰 시도** [low] - `/server-status`에 대한 GET 요청이 403으로 차단되었고, 추가 페이로드나 후속 성공 증거는 보이지 않았습니다. 이는 접근 통제에 의해 막힌 정찰/탐색 정황으로 해석하는 것이 타당하며, 침해 성공으로 볼 근거는 부족합니다.
- **같은 출발지에서 민감 경로 중심의 짧은 시간 탐색이 관찰됨** [low] - `.env`, `backup.zip`, `wp-login.php`, `server-status` 같은 민감/관리 경로가 같은 IP에서 연속적으로 관찰되었습니다. 다만 Apache 로그 표면에서는 본문 원문이 없고, 200 응답도 실제 파일 노출이나 앱 존재를 확정하지 않으므로 시도 수준으로 해석해야 합니다.
- **기준선 요청과 탐색 요청이 혼재한 혼합 문맥** [info] - `/`, `/robots.txt`, `/favicon.ico`, `/assets/app.js`, `/assets/style.css`, `/sitemap.xml`, `/products/` 같은 정상/기준선성 요청이 동시에 보입니다. 이는 같은 IP의 동작을 단일 공격 체인으로 묶기보다 정상 조회와 탐색성 요청이 섞인 관찰 문맥으로 보는 것이 적절합니다.

## 5. 주목할 사건
- request_id=afcqk19TYrFq3zXDH9-VqQAAAM4 | src_ip=192.168.56.1 | verdict=suspicious_scan | severity=low
  - 이유: `/server-status`는 일반적으로 관리자용 상태 페이지로, 외부에서 접근을 시도한 정황 자체가 정찰성 요청으로 볼 수 있습니다. 다만 403 차단이 확인되어 실제 노출이나 침해 성공으로 확대 해석할 근거는 없습니다.
  - uri=/server-status | method=GET | status=403 | score=5 | log_time=2026-05-03T19:59:31.089 09:00
  - incident_ref=request_id:afcqk19TYrFq3zXDH9-VqQAAAM4|table:security|log_id:31740|candidate:0 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: `/server-status`는 일반적으로 관리자용 상태 페이지로, 외부에서 접근을 시도한 정황이 정찰/탐색에 가깝습니다. 다만 쿼리스트링이나 추가 공격 페이로드는 없고 403으로 차단되어 실제 침해나 노출 성공을 단정할 근거는 부족합니다.

## 6. 주목할 출발지 IP
- 192.168.56.1: 이 IP에서 유일한 top incident가 관찰되었고, 동시에 `.env`, `backup.zip`, `wp-login.php`, `/server-status` 등을 포함한 민감 경로 탐색과 일반 기준선 요청이 함께 보였습니다. known asset IP이므로 내부 테스트, 자체 호출, 운영 점검 가능성을 반드시 함께 고려해야 합니다.

참고: 위 출발지 IP 중 일부는 known asset 목록과 일치하므로, 실제 공격자 IP 로 단정하지 말고 내부 테스트/자체 호출 여부를 먼저 확인해야 합니다.

## 7. 후보 밖 문맥 요청
후보 밖으로 정리된 요청은 `benign_normal_search` 12건(정상/기준선 조회), `low_signal_dir_probe` 6건(민감 경로 존재 확인 수준의 탐색), `low_signal_fuzzing` 3건으로 분포합니다. 특히 `low_signal_dir_probe`는 `.env`, `backup.zip` 같은 민감 경로 반복 접근 정황을 보여 주지만, 성공 여부나 실제 파일 노출을 의미하지는 않습니다. `benign_normal_search`는 공격 징후가 아니라 같은 endpoint의 정상 비교군으로 보는 것이 맞습니다.

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
- **P1** 192.168.56.1의 요청 시퀀스를 원시 로그와 함께 재검토하고, 해당 IP가 내부 테스트/운영 점검용인지 자산 관리 정보와 대조하라.
  - 근거: known asset IP이므로 외부 공격 단정은 위험합니다. 내부 자동화, 스캐너, 운영 점검과 실제 탐색을 구분해야 합니다.
- **P2** `.env`, `backup.zip`, `wp-login.php`, `/server-status` 접근에 대한 접근 로그와 WAF/리버스 프록시 로그를 상관분석하여 반복성, 시간대, 동일 세션 여부를 확인하라.
  - 근거: 현재는 시도 정황만 보이며 성공 여부는 확인되지 않습니다. 추가 상관분석이 있어야 실제 위험도를 평가할 수 있습니다.
- **P3** 관리자성 경로와 민감 파일 경로에 대한 외부 접근 차단 정책, 네트워크 ACL, 인증 요구 여부를 점검하라.
  - 근거: 정찰성 탐색이 반복될 경우, 차단 정책이 충분한지 사전 점검이 필요합니다.
- **P3** 분석 대상 시간대의 `low_signal_dir_probe`와 `benign_normal_search`를 운영 점검 트래픽과 분리 기록해 두라.
  - 근거: 추후 동일 패턴이 재발했을 때 정상 점검과 탐색을 구분하는 기준선이 됩니다.

## 16. 신뢰도와 한계
- Apache 로그 요약본만 사용했기 때문에 raw response body, 실제 파일 내용, 브라우저 실행 결과, 인증 성공 여부는 확인할 수 없습니다.
- `200` 상태코드가 있더라도 본문 원문이 없으면 파일 노출 성공으로 볼 수 없고, 특히 `.env`/`backup.zip`/`wp-login.php` 접근은 탐색 시도 수준으로 해석해야 합니다.
- 출발지 IP가 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 배제할 수 없습니다.
- top incident는 1건의 low severity 정찰성 요청이며, 이를 넘어선 medium/high 수준의 침해 증거는 현재 제공 자료에 없습니다.

## 17. 발표용 한 줄 정리
이번 구간은 ‘침해 성공’보다 ‘내부 자산에서 관찰된 경량 정찰 및 민감 경로 탐색’으로 보는 것이 정확합니다. 핵심은 403으로 차단된 `/server-status` 접근과, 같은 IP에서 섞여 나온 민감 경로 탐색·정상 기준선 요청을 분리해 해석하는 것입니다.
