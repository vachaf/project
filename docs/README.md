# docs/ 안내

## 1. docs/ 폴더의 목적

`docs/`는 이 저장소의 문서 허브다. 운영 기준, 파이프라인 설명, 실험 세트 문서, 설계 결정, 리뷰 문서, 후속 작업 계획을 관리한다.

문서를 해석할 때는 아래 원칙을 먼저 본다.

- 현재 파이프라인 기준: `export -> prepare -> stage1 -> stage2`
- 분석 근거는 Apache 로그 표면에 직접 남는 필드로 제한한다.
- raw POST body, response body 원문, DB 결과, 브라우저 실행 여부는 분석 근거로 사용하지 않는다.
- `status_code=200`, `text/html`, `response_body_bytes`만으로 성공, 침해, 유출을 단정하지 않는다.

## 2. 현재 문서 탐색 방법

현재 주요 문서는 주제별 하위 폴더로 1차 정리된 상태다. 아래 순서로 찾는 것이 빠르다.

1. 현재 상태를 먼저 볼 때는 [진행상황.md](./진행상황.md)를 본다.
2. 전체 흐름과 실행 순서를 볼 때는 [00_전체_흐름_요약_가이드.md](./operations/00_전체_흐름_요약_가이드.md), [01_운영_기준_실행_가이드.md](./operations/01_운영_기준_실행_가이드.md)를 본다.
3. 실험 세트 문서는 `experiments/` 아래의 `A_set/` ~ `H_set/`을 본다.
4. 실험 표준과 결과 기록 양식은 `standards/`를 본다.
5. 설계, 회귀 검증, 해석 한계, 보류 결정은 `design/`을 본다.
6. 중간정리, 샘플 리뷰, wording 품질 검토는 `reviews/`를 본다.
7. 환경 구축, 로그 구조, 실행 가이드, 운영 메모는 `operations/`를 본다.
8. 후속 작업 계획과 TODO는 `planning/`을 본다.

## 3. 문서 분류 기준

- `standards/`: 실험 문서 작성 표준, 공통 템플릿, naming rule
- `experiments/`: A~H 세트별 설계 문서, 실행 요청 문서, 라운드별 세부 문서
- `design/`: 파이프라인 구조 설계, regression 설계, `prepare` module split 계획, context summary 설계, 해석 한계와 설계 결정
- `reviews/`: 중간정리, LLM 샘플 검증, Stage2 wording 품질 검토, 완료·평가성 문서
- `operations/`: 실행 가이드, 운영 기준, 로컬 실험 환경 기준, 로그 구조, 구축 문서
- `planning/`: 후속 작업 계획, TODO, 우선순위 관리
- `archive/`: 오래된 초안, 길어진 과거 TODO, 교체된 설계안

## 4. 현재 구조

```text
docs/
├── README.md
├── 진행상황.md
├── standards/
│   └── 실험 문서 작성 표준, 결과 기록 템플릿
├── experiments/
│   ├── A_set/
│   ├── B_set/
│   ├── C_set/
│   ├── D_set/
│   ├── E_set/
│   ├── F_set/
│   ├── G_set/
│   └── H_set/
├── design/
│   └── 파이프라인 구조, regression 설계, prepare/module split 계획, 해석 한계와 보류 결정
├── reviews/
│   └── 중간정리, LLM 샘플 검증, Stage2 wording 품질 검토
├── operations/
│   └── 실행 가이드, 환경 구축, 로그 구조, export/prepare/stage1/stage2 사용법
├── planning/
│   └── 후속 작업 계획, TODO, 우선순위 관리
└── archive/
    └── 오래된 초안, 교체된 설계안, 더 이상 직접 참조하지 않는 문서
```

`archive/`는 필요할 때 생성한다. 현재 직접 참조되는 문서는 archive로 보내지 않는다.

## 5. 현재 주요 문서 목록

아래 목록은 `docs/` 내 주요 문서의 위치를 안내하는 대표 인덱스다.

### 운영/흐름

- [진행상황.md](./진행상황.md)
- [00_전체_흐름_요약_가이드.md](./operations/00_전체_흐름_요약_가이드.md)
- [01_운영_기준_실행_가이드.md](./operations/01_운영_기준_실행_가이드.md)
- [01_프로젝트_방향과_실험대상.md](./operations/01_프로젝트_방향과_실험대상.md)
- [02_Juice_shop_환경_구축_및_설치.md](./operations/02_Juice_shop_환경_구축_및_설치.md)
- [02_LLM_환경_구축_및_설치.md](./operations/02_LLM_환경_구축_및_설치.md)
- [02_MariaDB_환경_구축_및_설치.md](./operations/02_MariaDB_환경_구축_및_설치.md)
- [02_OpenCart_환경_구축_및_설치.md](./operations/02_OpenCart_환경_구축_및_설치.md)
- [03_로그_표준과_DB_구조.md](./operations/03_로그_표준과_DB_구조.md)
- [04_로그_적재_및_운영.md](./operations/04_로그_적재_및_운영.md)
- [05_Export_LLM_분석_전략.md](./operations/05_Export_LLM_분석_전략.md)
- [06_통합_스크립트_설명_정리본.md](./operations/06_통합_스크립트_설명_정리본.md)

### 표준/템플릿

- [98_비교_실험_요청_세트_표준.md](./standards/98_비교_실험_요청_세트_표준.md)
- [99_비교_실험_결과_기록_템플릿.md](./standards/99_비교_실험_결과_기록_템플릿.md)

### 실험 세트

- A 세트: [98A_A세트_비교실험.md](./experiments/A_set/98A_A세트_비교실험.md)
- B 세트: [98B_B세트_비교실험.md](./experiments/B_set/98B_B세트_비교실험.md), [98B_B세트_비교실험_라운드2.md](./experiments/B_set/98B_B세트_비교실험_라운드2.md), [98B_B세트_SQLi_runner_전환.md](./experiments/B_set/98B_B세트_SQLi_runner_전환.md)
- C 세트: [98B_C세트_비교실험.md](./experiments/C_set/98B_C세트_비교실험.md), [98B_C세트_XSS_runner_전환.md](./experiments/C_set/98B_C세트_XSS_runner_전환.md)
- D 세트: [98B_D세트_비교실험.md](./experiments/D_set/98B_D세트_비교실험.md), [98B_D세트_runner_전환.md](./experiments/D_set/98B_D세트_runner_전환.md)
- E 세트: [98B_E세트_OpenCart_비교실험.md](./experiments/E_set/98B_E세트_OpenCart_비교실험.md), [98B_E세트_OpenCart_R2_R2B_php_wrapper.md](./experiments/E_set/98B_E세트_OpenCart_R2_R2B_php_wrapper.md), [98B_E세트_OpenCart_R3_R3B_search.md](./experiments/E_set/98B_E세트_OpenCart_R3_R3B_search.md), [98B_E세트_OpenCart_runner_전환.md](./experiments/E_set/98B_E세트_OpenCart_runner_전환.md)
- F 세트: [98B_F세트_Auth_Login_Abuse_비교실험.md](./experiments/F_set/98B_F세트_Auth_Login_Abuse_비교실험.md), [98B_F세트_Auth_Login_Abuse_R2.md](./experiments/F_set/98B_F세트_Auth_Login_Abuse_R2.md)
- G 세트: [98B_G세트_HTTP_Method_Protocol_Anomaly_비교실험.md](./experiments/G_set/98B_G세트_HTTP_Method_Protocol_Anomaly_비교실험.md)
- H 세트: [98B_H세트_Static_Crawler_Noise_비교실험.md](./experiments/H_set/98B_H세트_Static_Crawler_Noise_비교실험.md)

### 설계/회귀 검증

- [99_prepare_regression_fixture_설계.md](./design/99_prepare_regression_fixture_설계.md)
- [99_stage_dryrun_regression_설계.md](./design/99_stage_dryrun_regression_설계.md)
- [99_prepare_module_split_plan.md](./design/99_prepare_module_split_plan.md)

### 설계 결정/해석 한계

- [99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md](./design/99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md)
- [99_POST_body_visibility_한계와_해석_기준.md](./design/99_POST_body_visibility_한계와_해석_기준.md)
- [99_sensitive_path_probe_context_category_검토.md](./design/99_sensitive_path_probe_context_category_검토.md)

### 리뷰/품질

- [99_A-H세트_중간정리.md](./reviews/99_A-H세트_중간정리.md)
- [99_llm_sample_review_plan.md](./reviews/99_llm_sample_review_plan.md)
- [99_stage2_wording_quality_review.md](./reviews/99_stage2_wording_quality_review.md)

### 계획/TODO

- [99_비교실험_후속개선_TODO.md](./planning/99_비교실험_후속개선_TODO.md)

## 6. 남은 정리 후보

- `docs/가상환경_구성_요약.txt`
  - 민감 정보 가능성이 있으므로 이동 전 별도 검토가 필요하다.
- `docs/archive/`
  - 오래된 초안, 교체된 설계안, 더 이상 직접 참조하지 않는 문서가 확인되면 별도 커밋으로 이동한다.
- 하위 폴더별 `README.md`
  - `experiments/`, `standards/`, `design/`, `reviews/`, `operations/`, `planning/`에 간단한 폴더 인덱스를 추가할 수 있다.
- 절대 경로 링크
  - `/opt/web_log_analysis/...` 형태 링크는 필요 시 단계적으로 repo 기준 상대 경로로 전환한다.

## 7. 문서 이동 원칙

- 한 커밋에 대량 이동하지 않는다.
- 문서 이동과 코드 변경을 섞지 않는다.
- `lab/` 산출물 이동은 문서 정리 범위에서 제외한다.
- 이동 시 `docs/README.md`와 `docs/진행상황.md`의 링크를 함께 갱신한다.
- 현재 참조되는 문서는 `archive/`로 보내지 않는다.
- 절대 경로 링크는 가능하면 후속 작업에서 repo 기준 상대 경로로 바꾼다.

## 8. lab/와 docs/의 역할 차이

- `docs/`: 운영 기준, 설계 의도, 실험 요청, 리뷰 결과처럼 사람이 읽고 판단하는 문서를 둔다.
- `lab/`: 실험 산출물, 중간 데이터, 실행 결과처럼 작업 과정에서 생성되거나 누적되는 자료를 둔다.
- `lab/` 하위 파일은 문서 구조 정리와 별개로 유지한다.

## 9. 현재 정리 상태

주요 문서의 1차 폴더 정리는 완료된 상태다.

남은 작업은 폴더별 README 추가, `docs/가상환경_구성_요약.txt` 민감 정보 검토, archive 후보 분류, 절대 경로 링크의 단계적 상대 경로 전환이다.
