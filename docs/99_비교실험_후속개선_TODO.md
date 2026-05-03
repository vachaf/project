# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-05-03
- 문서 역할: 앞으로 해야 할 일만 남기는 TODO
- 원칙: 완료된 항목은 이 문서에 길게 유지하지 않는다.

## 최근 완료 요약

- prepare regression 12개 fixture 정리
- Stage1/Stage2 dry-run regression 6개 fixture 정리
- `suspicious_file_disclosure` verdict 정식화
- `ip_behavior_aggregates` context-only 도입 및 Stage2 설명 반영
- `auth_behavior_summaries` context-only 도입
- 반복 auth `401` candidate demotion 및 `auth_behavior_support` supporting context 정리
- PHP wrapper 보수 설명 반영
- SQLi 구조 hint 보강
- Log4Shell / SSRF / SSTI / webshell 제한적 L3 hint 추가

## P1. prepare 모듈 분리 설계

- 목표: `prepare_llm_input.py`의 순수 함수부터 작은 커밋으로 분리
- 후보 파일:
  - `decoders.py`
  - `sqli_hints.py`
  - `xss_hints.py`
  - `file_disclosure_hints.py`
  - `l3_hints.py`
  - `ip_behavior.py`
- 조건:
  - 전면 리팩터링 금지
  - 회귀 유지
  - 분리 후에도 `check_prepare_regression.py`, `check_stage_dryrun_regression.py`, `py_compile` 통과 유지

## P2. retention / output cleanup 정책

- raw export / processed JSON / reports 보관 기준 정의
- 기본 dry-run cleanup script 추가 검토
- `--apply` 옵션일 때만 실제 삭제
- `lab/` 산출물은 기본 보존

## P3. F세트 Auth/Login abuse 설계

- 전제:
  - raw POST body 없음
  - username/password 내용 확인 불가
- 사용 가능 신호:
  - 반복 login endpoint 접근
  - status / bytes / duration 변화
  - 같은 `src_ip` 시간창
- 해석 원칙:
  - 성공/실패 단정 금지
  - brute-force-like 또는 auth abuse suspicion 수준으로 제한
- 현재 상태:
  - prepare `auth_behavior_summaries` 추가 완료
  - repeated `401`, mixed `401/200`, single `200` baseline context 보존 완료
  - representative `401` candidate만 남기고 나머지 반복 `401`은 `supporting_events.auth_behavior_support`로 정리 완료
  - Stage2의 auth behavior 서술 보강은 추가 fixture와 실제 샘플 기준으로 계속 다듬을 여지 있음

## P4. G세트 HTTP method / protocol anomaly 설계

- 후보:
  - `OPTIONS`
  - `TRACE`
  - `PUT`
  - `DELETE`
  - `HEAD`
- 해석 원칙:
  - method probing
  - reconnaissance
  - misconfiguration 가능성
- 성공/침해 단정 금지
- 현재 상태:
  - prepare `method_behavior_summaries` 추가 완료
  - mixed `OPTIONS/TRACE/PUT/DELETE/HEAD/GET` window 를 context-only 로 보존하고 `dir_probe:*` 단독 hint 문제 완화 완료
  - Stage2 method behavior 설명 보강은 dry-run 기준 최소 반영 완료
  - 실제 LLM 샘플 기준 narrative 튜닝은 후속 검토 여지 있음
  - prepare `protocol_anomaly_summaries` 추가 완료
  - invalid method / bad protocol / missing Host / odd Host / long path row 의 filtered hint 를 `protocol_anomaly:*` 중심으로 정리 완료
  - Stage2 protocol anomaly 설명은 dry-run 기준 최소 반영 완료
  - 실제 LLM narrative 에서 protocol anomaly context 표현이 과승격 없이 유지되는지는 후속 실제 샘플로 계속 점검

## P5. 실제 LLM 샘플 검증 체계

- dry-run regression 유지가 우선
- API 비용과 비결정성을 고려해 고정 샘플 + 수동 review 중심으로 설계
- schema/prompt/report-input 구조 검증과 실제 모델 품질 검증을 계속 분리

## 장기 후보

- known asset 운영 가이드 정리
- Threat intelligence 연동 검토
- 알림, 대시보드, 자동 대응 검토

장기 후보 주의:

- Apache 로그 표면만으로 성공/침해를 단정하지 않으므로 자동 차단은 가장 나중이다.
- 실시간 Slack/email 알림, 웹 대시보드, 자동 차단은 현재 범위 밖이다.
