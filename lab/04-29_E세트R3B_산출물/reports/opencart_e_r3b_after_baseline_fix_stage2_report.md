# Apache 웹 로그 2차 분석 요약: 동일 내부 자산에서의 SQLi/XSS 탐지

- 생성 시각: 2026-04-30T10:05:35.813+09:00
- 분석 모드: routine
- 사용 모델: gpt-5.4-mini
- 분석 시간대: Asia/Seoul
- 분석 구간: 2026-04-29T00:04:00.000+09:00 ~ 2026-04-29T00:05:00.000+09:00
- known asset IP: 192.168.56.105, 192.168.56.109, 192.168.56.110, 192.168.56.111

## 1. 전체 평가
분석 구간(2026-04-29 00:04:00~00:05:00 KST) 동안 192.168.56.109에서 검색 파라미터를 대상으로 한 SQL 인젝션 1건과 XSS 시도 2건이 연속 관찰되었습니다. 전반적으로 공격 의도가 강한 요청 패턴이지만, 대상 IP가 known asset 이므로 내부 테스트·자체 호출·운영 점검 가능성도 함께 고려해야 합니다. Apache 로그만으로 실제 취약점 성공이나 데이터 탈취·실행 성공은 확정할 수 없습니다.

## 2. 경영 요약
- 같은 내부 IP(192.168.56.109)에서 1분 내 SQLi 1건, XSS 2건이 연속 탐지되었습니다.
- 모든 핵심 요청은 /index.php 검색 파라미터를 겨냥했고, 정상 검색 baseline과 대비해 비정상적인 페이로드가 포함되었습니다.
- 응답은 모두 200 text/html이었지만, 이 로그만으로는 실행 성공이나 실제 침해를 단정할 수 없습니다.

## 3. 파이프라인 요약
- 전체 export row 수: 4
- 1차 후보 row 수: 3
- distinct incident 수: 3
- filtered out row 수: 1
- filtered out 비집계 row 수: 1
- noise 집계 그룹 수: 0
- stage1 성공/오류: 3 / 0
- verdict 분포: {"suspicious_sqli": 1, "suspicious_xss": 2}
- severity 분포: {"high": 1, "medium": 2}
- 대표 source table 분포: {"security": 3}
- filtered_out 세부 분포: {"benign_normal_search": 1}
- 후보 밖 주요 카테고리: benign_normal_search 1건 (100.0%)

## 4. 핵심 발견
- **검색 파라미터를 이용한 전형적 SQL 인젝션 시도** [high] - `search=x')) OR 1=1 --` 형태의 페이로드가 포함되어 있어 SQL 인젝션 시도로 해석하는 것이 타당합니다. 다만 200 응답과 HTML 본문만으로는 DB 오류, 우회 성공, 실제 데이터 노출을 확인할 수 없습니다.
- **반사형 XSS 시도 2건 관찰** [medium] - `<script>alert(1)</script>` 및 HTML entity로 인코딩된 동등 페이로드가 검색 파라미터에 포함되어 있어 XSS 시도로 보는 것이 적절합니다. 그러나 Apache 로그만으로 브라우저 실행 성공이나 취약점 성공은 확인되지 않습니다.
- **known asset IP에서의 내부성 트래픽 가능성** [info] - 출발지 IP 192.168.56.109는 known asset 목록과 일치합니다. 따라서 공격자 단정 대신 내부 테스트, 자체 호출, 운영 점검 트래픽 가능성을 함께 고려해야 합니다.
- **정상 검색 baseline 과의 근접 문맥** [info] - 동일 IP·동일 엔드포인트에서 `search=apple` 정상 검색 요청이 근접 시각에 확인되어, 비교 기준(reference baseline)으로 활용할 수 있습니다. 이는 공격 의도를 낮추는 근거는 아니며, 정상/비정상 비교 문맥으로만 해석해야 합니다.

## 5. 주목할 사건
- request_id=afDMf6MXtcVwDuh1vX3CbQAAAAM | src_ip=192.168.56.109 | verdict=suspicious_sqli | severity=high
  - 이유: 전형적인 SQL 인젝션 형태의 페이로드가 포함되어 있어 입력 검증 우회 및 쿼리 조작 시도를 시사합니다. 다만 응답 본문만으로 실제 취약점 성공이나 데이터 노출은 확정할 수 없습니다.
  - uri=/index.php | method=GET | status=200 | score=8 | log_time=2026-04-29T00:04:31.521 09:00
  - incident_ref=request_id:afDMf6MXtcVwDuh1vX3CbQAAAAM|table:security|log_id:1587|candidate:2 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: 검색 파라미터에 `OR 1=1`과 SQL 주석 형태가 포함되어 있어 전형적인 SQL 인젝션 시도로 보는 것이 타당합니다. 응답이 200이고 text/html이라 실제 DB 오류나 성공 여부를 바로 단정할 수는 없지만, 요청 자체의 공격 징후는 강합니다.
- request_id=afDMiEgRzqzQm4rYaTxh1wAAAAE | src_ip=192.168.56.109 | verdict=suspicious_xss | severity=medium
  - 이유: `<script>alert(1)</script>` 형태의 전형적 XSS 페이로드가 포함되어 있습니다. HTML entity 인코딩은 우회 또는 복원 관점의 정황이며, 실제 브라우저 실행 성공은 이 로그만으로 확인되지 않습니다.
  - uri=/index.php | method=GET | status=200 | score=10 | log_time=2026-04-29T00:04:40.189 09:00
  - incident_ref=request_id:afDMiEgRzqzQm4rYaTxh1wAAAAE|table:security|log_id:1589|candidate:0 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: 검색 파라미터에 `<script>alert(1)</script>` 형태의 XSS 페이로드가 HTML 엔티티로 인코딩되어 포함되어 있어 반사형 XSS 시도로 보는 것이 타당합니다. 다만 응답이 `text/html`의 일반 페이지로 보이고, 실제 스크립트 실행 여부나 취약점 성공은 이 로그만으로 확인되지 않습니다.
- request_id=afDMhEuHmHcIKLg-is77XgAAAAQ | src_ip=192.168.56.109 | verdict=suspicious_xss | severity=medium
  - 이유: URL 인코딩된 `<script>alert(1)</script>`가 검색 파라미터에 포함되어 있어 반사형 XSS 시도로 해석됩니다. 200 text/html 응답만으로는 스크립트 실행 성공을 단정할 수 없습니다.
  - uri=/index.php | method=GET | status=200 | score=10 | log_time=2026-04-29T00:04:36.636 09:00
  - incident_ref=request_id:afDMhEuHmHcIKLg-is77XgAAAAQ|table:security|log_id:1588|candidate:1 | merged_rows=1 | source_tables=security
  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.
  - stage1 요약: 검색 파라미터에 `<script>alert(1)</script>` 형태의 전형적인 XSS 페이로드가 포함되어 있어 반사형 XSS 시도로 보는 것이 타당합니다. 다만 응답이 `text/html`이고 상태코드가 200이라서 실제 실행/취약점 성공 여부는 이 로그만으로는 확인되지 않습니다.

## 6. 주목할 출발지 IP
- 192.168.56.109: 3건의 후보 사건이 모두 이 IP에서 발생했으며, SQLi와 XSS 패턴이 /index.php 검색 기능을 대상으로 짧은 시간에 연속 관찰되었습니다. 다만 known asset 이므로 내부 테스트 또는 운영 점검 가능성을 함께 고려해야 합니다.

참고: 위 출발지 IP 중 일부는 known asset 목록과 일치하므로, 실제 공격자 IP 로 단정하지 말고 내부 테스트/자체 호출 여부를 먼저 확인해야 합니다.

## 7. 후보 밖 문맥 요청
후보 밖 분포에는 benign_normal_search 1건이 보존되어 있어, 동일 엔드포인트의 정상 검색 비교군(reference baseline)이 존재합니다. 이는 low_signal_fuzzing이나 별도 탐색성 요청으로 보기는 어렵고, 공격 후보와 정상 요청을 비교하는 기준점으로 해석하는 것이 적절합니다. filtered_out_breakdown 이 존재하므로 후보 밖 세부 분포는 실제로 있었던 것으로 봐야 합니다.

정책:
- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.
- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.
- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.
- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.

후보 밖 세부 분포:
- benign_normal_search: 1건 (100.0%)

## 8. 권고 조치
- **P1** 해당 요청들의 원본 Apache 로그와 애플리케이션 로그를 상호 대조해 동일 시각의 서버측 오류, 입력 검증 실패, WAF 차단 여부를 확인하세요.
  - 근거: Apache 로그만으로 SQLi/XSS 성공 여부를 확정할 수 없으므로, 서버측 근거를 추가로 확인해야 합니다.
- **P1** 192.168.56.109의 트래픽 목적을 내부 테스트·운영 점검·자동화 도구 사용 여부까지 포함해 즉시 확인하세요.
  - 근거: known asset IP와 일치하므로 공격자 단정 대신 내부 정당 트래픽 가능성을 배제할 수 없습니다.
- **P2** /index.php의 검색 파라미터에 대한 입력 검증, 출력 인코딩, SQL 파라미터화 적용 여부를 점검하세요.
  - 근거: 동일 엔드포인트에서 SQLi와 XSS 시도가 연속 관찰되어 취약한 입력 처리 가능성을 시사합니다.
- **P2** 동일 IP의 짧은 시간대 요청을 추가로 추적해 후속 고신호 사건과의 연계 여부를 확인하세요.
  - 근거: 현재 구간에는 3건만 보이지만, 같은 소스에서 연속된 시도가 관찰되어 추가 맥락이 중요합니다.
- **P3** 정상 검색 baseline(예: search=apple)과 공격성 요청의 응답 차이를 비교해 탐지 규칙의 오탐 가능성을 점검하세요.
  - 근거: reference baseline 이 존재하므로 정상/비정상 비교를 통해 탐지 품질을 보완할 수 있습니다.

## 9. 신뢰도와 한계
- 분석 신뢰도는 높지만, 근거는 Apache 로그 요약에 한정됩니다.
- 200 text/html 응답은 정상 라우팅, 템플릿 응답, 빈 출력, 또는 단순 처리 결과일 수 있어 성공적 침해의 직접 증거가 아닙니다.
- known asset IP 일치로 인해 내부 테스트·자체 호출 가능성을 반드시 함께 고려해야 합니다.
- XSS 페이로드는 실행 의도는 분명하나, 브라우저 실행 성공은 별도 증거가 없으면 확정할 수 없습니다.

## 10. 발표용 한 줄 정리
이번 구간의 핵심은 동일 내부 IP에서 검색 기능을 겨냥한 SQLi 1건과 XSS 2건이 짧은 시간에 연속 관찰되었다는 점입니다. 다만 대상 IP가 내부 자산이므로, 공격 시도로만 단정하지 말고 내부 테스트·운영 점검 가능성을 병행 확인해야 합니다.
