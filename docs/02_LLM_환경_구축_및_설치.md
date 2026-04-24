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

git은 일반 개발 목적보다는 운영 서버의 LLM 관련 주요 파일을 GitHub 기준으로 맞추거나 덮어씌우기 위해 설치한다.

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
sudo git clone https://github.com/vachaf/project web_log_analysis
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
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_BASE_URL=https://api.openai.com/v1

ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_MAX_TOKENS=8192

LOG_DB_HOST=DB_SERVER_IP
LOG_DB_PORT=3306
LOG_DB_NAME=web_logs
LOG_DB_USER=log_writer
LOG_DB_PASSWORD=YOUR_DB_PASSWORD
KNOWN_ASSET_IPS=OPTIONAL_ASSET_IP_LIST
```

정책:

- `config/llm.env` 하나에 OpenAI / Anthropic 설정을 함께 둔다.
- `LLM_PROVIDER`는 기본값으로 강제하지 않는다.
- 실행 시 provider는 CLI에서 명시한다.
- OpenAI 실행은 `--llm-provider openai` 또는 `--provider openai`
- Anthropic 실행은 `--llm-provider anthropic` 또는 `--provider anthropic`

이유:

- 현재 코드의 provider 해석 순서는 `CLI 인자 -> LLM_PROVIDER -> openai 기본값`이다.
- 따라서 같은 셸에서 env 파일을 여러 번 `source`하면 이전 provider 환경변수가 남아 잘못된 provider로 실행될 수 있다.
- 단일 `llm.env`를 한 번만 적용하고 provider를 실행 명령에서 명시하면 이 오염을 막을 수 있다.

비권장 방식:

- OpenAI용 / Anthropic용 env 파일을 분리해 두고 같은 셸에서 반복 `source`하는 방식
- `LLM_PROVIDER`에 기본 provider를 고정해 두고 실행 명령에서 provider를 생략하는 방식

적용:

```bash
chmod 600 /opt/web_log_analysis/config/llm.env

cd /opt/web_log_analysis
source .venv/bin/activate
set -a
source ./config/llm.env
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
- `config/llm.env`가 준비된다.
- `data/raw`, `data/processed`, `reports`, `logs`가 존재한다.
- `export_db_logs_cli.py --test-connection`이 성공한다.
- OpenAI / Anthropic 비교 실험 시에도 추가 env 파일 없이 같은 `config/llm.env`를 재사용한다.

## 10. 주요 파일 GitHub 기준 복원

운영 서버에서 일부 파일을 직접 수정했더라도, 기준 버전으로 되돌릴 필요가 있을 때 GitHub `origin/main` 기준으로 덮어쓴다. 특히 다음 주요 LLM 파이프라인 파일을 GitHub 기준으로 복원하거나 동기화할 때 `git restore --source origin/main -- ...` 명령을 사용한다.

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
