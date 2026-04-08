# OWASP Juice Shop 설치 가이드

## 1. 목적

이 문서는 Ubuntu 22.04 Server 환경에서 Apache2와 Docker를 사용해 OWASP Juice Shop을 설치하고, Windows 브라우저에서 접속 가능한 상태까지 만드는 절차를 정리한 설치 가이드이다.

---

## 2. 실습 환경 예시

- 운영체제: Ubuntu 22.04 LTS Server
- 웹서버: Apache2
- 애플리케이션: OWASP Juice Shop
- 실행 방식: Docker
- 접속 방식: Apache Reverse Proxy를 통해 `http://서버IP/` 로 접속

---

## 3. 전체 절차

1. Ubuntu 22.04 가상머신 준비
2. 기본 패키지 업데이트
3. Apache2 설치
4. Docker 설치
5. OWASP Juice Shop 컨테이너 실행
6. Apache Reverse Proxy 설정
7. 브라우저 접속 확인

---

## 4. 단계별 설치 절차

## 4-1. Ubuntu 22.04 가상머신 준비

VirtualBox, VMware 등의 가상화 프로그램에 Ubuntu 22.04 Server를 설치한다.

권장 사양은 다음과 같다.

- CPU: 2코어 이상
- RAM: 4GB 이상
- 디스크: 20GB 이상
- 네트워크: 브리지 또는 NAT + 포트포워딩

설치 후 서버에 로그인한 뒤 시스템을 업데이트한다.

```bash
sudo apt update
sudo apt upgrade -y
```

기본 유틸리티도 함께 설치한다.

```bash
sudo apt install -y curl wget unzip ca-certificates gnupg lsb-release
```

---

## 4-2. Apache2 설치

Apache2를 설치한다.

```bash
sudo apt install -y apache2
```

서비스를 시작하고 자동 시작을 설정한다.

```bash
sudo systemctl enable apache2
sudo systemctl start apache2
sudo systemctl status apache2
```

서버 내부에서 정상 동작 여부를 확인한다.

```bash
curl -I http://127.0.0.1
```

Windows 브라우저에서는 아래 주소로 접속해 Apache 기본 페이지가 보이면 정상이다.

```text
http://서버IP/
```

---

## 4-3. Docker 설치

Juice Shop은 Docker로 실행하는 방식이 가장 간단하다.

```bash
sudo apt install -y docker.io
```

서비스를 활성화한다.

```bash
sudo systemctl enable docker
sudo systemctl start docker
sudo systemctl status docker
```

현재 계정으로 Docker를 사용하고 싶다면 아래를 실행한 뒤 다시 로그인한다.

```bash
sudo usermod -aG docker $USER
```

바로 실습할 때는 `sudo docker ...` 형식으로 실행해도 된다.

---

## 4-4. OWASP Juice Shop 실행

Juice Shop 이미지를 내려받고 컨테이너를 실행한다.

```bash
sudo docker pull bkimminich/juice-shop:v19.2.1
sudo docker run -d \
  --name juice-shop \
  -p 127.0.0.1:3000:3000 \
  --restart unless-stopped \
  bkimminich/juice-shop:v19.2.1
```

실행 상태를 확인한다.

```bash
sudo docker ps
curl -I http://127.0.0.1:3000
```

설명:

* `127.0.0.1:3000:3000` 으로 바인딩했기 때문에 Juice Shop은 서버 내부에서만 직접 접근된다.
* 외부에서는 Apache가 요청을 받아 내부의 Juice Shop으로 전달한다.
* 따라서 Windows에서는 `http://서버IP:3000/` 이 아니라 `http://서버IP/` 로 접속한다.

---

## 4-5. Apache Reverse Proxy 모듈 활성화

Apache가 앞단에서 요청을 받고 Juice Shop으로 전달하도록 필요한 모듈을 활성화한다.

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
sudo a2enmod rewrite
sudo a2enmod unique_id
```

적용한다.

```bash
sudo systemctl restart apache2
```

---

## 4-6. Apache 사이트 설정

새 사이트 설정 파일을 만든다.

```bash
sudo nano /etc/apache2/sites-available/juice-shop.conf
```

아래 내용을 입력한다.

```apache
<VirtualHost *:80>
    ServerAdmin admin@example.com
    ServerName localhost

    ProxyRequests Off
    ProxyPass        / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/

    # 사람이 보기 쉬운 에러 로그
    ErrorLogFormat "[%{uc}t] [errid:%L] [reqid:%{UNIQUE_ID}e] [%-m:%-l] [src:%a peer:%{c}a] %M"
    ErrorLog ${APACHE_LOG_DIR}/juice_shop_error.log

    # 사람이 익숙한 표준형
    LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
    CustomLog ${APACHE_LOG_DIR}/juice_shop_access.log combined

    # I/O 및 TTFB 수집
    LogIOTrackTTFB ON

    # 분류/탐지용 key=value 로그
    LogFormat "ts=%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t reqid=%{UNIQUE_ID}e errid=%L vhost=%v src=%a peer=%{c}a method=%m raw_req=\"%r\" uri=\"%U\" qs=\"%q\" proto=%H status=%>s resp_body_bytes=%B in_bytes=%I out_bytes=%O total_bytes=%S dur_us=%D ttfb_us=%^FB keepalive=%k conn=%X req_ct=\"%{Content-Type}i\" req_cl=\"%{Content-Length}i\" resp_ct=\"%{Content-Type}o\" referer=\"%{Referer}i\" ua=\"%{User-Agent}i\" host=\"%{Host}i\" xff=\"%{X-Forwarded-For}i\"" security_ext

    CustomLog ${APACHE_LOG_DIR}/juice_shop_security.log security_ext
</VirtualHost>
```

다음 설정

```bash
sudo a2ensite juice-shop.conf
sudo a2dissite 000-default.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

`Syntax OK` 가 나오면 정상이다.

---

## 4-7. 동작 확인

서버 내부에서 먼저 확인한다.

```bash
curl -I http://127.0.0.1:3000
curl -I http://localhost
```

서비스 상태도 확인한다.

```bash
sudo systemctl status apache2
sudo docker ps
```

Windows 브라우저에서는 아래 주소로 접속한다.

```text
http://서버IP/
```

정상이라면 OWASP Juice Shop 화면이 열린다.

---

## 5. 설치 완료 확인 체크리스트

아래 항목이 충족되면 설치가 완료된 것이다.

* Ubuntu 22.04 가상머신이 정상 부팅된다.
* Apache2 서비스가 실행 중이다.
* Docker 서비스가 실행 중이다.
* `sudo docker ps` 에서 `juice-shop` 컨테이너가 보인다.
* `curl -I http://127.0.0.1:3000` 이 정상 응답한다.
* `curl -I http://localhost` 가 정상 응답한다.
* Windows 브라우저에서 `http://서버IP/` 접속 시 Juice Shop 화면이 보인다.

---

## 6. 자주 쓰는 관리 명령

### 컨테이너 상태 확인

```bash
sudo docker ps
sudo docker logs juice-shop --tail 50
```

### 컨테이너 재시작

```bash
sudo docker restart juice-shop
```

### 컨테이너 중지

```bash
sudo docker stop juice-shop
```

### 컨테이너 삭제 후 다시 실행

```bash
sudo docker rm -f juice-shop
sudo docker run -d \
  --name juice-shop \
  -p 127.0.0.1:3000:3000 \
  --restart unless-stopped \
  bkimminich/juice-shop:v19.2.1
```

### Apache 설정 테스트

```bash
sudo apache2ctl configtest
```

### Apache 재시작 / 리로드

```bash
sudo systemctl restart apache2
sudo systemctl reload apache2
```

---

## 7. 참고 메모

* Juice Shop은 학습용 취약 애플리케이션이므로 외부 인터넷에 그대로 공개하지 않는 것이 좋다.
* 실습은 반드시 본인 소유 또는 허가된 환경에서만 수행한다.
* Windows에서 직접 `서버IP:3000` 으로 접속하지 말고 `서버IP` 로 접속한다.
* 서버 IP가 바뀌는 환경이라면 `ip addr` 명령으로 현재 IP를 먼저 확인한다.