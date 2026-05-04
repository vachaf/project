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
- 분석 품질 기준/체크리스트 정리 완료
  - `docs/standards/99_analysis_quality_criteria.md`
  - `docs/standards/99_LLM분석_품질평가_체크리스트.md`
  - `docs/reviews/99_A-F세트_대표샘플_6선.md`
- file disclosure verdict taxonomy 검토 완료
  - `suspicious_file_disclosure` verdict는 이미 존재하며 새 verdict 추가는 현재 필요 없음
- Stage1/Stage2 `lab-*` / experiment-like User-Agent wording guard 1차 보강 완료
  - Stage1 prompt guard 추가
  - Stage2 `stage1_carryover_rule` 추가
  - `e_r2_php_wrapper.expected.json` guard 확인 rule 보강 완료
- prepare regression 18 fixtures, stage dry-run regression 12 fixtures 모두 strict 기준 통과
  - `python3 scripts/check_prepare_regression.py --strict`
  - `python3 scripts/check_stage_dryrun_regression.py --strict`
- retention/output cleanup 정책과 cleanup script 설계 문서 작성 완료
  - `docs/operations/99_output_retention_policy.md`
  - `docs/design/99_output_cleanup_script_설계.md`
- cleanup output inventory list-only prototype 추가 완료
  - `scripts/cleanup_outputs.py`
  - `tests/test_cleanup_outputs.py`
  - 삭제 기능 없음, `--apply` 미구현
  - 단위 테스트 15개 통과
- prepare module split 진행
  - `src/prepare/decoders.py` 분리 완료
  - `src/prepare/l3_hints.py` 분리 완료
  - `src/prepare/models.py` 분리 완료
  - `src/prepare/method_summaries.py` 분리 완료
  - `src/prepare/protocol_anomalies.py` 분리 완료
  - `src/prepare/auth_behavior.py` 분리 완료
  - `src/prepare/static_baseline.py` 분리 완료
  - `Candidate` / `NoiseAggregate` dataclass 이동 완료
  - `method_behavior_summaries` helper 이동 완료
  - `protocol_anomaly_summaries` helper 이동 완료
  - `auth_behavior_summaries` helper 이동 완료
  - `static_baseline_summaries` helper 이동 완료
  - prepare/stage dry-run regression strict 통과 유지

## P1. 실제 LLM 샘플 검증 체계 정리 — 1차 완료

- 완료:
  - F/G/H 5개 샘플 수동 리뷰 완료
  - B/C/E 3개 샘플 수동 리뷰 완료
  - 누적 8개 샘플, 72/80 = 90%
  - dry-run regression과 실제 LLM 품질 검증을 분리해서 문서화
  - 분석 품질 기준과 수동 평가 체크리스트 추가
  - A~F 대표 샘플 6선 문서 추가
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

## P3. retention / output cleanup — list-only prototype 완료

- 완료:
  - output retention policy 작성
  - cleanup script 설계 문서 작성
  - dry-run 기본, `--apply`에서만 삭제, 보호 경로 제외 원칙 문서화
  - `scripts/cleanup_outputs.py` list-only inventory prototype 추가
  - `tests/test_cleanup_outputs.py` 단위 테스트 추가
  - `scripts/README.md` 인덱스 반영
- 현재 동작:
  - 삭제 기능 없음
  - `--apply`는 NOT IMPLEMENTED로 종료
  - `KEEP` / `REVIEW` / `CLEANUP_CANDIDATE` / `DO_NOT_AUTO_DELETE` 분류 출력
  - `lab/`, `docs/`, `src/`, `tests/fixtures`, `tests/expected`, `.git` 보호
  - `/tmp/stage-dryrun-regression` 하위는 cleanup 후보로 분류
- 남은 후보:
  - 실제 필요 시점에만 JSONL 로그 출력 검토
  - 실제 필요 시점에만 `--kind temp-dryrun`, `--older-than-days` 필터 검토
  - `--apply` 또는 실제 삭제 기능은 별도 승인 전까지 보류
- 주의:
  - 실제 삭제 기능은 아직 구현하지 않는다.
  - `lab/`, `docs/`, `tests/fixtures`, `tests/expected`, `src/`는 기본 보호한다.
  - cleanup script가 민감 정보 여부를 자동 판단하게 하지 않는다.

## P4. prepare 모듈 분리 — 1차 진행 완료, crawler baseline 후보 검토

- 완료:
  - `decoders.py` 분리 완료
  - `l3_hints.py` 분리 완료
  - `models.py` 분리 완료
  - `method_summaries.py` 분리 완료
  - `protocol_anomalies.py` 분리 완료
  - `auth_behavior.py` 분리 완료
  - `static_baseline.py` 분리 완료
  - `Candidate` / `NoiseAggregate` dataclass 이동 완료
  - `method_behavior_summaries` helper 이동 완료
  - `protocol_anomaly_summaries` helper 이동 완료
  - `auth_behavior_summaries` helper 이동 완료
  - `static_baseline_summaries` helper 이동 완료
  - `docs/design/99_prepare_module_split_plan.md` 최신화
  - `docs/design/99_prepare_llm_input_inventory.md` 작성
  - `docs/design/99_prepare_context_summary_contract.md` 작성
  - `docs/design/99_prepare_context_summary_split_candidate.md` 작성
  - `docs/design/99_prepare_method_summary_split_plan.md` 작성 및 완료 상태 반영
  - `docs/design/99_prepare_protocol_anomaly_split_plan.md` 작성 및 완료 상태 반영
  - `docs/design/99_prepare_auth_behavior_split_plan.md` 작성 및 완료 상태 반영
  - `docs/design/99_prepare_static_baseline_split_plan.md` 작성 및 완료 상태 반영
  - prepare/stage dry-run regression strict 통과 유지
- 다음 후보:
  - `crawler_baseline_summaries` 계열 검토
  - 바로 코드 분리하지 말고 `docs/design/99_prepare_crawler_baseline_split_plan.md` 같은 좁은 계획 문서를 먼저 작성한다.
  - crawler baseline은 user-agent 해석, browser-like/crawler-like family, product/category/list/browse path 존재 여부 단정 금지와 연결되므로 static baseline보다 더 보수적으로 본다.
  - `constants.py`, `sqli_hints.py`, `xss_hints.py`, `file_disclosure_hints.py`, 전체 `context_summaries.py` 분리는 아직 보류한다.
- 조건:
  - 전면 리팩터링 금지
  - 작은 커밋 유지
  - prepare regression, stage dry-run regression, py_compile 통과 유지
  - 기존 behavior 변경 없이 구조 분리 우선

## P5. docs 유지보수

- 할 일:
  - 문서 구조가 바뀌면 루트 README와 docs/README.md 동기화
  - operations 문서가 코드 옵션과 어긋나지 않는지 주기적으로 확인
  - 새 standards/reviews 문서가 생기면 해당 README 인덱스를 먼저 갱신
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
