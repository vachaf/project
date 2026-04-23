# 02_LLM_환경_구축_및_설치

- 문서 상태: 구축 절차서
- 목적: LLM 분석 서버를 새로 구축하거나 재현할 때 본다.

실제 운영 명령과 실행 순서는 [docs/01_운영_기준_실행_가이드.md](docs/01_운영_기준_실행_가이드.md)를 우선한다.

## 1. 목표 상태

이 문서는 `/opt/web_log_analysis` 기준으로 다음 상태를 만드는 절차를 정리한다.

- Python 가상환경이 준비된다.
- `src/` 스크립트가 배치된다.
- `config/llm.env`가 준비된다.
- raw, processed, reports, logs 디렉터리가 준비된다.
- 운영자는 이후 `docs/01` 기준 명령으로 export, prepare, stage1, stage2, pipeline을 실행한다.

## 2. 권장 환경

- 운영체제: Ubuntu 22.04 LTS
- Python: 3.10 이상
- 시간대: `Asia/Seoul`
- 네트워크:
  - DB 서버 `3306/tcp` 접근 가능
  - OpenAI 또는 Anthropic API 접근 가능

## 3. 권장 디렉터리 구조

```text
/opt/web_log_analysis/
├── .venv/
├── config/
│   └── llm.env
├── data/
│   ├── raw/
│   └── processed/
├── reports/
├── logs/
└── src/
```

현재 운영 기준:

- raw 입력: `/opt/web_log_analysis/data/raw`
- 전처리 결과: `/opt/web_log_analysis/data/processed`
- 보고서 결과: `/opt/web_log_analysis/reports`
- 실행 로그: `/opt/web_log_analysis/logs`

## 4. 기본 패키지 설치

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git curl ca-certificates jq
sudo timedatectl set-timezone Asia/Seoul
```

## 5. 작업 디렉터리 준비

Git 기준 배치를 권장한다.

```bash
cd /opt
sudo git clone <GitHub_저장소_URL> web_log_analysis
sudo chown -R "$USER":"$USER" /opt/web_log_analysis
cd /opt/web_log_analysis
mkdir -p config data/raw data/processed reports logs
```

## 6. Python 가상환경 생성

```bash
cd /opt/web_log_analysis
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install PyMySQL
```

현재 코드 기준 필수 외부 패키지는 `PyMySQL`이다.

## 7. env 파일 작성

파일: `/opt/web_log_analysis/config/llm.env`

```dotenv
OPENAI_API_KEY=실제_OpenAI_API_KEY
OPENAI_BASE_URL=https://api.openai.com/v1

LLM_PROVIDER=openai

# Claude를 사용할 때만 활성화
# ANTHROPIC_API_KEY=실제_Anthropic_API_KEY
# ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
# ANTHROPIC_MODEL=claude_모델명

LOG_DB_HOST=192.168.35.223
LOG_DB_PORT=3306
LOG_DB_NAME=web_logs
LOG_DB_USER=log_reader
LOG_DB_PASSWORD=실제_DB_조회_비밀번호
KNOWN_ASSET_IPS=192.168.35.191,192.168.35.193,192.168.35.223,192.168.35.233, 192.168.35.27
```

기준:

- provider 미지정 시 기본은 `openai`
- Claude 사용 시 `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` 필요
- 사용하지 않는 provider 키는 주석 처리 가능
- `KNOWN_ASSET_IPS`는 현재 운영 기준의 필수 설정이 아니다

적용:

```bash
chmod 600 /opt/web_log_analysis/config/llm.env
set -a
source /opt/web_log_analysis/config/llm.env
set +a
```

## 8. DB 연결 확인

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

## 9. 운영 전 확인 사항

- `src/`에 주요 스크립트가 있다.
- `config/llm.env`가 적용된다.
- `data/raw`, `data/processed`, `reports`, `logs`가 존재한다.
- `export_db_logs_cli.py --test-connection`이 성공한다.

## 10. 주요 파일 GitHub 기준 복원

```bash
cd /opt/web_log_analysis

git status
git fetch origin

git restore --source origin/main -- \
  src/export_db_logs_cli.py \
  src/llm_stage1_classifier.py \
  src/llm_stage2_reporter.py \
  src/prepare_llm_input.py \
  src/run_analysis_pipeline.py \
  src/llm_client.py

git status
```

## 11. 문서 역할 경계

- 이 문서는 서버 구축과 배치 절차를 다룬다.
- 실제 운영 명령은 [docs/01_운영_기준_실행_가이드.md](docs/01_운영_기준_실행_가이드.md)를 본다.
