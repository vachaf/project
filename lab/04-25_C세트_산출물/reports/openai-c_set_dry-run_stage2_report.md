# 드라이런 보안 분석 보고서

- 분석 모드: routine
- 사용 모델 예정: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-04-25T21:30:00.000+09:00 ~ 2026-04-25T21:33:00.000+09:00
- known asset IP: 192.168.56.1, 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 요약
- 전체 export row 수: 10
- 1차 후보 row 수: 9
- distinct incident 수: 9
- filtered out row 수: 1
- probing sequence summary 수: 0
- static baseline summary 수: 0
- crawler baseline summary 수: 0
- sensitive path probe summary 수: 0
- mixed baseline/scanner summary 수: 0
- ip behavior aggregate 수: 1
- auth behavior summary 수: 0
- method behavior summary 수: 0
- protocol anomaly summary 수: 0
- stage1 성공/오류: 9 / 0
- key finding severity 기준: max_top_incident_severity=high | context-only summary 단독으로 severity 를 올리지 않음
- 후보 밖 주요 카테고리:
  - benign_normal_search: 1건 (100.0%)
- 정상 baseline 정책: benign_normal_search / normal_search_baseline 은 후보 밖 탐색성 요청이 아니라 정상 비교군 또는 reference baseline 으로 해석
- context-only IP behavior aggregates:
- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수다.
  - src_ip=192.168.56.110 | window_requests=10 | distinct_paths=1 | 4xx_ratio=0.00 | attempted_categories=xss

## 상위 incident 미리보기
- incident_ref=request_id:aey0EXHCi27Md-UoFOnpMwAAAEg|table:security|log_id:9566|candidate:0 | request_id=aey0EXHCi27Md-UoFOnpMwAAAEg | src_ip=192.168.56.110 | verdict=likely_xss | severity=high | uri=/rest/products/search | merged_rows=1 | known_asset=yes
- incident_ref=request_id:aeyz-HHCi27Md-UoFOnpMQAAAEQ|table:security|log_id:9563|candidate:1 | request_id=aeyz-HHCi27Md-UoFOnpMQAAAEQ | src_ip=192.168.56.110 | verdict=likely_xss | severity=high | uri=/rest/products/search | merged_rows=1 | known_asset=yes
- incident_ref=request_id:aeyz73HCi27Md-UoFOnpMAAAAEM|table:security|log_id:9562|candidate:2 | request_id=aeyz73HCi27Md-UoFOnpMAAAAEM | src_ip=192.168.56.110 | verdict=likely_xss | severity=high | uri=/rest/products/search | merged_rows=1 | known_asset=yes
- incident_ref=request_id:aey0PXHCi27Md-UoFOnpNAAAAEk|table:security|log_id:9567|candidate:3 | request_id=aey0PXHCi27Md-UoFOnpNAAAAEk | src_ip=192.168.56.110 | verdict=likely_xss | severity=high | uri=/rest/products/search | merged_rows=1 | known_asset=yes
- incident_ref=request_id:aey0THHCi27Md-UoFOnpNgAAAEw|table:security|log_id:9569|candidate:4 | request_id=aey0THHCi27Md-UoFOnpNgAAAEw | src_ip=192.168.56.110 | verdict=likely_xss | severity=high | uri=/rest/products/search | merged_rows=1 | known_asset=yes

## 메모
- dry-run 이므로 실제 LLM API 호출 없이 요약 입력만 검증했다.
- incident 는 request_id 우선, 없으면 src_ip+method+uri+status_code+1초 단위 시각으로 병합했다.
- filtered_out_breakdown 은 noise_summary 와 별도로 보존되며, 보고서 초안에도 함께 노출된다.
- static_baseline_summaries, crawler_baseline_summaries, sensitive_path_probe_summaries, mixed_baseline_scanner_summaries, auth_behavior_summaries, method_behavior_summaries, protocol_anomaly_summaries, ip_behavior_aggregates 는 scope 가 다르므로 count 를 range 로 합치거나 같은 사건 수처럼 직접 합산하지 않는다.
- key_findings severity 는 명시적인 non-context-only 근거가 없으면 top_incidents 최대 severity 를 넘기지 않는다.
- top_incidents 가 없거나 모두 info/low 이고 관찰 근거가 context-only summary 중심이면 key_findings severity 는 info 또는 low 를 사용한다.
- static_baseline_summaries 는 context-only 이며 static/health/browse baseline 문맥으로만 사용하고 static file 존재, robots/sitemap 내용, JS 실행, file exposure, health 정상 여부를 단정하지 않는다.
- crawler_baseline_summaries 는 context-only 이며 crawler-like baseline 문맥으로만 사용하고 crawler authenticity, robots/sitemap 내용, site structure, page existence, attack success 를 단정하지 않는다.
- sensitive_path_probe_summaries 는 context-only 이며 scanner-like sensitive path probing 문맥으로만 사용하고 WordPress 존재, admin access, .env/phpinfo/server-status/backup 노출, 차단 성공, attack success 를 단정하지 않는다.
- mixed_baseline_scanner_summaries 는 context-only 이며 baseline/static/crawler-like 와 scanner-like 문맥을 분리해서 설명하고, 이를 같은 성공 공격이나 단일 침해 체인으로 합치지 않는다.
- ip_behavior_aggregates 는 context-only 이며 개별 incident 승격이나 severity 상향 근거로 사용하지 않는다.
- auth_behavior_summaries 는 context-only 이며 raw POST body 미확인 상태에서 auth sequence 문맥으로만 사용한다.
- method_behavior_summaries 는 context-only 이며 method probing / baseline 문맥으로만 사용하고 method 허용이나 성공 근거로 사용하지 않는다.
- protocol_anomaly_summaries 는 context-only 이며 request parsing / protocol surface 문맥으로만 사용하고 우회 성공이나 침해 성공 근거로 사용하지 않는다.
- User-Agent 값은 evidence 로 참조할 수 있지만 lab-* 같은 실험 prefix 자체를 공격 근거로 사용하지 않는다.
