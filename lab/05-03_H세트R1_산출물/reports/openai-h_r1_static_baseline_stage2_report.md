# Apache 웹 로그 2차 분석 요약: 내부 테스트성/기준선 트래픽 중심, 고신호 침해 징후 없음

- 생성 시각: 2026-05-03T14:16:58.486+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-05-03T13:52:26.000+09:00 ~ 2026-05-03T13:52:40.000+09:00
- known asset IP: 192.168.56.1, 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
분석 시간 구간(2026-05-03 13:52:26~13:52:40, Asia/Seoul)에서는 확정적인 침해 사건이 식별되지 않았습니다. 다만 동일 출발지 IP(192.168.56.1)에서 짧은 시간에 여러 정적/기본 경로와 상태 점검 경로를 조회한 기준선성 트래픽이 관찰되었고, 후보 밖 탐색성 요청이 1건 포함되었습니다. 해당 IP는 known asset 범주와 일치하므로 내부 테스트, 자체 호출, 운영 점검 가능성을 우선 함께 고려하는 것이 타당합니다.

## 2. 경영 요약
- 총 16건 중 후보 사건은 0건이었고, 대부분은 정상 비교군(benign_normal_search) 또는 경미한 탐색성 요청(low_signal_fuzzing)으로 정리되었습니다.
- 주요 관찰은 192.168.56.1의 짧은 시간대 다경로 요청으로, favicon/robots.txt/sitemap.xml/정적 자산/health check/루트 경로를 포함한 기준선성 접근이었습니다.
- 동일 IP는 known asset 이므로 외부 공격자 단정은 부적절하며, 내부 테스트나 운영 점검 트래픽일 가능성을 함께 봐야 합니다.
- 응답 코드 500이 1회 있었지만 Apache 로그 표면만으로는 오류 원인이나 침해 성공을 단정할 수 없습니다.
- 현재 자료만으로는 파일 유출, XSS 실행, 인증 성공, 프로토콜 우회 성공을 입증할 근거가 없습니다.

## 3. 파이프라인 요약
- 전체 export row 수: 16
- 1차 후보 row 수: 0
- distinct incident 수: 0
- filtered out row 수: 8
- filtered out 비집계 row 수: 8
- noise 집계 그룹 수: 0
- static baseline summary 수: 1
- ip behavior aggregate 수: 1
- auth behavior summary 수: 0
- method behavior summary 수: 0
- protocol anomaly summary 수: 0
- stage1 성공/오류: 0 / 0
- filtered_out 세부 분포: {"benign_normal_search": 7, "low_signal_fuzzing": 1}
- 후보 밖 주요 카테고리: benign_normal_search 7건 (87.5%), low_signal_fuzzing 1건 (12.5%)

## 4. 핵심 발견
- **확정 incident 없음** [info] - 분석 창 내에서 top-level incident 후보는 0건이었고, stage1 성공/에러 집계도 제공된 범위에서는 고신호 사건이 형성되지 않았습니다. 따라서 본 구간은 사건 대응보다는 관찰된 기준선 트래픽과 후보 밖 탐색성 요청의 문맥 정리에 가깝습니다.
- **known asset IP의 짧은 다경로 접근** [info] - 192.168.56.1에서 8건이 7초 내에 관찰되었고, /, /api/health, /assets/app.js, /assets/style.css, /favicon.ico, /images/logo.png, /robots.txt, /sitemap.xml 등 정적/기본 경로가 포함되었습니다. 이는 reconnaissance라기보다 내부 테스트, 자체 호출, 운영 점검 또는 정상 기준선 접근으로 해석하는 것이 더 신중합니다.
- **후보 밖 탐색성 요청 1건** [low] - filtered_out_breakdown에서 low_signal_fuzzing 1건이 분리되어 있어, 후보 밖 탐색성 요청이 실제로 존재합니다. 다만 단독으로는 개별 incident로 승격할 수준은 아니며, 후속 고신호 징후와 결합될 때만 재검토 대상입니다.
- **정상 비교군 비중이 높음** [info] - benign_normal_search가 7건으로 전체 필터링의 87.5%를 차지합니다. 이는 공격 신호보다 정상 비교군 또는 reference baseline 성격의 요청이 우세했음을 보여줍니다.

## 5. 주목할 사건
- request_id=N/A | src_ip=192.168.56.1 | verdict=incident 없음 | severity=info
  - 이유: 탑 티어 사건은 없었습니다. 다만 동일 IP에서 기준선성 다경로 접근이 관찰되어, 향후 유사 패턴이 증가하거나 민감 경로 접근이 섞이는지 추적할 필요가 있습니다.
  - incident_ref=N/A

## 6. 주목할 출발지 IP
- 192.168.56.1: known asset IP와 일치하며, 짧은 시간에 정적 자산과 health check를 포함한 다경로 접근이 관찰되었습니다. 공격자 단정보다는 내부 테스트, 자체 호출, 운영 점검 또는 정상 기준선 트래픽 가능성을 함께 고려해야 합니다.

## 7. 후보 밖 문맥 요청
필터링된 8건 중 7건은 benign_normal_search, 1건은 low_signal_fuzzing이었습니다. 즉, 이 구간의 잡음은 대부분 정상 비교군 또는 기준선 검색 성격이며, 소량의 후보 밖 탐색성 요청만 별도로 남아 있습니다. static_baseline_summaries와 ip_behavior_aggregates는 모두 context-only로 해석해야 하며, 200 응답이나 text/html, 응답 바이트 수만으로 파일 노출·실행 성공을 추정하면 안 됩니다.

정책:
- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.
- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.
- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.
- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.

후보 밖 탐색성 요청 분포:
- low_signal_fuzzing: 1건 (12.5%)

## 8. Static baseline context
- 아래 항목은 context-only 이며 개별 incident 승격이나 baseline outcome 확정 근거가 아닙니다.
- static_baseline_summaries 의 request 수는 같은 src_ip 와 static/health/browse baseline 시간창 기준 관찰 수입니다.
- src_ip=192.168.56.1 | window=2026-05-03T13:52:31.510 09:00 ~ 2026-05-03T13:52:38.651 09:00 | window_requests=8 | asset_categories=favicon, robots_txt, sitemap_xml, javascript_asset, css_asset, image_asset, health_check, normal_get | status_counts={"200": 7, "500": 1}
  - reason_hints=baseline:favicon, baseline:static_asset, baseline:robots_txt, baseline:no_crawler_policy_inference, baseline:sitemap_xml, baseline:no_site_structure_inference, baseline:static_js, baseline:no_js_execution_inference, baseline:static_css, baseline:static_image
  - 해석: static/health/browse baseline 관찰 문맥으로만 본다.
  - 제한: status, bytes, content_type 만으로 static file 존재, robots/sitemap 내용, JS 실행, file exposure, health 정상 여부를 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 9. IP behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 severity 상향 근거가 아닙니다.
- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수이며, auth behavior count 와 직접 합산하지 않습니다.
- src_ip=192.168.56.1 | window=2026-05-03T13:52:31.510 09:00 ~ 2026-05-03T13:52:38.651 09:00 | window_requests=8 | distinct_paths=8 | 4xx_ratio=0.00 | 5xx_count=1
  - attempted_categories=-
  - sensitive_path_hits=-
  - reason_hints=ip_behavior:multi_path_burst
  - 해석: 같은 src_ip 에서 scanning-like 또는 reconnaissance-like behavior 가 관찰된 문맥으로만 본다.
  - 제한: context_only_no_success_inference
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 10. Auth behavior context
- 관찰된 auth_behavior_summaries 없음

## 11. Method behavior context
- 관찰된 method_behavior_summaries 없음

## 12. Protocol anomaly context
- 관찰된 protocol_anomaly_summaries 없음

## 13. 권고 조치
- **P1** 192.168.56.1의 요청 주체를 내부 테스트/운영 점검/자동화 작업 관점에서 확인하고, 해당 시간대에 수행된 배포·점검 작업과 대조하세요.
  - 근거: known asset IP에서 관찰된 다경로 접근이므로 외부 공격으로 오인하지 않으려면 운영 맥락 상관분석이 우선입니다.
- **P2** 후속 구간에서 /robots.txt, /sitemap.xml, /favicon.ico, /health 계열 경로와 민감 경로가 함께 나타나는지 모니터링하세요.
  - 근거: 현재는 기준선성 접근이 우세하지만, 민감 경로가 추가되면 탐색성 활동으로 재평가할 수 있습니다.
- **P2** low_signal_fuzzing으로 분류된 요청 1건의 원시 요청 대상과 직후 연속 요청을 확인해 동일 IP의 탐색 흐름과 연계되는지 점검하세요.
  - 근거: 단건이지만 동일 시점의 다른 요청들과 결합되면 해석 가치가 커질 수 있습니다.
- **P3** 정상 비교군(benign_normal_search)과 기준선(static_baseline) 경로를 별도로 라벨링해 향후 유사 패턴이 들어오면 빠르게 구분되도록 하세요.
  - 근거: 현재 트래픽은 정상 비교군 비중이 높아, 기준선 정리가 향후 오탐 감소에 도움이 됩니다.

## 14. 신뢰도와 한계
- Apache 로그 요약본만 사용했으며 raw POST body, 응답 본문 원문, 서버 내부 파일 존재 여부를 확인할 수 없습니다.
- static_baseline_summaries, ip_behavior_aggregates는 모두 context-only이며 개별 incident 승격 근거가 아닙니다.
- known asset IP와 일치하는 출발지이므로 내부 테스트/자체 호출 가능성을 배제할 수 없습니다.
- 200, 500, text/html, response_body_bytes 같은 표면 지표만으로 파일 유출, XSS 실행, 인증 성공, 프로토콜 우회를 확정하지 않았습니다.
- filtered_out_breakdown이 존재하므로 잡음이 실제로 있었지만, 현 시점에서는 대부분 정상 비교군 성격으로 해석됩니다.

## 15. 발표용 한 줄 정리
이 구간은 ‘침해 사건’보다 ‘기준선성 트래픽과 소량의 탐색성 요청’으로 보는 것이 정확합니다. 특히 known asset IP에서의 다경로 접근이 핵심이며, 즉시 대응보다는 내부 점검 맥락 확인과 후속 구간 모니터링이 우선입니다.
