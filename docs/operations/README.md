# operations

## 목적

- `operations/`는 실행 가이드, 운영 기준, 환경 구축, 로그 구조 문서를 둔다.
- `export -> prepare -> stage1 -> stage2` 흐름을 실제로 따라갈 때 필요한 운영 문서를 모아 둔다.

## 문서 목록

- 전체 흐름/실행
  - [00_전체_흐름_요약_가이드.md](./00_전체_흐름_요약_가이드.md): 전체 파이프라인 흐름 요약
  - [01_운영_기준_실행_가이드.md](./01_운영_기준_실행_가이드.md): 운영 기준과 실행 절차(`export --table`, pipeline auto prepare source table 해석, Web UI run_dir default scan 기준 포함)
  - [06_통합_스크립트_설명_정리본.md](./06_통합_스크립트_설명_정리본.md): 통합 스크립트 설명(`run_analysis_pipeline.py`, `--run-dir`, run_dir manifest/Web UI 연결 기준 포함)
- 프로젝트/실험 대상
  - [01_프로젝트_방향과_실험대상.md](./01_프로젝트_방향과_실험대상.md): 프로젝트 방향과 실험 대상 정리
- 환경 구축
  - [02_LLM_환경_구축_및_설치.md](./02_LLM_환경_구축_및_설치.md): LLM 환경 구축과 설치
  - [02_Juice_shop_환경_구축_및_설치.md](./02_Juice_shop_환경_구축_및_설치.md): Juice Shop 환경 구축과 설치
  - [02_MariaDB_환경_구축_및_설치.md](./02_MariaDB_환경_구축_및_설치.md): MariaDB 환경 구축과 설치
  - [02_OpenCart_환경_구축_및_설치.md](./02_OpenCart_환경_구축_및_설치.md): OpenCart 환경 구축과 설치
- 로그/DB/export
  - [03_로그_표준과_DB_구조.md](./03_로그_표준과_DB_구조.md): 로그 표준과 DB 구조
  - [04_로그_적재_및_운영.md](./04_로그_적재_및_운영.md): 로그 적재와 운영
  - [05_Export_LLM_분석_전략.md](./05_Export_LLM_분석_전략.md): export와 LLM 분석 전략(`table_option/counts/data` 기반 auto resolution, run_dir 표준 산출물/manifest 중심 흐름 포함)
  - [99_output_retention_policy.md](./99_output_retention_policy.md): 산출물 보존/정리 기준

## 읽는 순서

1. [00_전체_흐름_요약_가이드.md](./00_전체_흐름_요약_가이드.md)
2. [01_운영_기준_실행_가이드.md](./01_운영_기준_실행_가이드.md)
3. 필요한 환경 구축 문서
4. [03_로그_표준과_DB_구조.md](./03_로그_표준과_DB_구조.md)
5. [04_로그_적재_및_운영.md](./04_로그_적재_및_운영.md)
6. [05_Export_LLM_분석_전략.md](./05_Export_LLM_분석_전략.md)
7. [06_통합_스크립트_설명_정리본.md](./06_통합_스크립트_설명_정리본.md)
8. [99_output_retention_policy.md](./99_output_retention_policy.md)

## 관리 원칙

- 실행 방법, 환경 구축, 로그 구조, 운영 절차는 `operations/`에 둔다.
- 실험 요청 세트는 `experiments/`에 둔다.
- 실험 결과 산출물은 `lab/`에 둔다.

## Web UI run_dir default scan

- Web UI 기본 목록은 `runs/*/manifest.json`을 기준으로 구성한다.
  - `REPORT_GLOBS=["runs/*/manifest.json"]`
- 기존 flat/lab glob은 호환성 후보로만 보존하며 기본 scan에서 제외한다.
  - `LEGACY_REPORT_GLOBS=["reports/*_stage2_report.json", "lab/**/reports/*_stage2_report.json"]`
- 따라서 `reports/` 또는 `lab/**/reports/` 산출물만 있는 경우 Web UI 기본 목록에 나오지 않는 것이 정상이다.

## Run Directory Output Flow

- Web UI 표시를 운영 기본 흐름으로 사용할 때는 pipeline 실행 시 `--run-dir runs/<run_id>`를 지정한다.
- run_dir 표준 파일은 `manifest.json`, `export.json`, `llm_input.json`, `stage1_results.json`, `stage2_report_input.json`, `stage2_report.json`, `stage2_report.md`, `viewer_payload.json`, `noise_summary.json`이다.
- `--run-dir` 없이 flat output만 생성하는 실행은 분석 자체는 가능하지만 Web UI 기본 목록 연동 대상이 아니다.

## Operational Output Hygiene

- `data/raw/`, `data/processed/`, `reports/`, `runs/`는 운영 산출물이며 기본적으로 repo에 커밋하지 않는다.
- `runs/`는 runtime artifact로 관리한다.
- `.gitignore`에 `/runs/`가 있어야 하며, 실수로 tracked 된 경우 아래처럼 index에서만 제거한다.

```bash
git rm -r --cached runs/
```

- `pathspec did not match any files`가 나오면 현재 index에 `runs/` tracked 항목이 없다는 의미다.

## Smoke Check

- loader 회귀:
  - `tests/test_web_loader_run_dir_scan.py`: `5 passed`
  - 관련 묶음: `24 passed`
- actual smoke:
  - scenario: `Mixed_Context_Heavy`
  - security export 기준 actual LLM 실행
  - run_dir: `runs/webui_run_dir_smoke_actual_2026-05-10`
  - Web UI list/detail/payload 표시 확인
  - payload 요약: `finding_count=2`, `context_count=3`, `supporting_event_count=0`
