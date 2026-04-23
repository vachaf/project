# 02_LLM_환경_구축_및_설치

- 문서 상태: 재현 절차서
- 버전: v1.4
- 작성일: 2026-04-09
- 기준 코드:
  - `src/export_db_logs_cli.py`
  - `src/prepare_llm_input.py`
  - `src/llm_stage1_classifier.py`
  - `src/llm_stage2_reporter.py`
  - `src/run_analysis_pipeline.py`

## 1. 목적

이 문서는 LLM 분석 서버를 새로 구축하고 현재 파이프라인을 그대로 재현하기 위한 절차서다.  
문서 안의 명령과 설정만 따라가면 다음 상태를 만들 수 있어야 한다.

- DB 서버에서 로그를 export 한다.
- export JSON을 `prepare_llm_input.py`로 전처리한다.
- `llm_stage1_classifier.py`와 `llm_stage2_reporter.py`를 dry-run 또는 live-run으로 실행한다.
- `run_analysis_pipeline.py`로 prepare → stage1 → stage2를 한 번에 실행한다.

## 2. 서버 역할

- 웹서버: Apache 로그 생성, shipper 실행, DB 서버로 적재
- DB 서버: `web_logs` 저장
- LLM 서버: export, prepare, stage1, stage2 실행

LLM 서버는 웹 로그 파일을 직접 읽지 않는다. 현재 기준으로 DB export 이후 단계만 담당한다.

## 3. 권장 환경

- 운영체제: Ubuntu 22.04 LTS
- Python: 3.10 계열 이상
- 네트워크:
  - DB 서버 `3306/tcp` 접근 가능
  - OpenAI API 또는 Anthropic API 접근 가능
- 시간대: `Asia/Seoul`

## 4. 권장 디렉터리 구조

권장 작업 루트는 `/opt/web_log_analysis`다.

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
├── data/
│   └── raw/
├── processed/
├── reports/
└── pipeline_manifest.json
```

용도:

- `data/raw/`: DB export JSON
- `processed/`: prepare 및 stage1 산출물
- `reports/`: stage2 입력/JSON/Markdown 보고서
- `pipeline_manifest.json`: `run_analysis_pipeline.py` 실행 결과 요약

## 5. 기본 패키지 설치

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git curl ca-certificates jq
sudo timedatectl set-timezone Asia/Seoul
```

확인:

```bash
python3 --version
pip3 --version
git --version
timedatectl
```

## 6. 작업 디렉터리 준비

배치 방식은 아래 둘 중 하나만 선택한다.  
GitHub 기준으로 운영 서버를 관리할 수 있으면 방식 B를 권장한다.

### 6.1 방식 A: 수동 디렉터리 생성 + src 파일 복사

```bash
sudo mkdir -p /opt/web_log_analysis/{config,src,data/raw,processed,reports}
sudo chown -R "$USER":"$USER" /opt/web_log_analysis
cd /opt/web_log_analysis
```

현재 리포지토리에서 스크립트를 복사하는 예시:

```bash
cp /path/to/project_repo/src/export_db_logs_cli.py /opt/web_log_analysis/src/
cp /path/to/project_repo/src/prepare_llm_input.py /opt/web_log_analysis/src/
cp /path/to/project_repo/src/llm_stage1_classifier.py /opt/web_log_analysis/src/
cp /path/to/project_repo/src/llm_stage2_reporter.py /opt/web_log_analysis/src/
cp /path/to/project_repo/src/run_analysis_pipeline.py /opt/web_log_analysis/src/
chmod 755 /opt/web_log_analysis/src/*.py
```

배치 확인:

```bash
ls -l /opt/web_log_analysis/src/
```

### 6.2 방식 B: GitHub 저장소를 clone 해서 배치

`/opt/web_log_analysis`가 아직 없거나 비어 있을 때 사용한다. GitHub 리포지토리를 기준으로 운영 서버를 관리하는 경우, `/opt/web_log_analysis`를 Git 작업 디렉터리로 두는 편이 좋다.

```bash
cd /opt
sudo git clone <GitHub_저장소_URL> web_log_analysis
sudo chown -R "$USER":"$USER" /opt/web_log_analysis
cd /opt/web_log_analysis
mkdir -p config data/raw processed reports
```

배치 확인:

```bash
ls -l /opt/web_log_analysis/src/
```

### 6.3 GitHub 기준 주요 파일 동기화

이 절차는 운영 서버의 주요 Python 파일을 GitHub `origin/main` 기준으로 되돌리거나 동기화하기 위한 것이다.  
이미 `/opt/web_log_analysis`가 Git 작업 디렉터리인 경우에 수행한다.

```bash
cd /opt/web_log_analysis

git status
git fetch origin

git restore --source origin/main -- \
  src/export_db_logs_cli.py \
  src/llm_stage1_classifier.py \
  src/llm_stage2_reporter.py \
  src/prepare_llm_input.py \
  src/run_analysis_pipeline.py

git status
```

주의:

- 위 명령은 지정한 주요 Python 파일의 로컬 수정분을 `origin/main` 기준으로 되돌린다.
- 운영 서버에서 직접 수정한 내용이 있으면 `git status`로 먼저 확인하고 필요한 내용은 별도로 백업한다.

## 7. Python 가상환경 생성

```bash
cd /opt/web_log_analysis
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install PyMySQL
```

현재 코드 기준으로 필수 외부 패키지는 `PyMySQL`이다.  
LLM 호출은 표준 라이브러리 `urllib` 기반이라 OpenAI/Anthropic SDK는 필수 아님이다.

검증:

```bash
python -c "import pymysql; print(pymysql.__version__)"
```

## 8. 환경파일 작성

파일: `/opt/web_log_analysis/config/llm.env`

```dotenv
OPENAI_API_KEY=여기에_실제_API_키
OPENAI_BASE_URL=https://api.openai.com/v1

# 기본값은 openai다. Claude 사용 시 anthropic으로 지정한다.
LLM_PROVIDER=openai
ANTHROPIC_API_KEY=여기에_Anthropic_API_키
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
ANTHROPIC_MODEL=claude_모델명

LOG_DB_HOST=192.168.35.223
LOG_DB_PORT=3306
LOG_DB_NAME=web_logs
LOG_DB_USER=log_reader
LOG_DB_PASSWORD=여기에_DB_조회_비밀번호

KNOWN_ASSET_IPS=192.168.35.191,192.168.35.193,192.168.35.223,192.168.35.233
```

설명:

- `OPENAI_API_KEY`: live-run에서 필요
- `OPENAI_BASE_URL`: 기본은 공식 OpenAI API
- `LLM_PROVIDER`: `openai` 또는 `anthropic`. 생략하면 기존처럼 OpenAI를 사용
- `ANTHROPIC_API_KEY`: Claude live-run에서 필요
- `ANTHROPIC_BASE_URL`: 기본은 공식 Anthropic API
- `ANTHROPIC_MODEL`: Claude 사용 시 기본 모델명. 또는 실행 명령에서 `--model`로 지정
- `LOG_DB_*`: `export_db_logs_cli.py` DB 접속 정보
- `KNOWN_ASSET_IPS`: stage2 보고서에서 내부 자산 IP 표시용. `--known-asset-ips` CLI 인자가 없으면 이 값을 fallback으로 사용한다.

적용:

```bash
chmod 600 /opt/web_log_analysis/config/llm.env
set -a
source /opt/web_log_analysis/config/llm.env
set +a
```

검증:

```bash
env | egrep 'LLM_PROVIDER|OPENAI_|ANTHROPIC_|LOG_DB_|KNOWN_ASSET_IPS'
```

## 9. DB 연결 확인

`export_db_logs_cli.py`에는 연결 테스트 옵션이 있다.

```bash
cd /opt/web_log_analysis
source .venv/bin/activate
set -a
source ./config/llm.env
set +a

python ./src/export_db_logs_cli.py \
  --host "$LOG_DB_HOST" \
  --port "$LOG_DB_PORT" \
  --user "$LOG_DB_USER" \
  --password "$LOG_DB_PASSWORD" \
  --database "$LOG_DB_NAME" \
  --test-connection
```

정상이라면 접속 성공 메시지가 출력된다.

## 10. export 실행

### 10.1 현재 동작 기준

- 기본 `--table`: `security`
- 입력 시간: KST 기준
- DB 조회: UTC 기준으로 변환 후 실행
- 출력 JSON 시간: KST ISO-8601 문자열
- 출력 경로: 작업 루트 기준 `data/raw/` 고정
- 동일 파일명이 이미 있으면 그대로 덮어쓴다.

### 10.2 기본 export 예시

```bash
python ./src/export_db_logs_cli.py \
  --host "$LOG_DB_HOST" \
  --port "$LOG_DB_PORT" \
  --user "$LOG_DB_USER" \
  --password "$LOG_DB_PASSWORD" \
  --database "$LOG_DB_NAME" \
  --date 2026-04-02 \
  --table security \
  --pretty
```

파일명은 아래 형식으로 생성된다.

```text
날짜 단위: ./data/raw/security_2026-04-02_kst.json
시간 범위: ./data/raw/security_2026-04-02_13-00-00_to_2026-04-02_15-30-00_kst.json
```

### 10.3 export 검증

```bash
ls -l ./data/raw/
jq '.meta, .counts' ./data/raw/security_2026-04-02_kst.json
```

확인 포인트:

- 최상위 키에 `meta`, `counts`, `data`가 있다.
- `meta.query_timezone`이 KST 기준 설명과 맞는다.
- `counts.security` 등 테이블별 건수와 `meta.total_count`를 함께 확인하고, `meta.total_count`가 0보다 크면 다음 단계로 진행 가능하다.

## 11. prepare 실행

`prepare_llm_input.py`는 export JSON에서 후보군과 요약 파일을 만든다.

### 11.1 기본 실행 예시

```bash
python ./src/prepare_llm_input.py \
  --input ./data/raw/security_2026-04-02_kst.json \
  --out-dir ./processed \
  --pretty \
  --write-filtered-out
```

현재 기본값:

- `--include-source-tables`: `security`
- `--min-score`: 4
- `--min-repeat-aggregate`: 3

### 11.2 생성 파일

- `security_2026-04-02_kst_llm_input.json`
- `security_2026-04-02_kst_analysis_candidates.json`
- `security_2026-04-02_kst_noise_summary.json`
- 선택: `security_2026-04-02_kst_filtered_out_rows.json`

### 11.3 prepare 검증

```bash
ls -l ./processed/
jq '.meta.model_usage_policy, .meta.pipeline_policy' ./processed/security_2026-04-02_kst_llm_input.json
jq '.analysis_candidates[0]' ./processed/security_2026-04-02_kst_llm_input.json
```

확인 포인트:

- `analysis_candidates`가 존재한다.
- `noise_summary`, `filtered_out_breakdown`가 보존된다.
- path traversal 해석에 필요한 필드가 후보에 반영된다.

현재 분석에서 직접 연결되는 축:

- `resp_content_type`
- `response_body_bytes`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`

## 12. stage1 실행

`llm_stage1_classifier.py`는 후보별 1차 분류를 만든다.

### 12.1 현재 모델 기본값

provider를 지정하지 않으면 기존처럼 OpenAI를 사용한다. Claude를 쓰려면 `--provider anthropic`과 `--model`을 지정하거나 `LLM_PROVIDER=anthropic`, `ANTHROPIC_MODEL`을 환경파일에 설정한다.

- `routine`: `gpt-5.4-mini`
- `milestone`: `gpt-5.4`
- `presentation`: `gpt-5.4`

추가 기본값:

- `--reasoning-effort none`
- `--candidate-limit 0`
- `--max-evidence-items 8`

### 12.2 dry-run

```bash
python ./src/llm_stage1_classifier.py \
  --input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./processed \
  --mode routine \
  --dry-run \
  --pretty
```

dry-run 특징:

- 실제 LLM API를 호출하지 않는다.
- 후보 기반 placeholder 결과를 만든다.
- live 분류 결과와 동일한 의미로 해석하면 안 된다.

### 12.3 live-run

```bash
python ./src/llm_stage1_classifier.py \
  --input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./processed \
  --mode routine \
  --pretty
```

Claude 사용 예시:

```bash
python ./src/llm_stage1_classifier.py \
  --provider anthropic \
  --model "$ANTHROPIC_MODEL" \
  --input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./processed \
  --mode routine \
  --pretty
```

필요 시 모델 override:

```bash
python ./src/llm_stage1_classifier.py \
  --input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./processed \
  --mode milestone \
  --model gpt-5.4 \
  --pretty
```

### 12.4 stage1 산출물

- `*_stage1_results.json`
- `*_stage1_errors.json`

검증:

```bash
jq '.meta' ./processed/security_2026-04-02_kst_stage1_results.json
jq '.results[0]' ./processed/security_2026-04-02_kst_stage1_results.json
```

현재 stage1 결과 핵심 필드:

- `verdict`
- `severity`
- `confidence`
- `reasoning_summary`
- `evidence_fields`
- `recommended_actions`

## 13. stage2 실행

`llm_stage2_reporter.py`는 stage1 결과를 incident 중심으로 정리해 최종 보고서를 만든다.

### 13.1 현재 모델 기본값

provider를 지정하지 않으면 기존처럼 OpenAI를 사용한다.

- `routine`: `gpt-5.4-mini`
- `milestone`: `gpt-5.4`
- `presentation`: `gpt-5.4`

추가 기본값:

- `--top-incidents 12`
- `--top-noise-groups 8`
- `--top-ips 8`

### 13.2 dry-run

```bash
python ./src/llm_stage2_reporter.py \
  --stage1-results ./processed/security_2026-04-02_kst_stage1_results.json \
  --llm-input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./reports \
  --mode routine \
  --dry-run \
  --pretty
```

dry-run 특징:

- 실제 LLM API를 호출하지 않는다.
- report input과 markdown 초안을 만든다.

### 13.3 live-run

```bash
python ./src/llm_stage2_reporter.py \
  --stage1-results ./processed/security_2026-04-02_kst_stage1_results.json \
  --llm-input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./reports \
  --mode routine \
  --pretty
```

Claude 사용 예시:

```bash
python ./src/llm_stage2_reporter.py \
  --provider anthropic \
  --model "$ANTHROPIC_MODEL" \
  --stage1-results ./processed/security_2026-04-02_kst_stage1_results.json \
  --llm-input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./reports \
  --mode routine \
  --pretty
```

`--llm-input`을 생략하면 stage1 결과 파일명 기준으로 연관 입력을 추론한다.

known asset IP는 아래 우선순위로 적용된다.

1. `--known-asset-ips` CLI 인자
2. 환경 변수 또는 `/opt/web_log_analysis/config/llm.env`의 `KNOWN_ASSET_IPS`
3. 빈 목록

### 13.4 stage2 산출물

- `*_stage2_report_input.json`
- `*_stage2_report.json`
- `*_stage2_report.md`
- 오류 시 `*_stage2_report_error.json`

검증:

```bash
ls -l ./reports/
jq '.meta' ./reports/security_2026-04-02_kst_stage2_report.json
sed -n '1,80p' ./reports/security_2026-04-02_kst_stage2_report.md
```

## 14. 통합 실행

`run_analysis_pipeline.py`는 prepare → stage1 → stage2를 순서대로 실행한다.  
현재 시작점은 세 가지다.

- `--export-input`
- `--llm-input`
- `--stage1-results`

### 14.1 export JSON에서 시작

```bash
python ./src/run_analysis_pipeline.py \
  --export-input ./data/raw/security_2026-04-02_kst.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --pretty
```

Claude로 통합 실행하려면 `--llm-provider anthropic`을 넘긴다. stage1/stage2 모두 같은 provider로 실행된다.

```bash
python ./src/run_analysis_pipeline.py \
  --llm-provider anthropic \
  --stage1-model "$ANTHROPIC_MODEL" \
  --stage2-model "$ANTHROPIC_MODEL" \
  --export-input ./data/raw/security_2026-04-02_kst.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --pretty
```

### 14.2 llm_input에서 재개

```bash
python ./src/run_analysis_pipeline.py \
  --llm-input ./processed/security_2026-04-02_kst_llm_input.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --pretty
```

### 14.3 stage1 결과에서 재개

```bash
python ./src/run_analysis_pipeline.py \
  --stage1-results ./processed/security_2026-04-02_kst_stage1_results.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --pretty
```

### 14.4 dry-run

```bash
python ./src/run_analysis_pipeline.py \
  --export-input ./data/raw/security_2026-04-02_kst.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --dry-run \
  --pretty
```

현재 dry-run 특징:

- prepare는 실제로 실행된다.
- stage1은 placeholder 결과가 생성될 수 있다.
- stage2는 live 보고서 대신 dry-run 산출물을 남긴다.

### 14.5 통합 실행 결과 위치

- `processed/`: `*_llm_input.json`, `*_analysis_candidates.json`, `*_noise_summary.json`, `*_stage1_results.json`, `*_stage1_errors.json`
- `reports/`: `*_stage2_report_input.json`, `*_stage2_report.json`, `*_stage2_report.md`
- `/opt/web_log_analysis/pipeline_manifest.json`

manifest 확인:

```bash
jq '.' /opt/web_log_analysis/pipeline_manifest.json
```

## 15. 현재 보수 해석 기준

path traversal과 유사한 탐색형 요청 해석에서는 아래 필드를 실제 사용 축으로 본다.

- `resp_content_type`
- `response_body_bytes`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`

`likely_html_fallback_response=true`만으로 성공 공격으로 확정하지는 않는다. 현재 문서 기준은 보수 해석이다.

## 16. `resp_html_*` 처리 기준

`resp_html_*` 계열은 현재 필수 구축 기능이 아니다.

- DB 스키마나 shipper 파서에 관련 컬럼이 남아 있을 수 있다.
- 현재 LLM 분석의 핵심 입력으로 보지 않는다.
- 기본 구축 절차에서 생성이나 검증 대상으로 삼지 않는다.
- 필요하면 선택 컬럼으로 보관할 수 있으나 기본 경로에서는 제외한다.

## 17. 최종 점검 체크리스트

- `llm.env`가 존재하고 권한이 `600`이다.
- `export_db_logs_cli.py --test-connection`이 성공한다.
- `data/raw/`에 export JSON이 생성된다.
- `processed/`에 `*_llm_input.json`과 `*_stage1_results.json`이 생성된다.
- `reports/`에 `*_stage2_report.md`가 생성된다.
- live-run 전 `OPENAI_API_KEY`가 실제 값으로 설정되어 있다.
- `pipeline_manifest.json`에서 각 산출물 경로를 확인할 수 있다.
