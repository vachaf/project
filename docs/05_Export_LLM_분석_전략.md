# 05_Export_LLM_분석_전략

- 문서 상태: 통합본(개정)
- 버전: v1.4
- 작성일: 2026-04-09
- 적용 대상: Apache → MariaDB → JSON export → 정제 → LLM 분석 파이프라인 기준 문서
- 연계 문서:
  - `01_프로젝트_방향과_실험대상.md`
  - `02_MariaDB_환경_구축_및_설치.md`
  - `03_로그_표준과_DB_구조.md`
  - `04_로그_적재_및_운영.md`

---
## 1. 문서 목적

이 문서는 현재 구축된 로그 수집 환경에서, **MariaDB에 적재된 Apache 로그를 어떤 방식으로 export 하고, 어떤 형태로 정제한 뒤, LLM에 전달하여 분석 및 보고서 생성에 활용할 것인지**를 정리한 문서이다.

이번 프로젝트의 목적은 단순 로그 조회가 아니라, 다음 흐름을 반복 가능한 형태로 만드는 데 있다.

1. KST 기준으로 분석 구간을 지정한다.
2. MariaDB에서 원본 로그를 JSON으로 export 한다.
3. 반복적인 정상 요청과 정적 리소스 요청 등 노이즈를 분리한다.
4. 분석 가치가 높은 요청 후보만 선별한다.
5. LLM으로 1차 분류를 수행한다.
6. 분류 결과를 바탕으로 2차 보고서를 생성한다.

즉, 이 문서는 **원본 로그 보존 전략과 LLM 입력 전략을 분리**하고, **토큰 낭비와 비용을 줄이면서도 분석 품질을 유지하는 방법**을 정의하는 기준 문서다.

---

## 2. 문서 범위

### 2.1 이 문서에서 다루는 것

- `export_db_logs_cli.py` 기준 JSON export 전략
- UTC 저장 / KST 조회·출력 원칙
- 원본 export 와 분석용 정제본의 역할 분리
- LLM 배치 위치
- 기본 운영 모델과 검증용 상위 모델의 사용 원칙
- 정제 Python 코드의 배치 위치와 역할 분리
- 노이즈 필터링 원칙
- 분석 후보 추출 기준
- LLM 입력 JSON 권장 구조
- LLM 1차 분석 및 2차 보고서 작성 흐름
- `likely_html_fallback_response` 와 선택적 `resp_html_*` 필드를 downstream 으로 전달하는 원칙
- 운영 시 권장 디렉터리 구조와 산출물

### 2.2 이 문서에서 다루지 않는 것

- Apache 로그 생성 설정 상세
- MariaDB 테이블 DDL 상세
- Shipper 구현 상세
- 공격 판정 정규식의 모든 세부 구현
- 외부 SIEM, 대시보드, 알림 시스템 구현

이 문서는 **LLM 분석 단계의 운영 기준서**이며, 로그 생성과 적재 자체의 상세 구현은 별도 문서에서 다룬다.

---

## 3. 전제 환경과 LLM 배치 위치

### 3.1 현재 기준 환경

현재 기준 환경은 다음과 같다.

- 웹서버: Apache2 Reverse Proxy 기반 로그 수집 서버
- 애플리케이션: OWASP Juice Shop (Docker)
- DB 서버: MariaDB `web_logs`
- 테이블:
  - `apache_access_logs`
  - `apache_security_logs`
  - `apache_error_logs`
- 기본 export 도구: `export_db_logs_cli.py`
- 기본 시간 원칙:
  - DB 저장 시각은 UTC 기준
  - 사용자의 조회 범위 입력은 KST 기준
  - 출력 JSON 시간도 KST 기준 ISO-8601 문자열 사용

즉, 저장 계층은 UTC를 기준으로 정렬 안정성을 유지하고, 사람이 읽는 조회 및 분석 단계는 KST를 기준으로 맞춘다.

### 3.2 LLM은 별도 분석 VM에 둔다

현재 구조에서 LLM은 **웹서버도 아니고 DB 서버도 아닌, 별도 분석 VM** 에 배치하는 것을 기준으로 한다.

구성은 다음과 같이 나눈다.

- **웹서버**
  - Apache 로그 생성
  - Python shipper 실행
- **DB 서버**
  - MariaDB 저장 및 조회
- **분석 VM**
  - JSON export 실행
  - 노이즈 필터링 및 후보 추출
  - LLM 호출
  - 보고서 생성

이렇게 분리하는 이유는 다음과 같다.

1. 웹서버의 수집 기능과 LLM 분석 기능을 분리할 수 있다.
2. DB 서버를 저장 계층으로만 유지할 수 있다.
3. API 키, 프롬프트, 전처리 코드를 별도 노드에서 관리할 수 있다.
4. 발표·검증 시 상위 모델 사용 정책을 운영 계층과 분리해 적용하기 쉽다.

### 3.3 권장 분석 디렉터리 구조

분석 VM에는 아래와 같은 별도 작업 디렉터리를 두는 것을 권장한다.

```text
/opt/web_log_analysis/
├── .venv/
├── config/
│   └── llm.env
├── src/
│   ├── export_db_logs_cli.py
│   ├── prepare_llm_input.py
│   ├── llm_stage1_classifier.py
│   ├── llm_stage2_reporter.py
│   └── run_analysis_pipeline.py
├── raw/
├── processed/
└── reports/
```

핵심은 **분석용 스크립트는 `src/` 아래에 두고, 산출물은 `raw/`, `processed/`, `reports/`로 분리한다**는 점이다.

---

## 4. 기본 원칙

### 4.1 DB는 원본 보존 계층이다

DB에는 가능한 한 원본에 가까운 로그를 유지한다.

- access 로그는 전체 요청 흐름 보존
- security 로그는 탐지·분류용 확장 필드 보존
- error 로그는 장애 및 상관분석용 보존

DB는 **원본 보존과 재조회**를 담당한다. 따라서 LLM 전송을 위해 DB 원본을 훼손하거나, DB에서부터 과도하게 제외 규칙을 적용하는 것은 바람직하지 않다.

### 4.2 LLM에는 원본 전체가 아니라 분석용 정제본을 우선 전달한다

LLM은 텍스트 입력 비용과 문맥 길이의 영향을 크게 받는다. 따라서 DB export 결과 전체를 그대로 넘기기보다, 전처리 과정을 거친 분석용 JSON을 기본 입력으로 사용한다.

현재 표준에서 가장 중요한 운영 원칙은 다음과 같다.

- **routine LLM 분석의 기본 입력은 security 로그 export** 이다.
- access 로그는 운영 확인용 기준선으로 남기되, routine LLM 후보 생성의 기본 입력으로는 사용하지 않는다.
- error 로그는 5xx, `request_id`, `error_link_id`가 연계될 때만 보조 근거로 붙인다.

권장 우선순위는 다음과 같다.

1. 원본 JSON export 생성
2. 노이즈 식별 및 집계
3. 분석 후보 추출
4. 후보 중심 LLM 입력 구성
5. 필요 시 원본 일부를 보조 근거로 첨부

### 4.3 잡음은 삭제보다 분리가 우선이다

정상 잡음을 바로 폐기하지 않는다.

- 원본 export 에서는 유지한다.
- 분석용 JSON 에서는 제외, 축약, 집계 중 하나를 선택한다.
- 보고서에는 필요할 때 요약 통계만 포함한다.

즉, **저장 계층과 분석 계층을 분리**하는 것이 핵심이다.

### 4.4 보고서는 두 단계로 나눈다

LLM은 한 번에 모든 것을 처리하게 하기보다 다음처럼 두 단계로 나누는 편이 안정적이다.

1. **1차 분석**: 요청 후보를 유형별로 분류
2. **2차 분석**: 분류 결과를 바탕으로 사람이 읽는 보고서 작성

이 방식은 오탐과 설명 누락을 줄이고, 재현 가능한 결과를 얻는 데 유리하다.

### 4.5 평상시에는 mini 모델을 기본으로 사용한다

운영 기본값은 **비용과 속도를 우선한 mini 계열 모델**로 둔다.

현재 기준 기본 운영 모델은 다음과 같이 잡는다.

- **기본 운영 모델**: `gpt-5.4-mini`
- **상위 검증 모델**: `gpt-5.4`

즉, 일상 분석과 반복 실험에서는 mini 모델을 사용하고, 상위 모델은 다음 경우에만 제한적으로 사용한다.

- 발표용 시연 전 점검
- 초반 기준선 테스트
- 중간 점검 테스트
- 최종 테스트 및 최종 보고서 검증

이 정책의 목적은 **평상시 운영 비용을 낮추면서도, 중요한 시점에는 더 높은 품질의 결과를 확보하는 것**이다.

---

## 5. 모델 사용 정책

### 5.1 기본 운영 정책

현재 문서 기준 모델 사용 정책은 다음과 같다.

#### 5.1.1 평상시 운영

- 1차 분류: `gpt-5.4-mini`
- 2차 보고서: `gpt-5.4-mini`

용도:

- 일일 실험 로그 검토
- 반복 테스트
- 노이즈 규칙 점검
- 후보 추출 품질 점검
- 발표 전 사전 연습

#### 5.1.2 중요 마일스톤 검증

- 1차 분류: `gpt-5.4`
- 2차 보고서: `gpt-5.4`

용도:

- 초반 기준선 문서화
- 중간 결과 점검
- 최종 결과 확인
- 발표 자료에 반영할 최종 보고서 생성

#### 5.1.3 발표 직전 시연

- 1차 분류: `gpt-5.4`
- 2차 보고서 또는 핵심 질의응답: `gpt-5.4`

목적:

- 설명 품질 향상
- 보고서 서술 완성도 향상
- 발표 질의응답 대비

현재 코드 기준에서 `llm_stage1_classifier.py` 와 `llm_stage2_reporter.py` 는 모두 같은 모드 매핑을 사용한다.

- `routine` → `gpt-5.4-mini`
- `milestone` → `gpt-5.4`
- `presentation` → `gpt-5.4`

필요하면 `--model`, `--stage1-model`, `--stage2-model`로 개별 override 할 수 있다.

### 5.2 모델을 두 종류로 나누는 이유

1. 1차 분류는 구조화된 후보 판정이 중심이므로 mini 모델로도 충분한 경우가 많다.
2. 2차 보고서는 요약, 비교, 근거 정리, 문장 품질이 중요하므로 상위 모델 이점이 크다.
3. 모든 분석을 상위 모델로 돌리면 반복 실험 비용이 커진다.
4. 발표용 결과만 상위 모델로 재검증하면 운영과 검증의 균형을 맞출 수 있다.

### 5.3 API 사용 원칙

새 구현은 **Responses API 기준**으로 잡는다.

또한 1차 분류 결과는 자유 서술보다 **JSON Schema 기반 Structured Outputs**로 고정하는 것을 권장한다.

권장 이유는 다음과 같다.

- 라벨 값 강제 가능
- 필수 필드 누락 방지
- 후속 파이프라인 연결이 쉬움
- 발표용 표·요약 자동화에 유리함

---

## 6. Export 전략

### 6.1 기본 도구

현재 export 단계의 기준 도구는 `export_db_logs_cli.py` 이다.

이 스크립트는 다음 원칙을 따른다.

- 사용자는 KST 기준으로 조회 범위를 입력한다.
- 스크립트는 KST 범위를 UTC로 변환해 DB를 조회한다.
- 조회 결과의 시간 필드는 KST ISO-8601 문자열로 다시 변환해 출력한다.
- `access`, `security`, `error`, `all` 옵션으로 테이블을 선택할 수 있다.
- `--today`, `--date`, `--start`/`--end` 방식으로 구간을 지정할 수 있다.

즉, 분석자는 KST 기준으로 직관적으로 범위를 지정하고, 내부적으로는 UTC 정렬 원칙을 유지할 수 있다.

### 6.2 기본 조회 단위

운영상 권장 조회 단위는 아래와 같다.

1. **하루 단위 raw export**
   - 원본 보존
   - 누락 확인
   - 수동 재검증
2. **시간대 단위 analysis export**
   - 실험 시간대만 분석
   - 공격 재현 직후 확인
3. **특정 테이블 단위 export**
   - routine 분석: `security`
   - 5xx/예외 조사: `security` + 필요 시 `error`
   - 원본 보존/운영 점검: `all`

실무적으로 가장 자주 쓰는 패턴은 아래 셋이다.

- routine 분석: `--date ... --table security`
- 특정 실험 시간대 정밀 분석: `--start ... --end ... --table security`
- 원본 보존/수동 검증: `--today --table all`

### 6.3 HTML fallback 관련 export 원칙

현재 `export_db_logs_cli.py` 는 DB에 존재하는 컬럼을 그대로 JSON으로 내보낸다. 따라서 `apache_security_logs` 에 `resp_html_*` 컬럼이 있으면 export 결과에도 그대로 포함된다.

다만 현재 코드 기준으로 **fingerprint 값을 생성하는 상류 로직은 구현 상태가 아니다.**

- shipper는 `resp_html_*` 키를 읽어 DB에 적재할 수 있다.
- 하지만 실제 운영에서는 해당 값이 `NULL` 또는 `"-"`로 남을 수 있다.
- 현재 분석 파이프라인에서 path traversal 보수 해석의 주 근거는 `likely_html_fallback_response` 이다.

즉, `resp_html_*`는 **있으면 보조 근거로만 사용**하고, 없다고 해서 실제 파일 노출 성공으로 해석하지 않는다.

### 6.4 권장 실행 예시

#### 6.4.1 routine 분석용 security export

```bash
python3 export_db_logs_cli.py \
  --host 192.168.35.223 \
  --user log_reader \
  --password '비밀번호' \
  --date 2026-04-02 \
  --table security \
  --pretty \
  --out security_2026-04-02_kst.json
```

#### 6.4.2 특정 시간대 security 정밀 분석

```bash
python3 export_db_logs_cli.py \
  --host 192.168.35.223 \
  --user log_reader \
  --password '비밀번호' \
  --start '2026-04-02 09:00:00' \
  --end   '2026-04-02 12:00:00' \
  --table security \
  --pretty \
  --out export_security_20260402_090000_to_20260402_120000_kst.json
```

#### 6.4.3 원본 보존/수동 검증용 all export

```bash
python3 export_db_logs_cli.py \
  --host 192.168.35.223 \
  --user log_reader \
  --password '비밀번호' \
  --today \
  --table all \
  --pretty \
  --out today_all_kst.json
```

### 6.5 권장 출력 파일명

현재 코드 기준 파일명 규칙은 아래와 같다.

- `export_db_logs_cli.py`
  - `--out` 미지정 시: `export_<table>_<start>_to_<end>_kst.json`
- `prepare_llm_input.py`
  - `<base>_llm_input.json`
  - `<base>_analysis_candidates.json`
  - `<base>_noise_summary.json`
  - `<base>_filtered_out_rows.json` (`--write-filtered-out` 사용 시)
- `llm_stage1_classifier.py`
  - `<base>_stage1_results.json`
  - `<base>_stage1_errors.json`
- `llm_stage2_reporter.py`
  - `<base>_stage2_report_input.json`
  - `<base>_stage2_report.json`
  - `<base>_stage2_report.md`
  - `<base>_stage2_report_error.json`
- `run_analysis_pipeline.py`
  - `<work-dir>/pipeline_manifest.json`

여기서 `<base>` 는 기본적으로 입력 파일의 stem 이다. 예를 들어 `security_2026-04-02_kst.json` 을 prepare 단계에 넣으면 산출물 접두어도 그대로 `security_2026-04-02_kst` 가 된다.

---

## 7. 왜 원본 JSON 전체를 그대로 LLM에 보내면 안 되는가

DB export 결과 전체를 그대로 LLM에 전달하는 방식은 구현이 쉽다. 그러나 현재 환경에서는 다음 문제가 있다.

### 7.1 토큰 낭비

security 로그 한 건만 보더라도 다음과 같은 필드가 포함된다.

- `log_time`
- `request_id`
- `src_ip`
- `raw_request`
- `query_string`
- `status_code`
- `duration_us`
- `ttfb_us`
- `user_agent`
- `raw_log`

이 상태에서 `socket.io` polling, 정적 리소스 요청, UI 동작에 따른 반복 API 호출이 많이 섞이면, 실제로는 분석 가치가 낮은 정상 트래픽이 입력 대부분을 차지하게 된다.

### 7.2 분석 품질 저하

잡음이 많을수록 LLM은 다음과 같은 오류를 일으키기 쉽다.

- 중요한 의심 요청을 놓침
- 반복적인 정상 요청을 과대해석
- 의미 없는 URI 반복을 과도하게 보고서에 기재
- 전체 구조보다 표면 빈도에 끌려감

### 7.3 운영 비용 증가

원본 전체 전달은 토큰 사용량을 크게 늘린다. 이 방식은 mini 모델 기준으로도 비효율적이고, 상위 모델을 사용하는 발표·검증 시점에는 더 부담이 커진다.

따라서 현재 환경에서는 **원본 JSON 전체 전달 방식은 기본 전략으로 적합하지 않다.**

### 7.4 access + security를 그대로 함께 보내면 중복 사건이 생길 수 있다

현재 표준에서 access 로그는 운영 확인용 기본 로그이고, security 로그는 탐지·분류용 핵심 로그다.
이 둘을 아무 전처리 없이 함께 LLM에 전달하면 같은 요청이 access/security 양쪽에 동시에 존재해 **중복 사건**처럼 해석될 수 있다.

따라서 기본 원칙은 다음과 같다.

- routine 분석: `security`만 사용
- 5xx 또는 예외 확인: `security`에 `error`를 보조 연계
- `access`는 사람이 읽는 기준선 확인과 수동 검증 시에만 제한적으로 사용

---

## 8. 노이즈 정의와 처리 원칙

### 8.1 대표적인 정상 노이즈 유형

현재 환경에서 노이즈가 될 가능성이 큰 요청은 다음과 같다.

#### 8.1.1 `socket.io` polling / websocket 보조 요청

예:

- `/socket.io/?EIO=4&transport=polling...`
- 짧은 간격으로 반복되는 GET/POST polling

특징:

- 빈도가 매우 높음
- URI 패턴이 반복적임
- 상태코드가 주로 200
- 브라우저 UA, referer 패턴이 정상에 가까움
- 공격 판단 기여도가 낮음

#### 8.1.2 정적 리소스 요청

예:

- `.js`, `.css`, `.png`, `.jpg`, `.svg`, `.ico`, `.woff`, `.map`
- `/assets/`, `/frontend/`, `/dist/` 계열

특징:

- 페이지 로딩 시 자동 발생
- 개별 분석 가치가 낮음
- 대량일 경우 보고서 품질 저하

#### 8.1.3 정상 브라우저의 반복 API 호출

예:

- 상태 갱신용 polling API
- 추천/검색 자동완성 API
- UI 갱신용 반복 요청

특징:

- 사용자 동작에 따라 반복 발생
- 개별 요청 단위의 공격 의미가 약함

### 8.2 노이즈 처리 우선순위

노이즈는 다음 순서로 처리한다.

1. **식별**: 어떤 요청이 반복 정상 요청인지 구분
2. **분리**: 원본과 분석용 데이터를 분리
3. **집계**: 같은 유형은 count 중심으로 요약
4. **예외 유지**: 정상으로 보이더라도 패턴이 이상하면 후보에 남김

### 8.3 완전 제외보다 집계를 우선하는 이유

정상으로 보이는 요청이라도 상황에 따라 공격과 섞여 있을 수 있다. 예를 들어 `socket.io` 경로를 악용한 비정상적인 파라미터 삽입, 비정상 상태코드, 도구형 UA 등은 별도로 봐야 한다.

따라서 규칙은 다음과 같이 두는 것이 적절하다.

- 정상 패턴 + 정상 상태 + 정상 빈도: 집계 후 제외 가능
- 정상 패턴이지만 비정상 파라미터 또는 상태코드 포함: 후보 유지
- 정상 패턴이지만 자동화 흔적 강함: 후보 유지

---

## 9. 분석 후보 추출 기준

분석 후보는 모든 로그 중에서 **공격 가능성, 이상 징후, 장애 연계 가능성이 있는 요청**을 추린 집합이다.

### 9.1 상태코드 기반

다음 조건은 기본 후보 조건으로 사용한다.

- `status_code >= 400`
- 특히 `401`, `403`, `404`, `500`, `502`, `503`

단, 모든 4xx/5xx가 곧 공격은 아니므로 다른 조건과 함께 본다.

### 9.2 페이로드/문자열 패턴 기반

다음 문자열이 `query_string`, `uri`, `raw_request`, `raw_log` 등에 포함되면 의심 후보로 본다.

#### SQL Injection 계열

- `' or 1=1`
- `union select`
- `sleep(`
- `benchmark(`
- `information_schema`

#### XSS 계열

- `<script>`
- `javascript:`
- `onerror=`
- `alert(`

#### Path Traversal 계열

- `../`
- `..%2f`
- `%2e%2e%2f`

#### Command Injection 계열

- `;cat /etc/passwd`
- `| whoami`
- `` `id` ``
- `$(id)`

#### 인코딩 우회 / 이상 요청 계열

- 과도한 `%25`
- 이중 인코딩 흔적
- 비정상적으로 긴 query string

### 9.3 반복성 기반

다음 특성은 공격성 탐색 가능성을 높인다.

- 동일 IP가 짧은 시간 안에 다양한 URI를 순회
- 동일 IP가 로그인/인증 관련 요청을 반복
- 동일 URI에 비정상 파라미터를 반복 삽입

### 9.4 error 연계 기반

다음 조건은 서버 오류 또는 처리 실패와 연결될 가능성이 있다.

- `error_link_id` 가 존재
- 같은 `request_id` 로 error 로그와 연계 가능
- 5xx 응답과 Apache error 로그가 시간상 근접

운영 메모:

- error 로그는 routine 후보 생성의 주 입력이 아니라 **원인 확인용 보조 입력**이다.
- 즉, error는 독립적으로 대량 투입하기보다 security 후보와 연결되는 경우에만 선택적으로 붙이는 것이 적절하다.

### 9.5 사용자 행태 기반

다음 조합은 자동화 도구 또는 비정상 행태 가능성을 높인다.

- 일반 브라우저가 아닌 UA 흔적
- referer 부재 + 고빈도 반복 + 탐색형 URI
- 순차 경로 탐색
- 정상 사용 패턴에 비해 과도한 요청 집중

### 9.6 보강 기준

현재 prepare 단계에서 후보 점수와 함께 보강되는 관점은 아래와 같다.

- 동일 IP의 짧은 시간 내 다수 404
- 인증 관련 다수 실패
- 매우 긴 URI 또는 query string
- HTML fallback 정황(`likely_html_fallback_response`)
- HPP 정황(`hpp_detected`, `hpp_param_names`, `embedded_attack_hint`)

`matched_rule`, `risk_score`, `is_suspicious` 는 DB 컬럼으로 존재할 수 있으나, 현재 `prepare_llm_input.py` 의 핵심 후보 선별 기준으로 직접 사용하지 않는다.

---

## 10. 현재 산출물 구조

현재 코드 기준 산출물은 아래처럼 나뉜다.

### 10.1 export 원본 JSON

`export_db_logs_cli.py` 결과 파일이다.

- 상위 구조: `meta`, `counts`, `data`
- `meta` 주요 필드:
  - `database`
  - `exported_at`
  - `query_timezone`
  - `db_timezone`
  - `range_mode`
  - `start`
  - `end_exclusive`
  - `start_db_query`
  - `end_exclusive_db_query`
  - `table_option`
  - `limit_per_table`
  - `total_count`
  - `analysis_recommendation`
- `counts` 는 `access`, `security`, `error`별 건수다.
- `data` 는 `access`, `security`, `error` 배열을 모두 가진다.

### 10.2 prepare 산출물

`prepare_llm_input.py` 는 아래 파일을 만든다.

- `<base>_llm_input.json`
- `<base>_analysis_candidates.json`
- `<base>_noise_summary.json`
- `<base>_filtered_out_rows.json` (`--write-filtered-out` 사용 시)

`<base>_llm_input.json` 구조는 다음이 핵심이다.

- `meta`
- `noise_summary`
- `candidate_group_summary`
- `analysis_candidates`

`meta` 주요 필드는 다음과 같다.

- `query_timezone`
- `analysis_window`
- `source_database`
- `source_table_option`
- `selected_source_tables`
- `analysis_primary_table`
- `exported_at`
- `prepared_at`
- `model_usage_policy`
- `pipeline_policy`
- `thresholds`
- `counts`
- `filtered_out_breakdown`

### 10.3 analysis_candidates 실제 필드

현재 `prepare_llm_input.py` 후보 스키마는 아래 필드를 유지한다.

- `source_table`
- `log_id`
- `log_time`
- `src_ip`
- `method`
- `uri`
- `query_string`
- `status_code`
- `score`
- `verdict_hint`
- `reason_hints`
- `request_id`
- `error_link_id`
- `raw_request`
- `user_agent`
- `referer`
- `duration_us`
- `ttfb_us`
- `raw_log`
- `response_body_bytes`
- `resp_content_type`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`
- `hpp_detected`
- `hpp_param_names`
- `embedded_attack_hint`
- `incident_group_key`
- `merged_row_count`
- `merged_source_tables`
- `merged_log_ids`

즉, 현재 후보 JSON은 `matched_rule`, `risk_score`, `known_asset`를 기본 필드로 쓰지 않는다.

### 10.4 noise_summary 실제 필드

현재 `noise_summary` 항목은 아래 필드로 고정된다.

- `category`
- `src_ip`
- `uri`
- `method`
- `status_code`
- `count`
- `start`
- `end`
- `user_agent`
- `note`

### 10.5 stage1 결과 구조

`llm_stage1_classifier.py` 는 `<base>_stage1_results.json` 과 `<base>_stage1_errors.json` 을 만든다.

`results` 각 행의 핵심 필드는 다음과 같다.

- 후보 원본 식별 필드:
  - `candidate_index`
  - `incident_group_key`
  - `request_id`
  - `error_link_id`
  - `source_table`
  - `merged_source_tables`
  - `merged_row_count`
  - `merged_log_ids`
  - `log_id`
- 요청/응답 요약 필드:
  - `src_ip`
  - `method`
  - `uri`
  - `query_string`
  - `log_time`
  - `status_code`
  - `score`
  - `verdict_hint`
  - `reason_hints`
  - `response_body_bytes`
  - `resp_content_type`
  - `raw_request_target`
  - `path_normalized_from_raw_request`
  - `likely_html_fallback_response`
  - `hpp_detected`
  - `hpp_param_names`
  - `embedded_attack_hint`
- LLM 분류 필드:
  - `verdict`
  - `severity`
  - `confidence`
  - `false_positive_possible`
  - `reasoning_summary`
  - `evidence_fields`
  - `recommended_actions`
  - `response_id`
  - `raw_output_text`

`verdict` enum 은 현재 아래 값만 허용한다.

- `benign_normal`
- `likely_false_positive`
- `suspicious_scan`
- `suspicious_bruteforce`
- `suspicious_sqli`
- `suspicious_xss`
- `suspicious_path_traversal`
- `suspicious_command_injection`
- `suspicious_auth_abuse`
- `server_error_probe`
- `inconclusive`

`severity` 는 `info`, `low`, `medium`, `high`, `critical` 이고, `confidence` 는 `low`, `medium`, `high` 이다.

`recommended_actions` 는 현재 아래 enum 으로 제한된다.

- `ignore`
- `watch`
- `review_raw_log`
- `review_error_log`
- `correlate_request_id`
- `correlate_src_ip`
- `rate_limit_or_block`
- `investigate_immediately`

### 10.6 stage2 입력과 최종 산출물

`llm_stage2_reporter.py` 는 먼저 `<base>_stage2_report_input.json` 을 만든 뒤, 최종적으로 아래 산출물을 남긴다.

- `<base>_stage2_report_input.json`
- `<base>_stage2_report.json`
- `<base>_stage2_report.md`
- `<base>_stage2_report_error.json` (오류 시)

`stage2_report_input.json` 의 핵심 상위 키는 다음과 같다.

- `analysis_context`
- `pipeline_counts`
- `distributions`
- `top_incidents`
- `top_src_ips`
- `top_noise_groups`
- `top_filtered_categories`
- `top_out_of_candidate_recon`
- `stage1_errors_excerpt`
- `asset_context`
- `policy_notes`

여기서 `top_incidents` 는 `incident_ref` 기준으로 정리되고, incident 병합 규칙은 다음과 같다.

- `request_id` 가 있으면 `request_id` 우선 dedup
- 없으면 `src_ip + method + uri + status_code + 1초 단위 시각` fallback dedup

`known_asset_ips` 는 stage2에서만 직접 사용되며, 보고서 해석 시 내부 테스트/자체 호출 가능성을 낮추지 않도록 보조 문맥으로 반영한다.

---

## 11. 현재 LLM 전달 방식

현재 기본 전략은 **원본 export 전체가 아니라 `prepare_llm_input.py` 결과인 `<base>_llm_input.json` 을 stage1 입력으로 사용**하는 방식이다.

이 구조의 특징은 다음과 같다.

- 원본 export 는 보존한다.
- 노이즈는 `noise_summary` 와 `filtered_out_breakdown` 으로 축약한다.
- 후보는 `analysis_candidates` 로 분리한다.
- stage1 은 후보 단위 Structured Outputs 분류만 수행한다.
- stage2 는 stage1 결과를 incident 단위로 다시 묶어 Markdown 보고서를 만든다.

즉, 현재 코드 기준 기본 전략은 예전 문서의 “원본 + 후보 혼합 전달”보다는 **prepare 산출물 단일 입력 방식**에 가깝다.

---

## 12. 현재 분석 파이프라인

현재 기준 파이프라인은 아래와 같다.

```text
MariaDB export JSON
  ↓
prepare_llm_input.py
  ↓
<base>_llm_input.json
  ↓
llm_stage1_classifier.py
  ↓
<base>_stage1_results.json
  ↓
llm_stage2_reporter.py
  ↓
<base>_stage2_report.md / .json
```

`run_analysis_pipeline.py` 는 이 흐름을 하나로 묶고, `pipeline_manifest.json` 에 실행 단계와 산출물 경로를 남긴다.

지원 시작점은 다음 셋이다.

- `--export-input`
- `--llm-input`
- `--stage1-results`

기본 디렉터리 정책은 다음과 같다.

- `--work-dir` 기본값: `.`
- `--processed-dir` 기본값: `<work-dir>/processed`
- `--reports-dir` 기본값: `<work-dir>/reports`

---

## 13. 단계별 운영 기준

### 13.1 prepare 단계

현재 `prepare_llm_input.py` 의 기본값은 다음과 같다.

- `--include-source-tables`: `security`
- `--min-score`: `4`
- `--min-repeat-aggregate`: `3`

후보 힌트는 현재 아래 값으로 생성된다.

- `xss`
- `sqli`
- `path_traversal`
- `command_injection`
- `suspicious`

`likely_html_fallback_response`, `hpp_detected`, `hpp_param_names`, `embedded_attack_hint` 는 이후 stage1과 stage2까지 그대로 전달된다.

### 13.2 stage1 단계

현재 `llm_stage1_classifier.py` 의 기본값은 다음과 같다.

- `--mode`: `routine`
- `routine` 모델: `gpt-5.4-mini`
- `milestone` 모델: `gpt-5.4`
- `presentation` 모델: `gpt-5.4`
- `--reasoning-effort`: `none`
- `--candidate-limit`: `0` (전체)
- `--max-evidence-items`: `8`
- `--store`: 기본 `false`

즉, stage1은 “후보 1건씩 보수적으로 분류하고, 결과를 JSON Schema에 맞춰 저장하는 단계”로 이해하면 된다.

### 13.3 stage2 단계

현재 `llm_stage2_reporter.py` 의 기본값은 다음과 같다.

- `--mode`: `routine`
- `routine` 모델: `gpt-5.4-mini`
- `milestone` 모델: `gpt-5.4`
- `presentation` 모델: `gpt-5.4`
- `--top-incidents`: `12`
- `--top-noise-groups`: `8`
- `--top-ips`: `8`
- `--reasoning-effort`: `none`
- `--store`: 기본 `false`

stage2는 stage1 결과를 그대로 나열하지 않고 dedup 후 incident 중심으로 보고서를 구성한다. 또한 `filtered_out_breakdown` 을 보존해 후보 밖 저신호 탐색성 요청을 별도 섹션으로 다룬다.

### 13.4 run_analysis_pipeline 단계

현재 `run_analysis_pipeline.py` 는 아래 prepare 기본값을 그대로 넘긴다.

- `--prepare-min-score`: `4`
- `--prepare-min-repeat-aggregate`: `3`
- `--prepare-source-tables`: `security`

dry-run 시에는 live API 호출 없이 stage1 계획 파일을 만들고, 필요하면 placeholder `stage1_results` 를 생성해 stage2 초안까지 이어갈 수 있다.

---

## 14. 실행 예시 기준

### 14.1 수동 단계 실행

```bash
python3 ./src/export_db_logs_cli.py \
  --host 192.168.35.223 \
  --user log_reader \
  --date 2026-04-02 \
  --table security \
  --pretty \
  --out ./raw/security_2026-04-02_kst.json

python3 ./src/prepare_llm_input.py \
  --input ./raw/security_2026-04-02_kst.json \
  --out-dir ./processed \
  --pretty \
  --write-filtered-out

python3 ./src/llm_stage1_classifier.py \
  --input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./processed \
  --mode routine \
  --pretty

python3 ./src/llm_stage2_reporter.py \
  --stage1-results ./processed/security_2026-04-02_kst_stage1_results.json \
  --llm-input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./reports \
  --mode routine \
  --pretty
```

### 14.2 통합 파이프라인 실행

```bash
python3 ./src/run_analysis_pipeline.py \
  --export-input ./raw/security_2026-04-02_kst.json \
  --work-dir . \
  --mode routine \
  --pretty
```

이 경우 기본 산출물은 아래 위치에 생성된다.

- `./processed/*`
- `./reports/*`
- `./pipeline_manifest.json`

---

## 15. 현재 미구현 또는 보류로 봐야 하는 항목

현재 코드 기준으로 아래 항목은 구현된 기능처럼 쓰지 않는 것이 맞다.

1. HTML fallback fingerprint 값 생성
   - `resp_html_*` 컬럼/키 전달 경로는 있으나, 실제 값 생성은 별도 미구현이다.
2. `rule_candidate_filter.py`
   - 현재 리포지토리 기준 사용하지 않는다.
3. 별도 `bin/` wrapper 스크립트
   - 현재 표준 실행 엔트리는 각 `src/*.py` 와 `run_analysis_pipeline.py` 이다.
4. `known_asset` 후보 필드
   - prepare 후보 기본 필드가 아니라 stage2 해석 문맥에서 계산된다.
5. `matched_rule`, `risk_score`, `is_suspicious` 기반 후보 선별
   - DB 컬럼은 있을 수 있으나, 현재 prepare의 실제 후보 선별 핵심은 자체 규칙/점수 계산이다.

---

## 16. 운영상 정리 메모

현재 문서 기준으로 유지할 표현은 다음과 같다.

1. routine 분석 기본 입력은 `security` 이다.
2. `error` 는 원인 확인용 보조 자료다.
3. `access` 는 운영 확인과 기준선 비교용 보조 자료다.
4. stage1/stage2의 모드별 기본 모델 매핑은 동일하다.
5. path traversal 200 응답은 `likely_html_fallback_response` 를 우선 근거로 해석한다.
6. `resp_html_*` 는 있으면 참고하되, 현재 미구현 상태를 전제로 보수적으로 다룬다.

---

## 17. 최종 권고

현재 환경에서 가장 적절한 전략은 다음과 같다.

1. **LLM은 웹서버나 DB 서버가 아니라 별도 분석 VM에 둔다.**
2. **`export_db_logs_cli.py` 는 KST 기준 export 도구로 사용한다.**
3. **정제 코드는 `prepare_llm_input.py` 형태로 분석 VM의 별도 파이프라인에 둔다.**
4. **routine LLM 분석의 기본 입력은 security export 로 둔다.**
5. **error 로그는 5xx와 request_id/error_link_id 연계 시 보조 근거로 붙인다.**
6. **LLM에는 원본 전체가 아니라 분석용 정제 JSON을 우선 전달한다.**
7. **`socket.io` polling 같은 정상 반복 요청은 제거보다 집계를 우선한다.**
8. **평상시에는 `gpt-5.4-mini` 를 기본으로 사용한다.**
9. **발표, 초반·중간·최종 테스트 같은 중요 시점에만 `gpt-5.4` 를 사용한다.**
10. **LLM은 1차 분류와 2차 보고서 작성을 분리해 사용한다.**
11. **`resp_html_*` metadata 는 현재 값 생성이 미구현일 수 있으므로, 있으면 보조 근거로만 사용한다.**
12. **최종 산출물은 원본, 노이즈 요약, 후보 리스트, 1차 결과, 보고서를 함께 남긴다.**

한 문장으로 요약하면 다음과 같다.

> **원본은 DB와 export 파일에 보존하고, 분석은 별도 분석 VM에서 정제본으로 수행하며, 평상시에는 mini 모델을 쓰고 발표·마일스톤 검증 시점에만 상위 모델을 사용한다. path traversal 해석은 `likely_html_fallback_response` 를 우선 사용하고, `resp_html_*` 는 값이 있을 때만 보조 근거로 참고한다.**
