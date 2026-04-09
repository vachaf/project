# 02_LLM_환경_구축_및_설치

- 문서 상태: 정리본
- 버전: v1.3
- 작성일: 2026-04-09
- 기준 코드:
  - `src/export_db_logs_cli.py`
  - `src/prepare_llm_input.py`
  - `src/llm_stage1_classifier.py`
  - `src/llm_stage2_reporter.py`
  - `src/run_analysis_pipeline.py`

## 1. 목적

LLM 분석 서버에서 현재 파이프라인을 실행하기 위한 최소 설치 절차를 정리한다.

## 2. 서버 역할

- 웹서버: Apache 로그 생성, shipper 실행
- DB 서버: `web_logs` 저장
- LLM 서버: export, 전처리, stage1, stage2 실행

LLM 서버는 로그를 직접 tail 하지 않는다. DB export 이후 분석만 담당한다.

## 3. 권장 환경

- Ubuntu 22.04 Server
- Python 3.10 계열
- DB 서버 `3306/tcp` 접근 가능
- OpenAI API 접근 가능

## 4. 권장 디렉터리

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

## 5. 설치 절차

### 5.1 기본 패키지

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git curl ca-certificates
sudo timedatectl set-timezone Asia/Seoul
```

### 5.2 작업 디렉터리

```bash
sudo mkdir -p /opt/web_log_analysis/{config,src,raw,processed,reports}
sudo chown -R $USER:$USER /opt/web_log_analysis
```

### 5.3 가상환경

```bash
cd /opt/web_log_analysis
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install PyMySQL
```

`PyMySQL` 은 `export_db_logs_cli.py` 와 shipper 계열 코드에서 필요하다.

### 5.4 스크립트 배치

`src/` 아래에 아래 파일을 둔다.

- `export_db_logs_cli.py`
- `prepare_llm_input.py`
- `llm_stage1_classifier.py`
- `llm_stage2_reporter.py`
- `run_analysis_pipeline.py`

### 5.5 환경파일

`/opt/web_log_analysis/config/llm.env`

```dotenv
OPENAI_API_KEY=여기에_실제_API_키
OPENAI_BASE_URL=https://api.openai.com/v1
LOG_DB_HOST=192.168.35.223
LOG_DB_PORT=3306
LOG_DB_NAME=web_logs
LOG_DB_USER=log_reader
LOG_DB_PASSWORD=여기에_DB_조회_비밀번호
KNOWN_ASSET_IPS=
```

적용:

```bash
set -a
source /opt/web_log_analysis/config/llm.env
set +a
chmod 600 /opt/web_log_analysis/config/llm.env
```

## 6. 현재 모델 기본값

`llm_stage1_classifier.py` 와 `llm_stage2_reporter.py` 공통:

- `routine`: `gpt-5.4-mini`
- `milestone`: `gpt-5.4`
- `presentation`: `gpt-5.4`

필요하면 각 스크립트에서 `--model` override 가능하다.

## 7. 현재 실행 흐름

### 7.1 export

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
  --date 2026-04-02 \
  --table security \
  --pretty \
  --out ./raw/security_2026-04-02_kst.json
```

### 7.2 prepare

```bash
python ./src/prepare_llm_input.py \
  --input ./raw/security_2026-04-02_kst.json \
  --out-dir ./processed \
  --pretty \
  --write-filtered-out
```

생성 파일:

- `*_llm_input.json`
- `*_analysis_candidates.json`
- `*_noise_summary.json`
- 선택: `*_filtered_out_rows.json`

### 7.3 stage1 dry-run

```bash
python ./src/llm_stage1_classifier.py \
  --input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./processed \
  --mode routine \
  --dry-run \
  --pretty
```

### 7.4 stage2 dry-run

```bash
python ./src/llm_stage2_reporter.py \
  --stage1-results ./processed/security_2026-04-02_kst_stage1_results.json \
  --llm-input ./processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./reports \
  --mode routine \
  --dry-run \
  --pretty
```

### 7.5 통합 실행

```bash
python ./src/run_analysis_pipeline.py \
  --export-input ./raw/security_2026-04-02_kst.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --pretty
```

## 8. 현재 보수 해석 기준

path traversal 계열에서는 다음 필드를 실제 사용 중인 기준으로 본다.

- `resp_content_type`
- `response_body_bytes`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`

`resp_html_*` 는 현재 운영 핵심이 아니다. 관련 기능은 보류 상태로 본다.

## 9. 최소 점검 항목

- `log_reader` 계정으로 DB 조회 가능
- `security` export 생성 가능
- prepare 산출물 생성 가능
- stage1/stage2 dry-run 가능
- live 실행 전 `OPENAI_API_KEY` 확인
- 필요 시 `KNOWN_ASSET_IPS` 설정
