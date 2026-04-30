# Apache 웹 로그 2차 분석 요약: known asset IP에서 관찰된 PHP 래퍼 기반 파일 노출 시도 정황

- 생성 시각: 2026-04-30T14:24:13.096+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-04-30T13:55:00.000+09:00 ~ 2026-04-30T13:56:00.000+09:00
- known asset IP: 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
단일 출발지 IP(known asset)에서 짧은 시간에 PHP 래퍼를 이용한 설정 파일 접근 시도가 연속적으로 관찰되었습니다. 응답 상태와 본문 크기만으로 실제 파일 내용 노출 성공은 확인되지 않으며, 현재까지는 침해 성공보다 시도·탐색 정황으로 해석하는 것이 타당합니다.

## 2. 경영 요약
- 분석 구간(2026-04-30 13:55:00~13:56:00 KST) 동안 총 6건 중 4건이 후보 incident로 분류되었습니다.
- 모든 후보는 동일 출발지 IP 192.168.56.109에서 발생했으며, known asset IP와 일치합니다.
- 주요 패턴은 /index.php에 대한 php://filter 및 convert.base64-encode를 이용한 파일 읽기/소스 노출 시도입니다.
- /config.php와 /admin/config.php 직접 지정은 민감 설정 경로 probing 문맥으로 보이며, 로그만으로 실제 노출 성공은 확정할 수 없습니다.
- 후보 밖 요청 2건은 low_signal_dir_probe로 정리되었고, 같은 IP에서 짧은 시간대의 보조 탐색 흐름이 있었음을 보여줍니다.

## 3. 파이프라인 요약
- 전체 export row 수: 6
- 1차 후보 row 수: 4
- distinct incident 수: 4
- filtered out row 수: 2
- filtered out 비집계 row 수: 2
- noise 집계 그룹 수: 0
- stage1 성공/오류: 4 / 0
- verdict 분포: {"suspicious_path_traversal": 4}
- severity 분포: {"medium": 4}
- 대표 source table 분포: {"security": 4}
- filtered_out 세부 분포: {"low_signal_dir_probe": 2}
- 후보 밖 주요 카테고리: low_signal_dir_probe 2건 (100.0%)

## 4. 핵심 발견
- **PHP 래퍼를 이용한 파일 노출 시도 정황** [medium] - raw_request_target에 php://filter, convert.base64-encode, resource= 조합이 반복되어 설정 파일 또는 소스 파일을 읽으려는 의도가 뚜렷합니다. 다만 Apache 로그만으로 실제 PHP source/config 내용이 노출되었는지는 확인되지 않았습니다.
- **같은 known asset IP에서 짧은 시간대 연속 요청** [medium] - 192.168.56.109에서 약 15초 내외에 /index.php, /config.php, /admin/config.php 계열 요청이 묶여 관찰되었습니다. 내부 테스트, 자체 호출, 운영 점검 가능성을 함께 고려해야 합니다.
- **200 응답과 text/html은 성공 근거가 아님** [info] - 일부 요청은 200이었지만 resp_content_type이 text/html이고 response_body_bytes가 큰 편이어서, 정상 라우팅·템플릿·fallback HTML일 가능성을 배제할 수 없습니다. 실제 파일 내용 노출 성공으로 단정하면 안 됩니다.
- **후보 밖 탐색성 요청이 별도로 존재** [info] - filtered_out_breakdown에 low_signal_dir_probe 2건이 보존되어 있으며, 이는 후보 밖 탐색성 요청으로 해석됩니다. 동일 IP의 짧은 시간대 reconnaissance 문맥은 있으나 개별 incident로 승격할 수준의 근거는 아닙니다.

## 5. 주목할 사건
- request_id=afLgyRmT0DpdHXxqXheyewAAAAQ | src_ip=192.168.56.109 | verdict=suspicious_path_traversal | severity=medium
  - 이유: php://filter/resource=config.php 조합은 PHP 래퍼를 이용한 민감 파일 접근 시도로 해석됩니다. 다만 404와 text/html 응답만으로 실제 파일 노출 성공은 확인되지 않아, 시도 정황으로 보는 것이 적절합니다.
  - uri=/index.php | method=GET | status=404 | score=12 | log_time=2026-04-30T13:55:37.427 09:00
  - incident_ref=request_id:afLgyRmT0DpdHXxqXheyewAAAAQ|table:security|log_id:1593|candidate:0 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: 요청 파라미터에 php://filter/resource=config.php가 포함되어 있어 PHP 래퍼를 이용한 민감 파일 접근 시도로 보입니다. 다만 응답이 404이고 resp_content_type 이 text/html이어서 실제 파일 노출 성공보다는 탐지/시도 정황으로 보는 것이 타당합니다.
- request_id=afLgxOeAB9en9-liEbFkQAAAAAM | src_ip=192.168.56.109 | verdict=suspicious_path_traversal | severity=medium
  - 이유: route=php://filter/resource=config.php 형태는 설정 파일을 읽으려는 전형적인 파일 노출 시도로 보입니다. 응답이 404이고 text/html이어서 실제 노출 성공은 확인되지 않습니다.
  - uri=/index.php | method=GET | status=404 | score=12 | log_time=2026-04-30T13:55:32.987 09:00
  - incident_ref=request_id:afLgxOeAB9en9-liEbFkQAAAAAM|table:security|log_id:1592|candidate:1 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: `route=php://filter/resource=config.php` 형태의 요청은 PHP 필터 래퍼를 이용해 설정 파일을 읽으려는 전형적인 파일 노출 시도로 보입니다. 다만 응답이 404이고 `resp_content_type` 이 `text/html` 이라 실제 파일 내용 노출 성공은 확인되지 않아, 시도 정황 중심으로 판단했습니다.
- request_id=afLgwWSoHnmpSRvjKFzotAAAAAA | src_ip=192.168.56.109 | verdict=suspicious_path_traversal | severity=medium
  - 이유: php://filter/convert.base64-encode/resource=admin/config.php는 소스 또는 설정 파일 읽기 의도가 강한 패턴입니다. 그러나 200 text/html 응답만으로 실제 파일 내용 노출을 단정할 수 없습니다.
  - uri=/index.php | method=GET | status=200 | score=12 | log_time=2026-04-30T13:55:29.540 09:00
  - incident_ref=request_id:afLgwWSoHnmpSRvjKFzotAAAAAA|table:security|log_id:1591|candidate:2 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: 요청 파라미터에 php://filter 래퍼와 base64 인코딩, resource=admin/config.php가 함께 보여 파일 읽기/노출을 노린 경로 탐색 시도로 해석하는 것이 타당합니다. 응답은 200이지만 content-type이 text/html이라 실제 파일 노출 성공 여부는 이 로그만으로 확정할 수 없고, 시도 정황 중심으로 판단했습니다.
- request_id=afLgvZHt9hGyqryjyhdXXwAAAAE | src_ip=192.168.56.109 | verdict=suspicious_path_traversal | severity=medium
  - 이유: php://filter/convert.base64-encode/resource=config.php는 파일 읽기 또는 소스 노출 시도로 볼 수 있습니다. 200 응답과 text/html만으로는 실제 config 내용 노출 성공을 확인할 수 없습니다.
  - uri=/index.php | method=GET | status=200 | score=12 | log_time=2026-04-30T13:55:25.327 09:00
  - incident_ref=request_id:afLgvZHt9hGyqryjyhdXXwAAAAE|table:security|log_id:1590|candidate:3 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: `file=php://filter/convert.base64-encode/resource=config.php` 형태의 요청은 PHP 래퍼를 이용해 민감 파일을 읽으려는 전형적인 파일 노출/경로 탐색 시도로 보입니다. 다만 응답이 `text/html`이고 상태코드가 200이라도 실제 파일 내용 노출 성공 여부는 이 필드만으로 확정할 수 없어, 시도 정황으로 분류합니다.

## 6. 주목할 출발지 IP
- 192.168.56.109: 4건의 후보 incident가 모두 이 IP에서 발생했고, known asset IP와 일치합니다. 내부 테스트·자체 호출·운영 점검 가능성을 반드시 함께 고려해야 하지만, 동일 시각대에 PHP 래퍼 기반 파일 노출 시도가 연속된 점은 주의가 필요합니다.

참고: 위 출발지 IP 중 일부는 known asset 목록과 일치하므로, 실제 공격자 IP 로 단정하지 말고 내부 테스트/자체 호출 여부를 먼저 확인해야 합니다.

## 7. 후보 밖 문맥 요청
filtered_out_breakdown에 low_signal_dir_probe 2건이 남아 있어 후보 밖 탐색성 요청이 실제로 존재합니다. 이는 같은 출발지 IP에서 짧은 시간에 민감 경로를 더듬는 탐색 흐름이 있었음을 뒷받침하지만, 현재 후보 incident의 심각도를 낮추는 근거로 쓰기보다는 보조 문맥으로 해석해야 합니다. normal_search_baseline 또는 reference_baseline 성격의 비교군은 제공되지 않았습니다.

정책:
- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.
- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.
- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.
- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.

후보 밖 탐색성 요청 분포:
- low_signal_dir_probe: 2건 (100.0%)

Context-only probing sequence 요약:
- src_ip=192.168.56.109 | window=2026-04-30T13:55:25.327 09:00 ~ 2026-04-30T13:55:40.426 09:00 | requests=6 | distinct_paths=3 | sample_paths=/index.php, /config.php, /admin/config.php
  - 해석: Multiple low-signal directory probing paths from the same source in a short window. Context only; do not treat as confirmed compromise.

## 8. 권고 조치
- **P1** 192.168.56.109의 원시 로그를 재확인하고 해당 시간대 애플리케이션/배포/운영 작업 기록과 대조하세요.
  - 근거: known asset IP이므로 내부 점검, 자동화 작업, 테스트 트래픽 가능성을 먼저 구분해야 합니다. 동시에 외부에서 유입된 요청인지, 사내 테스트인지 상관분석이 필요합니다.
- **P1** 같은 IP에서 /index.php, /config.php, /admin/config.php 및 php://filter 패턴이 재발하는지 추적하고, 짧은 시간대 반복을 차단 기준으로 검토하세요.
  - 근거: 현재는 시도 정황이 중심이지만, 동일 패턴의 반복은 실제 탐색 강도 증가를 의미할 수 있습니다.
- **P2** 해당 애플리케이션의 /index.php 파라미터 처리 로직에서 route/file/path 입력 검증과 허용 목록을 점검하세요.
  - 근거: php://filter 같은 래퍼 문자열이 경로 처리에 전달될 가능성을 줄여 파일 읽기 시도를 차단할 수 있습니다.
- **P2** /config.php와 /admin/config.php에 대한 직접 접근 정책, 리라이트 규칙, 접근 제어 및 에러 처리 동작을 확인하세요.
  - 근거: 직접 경로 probing이 관찰되었으므로 민감 설정 경로가 외부에 노출되지 않도록 방어면을 점검할 필요가 있습니다.
- **P3** 후보 밖 탐색성 요청(low_signal_dir_probe 2건)을 동일 시각대 요청 묶음과 함께 장기적으로 모니터링하세요.
  - 근거: 현재는 경미한 탐색성 요청이지만, 동일 IP에서 후속 고신호 incident로 이어질 수 있어 추세 관찰이 유용합니다.

## 9. 신뢰도와 한계
- 분류 신뢰도는 높지만, 이는 '시도 정황'에 대한 신뢰도입니다.
- Apache 로그만으로 실제 파일 내용 노출, PHP 소스 유출, 설정값 탈취 성공은 확인할 수 없습니다.
- known asset IP와 일치하므로 내부 테스트/자체 호출 가능성을 배제할 수 없습니다.
- response_body_bytes가 크거나 status_code가 200이어도 fallback HTML, 템플릿, 정상 라우팅일 수 있어 성공 근거로 사용하지 않았습니다.
- 후보 밖 low_signal_dir_probe는 개별 incident로 승격하지 않고 문맥 정보로만 반영했습니다.

## 10. 발표용 한 줄 정리
이번 구간의 핵심은 '실제 침해 확정'이 아니라, known asset IP에서 PHP 래퍼를 이용해 설정 파일을 읽으려는 탐색·시도 정황이 짧은 시간에 연속 관찰되었다는 점입니다. 즉시 차단보다 먼저 내부 테스트 여부와 애플리케이션의 경로 검증 상태를 확인하는 것이 우선입니다.
