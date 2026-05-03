# Apache 웹 로그 2차 분석 요약 (2026-05-03 10:00:06~10:00:18 KST)

- 생성 시각: 2026-05-03T10:24:05.855+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-05-03T10:00:06.000+09:00 ~ 2026-05-03T10:00:18.000+09:00
- known asset IP: 192.168.56.1, 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
이번 구간에서는 확정적인 침해나 성공한 악용 정황은 보이지 않았습니다. 전체 6건이 후보 밖(low_signal_fuzzing)으로 정리되었고, 주목할 만한 사건형 고신호는 없습니다. 다만 한 출발지 IP에서 짧은 시간에 여러 HTTP 메서드를 섞어 호출한 정황이 있어, 내부 테스트 또는 자동화된 메서드 점검 가능성을 포함한 탐색성 행위로는 볼 수 있습니다.

## 2. 경영 요약
- 분석 구간 내 6건 모두 후보 밖 탐색성 요청(low_signal_fuzzing)으로 분류되었습니다.
- 고신호 incident 는 없었고, 확정된 침해·노출·실행 성공 근거도 확인되지 않았습니다.
- 192.168.56.1 에서 OPTIONS/TRACE/PUT/DELETE 와 GET/HEAD 가 섞인 메서드 probing 패턴이 관찰되었습니다.
- 해당 IP 는 known_asset 범주와 일치하므로 내부 테스트, 자체 호출, 운영 점검 가능성을 함께 고려해야 합니다.

## 3. 파이프라인 요약
- 전체 export row 수: 6
- 1차 후보 row 수: 0
- distinct incident 수: 0
- filtered out row 수: 6
- filtered out 비집계 row 수: 6
- noise 집계 그룹 수: 0
- ip behavior aggregate 수: 0
- auth behavior summary 수: 0
- method behavior summary 수: 1
- stage1 성공/오류: 0 / 0
- filtered_out 세부 분포: {"low_signal_fuzzing": 6}
- 후보 밖 주요 카테고리: low_signal_fuzzing 6건 (100.0%)

## 4. 핵심 발견
- **후보 밖 탐색성 요청이 전체를 차지** [info] - 분석된 6건은 모두 low_signal_fuzzing 으로 필터링되었고, 별도 incident 로 승격된 항목은 없습니다. 즉, 이번 구간의 주된 특징은 공격 성공보다 경미한 탐색성 요청의 존재입니다.
- **192.168.56.1 의 메서드 probing 정황** [low] - 같은 출발지에서 6건의 요청이 짧은 시간대에 집중되었고, OPTIONS, TRACE, PUT, DELETE 같은 위험 메서드와 GET, HEAD 같은 기준 메서드가 함께 관찰되었습니다. 이는 메서드 탐색 또는 점검성 트래픽으로 해석하는 것이 타당합니다.
- **내부 자산 IP 와의 일치로 인한 해석 주의** [info] - 192.168.56.1 은 known_asset_ips 에 포함되어 있어 외부 공격자 단정은 부적절합니다. 내부 테스트, 자동화 점검, 또는 자체 호출 트래픽일 가능성을 함께 두고 봐야 합니다.

## 5. 주목할 사건
- request_id=- | src_ip=192.168.56.1 | verdict=사건형 고신호 incident 없음. 다만 메서드 probing 문맥의 저신호 요청이 관찰됨. | severity=info
  - 이유: 짧은 시간 내 다양한 HTTP 메서드를 섞어 호출한 정황은 취약점 악용 전 점검 또는 내부 테스트일 수 있어, 운영 환경에서는 의도 확인이 필요합니다. 다만 Apache 로그만으로 업로드 성공, 삭제 성공, XST 성공은 단정할 수 없습니다.
  - incident_ref=-

## 6. 주목할 출발지 IP
- 192.168.56.1: 짧은 시간에 6건의 메서드 probing 정황이 관찰된 유일한 주목 IP입니다. known_asset 범주와도 일치하므로 내부 테스트 또는 운영 점검 가능성을 함께 고려해야 합니다.

## 7. 후보 밖 문맥 요청
후보 밖 요청 6건은 모두 low_signal_fuzzing 으로 분류되었습니다. 필터링 세부 분포는 low_signal_fuzzing 100%이며, 별도의 benign_normal_search 나 normal_search_baseline 항목은 보이지 않습니다. 이번 구간의 잡음은 메서드 탐색성 요청 중심으로 해석하는 것이 적절합니다.

정책:
- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.
- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.
- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.
- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.

후보 밖 탐색성 요청 분포:
- low_signal_fuzzing: 6건 (100.0%)

## 8. IP behavior context
- 관찰된 ip_behavior_aggregates 없음

## 9. Auth behavior context
- 관찰된 auth_behavior_summaries 없음

## 10. Method behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 method success 확정 근거가 아닙니다.
- method_behavior_summaries 의 request 수는 같은 src_ip 와 method/protocol relevant row 시간창 기준 관찰 수이며, auth/ip behavior count 와 직접 합산하지 않습니다.
- src_ip=192.168.56.1 | window=2026-05-03T10:00:11.047 09:00 ~ 2026-05-03T10:00:16.093 09:00 | window_requests=6 | method_counts={"DELETE": 1, "GET": 1, "HEAD": 1, "OPTIONS": 1, "PUT": 1, "TRACE": 1} | status_counts={"200": 3, "204": 1, "405": 1, "500": 1}
  - risky_methods=OPTIONS, TRACE, PUT, DELETE
  - baseline_methods=HEAD, GET
  - reason_hints=method_probe:options, method_probe:trace, method_probe:put, method_probe:destructive_method, method_probe:delete, baseline:normal_head, baseline:normal_get, method_probe:mixed_method_sequence, method_probe:no_method_success_inference
  - 해석: method probing 또는 baseline comparison context 로만 본다.
  - 제한: OPTIONS/TRACE/PUT/DELETE/PATCH 의 status 만으로 method 허용, 업로드/삭제, XST, CORS 취약점을 단정하지 않는다.
  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

## 11. 권고 조치
- **P2** 192.168.56.1 의 요청 주체를 내부 테스트/운영 점검/자동화 도구 중 무엇으로 운용했는지 확인하세요.
  - 근거: known_asset IP 이고 비브라우저성·탐색성 메서드 조합이 관찰되어, 악성 여부보다 먼저 정상 운영 활동인지 확인하는 것이 실무적으로 우선입니다.
- **P2** OPTIONS, TRACE, PUT, DELETE 를 포함한 메서드 사용이 실제 운영에서 필요한지 점검하고, 필요 없으면 서버/프록시 레벨에서 제한을 검토하세요.
  - 근거: 메서드 probing 은 직접적인 침해 증거는 아니지만, 불필요한 메서드 노출은 공격 표면을 넓힐 수 있습니다.
- **P3** 후속 분석 시 동일 IP 의 전후 시간대 요청과 인증 로그를 함께 상관분석하세요.
  - 근거: 현재 구간만으로는 의도와 영향도를 확정하기 어렵고, 짧은 burst 가 테스트인지 점검인지 추가 문맥이 필요합니다.

## 12. 신뢰도와 한계
- 원본 DB 로그가 아니라 전처리·1차 분류 요약만 사용했으므로, 세부 요청 본문이나 응답 본문 수준의 성공 여부는 확인할 수 없습니다.
- Apache 로그 표면에서는 method probing, file disclosure, XSS 실행, 인증 성공 여부를 확정할 수 없습니다.
- known_asset IP 와 겹치는 요청은 내부 테스트나 운영 점검일 수 있으므로 공격자 단정은 피했습니다.
- 이번 구간은 표본 수가 적고 모두 저신호로 분류되어, 위험도 평가는 보수적으로 해석해야 합니다.

## 13. 발표용 한 줄 정리
이번 구간은 ‘침해 성공’보다는 ‘내부 자산에서 관찰된 메서드 탐색성 요청’으로 요약하는 것이 정확합니다. 즉시 필요한 조치는 공격 차단보다도 출발지의 정체와 운영 목적을 확인하는 것입니다.
