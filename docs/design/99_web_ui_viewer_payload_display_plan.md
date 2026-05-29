# Web UI Viewer Payload Display Plan

- 작성일: 2026-05-08
- 문서 역할: `viewer_payload.json`을 Web UI에서 read-only로 표시하기 위한 범위, fallback 전략, UI 정보 구조 후보를 정리하는 설계 문서
- 관련 문서:
  - `docs/00_current_architecture.md`
  - `docs/design/99_db_backed_log_collection_and_analysis_job_design.md`
  - `docs/design/99_db_backed_web_ui_api_safety_addendum.md`
  - `web/README.md`
  - `src/README.md`
  - `docs/design/99_web_ui_report_viewer_execution_scope_review.md`
  - `docs/design/99_run_analysis_pipeline_user_runner_ux_review.md`
  - `docs/진행상황.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`

## 0. 현재 기준 상태 업데이트

- 이 문서의 기존 판단은 2026-05-08 당시 `viewer_payload` display-only path 기준으로 보존한다.
- 2026-05-28 이후 현재 상위 운영 방향은 [../00_current_architecture.md](../00_current_architecture.md)의 DB-backed MVP다.
- Web UI read-only 원칙은 보안 결과 해석 read-only로 재정의한다.
- Web UI는 `analysis_jobs` 등록/조회와 job lifecycle 표시를 위해 DB read/write를 수행할 수 있다.
- pipeline stage 실행과 `viewer_payload` 생성은 Web UI가 직접 하지 않고 Analysis Agent가 수행한다.
- `viewer_payload` display는 여전히 read-only projection이며 Stage2 report 의미를 변경하지 않는다.
- arbitrary pipeline run button, arbitrary path input, regression run button, scheduling, alerting, destructive cleanup은 여전히 제외한다.

## 1. 목적

- `viewer_payload.json`을 Web UI에서 read-only로 표시하기 위한 표시 범위, fallback 전략, UI 구조 후보를 정리한다.
- Web UI는 새 보안 판정 생성, severity 재계산, category 재판별을 수행하지 않는다.
- `viewer_payload`는 Web UI 표시용 파생 산출물이며, 원본 Stage2 report의 보안 의미를 새로 만들지 않는다.

## 2. 현재 Web UI 범위

- 현재 `web/`은 Stage2 report viewer를 중심으로 동작한다.
- 제공 범위는 list/detail/compare/filter이며 기술 스택은 `FastAPI + Jinja2 + Plain CSS`를 유지한다.
- 당시 viewer_payload display-only path에는 외부 CDN, React, npm, webpack, 별도 DB/SQLite 의존은 도입하지 않는다.
- 보안 결과 해석 read-only 원칙을 유지한다.
  - Web UI 직접 pipeline execution 없음
  - Analysis Agent를 통한 DB-backed `full_report` 실행은 별도 현재 MVP 경로
  - report rewrite 없음
  - display-only path에서는 DB/SQLite 없음
  - DB-backed MVP의 `analysis_jobs` 등록/조회 DB read/write는 허용
  - raw JSON/body full search 없음
  - source IP raw search 없음
  - 새 보안 판정 생성 없음

## 3. viewer_payload 입력 기준

- 기본 파일명 후보:
  - `reports/<base>_viewer_payload.json`
- 관련 파일:
  - `reports/<base>_stage2_report.json`
  - `reports/<base>_stage2_report.md`
  - `reports/<base>_pipeline_manifest.json`
  - `<work-dir>/pipeline_manifest.json`
- Web UI는 위 파일을 read-only로 조회한다.
- Web UI는 `viewer_payload`를 생성하거나 수정하지 않는다.
- DB-backed MVP에서는 Analysis Agent가 job-scoped artifact root에 `viewer_payload`를 생성하고, Web UI는 DB의 artifact metadata를 통해 이를 표시할 수 있다.

## 4. Fallback 전략

팀원 피드백을 반영해 `viewer_payload` 유무와 report 유무를 분리해서 처리한다.

- Case A: `viewer_payload` 있음
  - `viewer_payload` 기반 상세 화면을 우선 사용한다.
  - `Overview / Findings / Contexts / Supporting Events / Noise / Guardrails`를 구조화해 표시한다.
  - Stage2 report JSON/Markdown 링크 또는 요약을 함께 제공한다.

- Case B: `viewer_payload` 없음, `stage2_report` 있음
  - 기존 Stage2 report detail 화면을 그대로 사용한다.
  - 과거 산출물 호환성을 유지한다.
  - `viewer_payload unavailable` 수준의 낮은 강도 안내를 표시할 수 있다.
  - `viewer_payload` 부재는 report invalid를 의미하지 않는다.

- Case C: `viewer_payload` 있음, `stage2_report` 없음
  - `viewer_payload.report` 또는 `viewer_payload.summary`를 기반으로 표시한다.
  - report 원본 링크는 missing 상태로 표시한다.
  - `payload.integrity.warnings`가 있으면 사용자에게 노출한다.
  - UI는 새 판정을 만들지 않고 payload 값만 표시한다.

- Case D: `viewer_payload`와 `stage2_report` 모두 없음
  - 기존 invalid/missing report 처리 흐름을 따른다.
  - 복구/재실행 버튼은 제공하지 않는다.
  - arbitrary Phase 2C execution 기능으로 승격하지 않는다.

## 5. UI 정보 구조 후보

- Overview
  - report title
  - generated_at
  - analysis window
  - provider/model/mode
  - total rows / candidate rows / finding count / context count / supporting event count
  - overall assessment
  - Apache logs-only guardrail note

- Findings
  - finding list table
  - column 후보:
    - severity
    - verdict
    - category
    - src_ip
    - method
    - uri
    - status_code
    - request_id
    - confidence
  - UI는 severity/category를 재계산하지 않고 payload 값을 표시한다.

- Finding Detail
  - reasoning_summary
  - evidence_fields
  - reason_hints
  - recommended_actions
  - raw_export_match metadata
  - linked supporting events count
  - linked contexts count
  - guardrail note

- Contexts
  - auth_behavior
  - ip_behavior
  - method_behavior
  - probing_sequence
  - sensitive_path_probe
  - mixed_baseline_scanner
  - static/crawler/protocol contexts
  - 모든 context는 `context_only=true`로 표시한다.
  - `should_promote_to_candidate`는 source metadata로만 보여주고 UI 승격 로직으로 사용하지 않는다.

- Supporting Events
  - top-level `supporting_events`를 별도 섹션으로 표시한다.
  - `context_only=true` badge를 표시한다.
  - `raw_log`는 payload에 있을 때만 debug/expanded 형태 후보로 제한한다.
  - 기본 UI에서는 `raw_log`를 전면 노출하지 않는다.

- Noise
  - `filtered_out_breakdown`
  - `noise_summary`
  - `top_filtered_categories`
  - `out-of-candidate recon` 요약

- Guardrails
  - Apache logs-only 해석 한계
  - success inference 금지
  - `status_code/content_type/response_body_bytes/lab-* UA`는 성공 증거가 아님

## 6. Drill-down 후보

- Finding -> Supporting Events drill-down
  - finding 선택 시 관련 supporting events를 하단 또는 side panel에 표시하는 후보.
  - 연결 기준 후보:
    - request_id
    - incident_group_key
    - src_ip + uri + time window
    - context_role
    - supporting_role
  - 단기 구현은 graph viewer가 아니라 table filter 또는 details accordion 수준으로 제한한다.

- Finding -> Contexts drill-down
  - finding의 src_ip/category와 관련된 context summary를 표시한다.
  - 예시:
    - auth finding -> auth_behavior + ip_behavior context
    - method finding -> method_behavior context
    - sensitive path finding -> probing_sequence/sensitive_path_probe context
  - 관련 context를 보여주기만 하며 finding severity를 바꾸지 않는다.

## 7. 기존 Stage2 report viewer와의 관계

- 기존 list/detail/compare 흐름은 유지한다.
- `viewer_payload` detail은 다음 후보를 둔다.
  - 기존 detail 대체
  - 별도 탭/링크 병행
- compare 화면은 우선 기존 Stage2 report 비교를 유지한다.
- `viewer_payload` compare는 별도 후속 후보로 분리한다.
- report-only 산출물과 `viewer_payload` 산출물은 공존 가능해야 한다.

## 8. ReportLoader / 파일 탐색 후보

- 전제: 기존 ReportLoader는 Stage2 report 중심이다.
- 후보 A:
  - 기존 Report model에 `viewer_payload_path` optional 추가
- 후보 B:
  - 별도 ViewerPayloadLoader 추가
- 후보 C:
  - ReportLoader가 동일 `base_name`의 `viewer_payload`를 best-effort 연결
- 단기 추천:
  - 기존 ReportLoader 구조를 크게 흔들지 않고 optional association 중심으로 검토
  - `viewer_payload`가 없어도 기존 report viewer가 계속 동작해야 함

## 9. API 후보

- `/api/report/{report_id}`는 기존 유지.
- 후보:
  - `/api/viewer-payload/{report_id}`
  - 기존 detail API에 `viewer_payload_available`, `viewer_payload_summary`만 확장
- 단기 우선순위는 template 렌더링이며 API 확장은 필요 확인 후 검토한다.

## 10. 보안/개인정보/노출 제한

- `raw_log` 기본 전면 표시 금지
- raw POST body 추정 금지
- response body 원문 추정 금지
- API key/config/secrets 표시 금지
- source IP raw search 기능 추가 금지
- raw JSON/body full search 기능 추가 금지
- payload에 민감 필드가 있어도 UI는 제한적으로 표시한다
- masking 정책은 기존 web의 `mask_value`/known_asset 흐름과 충돌하지 않게 검토한다

## 11. Non-goals

- Web UI 직접 pipeline 실행 버튼 구현 아님
- arbitrary path/provider/mode 기반 New Analysis runner 구현 아님
- live progress 구현 아님
- regression run button 구현 아님
- scheduling/alert 구현 아님
- destructive cleanup 구현 아님
- display-only path의 별도 DB/SQLite 연결 구현 아님
- DB-backed MVP의 `analysis_jobs` 등록/조회 DB read/write 금지를 뜻하지 않음
- React/npm/webpack 도입 아님
- Web UI의 `viewer_payload` 생성 기능 구현 아님
- category/severity 재계산 아님
- raw log search 구현 아님

## 12. 단계별 제안

- Phase VP-1: `viewer_payload` display plan 문서화
- Phase VP-2: read-only loader 설계 및 최소 template 후보 검토
- Phase VP-3: detail 화면에 `Overview/Findings/Contexts` 표시 MVP
- Phase VP-4: Finding -> Supporting Events drill-down 개선
- Phase VP-5: `viewer_payload` compare/history 후보 검토
- arbitrary Phase 2C execution console은 별도 risk review 전까지 보류

## 13. 검증 후보

- `viewer_payload` 있음/없음 fallback 동작 확인
- 기존 Stage2 report-only 산출물 표시 유지 확인
- malformed `viewer_payload` 처리 확인
- findings/contexts/supporting_events count 표시 확인
- `context_only` badge 표시 확인
- `raw_log` 미포함 payload에서 raw_log UI 미표시 확인
- `raw_log` 포함 payload에서도 기본 접힘/제한 표시 확인
- mobile/small viewport table overflow 확인
- web py_compile 및 template load 확인

## 14. 결론

- Web UI는 `viewer_payload`를 read-only 표시 입력으로 활용할 수 있다.
- `viewer_payload`가 없어도 기존 Stage2 report viewer는 계속 동작해야 한다.
- 우선순위는 fallback-safe, read-only, low-risk 표시다.
- drill-down은 유용하지만 단기에는 details/table filter 수준으로 제한한다.
- DB-backed MVP에서는 Analysis Agent가 생성한 `viewer_payload`를 Web UI가 표시할 수 있다.
- arbitrary execution console은 계속 보류한다.
