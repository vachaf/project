# 02_LLM_환경_구축_및_설치

- 문서 상태: 통합본
- 버전: v1.1
- 작성일: 2026-04-02
- 적용 대상: Ubuntu 22.04 Server 기반 LLM 분석 서버 구축 문서
- 연계 문서:
  - `01_프로젝트_방향과_실험대상.md`
  - `02_Juice_shop_환경_구축_및_설치.md`
  - `02_MariaDB_환경_구축_및_설치.md`
  - `04_로그_적재_및_운영.md`
  - `05_Export_LLM_분석_전략.md`

---

## 1. 문서 목적

이 문서는 **웹서버와 DB 서버와 분리된 별도 LLM 분석 서버를 구축하는 절차와 운영 기준**을 정리한 설치 문서다.

이번 프로젝트에서 LLM 서버의 목적은 다음과 같다.

- MariaDB `web_logs` 에서 분석 대상 로그를 조회하거나 export 한다.
- export 결과를 분석용 JSON 으로 정제한다.
- 기본적으로 `security` export 를 중심으로 후보를 생성한다.
- 필요 시 `error` 로그를 보조 근거로 연결한다.
- 후보 로그를 LLM 으로 1차 분류한다.
- 분류 결과를 바탕으로 2차 Markdown 보고서를 생성한다.
- known asset IP 와 테스트 호스트 정보를 함께 반영해 과도한 오탐 해석을 줄인다.
- 평상시에는 비용 효율 모드로, 발표 전 점검이나 중간/최종 테스트 시에는 상위 모델로 분석 모드를 전환한다.

즉, 이 문서는 **LLM 분석 계층을 실제로 띄우는 설치 절차서**이며, 단순한 코드 보관 문서가 아니다.

---

## 2. 왜 LLM 서버를 별도로 두는가

현재 구조는 다음 세 계층으로 나누는 것이 가장 적절하다.

1. **웹서버**: Apache Reverse Proxy + Juice Shop + 로그 생성 + shipper
2. **DB 서버**: MariaDB `web_logs` 저장 및 조회
3. **LLM 서버**: export, 전처리, LLM 호출, 보고서 생성

이렇게 분리하는 이유는 다음과 같다.

1. 웹서버는 요청 처리와 로그 생성에 집중해야 하므로, 분석 로직과 API 호출을 함께 두는 것이 바람직하지 않다.
2. DB 서버는 저장 계층이므로, 외부 API 호출과 보고서 생성을 맡기면 역할이 불필요하게 커진다.
3. 분석 서버를 별도로 두면 모델 교체, 전처리 규칙 변경, 보고서 템플릿 수정이 쉬워진다.
4. API 키, 정제 규칙, 분석 산출물을 웹 계층과 분리할 수 있어 운영이 더 깔끔하다.
5. 발표 전 점검이나 대량 재분석 시에도 웹서버와 DB 서버 자원 간섭을 줄일 수 있다.

즉, LLM 서버는 **원본 로그를 만드는 서버가 아니라, 원본 로그를 읽어 해석하는 분석 전용 서버**로 정의한다.

---

## 3. 대상 환경과 위치 정의

### 3.1 기준 서버 구성

현재 기준 구성은 다음과 같다.

- 웹서버: `juice` (Ubuntu 22.04.5)
  - Apache 2.4 계열
  - OWASP Juice Shop Reverse Proxy
  - 로그 파일:
    - `/var/log/apache2/app_access.log`
    - `/var/log/apache2/app_security.log`
    - `/var/log/apache2/app_error.log`
- DB 서버: `maria` (Ubuntu 22.04.5)
  - MariaDB 10.6 계열
  - DB: `web_logs`
  - 테이블:
    - `apache_access_logs`
    - `apache_security_logs`
    - `apache_error_logs`
- 신규 서버: `llm`
  - Ubuntu 22.04.5 Server
  - 로그 export / 정제 / LLM 분석 / 보고서 생성 담당

### 3.2 권장 네트워크 위치

LLM 서버는 다음 조건을 만족해야 한다.

- DB 서버 `3306/tcp` 접근 가능
- 외부 인터넷으로 OpenAI API 호출 가능
- SSH 관리 가능
- 필요 시 보고서 파일을 내려받거나 복사할 수 있어야 함

권장 배치는 아래와 같다.

```text
클라이언트 / 실험 스크립트
                ↓
          Web Server (juice)
                ↓ shipper
          DB Server (maria)
                ↑
                │ read-only query / export
                │
          LLM Server (analysis)
                ↓
      preprocessing / stage1 / stage2 / report
```

LLM 서버는 웹 요청을 직접 처리하지 않으므로, Apache나 Docker 기반 서비스 노출은 필수가 아니다.

---

## 4. 권장 사양

이 프로젝트에서 LLM 서버는 **로컬 GPU 추론 서버가 아니라 OpenAI API 를 호출하는 분석 서버**로 사용한다. 따라서 GPU는 필수 조건이 아니다.

### 4.1 최소 사양

- CPU: 2 vCPU
- RAM: 4GB
- 디스크: 20GB
- 네트워크: 내부망 + 인터넷 아웃바운드

### 4.2 권장 사양

- CPU: 4 vCPU
- RAM: 8GB
- 디스크: 40GB 이상
- 네트워크: 내부 DB 접근 가능 + 안정적인 인터넷 연결

### 4.3 왜 이 정도면 충분한가

- 실제 추론은 로컬 GPU가 아니라 외부 API 에서 수행한다.
- 이 서버는 JSON 처리, 파일 저장, API 요청, 보고서 생성이 주 역할이다.
- 다만 하루치 export, 후보 정제, 보고서 누적 보관을 감안하면 RAM 8GB 와 40GB 디스크가 운영상 더 여유롭다.

향후 로컬 오픈소스 모델이나 벡터 DB 를 붙일 계획이 생기면 별도 확장 문서를 두는 것이 적절하다.

---

## 5. 운영체제와 기본 전제

- 운영체제: **Ubuntu 22.04.5 Server**
- 설치 이미지: `ubuntu-22.04.5-live-server-amd64.iso`
- 기본 사용자: 관리자 권한이 있는 일반 계정 + `sudo`
- 시간대: `Asia/Seoul`
- Python: Ubuntu 기본 Python 3.10 계열 사용

기본 전제는 다음과 같다.

- 웹서버와 DB 서버가 이미 구축되어 있어야 한다.
- DB 서버의 `log_reader` 계정 또는 이에 준하는 읽기 전용 계정이 준비되어 있어야 한다.
- OpenAI API 키를 발급받아 안전하게 보관할 수 있어야 한다.

---

## 6. 이 서버에서 수행할 역할

LLM 서버는 아래 작업을 담당한다.

1. **DB export**
   - `export_db_logs_cli.py` 로 KST 기준 조회
2. **전처리**
   - `prepare_llm_input.py` 로 노이즈 요약과 후보 추출
3. **1차 분류**
   - `llm_stage1_classifier.py` 로 후보 단위 LLM 판정
4. **2차 보고서**
   - `llm_stage2_reporter.py` 로 Markdown 보고서 생성
5. **통합 실행**
   - `run_analysis_pipeline.py` 로 일괄 실행
6. **산출물 보관**
   - raw export / processed JSON / reports 분리 저장

반대로 아래 작업은 이 서버의 직접 역할이 아니다.

- Apache 로그 생성
- MariaDB 적재
- 웹 서비스 Reverse Proxy 처리
- 실시간 인라인 차단

즉, 이 서버는 **분석 전용 계층**이다.

운영 기준 메모:

- routine 분석의 기본 입력은 `security` export 로 둔다.
- `error` 는 5xx 또는 예외 조사 시 보조 근거로만 연결한다.
- `access` 는 운영 확인과 기준선 비교용으로만 제한적으로 사용한다.

---

## 7. 모델 사용 정책 확정안

현재 프로젝트 기준 모델 사용 정책은 다음과 같이 고정한다.

### 7.1 기본 정책

- **routine**: `gpt-5.4-mini`
- **milestone**: `gpt-5.4`
- **presentation**: `gpt-5.4`

### 7.2 적용 의미

- 평상시 반복 분석, 수시 점검, 개발 중 테스트는 `routine`
- 중간 점검, 실험 단계 검증, 보고서 품질 확인은 `milestone`
- 발표 전 최종 시연, 핵심 결과 산출은 `presentation`

즉, **기본은 mini**, 중요한 시점에서만 상위 모델을 사용한다.

OpenAI 공식 모델 문서는 `gpt-5.4`를 복합 전문 작업용 기본 모델로, `gpt-5.4-mini`를 더 빠르고 비용 효율적인 선택지로 설명한다. 또한 새 구현은 Responses API 기준으로 안내한다. 
---

## 8. 권장 디렉터리 구조

LLM 서버에서는 분석 코드를 하나의 루트 아래에 모아 두는 것이 좋다.

예시는 다음과 같다.

```text
/opt/web_log_analysis/
├── .venv/
├── config/
│   ├── llm.env
│   └── analysis_rules.yaml
├── src/
│   ├── export_db_logs_cli.py
│   ├── prepare_llm_input.py
│   ├── llm_stage1_classifier.py
│   ├── llm_stage2_reporter.py
│   └── run_analysis_pipeline.py
├── data/
│   ├── raw/
│   └── processed/
├── reports/
├── logs/
└── tmp/
```

권장 의미는 다음과 같다.

- `config/`: 환경변수 파일, 규칙 파일
- `src/`: 실행 스크립트
- `data/raw/`: DB export 원본 JSON
- `data/processed/`: 전처리 및 stage1 결과
- `reports/`: 최종 Markdown 보고서
- `logs/`: 파이프라인 실행 로그
- `tmp/`: 임시 파일

---

## 9. 단계별 구축 절차

### 9.1 시스템 업데이트와 기본 패키지 설치

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y \
  python3 python3-venv python3-pip \
  curl wget jq unzip git ca-certificates
```

시간대를 KST 로 맞춘다.

```bash
sudo timedatectl set-timezone Asia/Seoul
timedatectl
```

### 9.2 작업 디렉터리 생성

```bash
sudo mkdir -p /opt/web_log_analysis/{config,src,data/raw,data/processed,reports,logs,tmp}
sudo chown -R $USER:$USER /opt/web_log_analysis
```

### 9.3 Python 가상환경 생성

```bash
cd /opt/web_log_analysis
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install PyMySQL
```

설명:

- `PyMySQL` 은 `export_db_logs_cli.py` 가 MariaDB 를 조회할 때 필요하다.
- 현재 `prepare_llm_input.py`, `llm_stage1_classifier.py`, `llm_stage2_reporter.py`, `run_analysis_pipeline.py` 는 표준 라이브러리 중심으로 작성되어 있으므로, 추가 패키지 의존성은 크지 않다.
- OpenAI Python SDK 는 현재 스크립트 기준 필수는 아니다. 다만 향후 SDK 기반 전환을 고려하면 가상환경은 유지하는 편이 좋다.

### 9.4 스크립트 배치

다음 파일을 `/opt/web_log_analysis/src/` 아래에 `nano`로 생성한다.

- `export_db_logs_cli.py`
- `prepare_llm_input.py`
- `llm_stage1_classifier.py`
- `llm_stage2_reporter.py`
- `run_analysis_pipeline.py`

예:

```bash
nano /opt/web_log_analysis/src/export_db_logs_cli.py
nano /opt/web_log_analysis/src/prepare_llm_input.py
nano /opt/web_log_analysis/src/llm_stage1_classifier.py
nano /opt/web_log_analysis/src/llm_stage2_reporter.py
nano /opt/web_log_analysis/src/run_analysis_pipeline.py

chmod +x /opt/web_log_analysis/src/*.py
```

각 파일에 해당 스크립트 내용을 붙여넣은 뒤 저장한다.

* 저장: `Ctrl + O`
* 엔터: `Enter`
* 종료: `Ctrl + X`

### 9.5 환경변수 파일 작성

`/opt/web_log_analysis/config/llm.env` 파일을 만든다.

```bash
nano /opt/web_log_analysis/config/llm.env
```

예시:

```dotenv
OPENAI_API_KEY=여기에_실제_API_키
OPENAI_BASE_URL=https://api.openai.com/v1
LOG_DB_HOST=192.168.35.223
LOG_DB_PORT=3306
LOG_DB_NAME=web_logs
LOG_DB_USER=log_reader
LOG_DB_PASSWORD=여기에_DB_조회_비밀번호
```

적용 예시:

```bash
set -a
source /opt/web_log_analysis/config/llm.env
set +a
```

현재 스크립트는 OpenAI API 키를 환경변수에서 읽는 구조로 사용하는 것이 적절하다.

### 9.6 권한 제한

환경파일은 소유자만 읽을 수 있게 제한한다.

```bash
chmod 600 /opt/web_log_analysis/config/llm.env
```

운영 원칙:

- API 키를 코드에 하드코딩하지 않는다.
- DB 비밀번호를 스크립트 본문에 넣지 않는다.
- 보고서 산출물과 raw export 는 일반 사용자 홈보다 별도 작업 디렉터리에 둔다.

### 9.7 DB 연결 점검

먼저 export 스크립트가 DB 에 접속 가능한지 확인한다.

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
  --out ./data/raw/security_2026-04-02_kst.json
```

이 단계가 성공하면 LLM 서버는 DB 에서 분석용 원본 JSON 을 가져올 수 있다.

### 9.8 전처리 점검

```bash
python ./src/prepare_llm_input.py   --input ./data/raw/security_2026-04-02_kst.json   --out-dir ./data/processed   --pretty   --write-filtered-out
```

이 단계에서 다음 파일이 생성되는지 본다.

- `*_llm_input.json`
- `*_analysis_candidates.json`
- `*_noise_summary.json`
- 선택: `*_filtered_out_rows.json`

### 9.9 1차 분류 dry-run 점검

```bash
python ./src/llm_stage1_classifier.py \
  --input ./data/processed/security_2026-04-02_kst_llm_input.json \
  --out-dir ./data/processed \
  --mode routine \
  --dry-run \
  --pretty
```

먼저 dry-run 으로 payload 형식과 파일 생성이 정상인지 확인한다.

### 9.10 2차 보고서 dry-run 점검

```bash
python ./src/llm_stage2_reporter.py   --stage1-results ./data/processed/security_2026-04-02_kst_stage1_results.json   --out-dir ./reports   --mode routine   --dry-run   --pretty
```

내부 실험망이나 자체 호출이 섞일 수 있다면, 보고서 작성 전에 known asset IP 목록을 함께 정리해 두는 것이 좋다.
예: 웹서버, DB 서버, LLM 서버, 실험용 윈도우 클라이언트 IP

### 9.11 전체 파이프라인 dry-run 점검

```bash
python ./src/run_analysis_pipeline.py \
  --export-input ./data/raw/security_2026-04-02_kst.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --dry-run \
  --pretty
```

### 9.12 실제 1건만 먼저 실행

실제 API 호출은 대량 실행 전에 반드시 소규모로 검증한다.

```bash
python ./src/run_analysis_pipeline.py \
  --export-input ./data/raw/security_2026-04-02_kst.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --stage1-candidate-limit 1 \
  --pretty
```

이 단계가 통과하면 routine 운영 준비가 된 것이다.

---

## 10. 네트워크 및 계정 체크포인트

### 10.1 DB 계정

LLM 서버는 읽기 전용 계정만 사용한다.

권장 기준:

- 계정: `log_reader`
- 권한: `SELECT` only
- 허용 대상: LLM 서버 IP 또는 필요한 내부 대역만 허용

이미 `log_reader@192.168.35.%` 구조가 있다면 이를 재사용할 수 있다. 다만 운영상 더 엄격하게 하려면 `log_reader@<LLM서버IP>` 로 좁히는 것이 더 바람직하다.

### 10.2 방화벽

권장 허용 방향은 다음과 같다.

- LLM 서버 → DB 서버 `3306/tcp`
- LLM 서버 → 인터넷 `443/tcp`
- 관리자 PC → LLM 서버 `22/tcp`

웹서버에서 LLM 서버로 직접 붙는 통신은 필수가 아니다.

### 10.3 시간 동기화

분석 결과의 시계열 정합성을 위해 LLM 서버도 KST 와 NTP 동기화를 점검한다.

```bash
timedatectl status
```

---

## 11. 운영 모드별 실행 기준

### 11.1 routine 모드

용도:

- 평상시 반복 분석
- 개발 중 수시 점검
- 토큰 비용 절감이 중요한 상황

모델:

- stage1: `gpt-5.4-mini`
- stage2: `gpt-5.4-mini`

### 11.2 milestone 모드

용도:

- 중간 점검
- 실험 결과 검증
- 보고서 품질 비교

모델:

- stage1: `gpt-5.4`
- stage2: `gpt-5.4`

### 11.3 presentation 모드

용도:

- 발표 직전 리허설
- 최종 시연
- 대외 보고용 산출물 생성

모델:

- stage1: `gpt-5.4`
- stage2: `gpt-5.4`

---

## 12. 해야 할 일 체크리스트

구축 전에 할 일:

- [ ] LLM 서버 VM 생성
- [ ] Ubuntu 22.04.5 Server 설치
- [ ] 고정 IP 또는 관리 가능한 IP 할당
- [ ] DB 서버 접근 가능 여부 확인
- [ ] OpenAI API 키 준비

구축 중 할 일:

- [ ] 기본 패키지 설치
- [ ] `/opt/web_log_analysis` 디렉터리 생성
- [ ] Python 가상환경 생성
- [ ] `PyMySQL` 설치
- [ ] 스크립트 5종 배치
- [ ] `llm.env` 생성 및 권한 제한
- [ ] DB export 단독 실행 성공
- [ ] 전처리 단독 실행 성공
- [ ] stage1 dry-run 성공
- [ ] stage2 dry-run 성공
- [ ] 전체 pipeline dry-run 성공
- [ ] known asset IP / 테스트 호스트 목록 정리

구축 후 할 일:

- [ ] 실제 후보 1건으로 live 호출 테스트
- [ ] routine / presentation 모드 결과 비교
- [ ] 보고서 저장 경로 정리
- [ ] 로그/산출물 백업 정책 결정
- [ ] API 키 교체 절차 문서화
- [ ] 운영용 실행 명령 또는 wrapper 스크립트 정리

---

## 13. 자주 틀리는 부분

### 13.1 LLM 서버에서 웹서버 로그 파일을 직접 읽으려는 경우

현재 표준 구조에서는 LLM 서버가 웹서버의 `/var/log/apache2/*.log` 를 직접 tail 하지 않는다.

기준 흐름은 아래와 같다.

1. 웹서버에서 로그 생성
2. shipper 가 DB 적재
3. LLM 서버가 DB export 실행
4. export JSON 을 전처리 및 분석

### 13.2 DB 쓰기 계정을 사용하려는 경우

LLM 서버는 분석 계층이므로 DB 쓰기 권한이 필요하지 않다.

`log_writer` 가 아니라 `log_reader` 를 사용한다.

### 13.3 API 키를 코드에 넣는 경우

현재 스크립트와 문서 기준에서는 API 키를 반드시 환경변수 또는 별도 환경파일로 주입한다.

### 13.4 실제 API 호출 전에 대량 분석부터 실행하는 경우

초기에는 다음 순서가 적절하다.

1. dry-run
2. 후보 1건 live 테스트
3. 소규모 시간대 실행
4. 하루 단위 실행

### 13.5 mini 와 상위 모델 사용 기준이 섞이는 경우

현재 확정 기준은 다음과 같다.

- 기본 운영: `gpt-5.4-mini`
- 중간/최종 점검, 발표: `gpt-5.4`

문서와 스크립트 모두 이 기준에 맞춘다.

---

## 14. 다음 단계

LLM 서버 구축이 끝난 뒤에는 아래 순서로 이어간다.

1. `05_Export_LLM_분석_전략.md` 의 실행 예시를 실제 경로 기준으로 맞춘다.
2. known asset IP 와 테스트 호스트 목록을 운영 메모에 반영한다.
3. `run_analysis_pipeline.py` 를 기준으로 운영용 wrapper 스크립트를 만든다.
4. 필요 시 `systemd` timer 또는 cron 기반 정기 분석을 붙인다.
5. 발표용 분석 구간을 별도로 정해 `presentation` 모드 결과를 확보한다.

즉, 이 문서는 **LLM 분석 서버를 띄우는 단계**까지를 다루고, 분석 결과의 해석과 보고서 활용은 후속 문서와 스크립트 운영으로 넘긴다.

---

## 15. 요약

이번 프로젝트에서 LLM 서버는 **웹서버와 DB 서버와 분리된 별도 분석 서버**로 정의한다.

이 서버는 MariaDB `web_logs` 에서 원본 로그를 export 하고, `prepare_llm_input.py` 로 정제한 뒤, `llm_stage1_classifier.py` 와 `llm_stage2_reporter.py` 를 통해 1차 분류와 2차 보고서를 생성한다.

운영 기준은 다음과 같이 정리한다.

1. 기본 분석은 `gpt-5.4-mini`
2. 중간 점검과 발표용 결과는 `gpt-5.4`
3. API 키와 DB 비밀번호는 환경파일로 분리
4. DB 는 읽기 전용 계정만 사용
5. raw / processed / report 디렉터리를 분리 저장

즉, LLM 서버는 단순한 테스트 머신이 아니라, **로그 분석 파이프라인을 실제로 실행하는 전용 운영 노드**다.
