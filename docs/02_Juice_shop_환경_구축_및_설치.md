# 02_Juice_shop_환경_구축_및_설치

- 문서 상태: 구축문서
- 버전: v1.3
- 작성일: 2026-04-09
- 수정일: 2026-04-26

## 1. 목적

Ubuntu 22.04 Server에서 Apache2와 Docker를 사용해 OWASP Juice Shop 실험 환경을 재현하고, 현재 로그 파이프라인이 기대하는 access/security/error 로그를 생성하는 절차를 정리한다.

현재 `apache_log_shipper.py`는 DB 접속 정보와 로그 경로를 코드에 하드코딩하지 않고 환경변수에서 읽는다. 따라서 이 문서는 Juice Shop 자체 구축뿐 아니라 `/opt/web_log_analysis/config/shipper.env` 생성과 shipper 실행 절차까지 포함한다.

## 2. 최종 구성

- OS: Ubuntu 22.04 Server
- 웹서버: Apache2
- 앱: OWASP Juice Shop
- 실행 방식: Docker
- 외부 접속: `http://서버IP/`
- 내부 앱 바인딩: `127.0.0.1:3000`
- shipper 작업 디렉터리: `/opt/web_log_analysis`
- shipper 환경변수 파일: `/opt/web_log_analysis/config/shipper.env`
- 로그 파일:
  - `/var/log/apache2/app_access.log`
  - `/var/log/apache2/app_security.log`
  - `/var/log/apache2/app_error.log`

예시 기준:

- Juice Shop 서버 IP: `192.168.56.105`
- MariaDB 로그 DB 서버 IP: `192.168.56.109`

## 3. 사전 조건

- Ubuntu 22.04 Server 준비
- `sudo` 가능한 계정
- 인터넷 연결 가능
- 서버 IP 확인 가능

서버 IP 확인:

```bash
ip addr
hostnamectl
```

## 4. 구축 순서

1. 시스템 업데이트
2. Python 및 shipper 작업 디렉터리 준비
3. shipper 환경변수 파일 생성
4. Apache 설치
5. Docker 설치
6. Juice Shop 컨테이너 실행
7. Apache 모듈 활성화
8. Apache VirtualHost 작성
9. 사이트 활성화
10. 브라우저 접속 검증
11. 로그 3종 생성 확인
12. shipper DB 연결 및 적재 확인

## 5. 시스템 업데이트

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y curl wget unzip ca-certificates gnupg lsb-release python3 python3-pip python3-venv netcat-openbsd
```

## 6. Python 및 shipper 작업 디렉터리 준비

웹서버에서 `apache_log_shipper.py`를 함께 배치할 경우 `/opt/web_log_analysis` 아래에 스크립트와 설정을 둔다.

```bash
sudo mkdir -p /opt/web_log_analysis/{config,src}
sudo chown -R "$USER":"$USER" /opt/web_log_analysis

cd /opt/web_log_analysis
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install PyMySQL
```

현재 저장소에는 웹서버용 별도 `requirements.txt`가 없으므로, 로그 적재 스크립트 실행에 필요한 외부 모듈은 `PyMySQL`을 직접 설치한다.

저장소의 shipper를 웹서버에 배치한다. 이미 `/opt/apache_log_shipper.py`로 운영 중인 환경이면 기존 경로를 유지해도 되지만, 신규 구축은 아래 경로를 권장한다.

```bash
# 저장소가 웹서버에 있는 경우 예시
cp /path/to/project/src/apache_log_shipper.py /opt/web_log_analysis/src/apache_log_shipper.py
chmod +x /opt/web_log_analysis/src/apache_log_shipper.py
```

확인:

```bash
/opt/web_log_analysis/.venv/bin/python --version
/opt/web_log_analysis/.venv/bin/python -c "import pymysql; print(pymysql.__version__)"
ls -l /opt/web_log_analysis/src/apache_log_shipper.py
```

## 7. shipper 환경변수 파일 생성

`apache_log_shipper.py`는 아래 환경변수를 읽는다.

- `LOG_DB_HOST`
- `LOG_DB_PORT`
- `LOG_DB_USER`
- `LOG_DB_PASSWORD`
- `LOG_DB_NAME`
- `APACHE_ACCESS_LOG`
- `APACHE_SECURITY_LOG`
- `APACHE_ERROR_LOG`
- `SHIPPER_STATE_DIR`
- `SHIPPER_SPOOL_DIR`
- `SHIPPER_APP_LOG`
- `SHIPPER_*` 튜닝값

환경변수 파일 생성:

```bash
sudo mkdir -p /opt/web_log_analysis/config
sudo tee /opt/web_log_analysis/config/shipper.env >/dev/null <<'EOF'
# MariaDB log storage
LOG_DB_HOST=192.168.56.109
LOG_DB_PORT=3306
LOG_DB_USER=log_writer
LOG_DB_PASSWORD=여기에_log_writer_비밀번호를_입력
LOG_DB_NAME=web_logs

# Apache log files
APACHE_ACCESS_LOG=/var/log/apache2/app_access.log
APACHE_SECURITY_LOG=/var/log/apache2/app_security.log
APACHE_ERROR_LOG=/var/log/apache2/app_error.log

# Shipper runtime paths
SHIPPER_STATE_DIR=/var/lib/apache_log_shipper
SHIPPER_SPOOL_DIR=/var/spool/apache_log_shipper
SHIPPER_APP_LOG=/var/log/apache2/apache_log_shipper.log

# Shipper tuning
SHIPPER_SCAN_INTERVAL_SEC=1.0
SHIPPER_FLUSH_INTERVAL_SEC=2.0
SHIPPER_BATCH_SIZE=100
SHIPPER_SPOOL_RETRY_INTERVAL_SEC=10.0
SHIPPER_CONNECT_TIMEOUT_SEC=5
SHIPPER_READ_TIMEOUT_SEC=10
SHIPPER_WRITE_TIMEOUT_SEC=10
EOF

sudo chown root:root /opt/web_log_analysis/config/shipper.env
sudo chmod 600 /opt/web_log_analysis/config/shipper.env
```

확인:

```bash
sudo ls -l /opt/web_log_analysis/config/shipper.env
sudo grep -v 'PASSWORD' /opt/web_log_analysis/config/shipper.env
```

주의:

- `LOG_DB_HOST`는 Juice Shop 서버 IP가 아니라 MariaDB 로그 저장 서버 IP다. 현재 예시는 `192.168.56.109`다.
- `LOG_DB_PASSWORD`는 실제 `log_writer` 계정 비밀번호로 바꾼다.
- `shipper.env`에는 비밀번호가 들어 있으므로 public repo에 올리지 않는다.
- `sudo python3 ...`처럼 바로 실행하면 현재 셸의 env가 사라질 수 있다. 아래처럼 `sudo bash -c 'source ...'` 방식으로 실행한다.

환경변수 로드 테스트:

```bash
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; env | grep -E "^(LOG_DB_HOST|LOG_DB_PORT|LOG_DB_USER|LOG_DB_NAME|APACHE_SECURITY_LOG)="'
```

DB 연결 테스트는 Apache 설정 후 또는 DB 서버 준비 후 수행한다.

```bash
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --test-db'
```

기대 결과:

```text
DB connection: OK
```

## 8. Apache 설치

```bash
sudo apt install -y apache2
sudo systemctl enable apache2
sudo systemctl start apache2
sudo systemctl status apache2
curl -I http://127.0.0.1
```

기대 결과:

- Apache 기본 페이지에 대한 `HTTP/1.1 200 OK` 응답

## 9. Docker 설치

```bash
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo systemctl status docker
sudo docker version
sudo docker ps
```

원하면 현재 사용자에 docker 그룹 권한 추가:

```bash
sudo usermod -aG docker $USER
```

## 10. Juice Shop 실행

```bash
sudo docker pull bkimminich/juice-shop:v19.2.1
sudo docker run -d \
  --name juice-shop \
  -p 127.0.0.1:3000:3000 \
  --restart unless-stopped \
  bkimminich/juice-shop:v19.2.1
```

확인:

```bash
sudo docker ps
curl -I http://127.0.0.1:3000
sudo docker logs --tail 50 juice-shop
```

기대 결과:

- `docker ps` 에 `juice-shop` 컨테이너 표시
- `127.0.0.1:3000` 에서 HTTP 응답 확인

## 11. Apache 모듈 활성화

현재 로그 포맷과 Reverse Proxy 구성을 위해 아래 모듈을 활성화한다.

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
sudo a2enmod logio
sudo a2enmod unique_id
sudo systemctl restart apache2
```

## 12. Apache 사이트 설정

설정 파일 생성:

```bash
sudo nano /etc/apache2/sites-available/juice-shop.conf
```

아래 내용을 저장한다.

```apache
<VirtualHost *:80>
    ServerAdmin admin@example.com
    ServerName localhost

    ProxyRequests Off
    ProxyPass        / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/

    ErrorLogFormat "[%{uc}t] [error_link_id:%L] [request_id:%{UNIQUE_ID}e] [module_name:%-m] [log_level:%-l] [src_ip:%a peer_ip:%{c}a] message=%M"
    ErrorLog ${APACHE_LOG_DIR}/app_error.log

    LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" \"%{Host}i\" %v" access_db_aligned
    CustomLog ${APACHE_LOG_DIR}/app_access.log access_db_aligned

    LogIOTrackTTFB ON

    LogFormat "log_time=%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t \
request_id=%{UNIQUE_ID}e error_link_id=%L \
vhost=%v src_ip=%a peer_ip=%{c}a \
method=%m raw_request=\"%r\" uri=\"%U\" query_string=\"%q\" protocol=%H \
status_code=%>s response_body_bytes=%B \
in_bytes=%I out_bytes=%O total_bytes=%S \
duration_us=%D ttfb_us=%^FB keepalive_count=%k connection_status=%X \
req_content_type=\"%{Content-Type}i\" req_content_length=\"%{Content-Length}i\" \
resp_content_type=\"%{Content-Type}o\" \
referer=\"%{Referer}i\" user_agent=\"%{User-Agent}i\" \
host=\"%{Host}i\" x_forwarded_for=\"%{X-Forwarded-For}i\"" security_db_aligned

CustomLog ${APACHE_LOG_DIR}/app_security.log security_db_aligned
</VirtualHost>
```

주의:

- 현재 코드 기준 핵심 security 로그 필드는 `resp_content_type`, `response_body_bytes`, `raw_request`, `uri`, `query_string`, `duration_us`, `ttfb_us` 등이다.
- `resp_html_*` 는 현재 필수 로그 포맷에 넣지 않는다.

## 13. 사이트 활성화

```bash
sudo a2dissite 000-default.conf
sudo a2ensite juice-shop.conf
sudo apache2ctl configtest
sudo systemctl restart apache2
sudo systemctl status apache2
```

기대 결과:

- `Syntax OK`

## 14. 브라우저 접속 검증

서버 내부:

```bash
curl -I http://127.0.0.1/
curl -I http://localhost/
```

클라이언트 PC:

```text
http://서버IP/
```

기대 결과:

- Apache 기본 페이지가 아니라 Juice Shop 화면이 열려야 한다.
- 외부에서 `http://서버IP:3000/` 로 직접 접속하지 않는다.

## 15. 로그 파일 생성 확인

파일 확인:

```bash
ls -l /var/log/apache2/
```

tail 확인:

```bash
sudo tail -f /var/log/apache2/app_access.log
sudo tail -f /var/log/apache2/app_security.log
sudo tail -f /var/log/apache2/app_error.log
```

요청 발생:

```bash
curl -I http://127.0.0.1/
curl -s http://127.0.0.1/ > /dev/null
```

기대 결과:

- `app_access.log` 증가
- `app_security.log` 증가
- `app_error.log` 는 정상 상황에서는 비어 있을 수 있음

## 16. security 로그 포맷 확인

`app_security.log` 한 줄에 아래 키가 보여야 한다.

- `log_time`
- `request_id`
- `error_link_id`
- `method`
- `raw_request`
- `uri`
- `query_string`
- `status_code`
- `response_body_bytes`
- `duration_us`
- `ttfb_us`
- `req_content_type`
- `resp_content_type`
- `user_agent`
- `host`

이 형식은 현재 `src/apache_log_shipper.py` 파서와 맞는다.

## 17. shipper DB 연결 및 적재 확인

DB 서버와 연결 가능한지 확인한다.

```bash
set -a
source /opt/web_log_analysis/config/shipper.env
set +a
nc -vz "$LOG_DB_HOST" "$LOG_DB_PORT"
```

DB 연결 테스트:

```bash
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --test-db'
```

1회 적재 테스트:

```bash
curl -s http://127.0.0.1/ >/dev/null
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --once'
```

상시 실행:

```bash
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py'
```

기대 결과:

```text
Apache log shipper started.
Using logs: access=/var/log/apache2/app_access.log security=/var/log/apache2/app_security.log error=/var/log/apache2/app_error.log
Connected to MariaDB 192.168.56.109:3306
Flushed: access=N security=N error=N
```

## 18. 설치 후 최소 점검

- `docker ps` 에서 `juice-shop` 확인
- `curl -I http://127.0.0.1:3000` 응답 확인
- `curl -I http://127.0.0.1/` 응답 확인
- 브라우저에서 Juice Shop 화면 확인
- `apache2ctl configtest` 가 `Syntax OK`
- `app_access.log`, `app_security.log` 생성 확인
- `/opt/web_log_analysis/config/shipper.env` 존재 확인
- `apache_log_shipper.py --test-db` 성공 확인
- `apache_log_shipper.py --once` 실행 시 `Flushed:` 로그 확인

## 19. env 관련 문제 해결

### 19.1 `LOG_DB_HOST is required`

원인:

- `shipper.env`를 source하지 않고 실행했다.
- `sudo python3 ...`로 실행하면서 env가 사라졌다.

해결:

```bash
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --test-db'
```

### 19.2 `LOG_DB_PASSWORD is required`

원인:

- `shipper.env`의 `LOG_DB_PASSWORD`가 비어 있다.
- placeholder를 실제 비밀번호로 바꾸지 않았다.

확인:

```bash
sudo grep '^LOG_DB_PASSWORD=' /opt/web_log_analysis/config/shipper.env
```

### 19.3 로그는 생기는데 DB에 안 들어감

확인 순서:

```bash
sudo tail -n 3 /var/log/apache2/app_security.log
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; env | grep -E "^(LOG_DB_HOST|APACHE_SECURITY_LOG)="'
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --test-db'
sudo tail -n 20 /var/log/apache2/apache_log_shipper.log
```

## 20. 다음 단계

Juice Shop 환경 구축 후 진행 순서:

1. DB 서버에 `web_logs` 구축
2. `/opt/web_log_analysis/config/shipper.env` 작성
3. `apache_log_shipper.py` 배치 및 DB 연결 확인
4. `security` export 실행
5. `prepare_llm_input.py`
6. `llm_stage1_classifier.py`
7. `llm_stage2_reporter.py`
