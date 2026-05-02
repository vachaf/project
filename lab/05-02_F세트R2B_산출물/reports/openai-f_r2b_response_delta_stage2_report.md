# Apache 웹 로그 사건형 분석 요약 (2026-05-02 19:08:09~19:08:37 KST)

- 생성 시각: 2026-05-02T19:28:32.062+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-05-02T19:08:09.000+09:00 ~ 2026-05-02T19:08:37.000+09:00
- known asset IP: 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
해당 시간 구간에서는 동일 출발지 IP(192.168.56.1)에서 /rest/user/login 으로 짧은 시간 안에 반복된 401 응답이 관찰되어 인증 실패 또는 인증 오용 정황이 있습니다. 다만 제공된 로그만으로 자격 증명 추측의 성공, 계정 탈취, 또는 침해 성공은 확인되지 않았습니다. 전반적으로 낮은 심각도의 인증 관련 이상 징후와, 동일 출발지의 다수 실패 요청이라는 문맥 수준의 반복성이 핵심입니다.

## 2. 경영 요약
- 분석 구간: 2026-05-02 19:08:09~19:08:37(KST), 동일 IP에서 인증 엔드포인트로의 짧은 실패 버스트가 관찰되었습니다.
- 상위 사건 3건 모두 /rest/user/login POST 요청에 대한 401 응답이며, 로그인 실패 또는 인증 오용 정황으로 해석하는 것이 타당합니다.
- IP 집계상 같은 출발지에서 11건, 4xx 비율 100%가 보이지만, 이는 context-only 지표로서 성공한 공격이나 침해를 뜻하지는 않습니다.
- User-Agent 는 도구/자동화 성격을 띠지만, lab-* 같은 실험형 표식만으로 공격자 단정은 하지 않았습니다.

## 3. 파이프라인 요약
- 전체 export row 수: 11
- 1차 후보 row 수: 3
- distinct incident 수: 3
- filtered out row 수: 0
- filtered out 비집계 row 수: 0
- noise 집계 그룹 수: 0
- ip behavior aggregate 수: 1
- auth behavior summary 수: 1
- stage1 성공/오류: 3 / 0
- verdict 분포: {"suspicious_auth_abuse": 2, "likely_false_positive": 1}
- severity 분포: {"low": 3}
- 대표 source table 분포: {"security": 3}

## 4. 핵심 발견
- **동일 IP의 반복 로그인 실패 정황** [medium] - 192.168.56.1에서 /rest/user/login 으로 POST 요청이 연속적으로 관찰되었고 모두 401 응답이었습니다. auth_behavior_summaries 기준으로 11건의 auth 요청이 짧은 시간 창에 몰렸으며, 반복 실패와 빠른 버스트가 확인됩니다. 다만 Apache 로그 표면만으로는 POST body 원문과 실제 인증 결과를 볼 수 없으므로, 로그인 성공이나 계정 탈취로는 해석하지 않았습니다.
- **IP 수준에서 높은 4xx 비율의 탐색성 문맥** [low] - ip_behavior_aggregate 에서 동일 출발지 IP의 관련 요청 11건이 모두 4xx였고, 단일 경로(/rest/user/login)로 집중되어 있었습니다. 이는 scanning-like 또는 reconnaissance-like 문맥으로는 볼 수 있으나, 집계 자체는 후보 승격 근거가 아니며 성공 여부를 시사하지 않습니다.
- **오탐 가능성이 남아 있는 인증 오용 분류** [low] - 개별 사건 중 1건은 likely_false_positive 로 분류되었고, 다른 사건은 suspicious_auth_abuse 로 분류되었습니다. 모두 동일한 로그인 엔드포인트와 401 상태를 근거로 한 보수적 분류이며, 추가 상관분석 없이는 실제 공격으로 단정하기 어렵습니다.

## 5. 주목할 사건
- request_id=afXNH-mLfH8izKVCAXGL1QAAAEg | src_ip=192.168.56.1 | verdict=suspicious_auth_abuse | severity=low
  - 이유: 로그인 엔드포인트에 대한 반복 실패 흐름의 일부로 보이며, 인증 오용 또는 비정상 로그인 시도 가능성을 시사합니다. 다만 단일 요청 자체로는 브루트포스 성공이나 계정 침해를 입증하지 못합니다.
  - uri=/rest/user/login | method=POST | status=401 | score=5 | log_time=2026-05-02T19:08:31.965 09:00
  - incident_ref=request_id:afXNH-mLfH8izKVCAXGL1QAAAEg|table:security|log_id:31674|candidate:0 | merged_rows=1 | source_tables=security
  - stage1 요약: 로그인 엔드포인트에 대한 POST 요청이고 401 응답이어서 인증 실패/반복 시도 정황은 있으나, 제공된 정보만으로는 실제 brute force 반복 여부를 확인할 수 없습니다. user_agent가 프로브 성격으로 보이지만 단일 요청 1건만으로는 공격을 강하게 단정하기 어려워 인증 오용 수준으로 보수적으로 분류합니다.
- request_id=afXNEEfyxNiLza2eCu6elQAAABc | src_ip=192.168.56.1 | verdict=suspicious_auth_abuse | severity=low
  - 이유: 같은 로그인 엔드포인트에서 관측된 401 응답 요청으로, 짧은 시간 내 반복 실패 패턴의 일부입니다. 그러나 제공된 필드만으로는 실제 자격 증명 추측 성공이나 인증 우회 성공을 확인할 수 없습니다.
  - uri=/rest/user/login | method=POST | status=401 | score=5 | log_time=2026-05-02T19:08:16.367 09:00
  - incident_ref=request_id:afXNEEfyxNiLza2eCu6elQAAABc|table:security|log_id:31667|candidate:1 | merged_rows=1 | source_tables=security
  - stage1 요약: 로그인 엔드포인트(/rest/user/login)에 대해 JSON 인증 요청이 들어왔고 401 응답이 반환되어 인증 실패 정황은 있습니다. 다만 단일 요청 1건만 보이며 반복 시도나 자격 증명 추측을 직접 입증할 근거는 부족하므로, 명확한 브루트포스로 단정하기보다는 가벼운 인증 오용 신호로 분류합니다.
- request_id=afXNDumLfH8izKVCAXGL0AAAAEI | src_ip=192.168.56.1 | verdict=likely_false_positive | severity=low
  - 이유: 동일 로그인 엔드포인트와 401 응답을 근거로 탐지 규칙이 반응했을 가능성이 높습니다. 도구성 User-Agent 는 보이지만, 단일 요청만으로 공격 성공이나 실제 계정 오용을 단정할 수는 없습니다.
  - uri=/rest/user/login | method=POST | status=401 | score=5 | log_time=2026-05-02T19:08:14.126 09:00
  - incident_ref=request_id:afXNDumLfH8izKVCAXGL0AAAAEI|table:security|log_id:31664|candidate:2 | merged_rows=1 | source_tables=security
  - stage1 요약: 로그상 /rest/user/login POST 요청에 대해 401 응답이 반환되었고, user_agent도 실험/도구성 문자열로 보여 인증 실패나 단일 로그인 시도 정도로 해석하는 것이 타당합니다. 제공된 필드만으로 반복 시도나 자격 증명 추측의 증거는 부족하며, 탐지 규칙이 로그인 엔드포인트와 401 상태에 반응했을 가능성이 있습니다.

## 6. 주목할 출발지 IP
- 192.168.56.1: 분석 구간 내 3개 상위 사건과 auth_behavior_summary, ip_behavior_aggregate 가 모두 이 출발지에 집중되어 있습니다. 다만 known_asset_ips 와는 일치하지 않아 내부 테스트 가능성을 특정할 근거는 부족하며, 현재로서는 반복 로그인 실패를 보인 출발지 정도로 보수적으로 표현하는 것이 적절합니다.

## 7. 후보 밖 문맥 요청
filtered_out_breakdown 이 비어 있어 후보 밖으로 집계된 세부 노이즈는 없었습니다. 대신 top-level 사건 바깥의 문맥으로 auth_behavior_summary 와 ip_behavior_aggregate 가 존재하며, 이는 같은 출발지의 짧은 시간 내 반복 인증 실패와 높은 4xx 비율을 보여 주는 보조 정보입니다. 이 구간에서는 low_signal_fuzzing, low_signal_dir_probe, benign_normal_search, benign_fallback_html 같은 별도 후보 밖 카테고리도 관측되지 않았습니다.

정책:
- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.
- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.
- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.
- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.

## 8. IP behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 severity 상향 근거가 아닙니다.
- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수이며, auth behavior count 와 직접 합산하지 않습니다.
- scope 구분: auth behavior summary 기준으로는 11건의 auth endpoint 요청이 관찰되었고, ip behavior aggregate 기준으로는 같은 src_ip/time window 에서 11건의 전체 요청 문맥이 관찰되었다. 두 집계는 scope 가 다르므로 같은 사건 수로 직접 합산하지 않는다.
- src_ip=192.168.56.1 | window=2026-05-02T19:08:14.126 09:00 ~ 2026-05-02T19:08:31.965 09:00 | window_requests=11 | distinct_paths=1 | 4xx_ratio=1.00 | 5xx_count=0
  - attempted_categories=-
  - sensitive_path_hits=-
  - reason_hints=ip_behavior:high_4xx_ratio
  - 해석: 같은 src_ip 에서 scanning-like 또는 reconnaissance-like behavior 가 관찰된 문맥으로만 본다.
  - 제한: context_only_no_success_inference

## 9. Auth behavior context
- 아래 항목은 context-only 이며 개별 incident 승격이나 auth success 확정 근거가 아닙니다.
- auth_behavior_summaries 의 request 수는 auth endpoint family 기준 auth 요청 수이며, ip behavior aggregate request 수와 scope 가 다릅니다.
- User-Agent 값은 raw evidence 로 참조할 수 있지만 lab-* 같은 실험 prefix 자체를 공격 근거로 사용하지 않고, 비브라우저성 또는 반복적 UA 패턴, 자동화/테스트성 UA 가능성 정도로 일반화해 해석합니다.
- scope 구분: auth behavior summary 기준으로는 11건의 auth endpoint 요청이 관찰되었고, ip behavior aggregate 기준으로는 같은 src_ip/time window 에서 11건의 전체 요청 문맥이 관찰되었다. 두 집계는 scope 가 다르므로 같은 사건 수로 직접 합산하지 않는다.
- src_ip=192.168.56.1 | endpoint_family=auth_login | window=2026-05-02T19:08:14.126 09:00 ~ 2026-05-02T19:08:31.965 09:00 | auth_requests=11 | status_counts={"401": 11}
  - reason_hints=auth_abuse:repeated_auth_endpoint, auth_abuse:repeated_401, auth_abuse:rapid_fail_burst, auth_abuse:post_body_not_visible, auth_abuse:no_auth_success_inference
  - 해석: raw POST body 미확인 상태에서 반복 auth interaction 문맥으로만 본다.
  - 제한: HTTP 200 observed after repeated 401 이어도 로그인 성공 confirmed 로 단정하지 않는다.

## 10. 권고 조치
- **P1** /rest/user/login 에 대한 최근 인증 실패 로그를 추가 상관분석하여 동일 IP의 시도 간 간격, 계정명 패턴, 실패 후 성공 여부를 확인하십시오.
  - 근거: 현재 로그에서는 반복 401만 보이며, 실제 credential stuffing 또는 계정 탈취 성공 여부는 확인되지 않습니다. 추가 상관분석이 있어야 위험도를 정확히 판단할 수 있습니다.
- **P2** 해당 출발지 IP(192.168.56.1)의 동일 시간대 요청을 원본 Apache 로그와 애플리케이션 인증 로그로 교차 확인하십시오.
  - 근거: Apache 표면 로그만으로는 POST body 와 인증 처리 결과를 볼 수 없어, 오탐과 실제 공격을 구분하는 데 한계가 있습니다.
- **P2** 로그인 엔드포인트에 대해 짧은 시간 내 반복 401 임계치, 도구성 User-Agent, 비정상 burst 를 탐지하는 경보 규칙을 점검하십시오.
  - 근거: 이번 사례는 공격 성공보다 반복 실패 패턴에 가깝기 때문에, 같은 유형의 재발을 빠르게 식별하는 것이 효과적입니다.
- **P3** 필요 시 해당 출발지의 내부 테스트/운영 점검 여부를 확인하십시오.
  - 근거: known_asset_ips 와는 불일치하지만, 도구성 User-Agent 와 실험형 명명 패턴이 있어 비운영성 트래픽 가능성도 완전히 배제할 수는 없습니다.

## 11. 신뢰도와 한계
- 신뢰도는 중간 수준입니다. 401 반복과 burst 패턴은 명확하지만, POST body 원문과 인증 성공/실패의 최종 상태는 Apache 로그만으로 확인되지 않습니다.
- 세 사건은 모두 낮은 심각도로 분류되었고, 하나는 likely_false_positive 입니다. 따라서 침해 성공으로 과장하지 않았습니다.
- ip_behavior_aggregate 와 auth_behavior_summary 는 context-only 정보이며, 개별 incident 승격 근거로 사용하지 않았습니다.
- known_asset_ips 와 일치하는 출발지는 없었으므로 내부 테스트 단정은 하지 않았습니다.

## 12. 발표용 한 줄 정리
이 구간의 핵심은 동일 IP에서 로그인 엔드포인트로 반복된 401 실패입니다. 현재 증거는 ‘성공한 침해’가 아니라 ‘인증 오용 또는 자동화된 실패 시도’ 수준이며, 추가 상관분석으로만 실제 위험도를 확정할 수 있습니다.
