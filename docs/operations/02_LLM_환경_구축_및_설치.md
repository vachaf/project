# 02_LLM_환경_구축_및_설치

- 문서 상태: 구축 절차서
- 목적: LLM 분석 서버를 새로 구축하거나 재현할 때 본다.

실제 운영 명령과 실행 순서는 [docs/operations/01_운영_기준_실행_가이드.md](01_운영_기준_실행_가이드.md)를 우선한다.

## 1. 목표 상태

이 문서는 `/opt/web_log_analysis` 기준으로 다음 상태를 만드는 절차를 정리한다.

- Python 가상환경이 준비된다.
- `src/` 스크립트가 배치된다.
- `config/.env`가 준비된다.

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
├── config/
│   └── .env
├── runs/
│   └── jobs/
├── src/
├── web/
```

현재 운영 기준:

- raw export: `/opt/web_log_analysis/runs/jobs/<jobs_id>/export.json`
- prepare 결과: 
  - `/opt/web_log_analysis/runs/jobs/<jobs_id>/llm_input.json`
  - `/opt/web_log_analysis/runs/jobs/<jobs_id>/noise_summary.json`
- 분석 결과: 
  - `/opt/web_log_analysis/runs/jobs/<jobs_id>/stage1_results.json`
  - `/opt/web_log_analysis/runs/jobs/<jobs_id>/stage2_report_input.json`
  - `/opt/web_log_analysis/runs/jobs/<jobs_id>/stage2_report.json`
  - `/opt/web_log_analysis/runs/jobs/<jobs_id>/stage2_report.md`
  - `/opt/web_log_analysis/runs/jobs/<jobs_id>/viewer_payload.json`
- 실행 로그: `/opt/web_log_analysis/runs/jobs/<jobs_id>/manifest.json`

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
sudo mkdir -p /opt
cd /opt
sudo git clone https://github.com/vachaf/project web_log_analysis
sudo chown -R "$USER":"$USER" /opt/web_log_analysis
cd /opt/web_log_analysis
mkdir -p runs/jobs
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

설정 파일 예시 복사 후 환경에 맞게 수정: 

```bash
cp config/.env.example config/.env
nano config/.env
```

적용:

```bash
chmod 600 /opt/web_log_analysis/config/.env

cd /opt/web_log_analysis
source .venv/bin/activate
set -a
source ./config/.env
set +a
```

## 8. DB 연결 확인

```bash
cd /opt/web_log_analysis
source .venv/bin/activate
set -a
source ./config/.env
set +a

python ./src/export_db_logs_cli.py \
  --test-connection
```

## 9. 서버에 애이전트 등록

```bash
sudo cp /opt/web_log_analysis/ops/systemd/web-log-analysis-worker.service.example /etc/systemd/system/web-log-analysis-worker.service
sudo systemctl daemon-reload
sudo systemctl enable web-log-analysis-worker.service
sudo systemctl start web-log-analysis-worker.service
```

상태 확인: `sudo systemctl status web-log-analysis-worker.service`

일시 종료: `sudo systemctl stop web-log-analysis-worker.service`

## 9. 운영 전 확인 사항

- `src/`에 주요 스크립트가 있다.
- `config/.env`가 준비된다.
- `runs/jobs`가 존재한다.
- `export_db_logs_cli.py --test-connection`이 성공한다.

## 10. 문서 역할 경계

- 이 문서는 서버 구축과 배치 절차를 다룬다.
- 실제 운영 명령은 [docs/operations/01_운영_기준_실행_가이드.md](01_운영_기준_실행_가이드.md)를 본다.