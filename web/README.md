# web/

## 목적

`web/`은 Stage2 report viewer Web UI를 위한 FastAPI 서버, Jinja2 템플릿, CSS 정적 자산을 관리한다.

## 현재 기준 상태

- 현재 canonical architecture overview는 [../docs/00_current_architecture.md](../docs/00_current_architecture.md)를 따른다.
- DB-backed MVP에서는 Web UI가 `analysis_jobs` 등록/조회와 job lifecycle 표시를 위해 DB read/write를 수행할 수 있다.
- Web UI read-only 원칙은 보안 결과 해석 read-only를 뜻한다.
- Stage1/Stage2/viewer_payload 생성은 Web UI가 직접 수행하지 않고 Analysis Agent가 수행한다.
- 기존 파일 기반 report viewer 경로는 Stage2 report / `viewer_payload` read-only projection으로 유지하며 Stage2 의미를 변경하지 않는다.

## 기술 원칙

- `FastAPI + Jinja2 + Plain CSS` 유지
- viewer-only display path는 외부 CDN, React, npm, webpack, 별도 DB/SQLite 의존 없이 동작
- report files와 `viewer_payload`는 read-only projection으로 조회만 수행
- Stage2 report viewer는 새 보안 판정을 생성하지 않음
- Stage2 quality lint는 `scripts/check_stage2_report_quality.py` 호출 결과를 표시/연계하는 방향 유지
- 보안 결과 해석 read-only 원칙 유지:
  - Web UI 직접 pipeline execution 없음
  - pipeline stage 실행은 Analysis Agent 담당
  - report rewrite 없음
  - viewer-only display path에서는 별도 DB/SQLite 없음
  - DB-backed MVP의 `analysis_jobs` 등록/조회 DB read/write는 허용
  - raw JSON/body full search 없음
  - source IP raw search 없음
  - arbitrary pipeline run button / arbitrary path input 없음
  - regression run button 없음
  - scheduling / alerting / destructive cleanup 없음

## 현재 주요 파일

- `app.py`: viewer 라우트와 템플릿 렌더링
- `templates/`: `index.html`, `detail.html`, `compare.html`
- `static/style.css`: viewer 스타일

## Phase 2A Filter MVP

- `/` list page에서 server-side GET query 기반 filter 지원
- 지원 filter:
  - `q`: `filename` / `scenario` / `report_id` 대상 대소문자 무시 부분 일치
  - `lint`: `pass | warn | fail | error`
  - `pair`: `both | partial`
  - `provider`: `openai | anthropic | unknown`
- 다중 filter는 AND로 결합
- invalid/empty filter는 safe ignore
- result count는 report 수가 아니라 group 수 기준
- active filter chips, Clear all, no-result state 제공
- 기존 Detail / Compare / Compare partial 링크 및 pair ready/missing pair 표시는 유지

예시 query:

- `/?q=xss`
- `/?q=h_r4`
- `/?lint=fail`
- `/?pair=partial`
- `/?provider=openai`
- `/?q=h_r4&provider=openai&pair=both`
- `/?q=__no_such_report__`

## UI polish 범위 원칙

- 우선 수정 범위는 template/CSS 중심
  - `templates/index.html`
  - `templates/detail.html`
  - `templates/compare.html`
  - `static/style.css`
- Python 로직 변경은 필요 최소로 제한
