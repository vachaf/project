# 02_OpenCart_환경_구축_및_설치

- 문서 상태: 통합본
- 버전: v1.1
- 작성일: 2026-04-08
- 적용 대상: Ubuntu 22.04 Server 기반 OpenCart 비교 실험 환경 구축 문서
- 연계 문서:
  - `01_프로젝트_방향과_실험대상.md`
  - `02_MariaDB_환경_구축_및_설치.md`
  - `03_로그_표준과_DB_구조.md`
  - `04_로그_적재_및_운영.md`
  - `05_Export_LLM_분석_전략.md`
  - `99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md`

---

## 1. 문서 목적

이 문서는 **Ubuntu 22.04 Server 환경에서 Apache2, PHP, MySQL 계열 구성을 사용해 OpenCart 비교 실험 환경을 구축하는 절차**를 정리한 설치 문서다.

이번 프로젝트의 실험 대상은 이미 구축된 **OWASP Juice Shop** 하나만이 아니다.  
Juice Shop은 계속 유지하고, 추가로 **OpenCart 기반의 현실적인 쇼핑몰형 웹 애플리케이션**을 별도 환경에 구축하여 다음과 같은 비교 실험을 가능하게 하는 것이 목표다.

- 같은 정상 요청을 보냈을 때 로그와 보고서가 어떻게 다른가
- 같은 탐색성 요청을 보냈을 때 후보/비후보 분리가 어떻게 달라지는가
- 같은 공격성 요청을 보냈을 때 stage1 / stage2 보고서가 어떻게 달라지는가
- 의도적 취약 앱과 일반 쇼핑몰형 앱에서 노이즈와 고신호 공격이 어떻게 다르게 보이는가

즉, 이 문서는 단순한 OpenCart 설치 가이드가 아니라, **Juice Shop과 병행 운영하는 비교 실험용 웹 애플리케이션 환경 구축 절차서**다.

---

## 2. 왜 OpenCart를 추가하는가

기존에 최종 실습 대상은 Juice Shop으로 선택되었다. 그 결정은 여전히 유효하다.

- Juice Shop은 보안 실습과 공격 재현에 매우 유리하다.
- 고신호 공격 요청을 비교적 쉽게 만들 수 있다.
- 공격 로그 수집, 후보 추출, 보고서 품질 검증에 적합하다.

그러나 Juice Shop만으로는 한계도 있다.

- 의도적 취약 앱이라 정상 운영형 웹앱의 기준선과 다를 수 있다.
- 정상 요청, 상품 탐색, 관리 기능, 장바구니 흐름 등 일반 쇼핑몰형 트래픽 분포와 다를 수 있다.
- “실서비스형 애플리케이션에서의 보수적 해석”을 검증하기에는 표본이 편향될 수 있다.

따라서 이번에는 OpenCart를 **교체 대상이 아니라 병행 비교 대상**으로 추가한다.

정리하면:

- **Juice Shop**: 의도적 취약 앱, 공격 재현 중심
- **OpenCart**: 일반 쇼핑몰형 앱, 현실적 요청 분포 비교 중심

이번 문서는 두 환경을 동시에 유지하는 전제 위에서, OpenCart 쪽 환경만 별도로 구축하는 절차를 다룬다.

---

## 3. 구축 전략

### 3.1 기본 전략

OpenCart는 **Juice Shop과 같은 서버에 덧붙이기보다, 별도 Ubuntu 22.04 Server / 별도 VM / 별도 서버 IP**에 구축하는 것을 권장한다.

그 이유는 다음과 같다.

1. Apache 가상호스트, PHP, MySQL 계열 구성이 Juice Shop의 Reverse Proxy 구조와 성격이 다르다.
2. 동일 서버에 공존시키면 설정 충돌과 운영 복잡도가 커진다.
3. 실험 로그를 더 깨끗하게 분리할 수 있다.
4. “앱별 보고서 비교”라는 목적에 더 잘 맞는다.

### 3.2 이번 문서 기준 IP

이번 OpenCart 서버의 IP는 아래와 같이 고정한다.

- **OpenCart 서버 IP: `192.168.35.193`**

이 IP는 이후 DB 계정 허용, known asset 목록, 보고서 해석 기준에도 반영한다.

### 3.3 권장 구성

- 운영체제: Ubuntu 22.04 LTS Server
- 웹서버: Apache2
- 애플리케이션: OpenCart 4.x
- DB: MySQL 서버
- PHP: Apache 모듈 방식 PHP
- Python: shipper 실행용 Python 3
- 웹 루트: `/var/www/opencart`
- Apache 로그:
  - `/var/log/apache2/app_access.log`
  - `/var/log/apache2/app_security.log`
  - `/var/log/apache2/app_error.log`

여기서 로그 파일명은 현재 프로젝트의 shipper 기본값과 맞추기 위해 Juice Shop 환경과 같은 이름을 유지한다.

### 3.4 왜 별도 서버/VM을 권장하는가

이번 문서는 OpenCart를 **Juice Shop의 대체재**가 아니라 **비교 실험용 병행 환경**으로 본다.  
그러므로 서버 단위 분리가 오히려 자연스럽다.

- Juice Shop 서버: Node.js 앱 + Apache Reverse Proxy
- OpenCart 서버: PHP 앱 + Apache DocumentRoot
- 두 환경은 모두 같은 DB export / prepare / stage1 / stage2 파이프라인으로 분석 가능

즉, 앱은 다르지만 로그 수집과 보고서 생성 파이프라인은 동일하게 유지한다.

---

## 4. 대상 환경

기준 환경은 아래와 같다.

- 운영체제: **Ubuntu 22.04 LTS Server**
- 웹서버: **Apache2**
- PHP: **PHP 8.x**
- Python: **Python 3 / pip / venv**
- DB: **MySQL 서버**
- 애플리케이션: **OpenCart 4.x**
- 웹 루트: **`/var/www/opencart`**
- 서버 IP: **`192.168.35.193`**
- 접속 주소: **`http://192.168.35.193/`**
- 관리자 페이지: 기본은 `/admin/` 또는 설치 시 지정한 admin 경로

OpenCart는 일반적인 Apache + PHP + MySQL 구조로 운영되며, 이 문서는 그 구조를 기준으로 작성한다.

---

## 5. OpenCart를 이번 프로젝트에 맞게 쓰는 방식

이번 프로젝트에서 OpenCart는 쇼핑몰 운영 자체가 목적이 아니다.  
**로그 수집과 비교 실험**이 목적이다.

따라서 설치 후 즉시 필요한 최소 운영 상태는 다음 정도면 충분하다.

- 메인 페이지 접속 가능
- 검색/카테고리/상품 상세 페이지 접속 가능
- 관리자 페이지 접속 가능
- Apache access/security/error 로그 기록 가능
- shipper → MariaDB → export → prepare → stage1 → stage2 흐름 연결 가능

즉, 결제, 실제 메일 발송, 상용 플러그인 설치, 테마 커스터마이징은 이번 단계의 필수 범위가 아니다.

---

## 6. 전체 구축 순서

1. Ubuntu 22.04 Server 준비
2. 시스템 패키지 업데이트
3. Apache2 설치
4. PHP 및 필수 확장 설치
5. Python 3 및 shipper 실행 환경 설치
6. MySQL 설치 및 DB 생성
7. OpenCart 소스 배치
8. OpenCart 설정 파일 준비 및 권한 설정
9. Apache 사이트 설정
10. 프로젝트 표준 security 로그 포맷 적용
11. Apache 문법 검사 및 재시작
12. 브라우저 설치 마무리
13. `install` 폴더 삭제
14. 기본 동작 검증
15. 로그 3종 생성 여부 확인
16. shipper 및 export 연결 확인

---

## 7. 단계별 설치 절차

### 7.1 시스템 업데이트

```bash
sudo apt update
sudo apt upgrade -y
```

필요한 기본 유틸리티를 함께 설치한다.

```bash
sudo apt install -y curl wget unzip ca-certificates gnupg lsb-release
```

점검:

```bash
uname -a
lsb_release -a
ip addr
```

---

### 7.2 Apache2 설치

```bash
sudo apt install -y apache2
```

서비스 활성화 및 시작:

```bash
sudo systemctl enable apache2
sudo systemctl start apache2
sudo systemctl status apache2
```

서버 내부 점검:

```bash
curl -I http://127.0.0.1
```

이 시점에서는 Apache 기본 페이지가 보이면 된다.

---

### 7.3 PHP 및 확장 설치

OpenCart 4.x 구동을 위해 Apache용 PHP와 주요 확장을 설치한다.

```bash
sudo apt install -y \
  php libapache2-mod-php php-cli php-mysql \
  php-curl php-gd php-mbstring php-xml php-zip php-intl php-opcache
```

필요 시 점검:

```bash
php -v
php -m | egrep 'curl|gd|mbstring|xml|zip|intl|mysqli|pdo_mysql'
```

Apache와 PHP 연동 반영을 위해 재시작:

```bash
sudo systemctl restart apache2
```

---

### 7.4 Python 3 및 shipper 실행 환경 설치

OpenCart 서버도 Juice Shop 서버와 마찬가지로 Apache 로그를 DB 서버에 적재해야 하므로, shipper 실행용 Python 환경을 준비한다.

설치:

```bash
sudo apt install -y python3 python3-pip python3-venv
```

확인:

```bash
python3 --version
pip3 --version
```

권장 배치 예시:

- shipper 스크립트: `/opt/apache_log_shipper.py`
- 가상환경(선택): `/opt/apache_log_shipper/.venv`

가상환경을 별도로 둘 경우 예시:

```bash
sudo mkdir -p /opt/apache_log_shipper
cd /opt/apache_log_shipper
python3 -m venv .venv
source .venv/bin/activate
pip install pymysql
deactivate
```

이미 `/opt/apache_log_shipper.py`를 시스템 Python으로 직접 실행하는 표준을 유지한다면, 최소한 `python3`, `python3-pip`, `python3-venv`가 설치되어 있어야 한다.

---

### 7.5 MySQL 설치 및 DB 준비

```bash
sudo apt install -y mysql-server
```

서비스 확인:

```bash
sudo systemctl enable mysql
sudo systemctl start mysql
sudo systemctl status mysql
```

루트로 접속:

```bash
sudo mysql -u root
```

DB와 사용자 생성:

```sql
CREATE DATABASE opencart DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'opencartuser'@'localhost' IDENTIFIED BY 'hoseo2026';
GRANT ALL PRIVILEGES ON opencart.* TO 'opencartuser'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

확인:

```bash
sudo mysql -e "show databases"
sudo mysql -e "select user, host from mysql.user"
```

---

### 7.6 OpenCart 소스 받기

이 문서는 OpenCart 4.x ZIP 파일을 서버에서 직접 받아 배치하는 방식을 기준으로 한다.

예시:

```bash
cd ~
wget https://github.com/opencart/opencart/releases/download/4.1.0.3/opencart-4.1.0.3.zip
```

웹 루트 준비:

```bash
sudo mkdir -p /var/www/opencart
cd /var/www/opencart
sudo unzip ~/opencart-4.1.0.3.zip
```

압축 해제 후 `upload` 내부 내용만 웹 루트로 복사:

```bash
sudo cp -r upload/. /var/www/opencart/
sudo rm -rf upload
sudo rm -f ~/opencart-4.1.0.3.zip
```

---

### 7.7 설정 파일 준비 및 권한 설정

설정 파일 생성:

```bash
sudo cp /var/www/opencart/config-dist.php /var/www/opencart/config.php
sudo cp /var/www/opencart/admin/config-dist.php /var/www/opencart/admin/config.php
```

생성 확인:

```bash
ls -l /var/www/opencart/config.php /var/www/opencart/admin/config.php
```

SEO URL 사용 준비:

```bash
sudo mv /var/www/opencart/htaccess.txt /var/www/opencart/.htaccess 2>/dev/null || true
sudo mv /var/www/opencart/.htaccess.txt /var/www/opencart/.htaccess 2>/dev/null || true
```

권한 설정:

```bash
sudo chown -R www-data:www-data /var/www/opencart
sudo find /var/www/opencart -type d -exec chmod 755 {} \;
sudo find /var/www/opencart -type f -exec chmod 644 {} \;
```

---

### 7.8 Apache 모듈 활성화

OpenCart 동작과 프로젝트 표준 로그 수집을 위해 필요한 모듈을 활성화한다.

```bash
sudo a2enmod rewrite
sudo a2enmod headers
sudo a2enmod logio
sudo a2enmod unique_id
```

재시작:

```bash
sudo systemctl restart apache2
```

---

### 7.9 Apache 사이트 설정

새 사이트 설정 파일 생성:

```bash
sudo nano /etc/apache2/sites-available/opencart.conf
```

아래 내용을 기준으로 저장한다.

```apache
<VirtualHost *:80>
    ServerAdmin admin@example.com
    ServerName 192.168.35.193
    DocumentRoot /var/www/opencart

    <Directory /var/www/opencart>
        AllowOverride All
        Require all granted
    </Directory>

    # 1) error 로그
    ErrorLogFormat "[%{uc}t] [error_link_id:%L] [request_id:%{UNIQUE_ID}e] [module_name:%-m] [log_level:%-l] [src_ip:%a peer_ip:%{c}a] message=%M"
    ErrorLog ${APACHE_LOG_DIR}/app_error.log

    # 2) access 로그
    LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" \"%{Host}i\" %v" access_db_aligned
    CustomLog ${APACHE_LOG_DIR}/app_access.log access_db_aligned

    # 3) security 로그
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

중요한 점:

- 이번 표준에서는 `resp_html_*` 출력은 넣지 않는다.
- 해당 항목은 구현 검토 후 보류되었으므로 OpenCart 환경에도 적용하지 않는다.
- security 로그 포맷은 Juice Shop 쪽과 동일한 기본 구조를 유지한다.

사이트 활성화:

```bash
sudo a2ensite opencart.conf
sudo a2dissite 000-default.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

---

### 7.10 브라우저에서 OpenCart 설치 마무리

브라우저에서 아래 주소로 접속한다.

```text
http://192.168.35.193/
```

설치 과정에서 입력할 예시는 아래와 같다.

#### DB 정보

- Driver: `MySQLi`
- Hostname: `localhost`
- Username: `opencartuser`
- Password: 7.5 단계에서 설정한 비밀번호
- Database: `opencart`
- Port: `3306`
- Prefix: `oc_`

#### 관리자 계정 정보

- Username: `admin` 또는 원하는 관리자 계정명
- Password: 관리자 로그인용 비밀번호
- Email: 본인 이메일

설치가 끝나면 OpenCart의 안내에 따라 `install` 디렉터리를 삭제한다.

```bash
sudo rm -rf /var/www/opencart/install
```

---

## 8. 설치 후 최소 확인 항목

### 8.1 웹 동작 확인

다음이 가능해야 한다.

- 메인 페이지 접속
- 카테고리 또는 상품 페이지 접속
- 검색 요청 발생
- 관리자 로그인 화면 접속

예시:

```bash
curl -I http://127.0.0.1/
curl -I "http://127.0.0.1/index.php?route=product/search"
```

### 8.2 Apache 로그 생성 확인

```bash
ls -l /var/log/apache2/
sudo tail -f /var/log/apache2/app_access.log
sudo tail -f /var/log/apache2/app_security.log
sudo tail -f /var/log/apache2/app_error.log
```

### 8.3 보안 로그 포맷 확인

security log 한 줄에 아래와 같은 key가 보여야 한다.

- `log_time`
- `request_id`
- `method`
- `raw_request`
- `uri`
- `query_string`
- `status_code`
- `response_body_bytes`
- `req_content_type`
- `resp_content_type`
- `user_agent`
- `host`

이 형식은 현재 프로젝트의 shipper / DB / export 파이프라인과 맞물린다.

---

## 9. shipper 연계

OpenCart 서버도 현재 표준 shipper를 그대로 사용할 수 있다.

기본 경로는 아래와 같다.

- access: `/var/log/apache2/app_access.log`
- security: `/var/log/apache2/app_security.log`
- error: `/var/log/apache2/app_error.log`

즉 별도 환경변수 override 없이도, 같은 `apache_log_shipper.py`를 적용하기 쉽다.

점검 예시:

```bash
sudo python3 /opt/apache_log_shipper.py --test-db
sudo python3 /opt/apache_log_shipper.py --once
```

DB에서 최근 적재 확인:

```sql
SELECT id, log_time, request_id, uri, status_code, resp_content_type
FROM apache_security_logs
ORDER BY id DESC
LIMIT 20;
```

중요한 운영 메모:

- OpenCart 서버 IP `192.168.35.193`도 DB 서버의 적재 허용 대상으로 반영되어야 한다.
- 즉 `log_writer@192.168.35.193` 계정 또는 동등한 허용 범위가 필요하다.

---

## 10. OpenCart 환경에서 먼저 수집할 정상 요청

비교 실험의 첫 단계에서는 공격보다 먼저 **정상 요청 기준선**을 쌓는 것이 좋다.

권장 시나리오:

1. 메인 페이지 접속
2. 카테고리 페이지 이동
3. 검색 사용
4. 상품 상세 페이지 조회
5. 로그인/회원가입 화면 접속
6. 장바구니 추가 시도
7. 관리자 로그인 화면 접속

이 요청들은 Juice Shop과 비교할 때 다음 항목에 유용하다.

- 정상 검색 요청의 형태
- 정적 리소스 비중
- 관리자 경로 접근 시 응답 특성
- 후보 밖 탐색성 요청과 정상 탐색의 경계

---

## 11. Juice Shop과 병행 운영 시 비교 포인트

OpenCart를 구축한 뒤에는 같은 파이프라인으로 아래를 비교할 수 있다.

### 11.1 정상 요청 비교

- 검색 요청이 얼마나 benign / normal_search 성격으로 보이는가
- 상품 페이지/정적 리소스 비중은 어떤가
- 관리자 경로의 정상/비정상 요청이 어떻게 구분되는가

### 11.2 탐색성 요청 비교

- `/admin`, `/admin_99`, `/robots.txt`, `/sitemap.xml` 같은 요청이 어떻게 보이는가
- low-signal recon 분포가 두 앱에서 어떻게 다른가

### 11.3 공격성 요청 비교

- 같은 SQLi/XSS/path traversal 시도가 두 앱에서 어떤 응답으로 나타나는가
- stage1 분류와 stage2 보고서 서술이 어떻게 달라지는가
- 의도적 취약 앱과 일반 쇼핑몰형 앱에서 “과장 없는 보수 해석”이 어떻게 달라지는가

---

## 12. 현 단계에서 하지 않는 것

이번 문서 범위에서 아래는 필수가 아니다.

- HTTPS 적용
- 메일 발송 설정
- 결제 모듈 실사용 설정
- 실제 운영용 재고/주문/배송 설정
- 상용 테마/확장 설치
- `resp_html_*` 기반 fallback fingerprint 구현

즉, 이번 단계는 **비교 실험에 필요한 최소 OpenCart 환경**까지만 구축한다.

---

## 13. 자주 틀리는 부분

### 13.1 `upload` 폴더째 웹 루트로 두는 경우

OpenCart ZIP을 풀면 `upload` 디렉터리가 생기는데, 이 디렉터리 자체를 DocumentRoot로 두기보다 **`upload` 안의 실제 파일을 `/var/www/opencart`에 복사**하는 것이 안전하다.

### 13.2 `config.php`와 `admin/config.php`를 안 만드는 경우

설치 화면에서 Missing 오류가 날 수 있다.

```bash
sudo cp /var/www/opencart/config-dist.php /var/www/opencart/config.php
sudo cp /var/www/opencart/admin/config-dist.php /var/www/opencart/admin/config.php
```

### 13.3 `.htaccess`를 활성화하지 않는 경우

SEO URL 사용 여부와 관계없이, OpenCart 동작 안정성을 위해 `.htaccess` 파일 상태를 미리 확인하는 편이 좋다.

### 13.4 Apache 로그 파일명을 제각각 쓰는 경우

이번 프로젝트에서는 shipper 기본값과 맞추기 위해 아래 이름을 유지한다.

- `app_access.log`
- `app_security.log`
- `app_error.log`

### 13.5 Juice Shop과 같은 서버에서 같은 포트에 바로 덮는 경우

이번 문서는 **별도 VM / 별도 서버 IP (`192.168.35.193`)**를 권장한다.  
기존 Juice Shop 환경을 그대로 유지하려면 OpenCart를 다른 서버에 두는 편이 더 안전하다.

### 13.6 Python을 설치하지 않고 shipper부터 실행하려는 경우

OpenCart 서버도 Apache 로그를 DB로 적재해야 하므로, 최소한 아래는 미리 설치되어 있어야 한다.

- `python3`
- `python3-pip`
- `python3-venv`

---

## 14. 이 문서 다음 단계

OpenCart 설치가 끝났다면 다음 순서로 진행한다.

1. Apache 로그 3종 생성 확인
2. shipper DB 적재 확인
3. security export 생성
4. `prepare_llm_input.py` 실행
5. `llm_stage1_classifier.py` 실행
6. `llm_stage2_reporter.py` 실행
7. Juice Shop 결과와 비교

즉, OpenCart는 단독 구축으로 끝나는 것이 아니라, **현재 프로젝트의 전체 로그 분석 파이프라인에 그대로 연결**되어야 한다.

---

## 15. 요약

이번 OpenCart 구축은 기존 Juice Shop 환경을 대체하는 것이 아니라, **현실적인 쇼핑몰형 웹 애플리케이션을 추가하여 비교 실험 범위를 넓히기 위한 작업**이다.

핵심은 다음과 같다.

1. OpenCart는 별도 Ubuntu 22.04 Server / 별도 VM에 구축한다.
2. OpenCart 서버 IP는 `192.168.35.193`으로 고정한다.
3. Apache + PHP + MySQL + Python 구조로 설치한다.
4. Apache 로그 3종은 프로젝트 표준(`app_access.log`, `app_security.log`, `app_error.log`)에 맞춘다.
5. shipper / DB / export / LLM 분석 파이프라인은 기존 구조를 그대로 재사용한다.
6. Juice Shop과 OpenCart를 병행 운영하면서 같은 요청에 대한 로그와 보고서 차이를 비교한다.

한 문장으로 요약하면:

> OpenCart는 Juice Shop을 대체하는 실습 앱이 아니라, 현실적인 쇼핑몰형 웹 애플리케이션 로그를 비교하기 위한 병행 실험 환경으로 구축한다.