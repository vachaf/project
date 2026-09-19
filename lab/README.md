# lab/

## 목적

`lab/`는 실험 실행 결과와 비교 산출물을 보관하는 폴더다.

설계 문서와 실행 요청 문서는 `docs/`에 두고, 실제 실행 결과와 비교 산출물은 `lab/`에 둔다.

## 보관 대상

- 실험 세트별 산출물
- provider 비교 결과
- prepare / stage1 / stage2 결과 요약
- Markdown 비교 보고서
- 실험 과정에서 생성된 보조 결과

## 관리 원칙

- 날짜와 세트 이름을 알 수 있는 폴더명을 사용한다.
- 문서 구조 정리 작업에서는 `lab/` 산출물을 기본적으로 이동하지 않는다.
- public repo 기준으로 민감 정보, 인증 정보, 대용량 원본 로그가 포함되지 않도록 주의한다.
- 재현 가능한 요약과 비교 결과를 우선 보관한다.
- 오래된 산출물 정리는 별도 기준이 있을 때만 수행한다.

## 관련 문서

- 현재 문서 허브: `../docs/README.md`
- 현재 runtime architecture: `../docs/00_current_architecture.md`
- 분석 의미 경계: `../docs/00_apache_logs_only_evidence_boundary.md`

과거 A~H 실험 설계와 비교 기준은 해당 lab 산출물 및 Git history에서 확인한다.
