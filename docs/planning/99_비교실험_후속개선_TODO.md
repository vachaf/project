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

- 현재 상태:
  - Phase 1B compare view 핵심 구현은 이미 존재한다.
  - 따라서 `compare.html 생성`, `compare CSS 추가`, `index compare link 추가`, `/compare route 추가`, `compare_reports() 생성`은 신규 TODO가 아니라 현존/확인 완료 항목이다.
- 남은 TODO:
  - 실제 브라우저에서 `/`, `/report/{report_id}`, `/compare/{timeframe_id}` 재확인
  - `Compare` / `Compare (partial)` UX 흐름 확인
  - `docs/design/99_web_ui_report_viewer_ui_polish_plan.md` 기준 template/CSS 중심 개선
  - Apache logs-only 원칙 유지 점검
  - IP masking 유지 점검
  - UI가 새 보안 판정을 생성하지 않는지 점검

### 추가 확인 항목 — 2026-05-06 팀원 체크리스트 반영

- 팀원 UI polish checklist는 Phase 2가 아니라 Phase 1B polish 완료 기준으로 관리한다.
- Phase 2 기능 확장은 Phase 1B polish + 브라우저 검증 완료 후 별도 문서화 여부를 판단한다.
- 현재는 Phase 2 문서 신규 생성을 보류한다.

Phase 1B polish checklist:

P1:

- [x] Compare Metrics를 provider panels보다 위에 두는 구조 최종 확인/개선
  - 팀원 체크 기준 현재 compare metrics가 provider panels 아래에 있을 가능성이 있어 우선 확인
  - provider panel 내용이 길어져도 주요 비교 지표 접근성이 떨어지지 않아야 함
  - count 차이는 실제 사건 수 차이가 아니라 report output 차이로만 표시
- [x] Provider panel 긴 section을 `<details>` 등으로 접기
  - `key_findings`, `recommended_actions` 등 긴 섹션 우선 검토
  - report text 원문 의미는 변경하지 않음
- [x] Header compacting 최종 확인
  - 현재 header 크기 약 1905x120px 수준으로 큰 문제 없음
- [x] Missing provider panel 시각 일관성 최종 확인
  - `Missing report`, `N/A`, detail link 없음 유지
  - partial group placeholder 및 1:1 card layout 확인됨

P2:

- [x] Badge spacing 1차 완료
  - 기본 badge padding/spacing은 유지
  - 추후 색상 대비 문제 발견 시만 조정
- [ ] Table/card border contrast 개선
  - 카드와 테이블 border가 단일 tone으로 보이는 부분 확인
  - 너무 강한 contrast가 되지 않도록 내부 콘솔 톤 유지
- [ ] List page card compacting 최종 확인
  - card/action/header polish 1차 반영 완료
  - 현재 나쁘지 않으나 미세 조정 필요 여부를 추가 판단
- [x] meta-grid spacing 1차 완료
  - metadata spacing은 현재 일관성 있게 관리됨
  - 추가 변경은 필요 시만 수행

P3:

- [x] hover/focus state 1차 완료
  - `.provider-card:hover`, `.compare-panel:hover`, `.action-link:hover`, `.action-link:focus-visible`, `a:focus-visible` 존재
  - keyboard focus outline 유지
- [x] section collapse styling 개선
  - `<details>` 적용 후 summary/collapse styling 정리
- [x] small viewport polish 최종 확인
  - 화면상 큰 문제 없음
  - 최종 확인 완료로 판단

- 남은 TODO 정리
  - Table/card border contrast 개선 여부 판단
  - List page card compacting 추가 필요 여부 판단
- QA v4 포맷 불일치 방어
  - C세트 및 E R2B의 `notable_incidents` 키 누락 원인 확인
  - QA 스크립트에서 missing key를 안전하게 처리할지, report schema/format 문서로 관리할지 결정
  - AttributeError로 전체 일괄 검증이 중단되지 않도록 방어 로직 검토
- 구현 제약:
  - Python 로직 변경은 가급적 피한다.
  - `FastAPI + Jinja2 + Plain CSS`를 유지한다.
  - `React`/`npm`/`webpack`/`DB`/외부 CDN은 사용하지 않는다.

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
