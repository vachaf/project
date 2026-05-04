# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-05-04
- 문서 역할: 앞으로 해야 할 일만 남기는 TODO
- 원칙: 완료된 항목은 이 문서에 길게 유지하지 않는다.

## 최근 완료 상태

- A~H 실험 문서, operations/design/reviews/standards/planning 문서 구조 정리 완료
- 폴더별 README와 루트 README 정비 완료
- A~H 실험 세트의 주요 context-only 문맥은 현재 regression/docs 기준에 반영 완료
- 실제 LLM 샘플 검증 1차 완료
  - F/G/H 5개 샘플 수동 리뷰 완료
  - B/C/E 3개 샘플 수동 리뷰 완료
  - 누적 8개 샘플, 72/80 = 90%
- 분석 품질 기준 문서 추가 완료
  - `docs/standards/99_analysis_quality_criteria.md`
- file disclosure verdict taxonomy 검토 완료
  - `suspicious_file_disclosure` verdict는 이미 존재하며 새 verdict 추가는 현재 필요 없음
- Stage1/Stage2 `lab-*` / experiment-like User-Agent wording guard 1차 보강 완료
  - Stage1 prompt guard 추가
  - Stage2 `stage1_carryover_rule` 추가
  - `e_r2_php_wrapper.expected.json` guard 확인 rule 보강 완료
- prepare regression 18 fixtures, stage dry-run regression 12 fixtures 모두 strict 기준 통과
  - `python3 scripts/check_prepare_regression.py --strict`
  - `python3 scripts/check_stage_dryrun_regression.py --strict`

## P1. 실제 LLM 샘플 검증 체계 정리 — 1차 완료

- 완료:
  - F/G/H 5개 샘플 수동 리뷰 완료
  - B/C/E 3개 샘플 수동 리뷰 완료
  - 누적 8개 샘플, 72/80 = 90%
  - dry-run regression과 실제 LLM 품질 검증을 분리해서 문서화
  - 분석 품질 기준 문서 추가
- 남은 관리:
  - 새 샘플은 반복 문제나 발표/보고 필요 시점에만 추가
  - provider별 비교는 필요할 때만 선택 수행
  - 실제 LLM 샘플 검증은 regression 통과 여부와 같은 의미가 아님

## P2. Stage1/Stage2 wording/taxonomy guard 관리 — 일부 완료

- 완료:
  - `suspicious_file_disclosure` taxonomy 검토
  - Stage1 `lab-*` / experiment-like UA guard 추가
  - Stage2 `stage1_carryover_rule` 추가
  - `e_r2_php_wrapper.expected.json` 보강
  - prepare/stage dry-run regression strict 통과
- 남은 후보:
  - 실제 LLM 출력에서 context-only 문맥이 과승격되는지 계속 관찰
  - 반복 wording 문제가 다시 나오면 report lint 검토
  - `suspicious_file_disclosure` 실제 LLM 재검증은 필요 시점에만 수행
- 주의:
  - Apache logs-only 한계를 유지한다.
  - status/bytes/content-type만으로 성공을 단정하지 않는다.
  - `lab-*` UA를 공격 근거로 일반화하지 않는다.

## P3. retention / output cleanup 정책 — 다음 우선순위

- 목표:
  - raw export, processed JSON, reports, manifest, lab 산출물 보관 기준을 정한다.
- 할 일:
  - 보관 대상과 삭제 후보 기준 정의
  - dry-run cleanup script 검토
  - `--apply` 옵션일 때만 실제 삭제하도록 설계
  - `lab/` 산출물은 기본 보존 원칙 유지
- 주의:
  - 삭제 자동화는 가장 나중에 적용한다.
  - 먼저 문서 기준부터 작성한다.
- 추천 다음 문서:
  - `docs/operations/99_output_retention_policy.md`

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
  - P3 이후 또는 별도 작업으로 분리 진행 가능

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
