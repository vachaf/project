# 02_Juice_shop_환경_구축_및_설치

- 문서 상태: 구축문서
- 버전: v1.2
- 작성일: 2026-04-09

## 1. 목적

Ubuntu 22.04 Server에서 Apache2와 Docker를 사용해 OWASP Juice Shop 실험 환경을 재현하고, 현재 로그 파이프라인이 기대하는 access/security/error 로그를 생성하는 절차를 정리한다.

## 2. 최종 구성

- OS: Ubuntu 22.04 Server
- 웹서버: Apache2
- 앱: OWASP Juice Shop
- 실행 방식: Docker
- 외부 접속: `http://서버IP/`
- 내부 앱 바인딩: `127.0.0.1:3000`
- 로그 파일:
  - `/var/log/apache2/app_access.log`
  - `/var/log/apache2/app_security.log`
  - `/var/log/apache2/app_error.log`

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
2. Apache 설치
3. Docker 설치
4. Juice Shop 컨테이너 실행
5. Apache 모듈 활성화
6. Apache VirtualHost 작성
7. 사이트 활성화
8. 브라우저 접속 검증
9. 로그 3종 생성 확인

## 5. 시스템 업데이트

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y curl wget unzip ca-certificates gnupg lsb-release
```

## 6. Apache 설치

```bash
sudo apt install -y apache2
sudo systemctl enable apache2
sudo systemctl start apache2
sudo systemctl status apache2
curl -I http://127.0.0.1
```

기대 결과:

- Apache 기본 페이지에 대한 `HTTP/1.1 200 OK` 응답

## 7. Docker 설치

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

## 8. Juice Shop 실행

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

## 9. Apache 모듈 활성화

현재 로그 포맷과 Reverse Proxy 구성을 위해 아래 모듈을 활성화한다.

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
sudo a2enmod logio
sudo a2enmod unique_id
sudo systemctl restart apache2
```

## 10. Apache 사이트 설정

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

## 11. 사이트 활성화

```bash
sudo a2dissite 000-default.conf
sudo a2ensite juice-shop.conf
sudo apache2ctl configtest
sudo systemctl restart apache2
sudo systemctl status apache2
```

기대 결과:

- `Syntax OK`

## 12. 브라우저 접속 검증

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

## 13. 로그 파일 생성 확인

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

## 14. security 로그 포맷 확인

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

## 15. 설치 후 최소 점검

- `docker ps` 에서 `juice-shop` 확인
- `curl -I http://127.0.0.1:3000` 응답 확인
- `curl -I http://127.0.0.1/` 응답 확인
- 브라우저에서 Juice Shop 화면 확인
- `apache2ctl configtest` 가 `Syntax OK`
- `app_access.log`, `app_security.log` 생성 확인

## 16. 다음 단계

Juice Shop 환경 구축 후 진행 순서:

1. DB 서버에 `web_logs` 구축
2. `apache_log_shipper.py` 배치 및 DB 연결 확인
3. `security` export 실행
4. `prepare_llm_input.py`
5. `llm_stage1_classifier.py`
6. `llm_stage2_reporter.py`
