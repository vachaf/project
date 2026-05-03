# Apache 웹 로그 2차 요약 보고서 - known asset 기반 저신호 탐색 및 프로토콜 이상 문맥

- 생성 시각: 2026-05-03T11:44:02.948+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-05-03T11:14:30.000+09:00 ~ 2026-05-03T11:14:42.000+09:00
- known asset IP: 192.168.56.1, 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
이번 분석 구간(2026-05-03 11:14:30~11:14:42, KST)에서는 후보로 승격된 개별 침해 사건은 없었습니다. 대신 known asset IP인 192.168.56.1에서 짧은 시간 안에 비정상 메서드와 프로토콜 형태가 섞인 저신호 탐색성 요청이 관찰되었고, 높은 4xx 비율과 함께 후보 밖 탐색성 문맥이 형성되었습니다. 다만 Apache 로그만으로 성공적인 침해, 파일 노출, 업로드/삭제 성공, 인증 성공, XSS 실행 성공은 확인되지 않았습니다.

## 2. 경영 요약
- 분석 시간대에 총 12건이 관찰되었고, 이 중 6건은 low_signal_fuzzing으로 필터링되었습니다.
- 후보로 승격된 incident 는 0건이며, 주된 관찰은 known asset IP 192.168.56.1의 탐색성 트래픽입니다.
- 동일 IP에서 GET과 비정상 메서드(FAKEMETHOD), HTTP/1.0·bad protocol version·missing/odd Host·long path 정황이 함께 보여 프로토콜/파싱 표면 점검 성격이 강합니다.
- 응답은 200과 400이 혼재했지만, 이것만으로 우회 성공이나 침해 성공을 단정할 수는 없습니다.
- known asset IP이므로 내부 테스트, 자체 호출, 운영 점검 가능성을 함께 고려하는 것이 적절합니다.

## 3. 파이프라인 요약
- 전체 export row 수: 12
- 1차 후보 row 수: 0
- distinct incident 수: 0
- filtered out row 수: 6
- filtered out 비집계 row 수: 6
- noise 집계 그룹 수: 0
- ip behavior aggregate 수: 1
- auth behavior summary 수: 0
- method behavior summary 수: 1
- protocol anomaly summary 수: 1
- stage1 성공/오류: 0 / 0
- filtered_out 세부 분포: {"low_signal_fuzzing": 6}
- 후보 밖 주요 카테고리: low_signal_fuzzing 6건 (100.0%)

## 4. 핵심 발견
- **known asset IP에서 저신호 탐색성 요청이 집중됨** [low] - 192.168.56.1에서 11:14:35.884~11:14:41.005 사이 6건이 짧게 묶여 관찰되었고, 2개 경로·2개 메서드·6개의 서로 다른 User-Agent가 보였습니다. 4xx 비율이 50%로 높아 스캐닝 유사 문맥은 있으나, context-only 집계이며 공격 성공 근거는 아닙니다.
- **비정상 메서드와 기본 메서드가 혼재된 method probing 문맥** [low] - method_behavior_summaries 기준으로 6건 중 GET 5건과 FAKEMETHOD 1건이 관찰되었고, 상태는 200/400이 혼재했습니다. 이는 method discovery 또는 비정상 메서드 시도 정황으로 해석하는 것이 적절하며, 업로드/삭제/XST 성공으로 볼 근거는 없습니다.
- **protocol parsing 표면의 이상 징후가 동반됨** [low] - protocol_anomaly_summaries 에서 unsupported_method, HTTP/1.0 요청, bad protocol version, missing_host, odd_host, long_path가 함께 관찰되었습니다. 이는 malformed/protocol surface 관찰 문맥이며, 우회 성공이나 취약점 악용 성공으로는 단정할 수 없습니다.
- **후보 밖 탐색성 요청이 전부 low_signal_fuzzing 으로 정리됨** [info] - filtered_out_breakdown 상 low_signal_fuzzing 6건이 전체 후보 밖 요청을 차지했습니다. 별도의 고신호 사건이 없어 단발성 또는 내부 점검성 탐색으로도 해석 가능한 수준입니다.

## 5. 주목할 사건
- request_id=none | src_ip=192.168.56.1 | verdict=후보 승격 없음; known asset 기반 저신호 탐색성/프로토콜 이상 문맥 | severity=info
  - 이유: 단일 incident 로 확정할 만한 강한 증거는 없지만, 짧은 시간 안에 비정상 메서드와 malformed/protocol 형태가 함께 보여 점검 대상 트래픽으로 볼 가치가 있습니다. known asset IP이므로 내부 테스트나 운영 점검일 가능성도 함께 고려해야 합니다.
  - incident_ref=none

## 6. 주목할 출발지 IP
- 192.168.56.1: known asset IP이며, 짧은 시간 내 GET과 비정상 메서드가 혼재하고 4xx 비율이 높아 스캐닝 유사 문맥이 관찰되었습니다. 다만 내부 테스트/자체 호출/운영 점검 가능성을 배제할 수 없습니다.

## 7. 후보 밖 문맥 요청
필터링된 6건은 모두 low_signal_fuzzing 으로 분류되었습니다. 즉, 후보 밖 세부 분포가 실제로 존재하며, 이번 구간의 노이즈는 단순 배경 잡음이 아니라 known asset IP에서의 저신호 탐색성 요청으로 해석하는 것이 적절합니다. benign_normal_search 또는 normal_search_baseline 로 분리된 정상 비교군은 별도로 제시되지 않았습니다.

정책:
- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.
- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.
- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.
- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.

후보 밖 탐색성 요청 분포:
- low_signal_fuzzing: 6건 (100.0%)

## 8. IP behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 severity 상향 근거가 아닙니다.
- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수이며, auth behavior count 와 직접 합산하지 않습니다.
- src_ip=192.168.56.1 | window=2026-05-03T11:14:35.884 09:00 ~ 2026-05-03T11:14:41.005 09:00 | window_requests=6 | distinct_paths=2 | 4xx_ratio=0.50 | 5xx_count=0
  - attempted_categories=-
  - sensitive_path_hits=-
  - reason_hints=ip_behavior:high_4xx_ratio
  - 해석: 같은 src_ip 에서 scanning-like 또는 reconnaissance-like behavior 가 관찰된 문맥으로만 본다.
  - 제한: context_only_no_success_inference
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 9. Auth behavior context
- 관찰된 auth_behavior_summaries 없음

## 10. Method behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 method success 확정 근거가 아닙니다.
- method_behavior_summaries 의 request 수는 같은 src_ip 와 method/protocol relevant row 시간창 기준 관찰 수이며, auth/ip behavior count 와 직접 합산하지 않습니다.
- src_ip=192.168.56.1 | window=2026-05-03T11:14:35.884 09:00 ~ 2026-05-03T11:14:41.005 09:00 | window_requests=6 | method_counts={"GET": 5, "FAKEMETHOD": 1} | status_counts={"200": 3, "400": 3}
  - risky_methods=-
  - baseline_methods=GET
  - reason_hints=method_probe:unsupported_method, baseline:normal_get, method_probe:mixed_method_sequence, method_probe:no_method_success_inference
  - 해석: method probing 또는 baseline comparison context 로만 본다.
  - 제한: OPTIONS/TRACE/PUT/DELETE/PATCH 의 status 만으로 method 허용, 업로드/삭제, XST, CORS 취약점을 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 11. Protocol anomaly context
- 아래 항목은 context-only 이며 개별 incident 승격이나 protocol bypass / exploit success 확정 근거가 아닙니다.
- protocol_anomaly_summaries 의 request 수는 같은 src_ip 와 protocol anomaly relevant row 시간창 기준 관찰 수이며, auth/method/ip behavior count 와 직접 합산하지 않습니다.
- src_ip=192.168.56.1 | window=2026-05-03T11:14:35.884 09:00 ~ 2026-05-03T11:14:41.005 09:00 | window_requests=6 | method_counts={"GET": 5, "FAKEMETHOD": 1} | status_counts={"200": 3, "400": 3}
  - anomaly_types=unsupported_method, http10_request, bad_protocol_version, missing_host, odd_host, long_path
  - reason_hints=method_probe:unsupported_method, protocol_anomaly:unsupported_method, protocol_anomaly:malformed_request, protocol_anomaly:http10_request, protocol_anomaly:legacy_protocol_observation, protocol_anomaly:bad_protocol_version, protocol_anomaly:missing_host, protocol_anomaly:odd_host, protocol_anomaly:long_path, protocol_anomaly:no_success_inference
  - 해석: request parsing / protocol surface 관찰 문맥으로만 본다.
  - 제한: status_code, response_body_bytes, status_counts 만으로 우회 성공, 침해 성공, virtual host bypass 성공을 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 12. 권고 조치
- **P2** 192.168.56.1의 동시간대 트래픽을 내부 테스트·점검 작업과 대조하여 출발지 정당성을 확인하세요.
  - 근거: known asset IP이므로 악성 단정보다 내부 점검 가능성 검증이 우선입니다. 동일 시각의 운영 작업, 자동화 점검, 보안 스캔 여부를 교차 확인하면 오탐 해소에 도움이 됩니다.
- **P2** 해당 IP에서 사용된 비정상 메서드(FAKEMETHOD)와 malformed/protocol 요청 패턴을 방화벽/WAF/리버스프록시 로그와 상관분석하세요.
  - 근거: Apache 로그만으로는 요청 원문과 내부 처리 결과를 모두 볼 수 없으므로, 차단 위치와 실제 시도 의도를 더 정확히 판단하려면 추가 계층 로그가 필요합니다.
- **P3** 운영 중 허용되지 않는 메서드와 비정상 프로토콜 요청에 대한 모니터링 규칙을 강화하세요.
  - 근거: 이번 구간은 고신호 공격은 아니지만, method probing과 protocol anomaly 징후가 반복될 수 있어 사전 탐지 기준을 정비해 두는 것이 좋습니다.
- **P3** known asset 대상 자동화 점검이 정기적으로 수행된다면 User-Agent와 시간대를 표준화해 식별 가능하게 관리하세요.
  - 근거: 서로 다른 User-Agent가 다수 관찰되어도 자동화 점검일 수 있습니다. 추적 가능한 식별 체계를 두면 향후 오탐을 줄이고 분석 속도를 높일 수 있습니다.

## 13. 신뢰도와 한계
- 이 보고서는 Apache 웹 로그의 전처리·1차 분류 결과만 기반으로 작성되었으며, raw POST body와 응답 본문 원문은 확인할 수 없습니다.
- 따라서 인증 성공, 파일 내용 노출, XSS 브라우저 실행, 외부 전송 성공, 업로드/삭제 성공은 확인하지 않았습니다.
- ip_behavior_aggregate, method_behavior_summaries, protocol_anomaly_summaries 는 모두 context-only 이며 개별 incident 승격 근거가 아닙니다.
- known asset IP는 내부 테스트 또는 운영 점검일 수 있으므로 공격자 단정은 피해야 합니다.
- 이번 결과는 저신호 탐색과 프로토콜 이상 관찰에 대한 요약이며, 침해 확정에는 추가 상관분석이 필요합니다.

## 14. 발표용 한 줄 정리
이번 구간은 실제 침해가 확인된 사건보다, known asset IP에서 관찰된 저신호 탐색성과 프로토콜 이상 징후가 핵심입니다. 즉시 단정할 만한 성공 증거는 없지만, 내부 테스트 여부와 비정상 메서드·프로토콜 요청에 대한 상관분석은 필요합니다.
