# Web UI Report Viewer Plan

> 작성일: 2026-05-05
> 문서 위치: `docs/design/99_web_ui_report_viewer_plan.md`
> 관련 상세 문서: [99_web_ui_report_viewer_phase1a_plan.md](./99_web_ui_report_viewer_phase1a_plan.md)

## 목적

- Stage2 report JSON을 로컬 웹 UI에서 안전하게 조회하는 설계 원칙과 phase 분할 기준을 정의한다.
- 현재 stable pipeline을 유지하면서 Phase 1A/1B/2/3의 범위를 분리한다.

## 비목표

- 이 문서에서 웹 구현 코드를 확정하지 않는다.
- src/scripts/tests/lab 동작 변경, 파이프라인 코어 변경, 외부 노출 배포를 다루지 않는다.

## 현재 repo 상태와 전제

- pipeline은 현재 regression/운영 기준에서 stable 상태다.
- Stage2 report JSON이 `reports/`, `lab/**/reports/`에 이미 존재한다.
- Stage2 quality lint CLI(`scripts/check_stage2_report_quality.py`)가 존재한다.
- 웹 UI는 로컬 운영 보조 도구이며, 분석 판정 엔진이 아니다.

## 기술 선택 요약

- 기본: FastAPI + Jinja2 + Plain CSS
- 대안: Streamlit(prototype only)
- Phase 1 제외: React/npm 번들 체인

## 핵심 설계 결정

- `REPORT_GLOBS` 기반 다중 report root 스캔
- repo-relative path hash 기반 `report_id` 사용
- `scripts/check_stage2_report_quality.py` 연동
- Plain CSS, no CDN
- localhost-only 바인딩
- report 파일 read-only 접근

## Phase 개요

- Phase 1A: report list/detail + Stage2 quality lint display
- Phase 1B: OpenAI/Anthropic report comparison
- Phase 2: pipeline execution integration
- Phase 3: regression/lint history 또는 dashboard(필요 시 SQLite)

Phase 1A 상세 구현 체크리스트와 코드 스니펫은 [99_web_ui_report_viewer_phase1a_plan.md](./99_web_ui_report_viewer_phase1a_plan.md)에서 관리한다.

## Apache Logs-Only UI Guard

- UI가 성공/침해/노출을 새로 판정하지 않는다.
- report text 본문 문장은 원문을 유지한다.
- metadata/source IP/known asset/raw preview는 마스킹 또는 기본 숨김 처리한다.
- raw JSON full view는 Phase 1A에서 기본 제외하거나 debug-only로 제한한다.

금지 badge/label:
- `Confirmed Exposure`
- `Attacker IP`
- `Real Crawler`
- `Successful Exploit`
- `DB Leak`
- `XSS Executed`

권장 badge/label:
- `Reported Verdict`
- `Source IP`
- `Known Asset`
- `Crawler-like UA`
- `Attempt Pattern`
- `Needs Review`
- `Lint PASS/WARN/FAIL`

## 보안/운영 원칙

- localhost only (`127.0.0.1`)
- API key read 금지 (`config/llm.env` 미노출)
- reports read-only
- external network exposure 금지

## 착수 조건

- [99_web_ui_report_viewer_phase1a_plan.md](./99_web_ui_report_viewer_phase1a_plan.md) 확인
- FastAPI/Jinja2 설치 가능 여부 확인
- report glob 유효성 확인
- lint script CLI 동작 확인

## 다음 문서

- Phase 1A 세부 구현: [99_web_ui_report_viewer_phase1a_plan.md](./99_web_ui_report_viewer_phase1a_plan.md)
