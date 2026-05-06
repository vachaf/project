# 99_비교실험_후속개선_TODO

- 기준 시점: 2026-05-05
- 문서 역할: 앞으로 해야 할 일만 남기는 TODO
- 원칙: 완료된 항목은 이 문서에 길게 유지하지 않는다.

## 최근 완료 상태

- A~H 실험/standards/reviews 정리 및 기준 문서 반영 완료
- retention/output cleanup list-only prototype 완료(삭제 기능 보류)
- prepare split round1/round2, constants mini-move, hints split(SQLi/XSS/file disclosure/traversal-CMDI) 완료
- auth/crawler constants move 및 shared attack/search policy boundary review 완료
- Stage2 prompt compaction + report quality lint 추가/튜닝 완료(`14 passed`)
- post-refactor dry-run/actual LLM spot check 완료, 주요 regression 기준 통과(`pass=18`, `pass=12`)
- Web UI Phase 1A/1B 핵심 구현 완료(compare view 포함) 및 기본 검증 통과
- 외부 Phase 1B 실행 가이드 stale/부분 불일치 검토 완료
- list page partial compare missing provider 1:1 layout, report viewer card/action/header polish 1차 완료

## P1. 실제 LLM 샘플 검증 체계 관리

- 남은 관리:
  - 새 샘플은 반복 문제나 발표/보고 필요 시점에만 추가
  - provider별 비교는 필요할 때만 선택 수행
  - 실제 LLM 샘플 검증은 regression 통과 여부와 같은 의미가 아님

## P2. Stage1/Stage2 wording/taxonomy guard 관찰

- 남은 후보:
  - actual LLM 출력에서 context-only 과승격을 계속 관찰
  - actual LLM 출력에서 file disclosure 성공 단정 등 과해석을 계속 관찰
  - lint warning/blocker 분포를 필요 시 확인
  - `suspicious_file_disclosure` 실제 LLM 재검증은 필요 시점에만 수행
- 주의:
  - Apache logs-only 한계를 유지한다.
  - status/bytes/content-type만으로 성공을 단정하지 않는다.
  - `lab-*` UA를 공격 근거로 일반화하지 않는다.
  - `check_stage2_report_quality.py`는 review-only lint이며 기본 모드는 CI를 깨지 않는다.

## P3. retention / output cleanup

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

## P4. prepare 모듈 분리(추가 코드 분리 보류)

- 보류:
  - `AUTOMATION_UA_PATTERNS`
  - `detect_decoded_attack_hints`
  - shared attack/search policy constants
  - normal search false-positive handling
  - candidate preservation/scoring/filtering
  - supporting_events 생성/연결 로직
  - Stage1/Stage2 reporter 구조 변경
  - expected/test fixture 변경
  - `constants.py` 대량 분리
- 다음 후보:
  - 추가 코드 분리는 당장 진행하지 않음
  - 반복 문제 재발 시 report lint, Stage2 wording, 보류 후보를 재검토

## P6. Web UI Phase 1B 후속(검증/Polish 중심)

- 상태 요약:
  - Phase 1B 핵심 구현(list/detail/compare viewer, compare route/API, provider 비교 레이아웃)과 P1 polish는 완료 상태다.
  - 완료 이력은 `docs/진행상황.md`로 이관하고, 이 섹션은 실제 남은 후보만 유지한다.

남은 선택적 polish 후보:

- [ ] Details 펼침 시 긴 리스트 가독성 추가 개선 여부 판단 (선택적 polish)
  - 현재 큰 문제는 없으나 `key_findings`/`recommended_actions`가 매우 길 때 list spacing/border 조정 여부만 필요 시 검토
- [ ] Table/card border contrast 개선 여부 판단 (선택적 polish/보류)
  - 현재 내부 콘솔 톤에서는 현상 유지 가능
  - 과도한 contrast 조정은 보류
- [ ] List page card compacting 추가 필요 여부 판단 (선택적 polish/보류)
  - 현재 card/action/header polish 이후 큰 문제 없음
  - 추가 compacting은 필요 시만 수행

QA v4 보조 스크립트 관리:

- [ ] QA v4 추가 개선 필요 여부 관찰
  - `scripts/run_qa_check_production_v4.py`는 공식 regression/lint 대체가 아니라 보조/실험 스크립트로 유지
  - `"report": null` 방어는 완료
  - 추가 QA v4 개선은 실제 사용 필요가 생길 때만 검토
  - 추가 traceback이 있으면 케이스를 분리해 재검토

## 장기 후보

- pipeline run button
- provider selection
- dry-run toggle
- live progress
- regression run button
- report search/filter
- SQLite history
- alert/dashboard
- comparison history trend
- 모바일 전용 UX
- 화려한 애니메이션
- dark/light theme toggle

주의:

- 위 항목은 Phase 1B polish 완료 후에만 검토한다.
- 현재는 Phase 2 문서 신규 생성 및 실행 TODO 승격을 하지 않는다.
- Phase 2를 시작하려면 read-only viewer 범위를 실행/운영 콘솔로 확장할지 먼저 별도 판단한다.
