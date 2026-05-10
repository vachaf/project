# Apache 웹 로그 사건형 분석 요약 (2026-05-10 11:29:44~11:30:56 KST)

- 생성 시각: 2026-05-10T11:36:27.731+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-05-10T11:29:44.000+09:00 ~ 2026-05-10T11:30:56.000+09:00
- known asset IP: 192.168.56.1, 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
같은 출발지 IP(192.168.56.1)에서 짧은 시간에 경로 이탈 시도와 SQLi 유사 요청이 각각 1건씩 관찰되었습니다. 다만 이 IP는 known asset로 분류되어 내부 테스트, 자체 호출, 운영 점검 가능성을 함께 고려해야 하며, Apache 로그 표면만으로 실제 파일 노출이나 DB 영향은 확인되지 않았습니다.

## 2. 경영 요약
- 분석 구간 동안 총 37건이 관찰됐고, 이 중 2건이 후보 사건으로 분류되었습니다.
- 핵심 후보는 `/view?file=../../etc/passwd` 형태의 경로 이탈 시도와 `/products?id=1 OR 1=1` 형태의 boolean 기반 SQLi 시도입니다.
- 동일 IP에서 robots.txt, sitemap.xml, 정적 자산, 제품/카테고리 탐색이 함께 보여 baseline/crawler 문맥도 존재합니다.
- 전체 맥락상 재현성 있는 탐색 패턴은 보이지만, Apache 로그만으로 성공적인 침해나 실제 유출은 단정할 수 없습니다.

## 3. 파이프라인 요약
- 전체 export row 수: 37
- 1차 후보 row 수: 2
- distinct incident 수: 2
- filtered out row 수: 35
- filtered out 비집계 row 수: 35
- noise 집계 그룹 수: 0
- static baseline summary 수: 1
- crawler baseline summary 수: 1
- sensitive path probe summary 수: 0
- mixed baseline/scanner summary 수: 0
- ip behavior aggregate 수: 1
- auth behavior summary 수: 0
- method behavior summary 수: 0
- protocol anomaly summary 수: 0
- stage1 성공/오류: 2 / 0
- verdict 분포: {"suspicious_path_traversal": 1, "suspicious_sqli": 1}
- severity 분포: {"medium": 2}
- 대표 source table 분포: {"security": 2}
- filtered_out 세부 분포: {"benign_normal_search": 26, "low_signal_fuzzing": 9}
- 후보 밖 주요 카테고리: benign_normal_search 26건 (74.3%), low_signal_fuzzing 9건 (25.7%)

## 4. 핵심 발견
- **경로 이탈 시도 1건 관찰** [medium] - `/view?file=../../etc/passwd` 형태의 디렉터리 이탈 패턴이 보이며, 응답은 200이지만 `text/html`과 fallback 정황이 함께 있어 실제 파일 노출 성공으로는 해석하지 않았습니다. known asset IP에서 발생했으므로 내부 테스트 또는 운영 점검 가능성도 함께 고려해야 합니다.
- **boolean 기반 SQLi 시도 1건 관찰** [medium] - `/products?id=1 OR 1=1` 형태의 전형적인 SQLi 패턴이 관찰되었습니다. 다만 200 응답과 HTML 응답만으로 DB 영향, 우회 성공, 데이터 노출은 확인되지 않아 시도 탐지 수준으로 보는 것이 적절합니다. 이 역시 known asset IP에서 발생했습니다.
- **정상/준정상 탐색 문맥이 함께 존재** [info] - 같은 IP에서 robots.txt, sitemap.xml, 정적 자산, 제품/카테고리 탐색이 다수 관찰되어 baseline 또는 crawler-like 문맥이 형성되어 있습니다. 이는 후보 사건의 존재를 약화시키는 근거라기보다, 같은 출발지에서 정상 탐색과 의심 요청이 혼재했음을 보여주는 보조 문맥입니다.

## 5. 주목할 사건
- request_id=af_tthajr9BZugnMrfrGxAAAAAQ | src_ip=192.168.56.1 | verdict=suspicious_path_traversal | severity=medium
  - 이유: 디렉터리 이탈 경로가 직접 포함된 요청으로, 파일 접근을 노린 시도로 해석할 수 있습니다. 다만 200 응답과 HTML fallback 정황이 있어 실제 파일 노출 성공은 확인되지 않았습니다.
  - uri=/view | method=GET | status=200 | score=10 | log_time=2026-05-10T11:30:14.160 09:00
  - incident_ref=request_id:af_tthajr9BZugnMrfrGxAAAAAQ|table:security|log_id:31918|candidate:0 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: `/view?file=../../etc/passwd` 형태로 디렉터리 이탈 경로가 직접 포함되어 있어 path traversal 시도로 보는 것이 타당합니다. 다만 응답은 `text/html`이고 `likely_html_fallback_response`가 true이며 200 상태코드만으로 실제 파일 노출 성공은 단정할 수 없어, 성공 여부는 분리해 해석해야 합니다.
- request_id=af_ttxajr9BZugnMrfrGxQAAAAU | src_ip=192.168.56.1 | verdict=suspicious_sqli | severity=medium
  - 이유: `OR 1=1` 구조의 SQLi 유사 패턴이 보이는 요청으로, 주입 시도 가능성이 높습니다. 하지만 Apache 로그만으로 DB 영향이나 우회 성공은 증명되지 않습니다.
  - uri=/products | method=GET | status=200 | score=5 | log_time=2026-05-10T11:30:15.382 09:00
  - incident_ref=request_id:af_ttxajr9BZugnMrfrGxQAAAAU|table:security|log_id:31919|candidate:1 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: 쿼리 문자열에 `id=1 OR 1=1` 형태의 전형적인 boolean-based SQLi 패턴이 보이고, 전처리 힌트도 `sqli:or_true`와 `sqli:boolean_true_condition`을 지지합니다. 다만 200 응답과 HTML 응답만으로 실제 영향이나 DB 오류는 확인되지 않아, 시도 탐지 수준으로 보는 것이 적절합니다.

## 6. 주목할 출발지 IP
- 192.168.56.1: 2건의 후보 사건이 모두 이 IP에서 발생했으며, 동시에 static/crawler baseline 문맥과 low-signal 탐색성 요청이 함께 관찰되었습니다. known asset로 분류되어 내부 테스트나 운영 점검 가능성을 반드시 함께 검토해야 합니다.

참고: 위 출발지 IP 중 일부는 known asset 목록과 일치하므로, 실제 공격자 IP 로 단정하지 말고 내부 테스트/자체 호출 여부를 먼저 확인해야 합니다.

## 7. 후보 밖 문맥 요청
후보 밖으로는 benign_normal_search 26건(74.3%), low_signal_fuzzing 9건(25.7%)이 걸러졌습니다. 즉, 전체 요청의 상당 부분은 정상 비교군 또는 낮은 신호의 탐색성 요청으로 정리되었고, 후보 사건 2건은 그 위에 얹혀 있는 의심 요청으로 해석하는 것이 적절합니다. 다만 filtered_out_breakdown이 존재하므로 후보 밖 요청 분포 자체도 무시하면 안 됩니다.

정책:
- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.
- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.
- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.
- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.

후보 밖 탐색성 요청 분포:
- low_signal_fuzzing: 9건 (25.7%)

## 8. Static baseline context
- 아래 항목은 context-only 이며 개별 incident 승격이나 baseline outcome 확정 근거가 아닙니다.
- static_baseline_summaries 의 request 수는 같은 src_ip 와 static/health/browse baseline 시간창 기준 관찰 수입니다.
- src_ip=192.168.56.1 | window=2026-05-10T11:29:52.513 09:00 ~ 2026-05-10T11:30:48.417 09:00 | window_requests=17 | asset_categories=robots_txt, sitemap_xml, css_asset, health_check, javascript_asset, normal_get | status_counts={"200": 17}
  - reason_hints=baseline:robots_txt, baseline:no_crawler_policy_inference, baseline:sitemap_xml, baseline:no_site_structure_inference, baseline:static_asset, baseline:static_css, baseline:health_check, baseline:no_health_status_inference, baseline:static_js, baseline:no_js_execution_inference
  - 해석: static/health/browse baseline 관찰 문맥으로만 본다.
  - 제한: status, bytes, content_type 만으로 static file 존재, robots/sitemap 내용, JS 실행, file exposure, health 정상 여부를 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 9. Crawler baseline context
- 아래 항목은 context-only 이며 개별 incident 승격이나 crawler authenticity 확정 근거가 아닙니다.
- crawler_baseline_summaries 의 request 수는 같은 src_ip 와 crawler-like UA/browse baseline 시간창 기준 관찰 수입니다.
- src_ip=192.168.56.1 | window=2026-05-10T11:29:52.513 09:00 ~ 2026-05-10T11:30:51.484 09:00 | window_requests=22 | ua_families=googlebot_like, bingbot_like, generic_crawler | path_categories=robots_txt, category_browse, sitemap_xml, product_browse, normal_get | status_counts={"200": 22}
  - reason_hints=crawler_like:robots_txt, crawler_like:no_crawler_policy_inference, crawler_like:category_browse, crawler_like:no_page_existence_inference, crawler_like:sitemap_xml, crawler_like:no_site_structure_inference, crawler_like:googlebot_like_ua, crawler_like:ua_spoofable, crawler_like:no_crawler_authenticity_inference, crawler_like:product_browse
  - 해석: crawler-like baseline 또는 low-signal crawl context 로만 본다.
  - 제한: User-Agent spoof 가능성, robots/sitemap 내용, site structure, page existence, attack success 를 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 10. Mixed baseline/scanner context
- 관찰된 mixed_baseline_scanner_summaries 없음

## 11. IP behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 severity 상향 근거가 아닙니다.
- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수이며, auth behavior count 와 직접 합산하지 않습니다.
- src_ip=192.168.56.1 | window=2026-05-10T11:29:52.513 09:00 ~ 2026-05-10T11:30:51.484 09:00 | window_requests=37 | distinct_paths=19 | 4xx_ratio=0.00 | 5xx_count=0
  - attempted_categories=path_traversal, dir_probe, sqli
  - sensitive_path_hits=/config/backup
  - reason_hints=ip_behavior:multi_path_burst, ip_behavior:multiple_attack_categories
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
- **P1** 두 후보 incident의 원본 로그를 request_id 기준으로 재검토하고, 같은 출발지 IP의 전후 요청과 묶어 시간 순서를 확인하십시오.
  - 근거: 경로 이탈과 SQLi 패턴이 같은 IP에서 연속 관찰되어 단발성 오입력인지, 내부 점검인지, 반복 탐색인지 구분이 필요합니다.
- **P1** 192.168.56.1이 known asset인 점을 반영해 내부 테스트/운영 점검 여부를 우선 확인하십시오.
  - 근거: known asset이면 외부 공격자 단정이 부적절하며, 실제 조치 방향이 달라질 수 있습니다.
- **P2** 애플리케이션의 `/view`와 `/products` 파라미터에 대해 경로 이탈/SQLi 방어 규칙이 실제로 적용되는지 점검하십시오.
  - 근거: 같은 패턴이 재발할 경우 실제 악용 시도로 이어질 수 있어 입력 검증과 파라미터 처리 방어를 확인할 필요가 있습니다.
- **P2** 같은 IP에서 관찰된 robots.txt, sitemap.xml, 정적 자산, 제품/카테고리 탐색 로그를 함께 보며 정상 탐색과 의심 요청의 혼재 여부를 확인하십시오.
  - 근거: baseline/crawler 문맥이 함께 있어 단순 스캔인지, 운영 점검인지, 사용자 탐색인지 구분하는 데 도움이 됩니다.
- **P3** 유사 요청에 대해 경보 룰을 유지하되, known asset에서는 낮은 우선순위 검토 또는 운영 점검 태그를 함께 사용하십시오.
  - 근거: 오탐 부담을 줄이면서도 반복 시도를 놓치지 않기 위한 운영적 균형이 필요합니다.

## 16. 신뢰도와 한계
- 신뢰도는 후보 패턴 식별에 한해서는 높지만, 실제 침해 성공 여부에 대해서는 낮습니다.
- Apache 로그만으로는 response body 원문, DB 결과, 서버 내부 파일 내용, 브라우저 실행 여부를 확인할 수 없습니다.
- 같은 IP가 known asset이므로 내부 테스트, 자체 호출, 운영 점검 가능성을 반드시 함께 고려해야 합니다.
- baseline/crawler 문맥과 의심 요청이 같은 시간창에 섞여 있어, 단일 공격 체인으로 과도하게 해석하지 않도록 주의가 필요합니다.

## 17. 발표용 한 줄 정리
이번 구간에서는 known asset IP에서 경로 이탈과 SQLi 유사 요청이 각각 1건씩 관찰됐습니다. 다만 로그 표면상 성공 증거는 없고, 정상 탐색 문맥도 함께 있어 내부 테스트 가능성을 포함한 신중한 추가 확인이 필요합니다.
