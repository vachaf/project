# LLM 기반 침입로그 분석 시스템

Apache 웹 로그를 MariaDB에 적재한 뒤 `export -> prepare -> stage1 -> stage2` 순서로 분석하고 보고서를 생성하는 파이프라인입니다.

## 빠른 시작

실제 운영/실행 기준은 [docs/01_운영_기준_실행_가이드.md](docs/01_운영_기준_실행_가이드.md) 한 문서로 통일합니다.

- 운영자가 바로 따라야 하는 절차: `docs/01_운영_기준_실행_가이드.md`
- 전체 구조와 서버 역할: `docs/00_전체_흐름_요약_가이드.md`
- 구축 절차: `docs/02_LLM_환경_구축_및_설치.md`
- 로그 적재 운영 정책: `docs/04_로그_적재_및_운영.md`
- 분석 기준과 데이터 구조: `docs/05_Export_LLM_분석_전략.md`
- 스크립트 역할 참조: `docs/06_통합_스크립트_설명_정리본.md`

## 현재 운영 기준 디렉터리

- raw 입력: `/opt/web_log_analysis/data/raw`
- 전처리 결과: `/opt/web_log_analysis/data/processed`
- 보고서 결과: `/opt/web_log_analysis/reports`
- 실행 로그: `/opt/web_log_analysis/logs`

## 문서 읽는 순서

1. `docs/01_운영_기준_실행_가이드.md`
2. `docs/00_전체_흐름_요약_가이드.md`
3. 필요 시 `docs/02`, `docs/04`, `docs/05`, `docs/06`

## 주의

- 실제 운영 명령, 경로, OpenAI/Claude 차이는 `docs/01_운영_기준_실행_가이드.md`를 우선합니다.
- 일부 코드 기본값은 현재 운영 경로와 다를 수 있습니다. 이런 경우에도 문서상 운영 기준은 `docs/01`을 기준으로 봅니다.
