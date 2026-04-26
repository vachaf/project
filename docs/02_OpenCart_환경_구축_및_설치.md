# 02_OpenCart_환경_구축_및_설치

- 문서 상태: 재현 절차서
- 버전: v1.2
- 작성일: 2026-04-09
- 적용 대상: Ubuntu 22.04 Server 기반 OpenCart 비교 실험 환경
- 기준:
  - Apache + PHP + MySQL 계열 OpenCart 단독 서버
  - Apache 로그를 `src/apache_log_shipper.py`가 읽어 DB로 적재하는 현재 구조

## 1. 목적

이 문서는 OpenCart 비교 실험 환경을 처음부터 다시 만들기 위한 구축 절차서다.  
문서 안의 명령과 설정만 따라가면 다음 상태를 재현할 수 있어야 한다.

- Apache가 OpenCart를 서비스한다.
- Apache가 `app_access.log`, `app_security.log`, `app_error.log`를 남긴다.
- 로그 포맷이 현재 shipper 파서와 맞는다.
- 웹 요청이 실제로 로그에 기록된다.
- 이후 웹서버에서 shipper를 붙여 MariaDB 서버로 적재할 수 있다.

## 2. 구성 요약

- 운영체제: Ubuntu 22.04 LTS
- 웹서버: Apache2
- 애플리케이션: OpenCart 4.x
- PHP: Apache 모듈 방식
- 로컬 DB: MySQL Server
- 웹 루트: `/var/www/opencart`
- Apache 사이트 설정: `/etc/apache2/sites-available/opencart.conf`
- 로그 파일:
  - `/var/log/apache2/app_access.log`
  - `/var/log/apache2/app_security.log`
  - `/var/log/apache2/app_error.log`

권장 구성은 Juice Shop 서버와 분리된 별도 VM 또는 별도 서버다. 비교 실험용 앱을 분리하면 로그가 섞이지 않는다.

## 3. 사전 준비

예시 기준:

- OpenCart 서버 IP: `192.168.56.111`
- OpenCart 접속 URL: `http://192.168.56.111/`
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

## 6. Python 준비

웹서버에서 Apache 로그를 DB 서버로 적재하려면 Python 3 환경이 필요하다.

```bash
sudo apt install -y python3 python3-pip python3-venv
python3 --version
pip3 --version
```

선택 사항으로 shipper 전용 가상환경을 둘 수 있다.

```bash
sudo mkdir -p /opt/apache_log_shipper
cd /opt/apache_log_shipper
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install PyMySQL
deactivate
```

## 7. MySQL 설치 및 OpenCart DB 생성

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

## 8. OpenCart 소스 설치

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
sudo find /var/www/opencart -type d -exec chmod 755 {} \\;
sudo find /var/www/opencart -type f -exec chmod 644 {} \\;
```

검증:

```bash
ls -l /var/www/opencart/config.php
ls -l /var/www/opencart/admin/config.php
```

## 9. Apache 모듈 활성화

현재 로그 포맷과 OpenCart 동작에 필요한 모듈을 켠다.

```bash
sudo a2enmod rewrite
sudo a2enmod headers
sudo a2enmod logio
sudo a2enmod unique_id
sudo systemctl restart apache2
```

## 10. Apache 사이트 설정

설정 파일 생성:

```bash
sudo nano /etc/apache2/sites-available/opencart.conf
```

아래 내용을 그대로 넣는다.

```apache
<VirtualHost *:80>
    ServerAdmin admin@example.com
    ServerName 192.168.56.111
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

## 11. 브라우저 설치 마무리

브라우저에서 아래 주소로 접속한다.

```text
http://192.168.56.111/
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

## 12. 설치 후 동작 확인

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

## 13. 로그 생성 확인

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
- `app_error.log`는 에러가 없으면 빈 상태일 수 있다.

## 14. shipper 연동 전 체크포인트

이 문서는 OpenCart 서버 자체 구축이 목적이지만, 현재 프로젝트 흐름상 아래 항목은 바로 이어서 확인하는 편이 안전하다.

- DB 서버에서 `web_logs`와 `log_writer` 계정이 준비되어 있다.
- 웹서버에서 DB 서버 `3306/tcp`로 연결된다.
- `src/apache_log_shipper.py` 또는 동일 사본이 웹서버에 배치되어 있다.
- shipper 설정이 아래 로그 파일을 가리킨다.
  - `/var/log/apache2/app_access.log`
  - `/var/log/apache2/app_security.log`
  - `/var/log/apache2/app_error.log`

연결 점검 예시:

```bash
nc -vz 192.168.56.111 3306
```

shipper 점검 예시:

```bash
python3 /opt/apache_log_shipper.py --test-db
python3 /opt/apache_log_shipper.py --once
```

## 15. 현재 분석 파이프라인과 직접 연결되는 필드

현재 분석 파이프라인에서 직접 쓰는 축은 아래다.

- `resp_content_type`
- `response_body_bytes`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`

이 중 `raw_request_target`, `path_normalized_from_raw_request`, `likely_html_fallback_response`는 DB 적재 후 LLM 준비 단계에서 계산 또는 해석에 사용된다.

## 16. `resp_html_*` 처리 기준

`resp_html_*` 계열은 현재 필수 구축 항목이 아니다.

- 현재 Apache 표준 로그 포맷에 넣지 않는다.
- `src/apache_log_shipper.py`와 DB 스키마에 관련 컬럼은 남아 있을 수 있다.
- 현재 운영과 분석의 핵심 기준으로 취급하지 않는다.
- 필요하면 나중에 선택 컬럼으로 확장할 수 있지만, 지금 문서 기준 기본 환경에서는 제외한다.
