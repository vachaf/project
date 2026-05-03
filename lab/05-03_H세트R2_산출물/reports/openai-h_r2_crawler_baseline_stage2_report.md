# Apache 웹 로그 2차 사건형 분석 요약

- 생성 시각: 2026-05-03T15:09:28.584+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-05-03T14:48:07.000+09:00 ~ 2026-05-03T14:48:22.000+09:00
- known asset IP: 192.168.56.1, 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
분석 시간 구간(2026-05-03 14:48:07~14:48:22, Asia/Seoul)에서는 확정적인 침해 사건은 확인되지 않았습니다. 주된 관찰은 내부 자산으로 보이는 출발지 IP 192.168.56.1에서 짧은 시간에 robots.txt, sitemap.xml, 정상 GET, 제품/카테고리 탐색이 함께 나타난 저신호 탐색/기준선 문맥이며, 후보로 승격된 고신호 사건은 없습니다. 다만 crawler-like User-Agent와 다중 경로 접근이 함께 보여 내부 테스트 또는 운영 점검 가능성도 함께 열어두는 해석이 적절합니다.

## 2. 경영 요약
- 총 16건 중 8건이 후보 밖으로 필터링되었고, 분석 후보 사건은 0건이었습니다.
- 192.168.56.1에서 robots.txt, sitemap.xml, /products/, /category/, / 로 이어지는 짧은 탐색 패턴이 관찰됐지만, 현재 로그만으로는 공격 성공이나 노출 성공을 말할 근거가 없습니다.
- crawller-like User-Agent와 내부 자산 IP가 겹치므로 자동화 점검, 내부 테스트, 자체 호출 가능성을 함께 고려해야 합니다.

## 3. 파이프라인 요약
- 전체 export row 수: 16
- 1차 후보 row 수: 0
- distinct incident 수: 0
- filtered out row 수: 8
- filtered out 비집계 row 수: 8
- noise 집계 그룹 수: 0
- static baseline summary 수: 1
- crawler baseline summary 수: 1
- ip behavior aggregate 수: 1
- auth behavior summary 수: 0
- method behavior summary 수: 0
- protocol anomaly summary 수: 0
- stage1 성공/오류: 0 / 0
- filtered_out 세부 분포: {"low_signal_fuzzing": 5, "benign_normal_search": 3}
- 후보 밖 주요 카테고리: low_signal_fuzzing 5건 (62.5%), benign_normal_search 3건 (37.5%)

## 4. 핵심 발견
- **후보 사건은 없고, 주된 패턴은 내부 자산의 저신호 탐색 문맥** [info] - 분석 구간 내 전체 16건 중 8건이 필터링되었고, 나머지는 개별 incident 로 승격되지 않았습니다. 관찰된 핵심은 192.168.56.1에서의 짧은 시간 내 다중 경로 요청이며, 현재 정보만으로는 악성 행위로 단정하기 어렵습니다.
- **robots.txt / sitemap.xml / 제품·카테고리 탐색은 기준선 또는 크롤링 유사 문맥** [low] - 같은 출발지에서 robots.txt, sitemap.xml, /products/, /category/, / 가 연속적으로 보이지만, Apache 로그 표면만으로 실제 크롤러 정체나 사이트 구조 노출을 확정할 수는 없습니다. 내부 테스트, 점검성 트래픽, 또는 크롤러 유사 자동화일 수 있습니다.
- **후보 밖 탐색성 요청은 low_signal_fuzzing 과 benign_normal_search 로 구성** [info] - 필터링된 8건 중 5건은 low_signal_fuzzing, 3건은 benign_normal_search 로 집계되었습니다. 이는 저신호 탐색과 정상 비교군이 함께 존재했음을 뜻하며, 현재 보고서는 이들을 개별 침해 사건으로 보지 않습니다.

## 5. 주목할 사건
- request_id=N/A | src_ip=192.168.56.1 | verdict=분석 후보 사건 없음 | severity=info
  - 이유: 현재 구간에서는 확정적인 공격 사건이 식별되지 않았습니다. 다만 내부 자산 IP에서 짧은 시간에 여러 기본 경로와 탐색성 요청이 관찰되어, 운영 점검이나 내부 테스트 문맥인지 추가 확인이 필요합니다.
  - incident_ref=N/A

## 6. 주목할 출발지 IP
- 192.168.56.1: known_asset_ip와 일치하는 출발지이며, robots.txt/sitemap.xml/제품·카테고리 탐색이 짧은 시간에 함께 관찰되었습니다. 내부 테스트, 자체 호출, 운영 점검 또는 자동화된 점검 트래픽 가능성을 함께 고려해야 합니다.

## 7. 후보 밖 문맥 요청
필터링된 후보 밖 요청은 low_signal_fuzzing 5건과 benign_normal_search 3건으로 구성되었습니다. 이는 저신호 탐색과 정상 비교군이 함께 존재했음을 의미합니다. 정상 비교군은 low_signal_fuzzing과 분리해서 해석해야 하며, 현재 구간에서는 뚜렷한 공격 시그니처보다 탐색/기준선 성격이 더 강합니다.

정책:
- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.
- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.
- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.
- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.

후보 밖 탐색성 요청 분포:
- low_signal_fuzzing: 5건 (62.5%)

## 8. Static baseline context
- 아래 항목은 context-only 이며 개별 incident 승격이나 baseline outcome 확정 근거가 아닙니다.
- static_baseline_summaries 의 request 수는 같은 src_ip 와 static/health/browse baseline 시간창 기준 관찰 수입니다.
- src_ip=192.168.56.1 | window=2026-05-03T14:48:12.344 09:00 ~ 2026-05-03T14:48:19.392 09:00 | window_requests=5 | asset_categories=robots_txt, sitemap_xml, normal_get | status_counts={"200": 5}
  - reason_hints=baseline:robots_txt, baseline:no_crawler_policy_inference, baseline:sitemap_xml, baseline:no_site_structure_inference, baseline:normal_get, baseline:no_static_content_inference
  - 해석: static/health/browse baseline 관찰 문맥으로만 본다.
  - 제한: status, bytes, content_type 만으로 static file 존재, robots/sitemap 내용, JS 실행, file exposure, health 정상 여부를 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 9. Crawler baseline context
- 아래 항목은 context-only 이며 개별 incident 승격이나 crawler authenticity 확정 근거가 아닙니다.
- crawler_baseline_summaries 의 request 수는 같은 src_ip 와 crawler-like UA/browse baseline 시간창 기준 관찰 수입니다.
- src_ip=192.168.56.1 | window=2026-05-03T14:48:12.344 09:00 ~ 2026-05-03T14:48:21.395 09:00 | window_requests=8 | ua_families=googlebot_like, generic_crawler | path_categories=robots_txt, sitemap_xml, product_browse, category_browse, normal_get | status_counts={"200": 8}
  - reason_hints=crawler_like:googlebot_like_ua, crawler_like:ua_spoofable, crawler_like:no_crawler_authenticity_inference, crawler_like:robots_txt, crawler_like:no_crawler_policy_inference, crawler_like:sitemap_xml, crawler_like:no_site_structure_inference, crawler_like:generic_crawler_ua, crawler_like:product_browse, crawler_like:no_page_existence_inference
  - 해석: crawler-like baseline 또는 low-signal crawl context 로만 본다.
  - 제한: User-Agent spoof 가능성, robots/sitemap 내용, site structure, page existence, attack success 를 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 10. IP behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 severity 상향 근거가 아닙니다.
- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수이며, auth behavior count 와 직접 합산하지 않습니다.
- src_ip=192.168.56.1 | window=2026-05-03T14:48:12.344 09:00 ~ 2026-05-03T14:48:21.395 09:00 | window_requests=8 | distinct_paths=5 | 4xx_ratio=0.00 | 5xx_count=0
  - attempted_categories=-
  - sensitive_path_hits=-
  - reason_hints=ip_behavior:multi_path_burst
  - 해석: 같은 src_ip 에서 scanning-like 또는 reconnaissance-like behavior 가 관찰된 문맥으로만 본다.
  - 제한: context_only_no_success_inference
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 11. Auth behavior context
- 관찰된 auth_behavior_summaries 없음

## 12. Method behavior context
- 관찰된 method_behavior_summaries 없음

## 13. Protocol anomaly context
- 관찰된 protocol_anomaly_summaries 없음

## 14. 권고 조치
- **P1** 192.168.56.1의 트래픽 목적을 운영팀/점검 주체와 대조해 내부 테스트, 자동화 점검, 자체 호출 여부를 확인하십시오.
  - 근거: known asset IP 이며 crawler-like/탐색성 요청이 함께 보여 공격자 단정은 부적절합니다. 업무 목적 트래픽인지 확인하면 오탐을 빠르게 제거할 수 있습니다.
- **P2** 같은 IP의 robots.txt, sitemap.xml, /products/, /category/ 접근이 정상 크롤링·점검 패턴인지 서버 접근 로그와 애플리케이션 로그를 함께 대조하십시오.
  - 근거: Apache 로그만으로는 실제 크롤러 인증, 페이지 존재 여부, 내용 열람 여부를 확인할 수 없습니다. 추가 상관분석이 필요합니다.
- **P3** 필터링된 low_signal_fuzzing 및 benign_normal_search의 원 요청 샘플을 보존하고, 향후 동일 출발지에서 고신호 행위가 이어지는지 모니터링하십시오.
  - 근거: 현재는 사건 승격 근거가 약하지만, 동일 IP에서 패턴이 반복되면 이후에는 더 강한 recon 맥락으로 재평가할 수 있습니다.

## 15. 신뢰도와 한계
- 이 보고서는 전처리·1차 분류 요약만을 기반으로 하며, 원본 Apache raw body와 애플리케이션 응답 본문은 확인하지 못했습니다.
- known_asset IP와의 일치 때문에 내부 테스트/운영 점검 가능성을 반드시 함께 고려해야 하며, 공격자 단정은 피했습니다.
- 후보 사건이 0건이므로 확정된 침해, 파일 노출, 인증 성공, 외부 전송 성공 등은 본 보고서에서 주장하지 않았습니다.
- static_baseline_summaries, crawler_baseline_summaries, ip_behavior_aggregates 는 모두 context-only 로 해석했으며 개별 incident 로 승격하지 않았습니다.

## 16. 발표용 한 줄 정리
이번 구간은 침해 사건보다 내부 자산에서의 탐색·기준선 트래픽이 중심입니다. 즉시 필요한 것은 공격 대응보다 출발지 목적 확인과 추가 상관분석이며, 현재 로그만으로는 성공적인 악용 정황을 확정할 수 없습니다.
