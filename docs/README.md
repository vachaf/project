# docs/ 안내

## 목적

`docs/`는 이 저장소의 문서 허브다. 현재 구조, Apache logs-only evidence boundary, 운영 기준, 설계 결정, 리뷰 결과, 후속 작업 계획을 연결한다.

문서를 해석할 때는 아래 원칙을 먼저 적용한다.

- 현재 canonical architecture overview는 [00_current_architecture.md](./00_current_architecture.md)를 따른다.
- Apache logs-only evidence boundary의 canonical 기준은 [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md)를 따른다.
- 상위 운영 흐름은 DB-backed MVP다.
- 기본 분석 mode는 `full_report` direct pipeline이다.
- `sliding_window / rollup / operator_queue`는 후속 `windowed_triage` 흐름으로 분리한다.
- Web UI read-only는 보안 결과 해석 read-only를 뜻하며, `analysis_jobs` 등록/조회 같은 제한된 DB-backed MVP write/read는 허용된다.
- `analysis_jobs` queue는 분석 실행 queue이고, `operator_queue`는 rollup 결과 검토 queue다.

## 먼저 읽을 문서

1. [00_current_architecture.md](./00_current_architecture.md): 현재 구조, DB-backed MVP, mode/queue 경계
2. [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md): Apache logs-only 판정 경계와 금지/권장 표현
3. [operations/01_프로젝트_방향과_실험대상.md](./operations/01_프로젝트_방향과_실험대상.md): v1.1 프로젝트 방향과 PHP sample/OpenCart/Juice Shop 역할 분리
4. [진행상황.md](./진행상황.md): 현재 완료 상태와 최신 진행 anchor
5. [planning/99_비교실험_후속개선_TODO.md](./planning/99_비교실험_후속개선_TODO.md): 현재 후속 작업 기준
6. 필요한 영역별 README
   - [design/README.md](./design/README.md)
   - [operations/README.md](./operations/README.md)
   - [planning/README.md](./planning/README.md)
   - [reviews/README.md](./reviews/README.md)

## 영역별 README

| 영역 | README | 역할 |
| --- | --- | --- |
| Design | [design/README.md](./design/README.md) | DB-backed MVP, Web UI/API safety, observability, prepare policy, Sliding Window, Stage2/report quality 설계 색인 |
| Operations | [operations/README.md](./operations/README.md) | 실행 가이드, 환경 구축, 로그/DB 운영, Analysis Job Worker 운영 기준 |
| Planning | [planning/README.md](./planning/README.md) | 최신 TODO, 후속 작업 큐, 완료 이력 분리 |
| Reviews | [reviews/README.md](./reviews/README.md) | 품질 검토, 완료 검토, post-refactor spot check, 사후 판단 근거 |
| Standards | [standards/README.md](./standards/README.md) | 실험 문서 작성 표준, 템플릿, 품질 기준 |
| Experiments | [experiments/README.md](./experiments/README.md) | A~H 세트 실험 문서 색인 |

## 현재 구조

```text
docs/
├── README.md
├── 진행상황.md
├── 00_current_architecture.md
├── 00_apache_logs_only_evidence_boundary.md
├── design/
├── operations/
├── planning/
├── reviews/
├── standards/
├── experiments/
└── archive/          # 오래된 초안, 교체된 설계안, 직접 참조하지 않는 문서 후보
```

`archive/` 이동, 문서 삭제, 본문 통합은 별도 작업에서 검토한다. 이 README는 현재 읽는 순서와 canonical 링크만 안내한다.

## 문서 분류 기준

- `design/`: 구현 설계, 해석 한계, 보류 결정, regression 설계, candidate policy, DB-backed MVP 설계
- `operations/`: 실행 방법, 환경 구축, 로그 구조, DB 운영, worker/systemd/env 운영 기준
- `planning/`: 아직 해야 할 일, 우선순위, 장기 후보, 최신 TODO
- `reviews/`: 현재 기준 문서가 아니라 품질 검토, 완료 검토, 사후 판단 근거
- `standards/`: 실험 문서 작성 표준, 공통 템플릿, 분석 품질 기준
- `experiments/`: A~H 세트별 실험 설계와 요청 문서
- `archive/`: 직접 읽을 필요는 낮지만 판단 근거 보존이 필요한 과거 문서

## 세부 문서 찾기

최상위 README에는 모든 설계 문서를 나열하지 않는다. 세부 문서는 하위 README에서 찾는다.

- DB-backed MVP, observability, prepare policy, Sliding Window는 [design/README.md](./design/README.md)
- Analysis Job Worker, MariaDB, log shipper, run_dir 운영은 [operations/README.md](./operations/README.md)
- 최신 TODO와 후속 작업 큐는 [planning/README.md](./planning/README.md)
- historical review와 quality review는 [reviews/README.md](./reviews/README.md)
- prepare 하위 모듈의 실제 역할은 [../src/prepare/README.md](../src/prepare/README.md)

## 관리 원칙

- 문서 이동과 코드 변경을 섞지 않는다.
- 오래된 문서라도 삭제/archive 전에는 README에서 historical 참고 여부를 먼저 분류한다.
- `lab/` 산출물은 문서 구조 정리와 별개로 유지한다.
- 현재 참조되는 문서는 `archive/`로 보내지 않는다.
