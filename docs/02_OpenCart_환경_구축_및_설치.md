# 02_OpenCart_환경_구축_및_설치

- 문서 상태: 재현 절차서
- 버전: v1.3
- 작성일: 2026-04-09
- 수정일: 2026-04-26
- 적용 대상: Ubuntu 22.04 Server 기반 OpenCart 비교 실험 환경
- 기준:
  - Apache + PHP + MySQL 계열 OpenCart 단독 서버
  - Apache 로그를 `src/apache_log_shipper.py`가 읽어 DB로 적재하는 현재 구조
  - shipper 설정은 하드코딩이 아니라 `/opt/web_log_analysis/config/shipper.env` 환경변수 파일로 관리

## 1. 목적

이 문서는 OpenCart 비교 실험 환경을 처음부터 다시 만들기 위한 구축 절차서다.  
문서 안의 명령과 설정만 따라가면 다음 상태를 재현할 수 있어야 한다.

- Apache가 OpenCart를 서비스한다.
- Apache가 `app_access.log`, `app_security.log`, `app_error.log`를 남긴다.
- 로그 포맷이 현재 shipper 파서와 맞는다.
- 웹 요청이 실제로 로그에 기록된다.
- shipper가 `/opt/web_log_analysis/config/shipper.env`를 통해 MariaDB 접속 정보를 읽는다.
- 이후 웹서버에서 shipper를 붙여 MariaDB 서버로 적재할 수 있다.

## 2. 구성 요약

- 운영체제: Ubuntu 22.04 LTS
- 웹서버: Apache2
- 애플리케이션: OpenCart 4.x
- PHP: Apache 모듈 방식
- 로컬 DB: MySQL Server
- 웹 루트: `/var/www/opencart`
- Apache 사이트 설정: `/etc/apache2/sites-available/opencart.conf`
- shipper 작업 디렉터리: `/opt/web_log_analysis`
- shipper 환경변수 파일: `/opt/web_log_analysis/config/shipper.env`
- 로그 파일:
  - `/var/log/apache2/app_access.log`
  - `/var/log/apache2/app_security.log`
  - `/var/log/apache2/app_error.log`

권장 구성은 Juice Shop 서버와 분리된 별도 VM 또는 별도 서버다. 비교 실험용 앱을 분리하면 로그가 섞이지 않는다.

## 3. 사전 준비

예시 기준:

- OpenCart 서버 IP: `192.168.56.108`
- MariaDB 로그 DB 서버 IP: `192.168.56.109`
- OpenCart 접속 URL: `http://192.168.56.108/`
- OpenCart 관리자 URL: 설치 후 출력되는 admin 경로

패키지 설치 전에 시간대를 맞춘다.

```bash
sudo timedatectl set-timezone Asia/Seoul
timedatectl
```

시스템 업데이트:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y curl wget unzip ca-certificates gnupg lsb-release
```

점검:

```bash
uname -a
lsb_release -a
ip addr
```

## 4. Apache 설치

```bash
sudo apt install -y apache2
sudo systemctl enable apache2
sudo systemctl start apache2
sudo systemctl status apache2
```

기본 응답 확인:

```bash
curl -I http://127.0.0.1
```

정상이라면 `HTTP/1.1 200 OK` 또는 기본 Apache 페이지 응답이 나온다.

## 5. PHP 설치

OpenCart 4.x 기준으로 필요한 주요 패키지를 설치한다.

```bash
sudo apt install -y \
  php libapache2-mod-php php-cli php-mysql \
  php-curl php-gd php-mbstring php-xml php-zip php-intl php-opcache
```

확인:

```bash
php -v
php -m | egrep 'curl|gd|mbstring|xml|zip|intl|mysqli|pdo_mysql'
```

Apache 반영:

```bash
sudo systemctl restart apache2
```

## 6. Python 및 shipper 작업 디렉터리 준비

웹서버에서 Apache 로그를 DB 서버로 적재하려면 Python 3 환경과 `PyMySQL`이 필요하다.

```bash
sudo apt install -y python3 python3-pip python3-venv
python3 --version
pip3 --version
```

현재 구조에서는 shipper 스크립트와 설정 파일을 `/opt/web_log_analysis` 아래에 둔다.

```bash
sudo mkdir -p /opt/web_log_analysis/{config,src}
sudo chown -R "$USER":"$USER" /opt/web_log_analysis

cd /opt/web_log_analysis
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install PyMySQL
```

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

`apache_log_shipper.py`는 DB 접속 정보와 로그 파일 경로를 코드에 하드코딩하지 않고 환경변수에서 읽는다. 따라서 OpenCart 서버에도 환경변수 파일을 만들어야 한다.

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

- `LOG_DB_HOST`는 OpenCart 서버 IP가 아니라 MariaDB 로그 저장 서버 IP다. 현재 예시는 `192.168.56.109`다.
- `LOG_DB_PASSWORD`는 실제 `log_writer` 계정 비밀번호로 바꾼다.
- password가 들어 있으므로 `shipper.env`는 public repo에 올리지 않는다.
- `sudo python3 ...`처럼 바로 실행하면 현재 셸의 env가 사라질 수 있다. 아래처럼 `sudo bash -c 'source ...'` 방식으로 실행한다.

환경변수 로드 테스트:

```bash
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; env | grep -E "^(LOG_DB_HOST|LOG_DB_PORT|LOG_DB_USER|LOG_DB_NAME|APACHE_SECURITY_LOG)="'
```

DB 연결 테스트:

```bash
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --test-db'
```

기대 결과:

```text
DB connection: OK
```

## 8. MySQL 설치 및 OpenCart DB 생성

OpenCart 애플리케이션 자체가 사용할 로컬 DB를 만든다. 이 DB는 Apache 로그 저장 DB(`web_logs`)와 다르다.

```bash
sudo apt install -y mysql-server
sudo systemctl enable mysql
sudo systemctl start mysql
sudo systemctl status mysql
```

루트 셸 접속:

```bash
sudo mysql -u root
```

OpenCart용 DB와 계정을 만든다.

```sql
CREATE DATABASE opencart
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER 'opencartuser'@'localhost' IDENTIFIED BY 'hoseo2026';
GRANT ALL PRIVILEGES ON opencart.* TO 'opencartuser'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

검증:

```bash
sudo mysql -e "SHOW DATABASES LIKE 'opencart';"
sudo mysql -e "SELECT user, host FROM mysql.user WHERE user='opencartuser';"
mysql -u opencartuser -p -e "USE opencart; SHOW TABLES;"
```

마지막 명령은 초기 설치 직후에는 빈 결과가 정상이다.

## 9. OpenCart 소스 설치

예시는 `4.1.0.3` 릴리스를 기준으로 한다.

```bash
cd ~
wget https://github.com/opencart/opencart/releases/download/4.1.0.3/opencart-4.1.0.3.zip
sudo mkdir -p /var/www/opencart
cd /var/www/opencart
sudo unzip ~/opencart-4.1.0.3.zip
sudo cp -r upload/. /var/www/opencart/
sudo rm -rf upload
rm -f ~/opencart-4.1.0.3.zip
```

설치 파일 준비:

```bash
sudo cp /var/www/opencart/config-dist.php /var/www/opencart/config.php
sudo cp /var/www/opencart/admin/config-dist.php /var/www/opencart/admin/config.php
sudo mv /var/www/opencart/htaccess.txt /var/www/opencart/.htaccess 2>/dev/null || true
sudo mv /var/www/opencart/.htaccess.txt /var/www/opencart/.htaccess 2>/dev/null || true
```

권한 설정:

```bash
sudo chown -R www-data:www-data /var/www/opencart
sudo find /var/www/opencart -type d -exec chmod 755 {} +
sudo find /var/www/opencart -type f -exec chmod 644 {} +
```

검증:

```bash
ls -l /var/www/opencart/config.php
ls -l /var/www/opencart/admin/config.php
```

## 10. Apache 모듈 활성화

현재 로그 포맷과 OpenCart 동작에 필요한 모듈을 켠다.

```bash
sudo a2enmod rewrite
sudo a2enmod headers
sudo a2enmod logio
sudo a2enmod unique_id
sudo systemctl restart apache2
```

## 11. Apache 사이트 설정

설정 파일 생성:

```bash
sudo nano /etc/apache2/sites-available/opencart.conf
```

아래 내용을 그대로 넣는다.

```apache
<VirtualHost *:80>
    ServerAdmin admin@example.com
    ServerName 192.168.56.108
    DocumentRoot /var/www/opencart

    <Directory /var/www/opencart>
        AllowOverride All
        Require all granted
    </Directory>

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

적용:

```bash
sudo a2ensite opencart.conf
sudo a2dissite 000-default.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

`Syntax OK`가 나와야 한다.

## 12. 브라우저 설치 마무리

브라우저에서 아래 주소로 접속한다.

```text
http://192.168.56.108/
```

설치 화면에서 입력할 값:

- DB Driver: `MySQLi`
- Hostname: `localhost`
- Username: `opencartuser`
- Password: 앞 단계에서 만든 비밀번호
- Database: `opencart`
- Port: `3306`
- Prefix: `oc_`

관리자 계정은 테스트에 쓸 값으로 설정한다. 설치가 끝나면 OpenCart가 admin 경로와 삭제할 디렉터리를 안내한다.

설치 후 `install` 디렉터리를 삭제한다.

```bash
sudo rm -rf /var/www/opencart/install
```

## 13. 설치 후 동작 확인

기본 응답:

```bash
curl -I http://127.0.0.1/
curl -I "http://127.0.0.1/index.php?route=product/search"
```

브라우저에서 아래를 확인한다.

- 메인 페이지 로드
- 카테고리 이동
- 상품 상세 페이지 이동
- 검색 요청 발생
- 관리자 로그인 화면 접속

MySQL 테이블 생성 여부 확인:

```bash
mysql -u opencartuser -p -e "USE opencart; SHOW TABLES;" | head
```

정상이라면 `oc_` 접두어 테이블이 보인다.

## 14. 로그 생성 확인

로그 파일 확인:

```bash
ls -l /var/log/apache2/app_access.log
ls -l /var/log/apache2/app_security.log
ls -l /var/log/apache2/app_error.log
```

테스트 요청을 만든다.

```bash
curl -s http://127.0.0.1/ >/dev/null
curl -s "http://127.0.0.1/index.php?route=product/search&search=apple" >/dev/null
curl -s "http://127.0.0.1/admin/" >/dev/null
```

최근 로그 확인:

```bash
sudo tail -n 5 /var/log/apache2/app_access.log
sudo tail -n 5 /var/log/apache2/app_security.log
sudo tail -n 5 /var/log/apache2/app_error.log
```

확인 포인트:

- `app_access.log`에 일반 Apache access 라인이 남는다.
- `app_security.log`에 `log_time=`, `request_id=`, `raw_request=`, `resp_content_type=` 형식의 key/value 로그가 남는다.
- `host="192.168.56.108"` 또는 OpenCart host가 남는지 확인한다.
- `app_error.log`는 에러가 없으면 빈 상태일 수 있다.

## 15. shipper 연동 체크포인트

현재 프로젝트 흐름상 아래 항목은 바로 이어서 확인하는 편이 안전하다.

- DB 서버에서 `web_logs`와 `log_writer` 계정이 준비되어 있다.
- OpenCart 서버에서 DB 서버 `3306/tcp`로 연결된다.
- `/opt/web_log_analysis/config/shipper.env`가 존재한다.
- `/opt/web_log_analysis/src/apache_log_shipper.py`가 존재한다.
- shipper 설정이 아래 로그 파일을 가리킨다.
  - `/var/log/apache2/app_access.log`
  - `/var/log/apache2/app_security.log`
  - `/var/log/apache2/app_error.log`

연결 점검 예시:

```bash
set -a
source /opt/web_log_analysis/config/shipper.env
set +a
nc -vz "$LOG_DB_HOST" "$LOG_DB_PORT"
```

shipper 점검 예시:

```bash
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --test-db'
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --once'
```

상시 실행 예시:

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

## 16. env 관련 문제 해결

### 16.1 `LOG_DB_HOST is required`

원인:

- `shipper.env`를 source하지 않고 실행했다.
- `sudo python3 ...`로 실행하면서 env가 사라졌다.

해결:

```bash
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --test-db'
```

### 16.2 `LOG_DB_PASSWORD is required`

원인:

- `shipper.env`의 `LOG_DB_PASSWORD`가 비어 있다.
- placeholder를 실제 비밀번호로 바꾸지 않았다.

확인:

```bash
sudo grep '^LOG_DB_PASSWORD=' /opt/web_log_analysis/config/shipper.env
```

### 16.3 로그는 생기는데 DB에 안 들어감

확인 순서:

```bash
sudo tail -n 3 /var/log/apache2/app_security.log
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; env | grep -E "^(LOG_DB_HOST|APACHE_SECURITY_LOG)="'
sudo bash -c 'set -a; source /opt/web_log_analysis/config/shipper.env; set +a; exec /opt/web_log_analysis/.venv/bin/python /opt/web_log_analysis/src/apache_log_shipper.py --test-db'
sudo tail -n 20 /var/log/apache2/apache_log_shipper.log
```
