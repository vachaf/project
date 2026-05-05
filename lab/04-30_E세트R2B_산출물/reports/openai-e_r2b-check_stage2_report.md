# Apache 로그 2차 분석 요약: known asset IP에서 관찰된 PHP wrapper 기반 파일 공개 시도

- 생성 시각: 2026-05-05T11:58:34.636+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-04-30T13:55:00.000+09:00 ~ 2026-04-30T13:56:00.000+09:00
- known asset IP: 192.168.56.1, 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
이번 구간에서는 192.168.56.109에서 짧은 시간 안에 /index.php 및 인접 민감 경로를 대상으로 한 PHP wrapper 기반 파일/소스 공개 시도가 연속적으로 관찰되었습니다. 다만 Apache 로그만으로 실제 파일 내용 노출이나 침해 성공은 확인되지 않았고, 응답은 주로 HTML 404/200으로 나타나 탐지된 시도와 실제 유출을 분리해서 봐야 합니다. 또한 해당 IP는 known asset 목록과 일치하므로 내부 테스트, 자체 호출, 운영 점검 가능성을 함께 고려해야 합니다.

## 2. 경영 요약
- 분석 시간대는 2026-04-30 13:55~13:56(KST)이며, 192.168.56.109에서 4건의 중복되지 않은 후보 incident가 확인되었습니다.
- 핵심 패턴은 `php://filter/convert.base64-encode/resource=...` 형태의 PHP wrapper 기반 source/config disclosure 시도입니다.
- `/config.php`, `/admin/config.php` 직접 접근은 민감 설정 경로 probing 맥락으로 보는 것이 적절하며, 응답 본문 원문이 없어 실제 노출 성공은 단정할 수 없습니다.
- 같은 IP에서 짧은 시간 동안 `/index.php`, `/config.php`, `/admin/config.php`가 함께 보여 reconnaissance/dir probing 흐름도 동반됩니다.
- known asset IP와 일치하므로 악의적 외부 공격으로 단정하기보다 내부 테스트/점검 가능성을 반드시 병기해야 합니다.

## 3. 파이프라인 요약
- 전체 export row 수: 6
- 1차 후보 row 수: 4
- distinct incident 수: 4
- filtered out row 수: 2
- filtered out 비집계 row 수: 2
- noise 집계 그룹 수: 0
- static baseline summary 수: 0
- crawler baseline summary 수: 0
- sensitive path probe summary 수: 1
- mixed baseline/scanner summary 수: 0
- ip behavior aggregate 수: 1
- auth behavior summary 수: 0
- method behavior summary 수: 0
- protocol anomaly summary 수: 0
- stage1 성공/오류: 4 / 0
- verdict 분포: {"suspicious_file_disclosure": 4}
- severity 분포: {"medium": 4}
- 대표 source table 분포: {"security": 4}
- filtered_out 세부 분포: {"low_signal_dir_probe": 2}
- 후보 밖 주요 카테고리: low_signal_dir_probe 2건 (100.0%)

## 4. 핵심 발견
- **PHP wrapper 기반 파일/소스 공개 시도 4건** [medium] - 모든 top incident가 `php://filter`를 사용한 파일 공개 시도였습니다. 특히 `convert.base64-encode/resource=admin/config.php`와 `resource=config.php` 조합은 PHP stream wrapper를 이용해 설정/소스 파일을 읽어보려는 시도로 해석하는 것이 타당합니다. 다만 Apache 로그만으로 실제 파일 내용이 반환되었는지는 확인되지 않았고, 200 또는 404 응답만으로 유출 성공을 단정할 수는 없습니다.
- **같은 출발지에서 민감 경로 probing 흐름 동반** [low] - probing_sequence_summary와 sensitive_path_probe_summary에 따르면 동일 출발지에서 `/index.php`, `/config.php`, `/admin/config.php`가 짧은 시간에 함께 관찰되었습니다. 이는 민감 경로를 훑는 reconnaissance 또는 directory probing 문맥으로 볼 수 있지만, 개별 경로의 존재나 파일 내용 노출 성공을 의미하지는 않습니다.
- **known asset IP로 확인되어 내부 점검 가능성 존재** [info] - 출발지 IP 192.168.56.109는 known asset 목록과 일치합니다. 따라서 외부 공격자로 단정하기보다는 내부 테스트, 자체 호출, 운영 점검 트래픽일 가능성을 함께 고려해야 합니다.
- **후보 밖 탐색성 요청이 일부 필터링됨** [info] - filtered_out_breakdown에 `low_signal_dir_probe` 2건이 보존되어 있습니다. 즉, 일부 경미한 디렉터리 탐색성 요청은 후보 밖으로 정리되었고, 현재 보고서는 상대적으로 신뢰도 높은 PHP wrapper 기반 파일 공개 시도 중심으로 요약됩니다.

## 5. 주목할 사건
- request_id=afLgyRmT0DpdHXxqXheyewAAAAQ | src_ip=192.168.56.109 | verdict=suspicious_file_disclosure | severity=medium
  - 이유: 쿼리에 `php://filter/resource=config.php`가 포함되어 있어 PHP wrapper를 이용한 설정 파일/소스 공개 시도로 보는 것이 적절합니다. 다만 응답은 404이고 text/html이어서 실제 파일 내용 노출 성공은 확인되지 않았습니다.
  - uri=/index.php | method=GET | status=404 | score=12 | log_time=2026-04-30T13:55:37.427 09:00
  - incident_ref=request_id:afLgyRmT0DpdHXxqXheyewAAAAQ|table:security|log_id:1593|candidate:0 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: 요청 쿼리에 `php://filter/resource=config.php`가 포함되어 있어 PHP stream wrapper를 이용한 설정 파일/소스 노출 시도로 보는 것이 타당합니다. 다만 응답은 404이고 응답 본문이 HTML이어서 실제 파일 내용 노출 성공은 확인되지 않았습니다.
  - file disclosure 해석: php://filter/convert.base64-encode/resource=... 계열은 PHP stream wrapper 를 이용한 source/config disclosure attempt 또는 LFI-like file disclosure attempt 로 해석할 수 있습니다.
  - 해석 제한: Apache 로그만으로 실제 파일 내용 반환 여부는 확인할 수 없으므로, 성공한 유출이 아니라 시도 정황으로만 제한해 해석해야 합니다.
- request_id=afLgxOeAB9en9-liEbFkQAAAAAM | src_ip=192.168.56.109 | verdict=suspicious_file_disclosure | severity=medium
  - 이유: `php://filter/resource=config.php` 조합은 민감한 설정 파일 조회 시도로 해석하는 것이 타당합니다. 다만 404 응답만으로 실제 유출 성공을 확인할 수는 없으며, 시도 탐지 수준으로 보는 것이 안전합니다.
  - uri=/index.php | method=GET | status=404 | score=12 | log_time=2026-04-30T13:55:32.987 09:00
  - incident_ref=request_id:afLgxOeAB9en9-liEbFkQAAAAAM|table:security|log_id:1592|candidate:1 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: 요청 쿼리에 `php://filter/resource=config.php`가 포함되어 있어 PHP stream wrapper를 이용한 설정/소스 파일 공개 시도로 보는 것이 타당합니다. 다만 응답은 404이고, 제공된 정보만으로 실제 파일 내용 노출 성공은 확인되지 않아 시도 탐지 수준으로 분류합니다.
  - file disclosure 해석: php://filter/convert.base64-encode/resource=... 계열은 PHP stream wrapper 를 이용한 source/config disclosure attempt 또는 LFI-like file disclosure attempt 로 해석할 수 있습니다.
  - 해석 제한: Apache 로그만으로 실제 파일 내용 반환 여부는 확인할 수 없으므로, 성공한 유출이 아니라 시도 정황으로만 제한해 해석해야 합니다.
- request_id=afLgwWSoHnmpSRvjKFzotAAAAAA | src_ip=192.168.56.109 | verdict=suspicious_file_disclosure | severity=medium
  - 이유: `php://filter/convert.base64-encode/resource=admin/config.php`는 PHP wrapper를 이용한 소스/설정 파일 조회 시도입니다. 응답이 200 text/html이지만 Apache 로그만으로 실제 파일 내용 노출이나 base64 기반 유출 성공은 확인되지 않습니다.
  - uri=/index.php | method=GET | status=200 | score=12 | log_time=2026-04-30T13:55:29.540 09:00
  - incident_ref=request_id:afLgwWSoHnmpSRvjKFzotAAAAAA|table:security|log_id:1591|candidate:2 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: 요청 쿼리스트링에 php://filter/convert.base64-encode/resource=admin/config.php 형태가 보여 PHP wrapper를 이용한 소스/설정 파일 조회 시도로 해석하는 것이 타당합니다. 다만 Apache 로그만으로 실제 파일 내용 노출 성공은 확인되지 않으며, 응답이 200이고 text/html이라 애플리케이션의 일반 HTML 응답 가능성도 배제할 수 없습니다.
  - file disclosure 해석: php://filter/convert.base64-encode/resource=... 계열은 PHP stream wrapper 를 이용한 source/config disclosure attempt 또는 LFI-like file disclosure attempt 로 해석할 수 있습니다.
  - 해석 제한: Apache 로그만으로 실제 파일 내용 반환 여부는 확인할 수 없으므로, 성공한 유출이 아니라 시도 정황으로만 제한해 해석해야 합니다.
- request_id=afLgvZHt9hGyqryjyhdXXwAAAAE | src_ip=192.168.56.109 | verdict=suspicious_file_disclosure | severity=medium
  - 이유: `file=php://filter/convert.base64-encode/resource=config.php`는 PHP wrapper 기반 소스/설정 파일 조회 시도입니다. 200 text/html 응답만으로는 실제 파일 내용이 노출되었는지 판단할 수 없습니다.
  - uri=/index.php | method=GET | status=200 | score=12 | log_time=2026-04-30T13:55:25.327 09:00
  - incident_ref=request_id:afLgvZHt9hGyqryjyhdXXwAAAAE|table:security|log_id:1590|candidate:3 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: `file=php://filter/convert.base64-encode/resource=config.php` 조합은 PHP wrapper를 이용한 소스/설정 파일 조회 시도로 보는 것이 타당합니다. 다만 Apache 로그만으로 실제 파일 내용이 반환되었는지는 확인할 수 없고, 응답이 `text/html`인 점도 앱의 일반 HTML 응답 가능성을 남겨둡니다.
  - file disclosure 해석: php://filter/convert.base64-encode/resource=... 계열은 PHP stream wrapper 를 이용한 source/config disclosure attempt 또는 LFI-like file disclosure attempt 로 해석할 수 있습니다.
  - 해석 제한: Apache 로그만으로 실제 파일 내용 반환 여부는 확인할 수 없으므로, 성공한 유출이 아니라 시도 정황으로만 제한해 해석해야 합니다.

## 6. 주목할 출발지 IP
- 192.168.56.109: 4건의 후보 incident가 모두 이 IP에서 발생했고, 짧은 시간 안에 `/index.php`, `/config.php`, `/admin/config.php`가 함께 관찰되었습니다. known asset과도 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.

참고: 위 출발지 IP 중 일부는 known asset 목록과 일치하므로, 실제 공격자 IP 로 단정하지 말고 내부 테스트/자체 호출 여부를 먼저 확인해야 합니다.

## 7. 후보 밖 문맥 요청
후보 밖 분포는 `low_signal_dir_probe` 2건으로 정리되어 있습니다. 이는 상대적으로 신호가 약한 디렉터리 탐색성 요청이 별도로 존재했음을 의미하며, 본 보고서의 핵심 incident와는 분리해 해석해야 합니다. 다만 noise가 적다고 해서 다른 요청의 의미가 약해지는 것은 아니며, 현재 핵심은 PHP wrapper 기반 파일 공개 시도입니다.

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

## 8. Static baseline context
- 관찰된 static_baseline_summaries 없음

## 9. Crawler baseline context
- 관찰된 crawler_baseline_summaries 없음

## 10. Mixed baseline/scanner context
- 관찰된 mixed_baseline_scanner_summaries 없음

## 11. IP behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 severity 상향 근거가 아닙니다.
- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수이며, auth behavior count 와 직접 합산하지 않습니다.
- src_ip=192.168.56.109 | window=2026-04-30T13:55:25.327 09:00 ~ 2026-04-30T13:55:40.426 09:00 | window_requests=6 | distinct_paths=3 | 4xx_ratio=0.33 | 5xx_count=0
  - attempted_categories=file_disclosure, dir_probe
  - sensitive_path_hits=/config.php, /admin/config.php
  - reason_hints=ip_behavior:multiple_attack_categories, ip_behavior:sensitive_path_focus
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
- **P1** 192.168.56.109의 요청 원문과 인접 시간대 로그를 추가 대조해 동일 주체의 테스트/운영 점검인지 확인하고, 예상되지 않은 활동이면 네트워크 주체를 식별하라.
  - 근거: known asset IP이므로 내부 테스트 가능성이 있으나, 실제 운영 트래픽인지 악성 시도인지 구분이 필요합니다.
- **P1** `php://filter` 및 `resource=config.php`, `resource=admin/config.php` 패턴을 WAF/탐지 룰에 반영하고, 동일 패턴 반복 시 알림 기준을 강화하라.
  - 근거: 현재 관찰된 핵심 행위가 PHP wrapper 기반 파일 공개 시도이므로 재발 탐지가 중요합니다.
- **P2** /config.php, /admin/config.php, /index.php 파라미터 처리 경로를 점검하고, 민감 설정 파일이 웹 루트 또는 취약한 include 경로로 노출되지 않도록 검토하라.
  - 근거: 응답 성공 여부와 무관하게 민감 경로 probing이 있었기 때문에 경로 설계를 점검할 필요가 있습니다.
- **P2** 동일 IP에서의 연속 요청을 시간축으로 재구성해 probing_sequence_summary와 top incident가 같은 작업 세션인지 확인하라.
  - 근거: 짧은 시간 내 연속 probing과 file disclosure 시도가 함께 보이므로 세션 단위 상관분석이 유용합니다.
- **P3** 탐지된 404/200 HTML 응답에 대해 서버 측 라우팅과 fallback 동작을 검토해, 실제 파일 접근 실패와 일반 HTML 응답을 구분할 수 있게 하라.
  - 근거: 현재는 Apache 로그만으로 유출 성공을 확정할 수 없으므로 응답 의미를 더 명확히 해야 합니다.

## 16. 신뢰도와 한계
- 신뢰도는 중간 수준입니다. `php://filter` 패턴과 민감 경로 지정은 비교적 명확하지만, Apache 로그만으로 실제 파일 내용 노출 성공은 확인할 수 없습니다.
- `200 text/html` 응답은 정상 라우팅, fallback HTML, 빈 PHP 출력 등 여러 해석이 가능하므로 유출 성공 근거로 사용하지 않았습니다.
- `404 text/html` 역시 탐지 실패 또는 잘못된 경로 접근일 수 있어, 공격 성공이나 침해 성공으로 확대 해석하지 않았습니다.
- 해당 IP는 known asset과 일치하므로 내부 테스트, 자체 호출, 운영 점검 가능성을 배제하지 않았습니다.
- raw POST body가 없는 환경이므로 body 내부 payload 성공/실패 여부는 확인하지 않았습니다.

## 17. 발표용 한 줄 정리
이번 구간의 핵심은 192.168.56.109에서 관찰된 PHP wrapper 기반 설정/소스 공개 시도입니다. 다만 이는 시도 탐지로 보는 것이 적절하며, 실제 유출이나 침해 성공은 확인되지 않았습니다. known asset IP라는 점을 감안해 내부 테스트 가능성까지 함께 검토하는 것이 가장 실용적입니다.
