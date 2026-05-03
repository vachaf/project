# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-05-04
- 문서 역할: 앞으로 해야 할 일만 남기는 TODO
- 원칙: 완료된 항목은 이 문서에 길게 유지하지 않는다.

## 최근 완료 상태

- A~H 실험 문서, operations/design/reviews/standards/planning 문서 구조 정리 완료
- 폴더별 README와 루트 README 정비 완료
- prepare regression: 18 fixtures, `warn=0 fail=0`
- stage dry-run regression: 12 fixtures, `warn=0 fail=0`
- A~H 실험 세트의 주요 context-only 문맥은 현재 regression/docs 기준에 반영 완료

## P1. 실제 LLM 샘플 검증 체계 정리

- 목표:
  - dry-run regression과 실제 LLM 품질 검증을 분리해서 운영한다.
  - 고정 샘플 기반 수동 리뷰 절차를 정리한다.
- 할 일:
  - 샘플 선정 기준 정리
  - provider별 비교 기준 정리
  - Stage2 narrative 품질 체크 항목 정리
  - 비용/비결정성 관리 기준 정리
- 주의:
  - 실제 LLM 샘플 검증은 regression 통과 여부와 같은 의미가 아니다.

## P2. Stage2 narrative 튜닝

- 대상:
  - auth behavior
  - method behavior
  - protocol anomaly
  - static baseline
  - crawler baseline
  - sensitive path probe
  - mixed baseline/scanner context
- 할 일:
  - 실제 LLM 출력에서 context-only 문맥이 과승격되지 않는지 점검
  - 성공/침해/노출 단정 표현이 다시 나타나지 않는지 점검
  - 여러 context summary가 하나의 성공 공격처럼 합쳐지지 않는지 점검
- 주의:
  - Apache logs-only 한계를 유지한다.
  - status/bytes/content-type만으로 성공을 단정하지 않는다.

## P3. retention / output cleanup 정책

- 목표:
  - raw export, processed JSON, reports, manifest, lab 산출물 보관 기준을 정한다.
- 할 일:
  - 보관 대상과 삭제 후보 기준 정의
  - dry-run cleanup script 검토
  - `--apply` 옵션일 때만 실제 삭제하도록 설계
  - `lab/` 산출물은 기본 보존 원칙 유지
- 주의:
  - 삭제 자동화는 가장 나중에 적용한다.

## P4. prepare 모듈 분리

- 목표:
  - `prepare_llm_input.py`의 순수 함수부터 작은 단위로 분리한다.
- 후보:
  - decoders
  - SQLi hints
  - XSS hints
  - file disclosure hints
  - L3 hints
  - context summary builders
- 조건:
  - 전면 리팩터링 금지
  - 작은 커밋 유지
  - prepare regression, stage dry-run regression, py_compile 통과 유지
  - 기존 behavior 변경 없이 구조 분리 우선

## P5. docs 유지보수

- 할 일:
  - 문서 구조가 바뀌면 루트 README와 docs/README.md 동기화
  - operations 문서가 코드 옵션과 어긋나지 않는지 주기적으로 확인
  - 오래된 문서는 archive 후보로 검토하되, 직접 참조 중인 문서는 이동하지 않음
- 현재 별도 후보:
  - archive 후보 조사
  - 절대 경로 링크의 단계적 상대 경로 전환

## 장기 후보

- known asset 운영 가이드 정리
- Threat intelligence 연동 검토
- 알림, 대시보드, 자동 대응 검토

장기 후보 주의:

- Apache 로그 표면만으로 성공/침해를 단정하지 않으므로 자동 차단은 가장 나중이다.
- 실시간 Slack/email 알림, 웹 대시보드, 자동 차단은 현재 범위 밖이다.
