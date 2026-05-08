# Web UI Report Viewer Execution Scope Review

- 작성일: 2026-05-08
- 문서 역할: read-only viewer 범위와 execution console 후보 범위를 분리해 운영/개발 경계를 고정하는 scope review
- 관련 문서:
  - `docs/design/99_web_ui_report_viewer_plan.md`
  - `docs/design/99_web_ui_report_viewer_phase2_candidate_review.md`
  - `docs/design/99_web_ui_report_viewer_phase2a_filter_plan.md`
  - `docs/진행상황.md`
  - `docs/planning/99_비교실험_후속개선_TODO.md`
  - `web/README.md`
  - `src/README.md`
  - `작업일지/0507.md`

## 1. 목적

- Web UI Report Viewer의 현재 범위를 `read-only report viewer`로 고정한다.
- 향후 실행 기능(execution console) 후보를 현재 운영 범위에서 분리한다.
- 사용자 UX는 단일 콘솔처럼 유지하되, 운영 역할과 책임 경계는 분명히 한다.

## 2. 현재 상태

- Phase 1A/1B/2A는 완료 상태로 본다.
- `web/`은 report list/detail/compare/filter를 제공한다.
- 단기 read-only Web UI가 읽는 주요 산출물 기준은 다음과 같다.
  - Stage2 report JSON
  - Stage2 report Markdown
  - `viewer_payload` JSON
  - pipeline manifest
  - Stage2 quality lint result
- `web/`은 위 산출물을 읽어 보여주는 역할이며, pipeline 실행이나 report rewrite를 수행하지 않는다.
- `viewer_payload`는 웹 표시용 파생 산출물이며, 원본 report의 보안 의미를 새로 생성하지 않는다.
- pipeline manifest는 run metadata, artifact path, 상태 확인용 산출물이며 보안 판정 결과가 아니다.
- `web/`은 read-only 원칙을 유지한다.
  - pipeline 실행 없음
  - report rewrite 없음
  - DB/SQLite 없음
  - raw JSON/body full search 없음
  - source IP raw search 없음
- Apache logs-only 해석 경계와 성공 단정 금지 원칙을 viewer 표시 정책에서도 유지한다.

## 3. 사용자 역할

- 일반 분석 사용자
  - 웹에서 report list/detail/compare/filter를 조회한다.
  - 실행/재생성/운영 제어 권한은 없다.
- 분석 엔지니어
  - CLI 기반으로 export 및 pipeline 실행을 담당한다.
  - 결과 산출물(report/viewer payload/manifest)의 운영 품질을 점검한다.
- 시스템 관리자
  - 실행 환경, 접근 경로, 보존/정리 정책, 장기 실행 안정성을 관리한다.
  - 인증/권한/감사 요구사항을 운영 관점에서 관리한다.
- 개발자/실험자
  - prepare/stage1/stage2/pipeline 코드 및 회귀 검증을 담당한다.
  - 기능 후보는 실험/검증 후 문서화하고 즉시 운영 기능으로 승격하지 않는다.

## 4. 서버 역할

- Target App Server / Web Service Server
  - Juice Shop, OpenCart 등 대상 웹 애플리케이션과 Apache가 동작한다.
  - Apache access/security/error log를 생성한다.
  - `apache_log_shipper.py`가 로그를 수집/전송한다.
- Log DB Server
  - MariaDB에 Apache 로그를 저장한다.
  - 분석 대상 원천 데이터를 보관한다.
- Analysis/LLM Server
  - DB export, `prepare`, Stage1, Stage2, `viewer_payload` 생성을 담당한다.
  - read-only Web UI를 실행한다.
- 운영 관점 정리
  - 사용자에게는 하나의 콘솔처럼 보이지만 서버 역할은 운영상 분리된다.
- 사용자 관점 UX
  - 위 구성은 내부적으로 분리되더라도 사용자에게는 하나의 `Security Analysis Console`로 보이게 설계한다.

## 5. 단기 운영 흐름

- 분석 엔지니어가 CLI로 export JSON 기반 pipeline을 실행한다.
- 생성된 결과(report JSON/Markdown, `viewer_payload`, manifest, lint result)를 저장하고 품질 검증을 수행한다.
- 일반 분석 사용자는 웹에서 기존 산출물을 탐색/비교한다.
- 단기 `Security Analysis Console`은 read-only console이다.
- 단기 console은 아래를 수행하지 않는다.
  - pipeline 실행
  - DB export 실행
  - regression 실행
  - report rewrite
  - raw JSON/body full search
  - source IP raw search
  - API key/config 노출
- New Analysis / pipeline run button / live progress / regression run button은 Phase 2C 후보로 보류한다.

## 6. 중기 후보: New Analysis / Job Runner

- 후보 기능
  - 웹에서 시간 구간/provider/mode 선택
  - 서버에서 DB export + pipeline 실행
  - status/progress/result 확인
- 판단
  - 위 항목은 Phase 2C execution console 후보로 분리한다.
  - 현재 범위에서는 구현하지 않으며 보류 상태를 유지한다.

## 7. `run_analysis_pipeline.py` UX 후보

- 향후 사용자용 runner 방향으로 export JSON one-shot 실행을 우선 후보로 검토한다.
- 이는 확정된 CLI 변경이 아니라 후보 방향으로 둔다.
- 기존 중간 산출물 재개(resume) 옵션은 개발/디버그 흐름과 연결되어 있으므로 즉시 제거하거나 deprecate하지 않는다.
- 본 문서에서는 runner UX를 확정하지 않고 계속 검토 대상으로 둔다.

## 8. Execution Console Risk

- output overwrite: 기존 report/manifest 덮어쓰기 방지 규칙 필요
- allowed input path: 허용된 입력 경로/패턴 강제 필요
- API key/config exposure: 키/시크릿/환경설정 노출 금지와 마스킹 규칙 필요
- long-running process: 타임아웃/취소/재시도/자원 제한 정책 필요
- failure log display: 실패 로그 노출 수준과 민감정보 제거 정책 필요
- concurrent execution: 동시 실행 충돌/락/큐잉 정책 필요
- auth/authorization: 역할별 실행 권한 분리와 감사 추적 필요
- cleanup/retention: 산출물 보존기간/정리 기준/복구 기준 필요

## 9. Phase 구분

- Phase 2A: read-only filter/navigation 완료
- Phase 2B: optional history/trend/navigation 후보
- Phase 2C: execution console 후보
  - New Analysis
  - pipeline run button
  - live progress
  - regression run button
- Phase 3: scheduling/alert/dashboard 후보

## 10. 결론

- 현재 `web/`은 read-only viewer로 유지한다.
- New Analysis / pipeline execution은 별도 risk review 전까지 보류한다.
- 사용자 UX는 하나의 Security Analysis Console로 유지하되, 운영 역할(Web/App, DB, Analysis)은 분리해 관리한다.
- Apache logs-only 원칙과 credential 비노출 원칙은 execution 기능 검토 단계에서도 완화하지 않는다.
