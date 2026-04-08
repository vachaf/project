# 02_Juice_shop_환경_구축_및_설치

- 문서 상태: 통합본
- 버전: v1.1
- 작성일: 2026-04-02
- 적용 대상: Ubuntu 22.04 Server 기반 OWASP Juice Shop 실습 환경 구축 문서
- 연계 문서:
  - `01_프로젝트_방향과_실험대상.md`
  - `03_로그_표준과_DB_구조.md`
  - `04_로그_적재_및_운영.md`
  - `05_Export_LLM_분석_전략.md`

---
## 1. 문서 목적

이 문서는 **Ubuntu 22.04 Server 환경에서 Apache2와 Docker를 사용해 OWASP Juice Shop 실습 환경을 구축하는 절차**를 정리한 설치 문서다.

이번 프로젝트의 목적은 단순한 웹서비스 설치가 아니라, **Apache를 중심으로 웹 요청을 수집하고, 이후 공격 탐지·로그 분석 실험으로 확장 가능한 기반 환경을 만드는 것**이다.

따라서 이 문서는 다음 항목을 한 번에 다룬다.

- Ubuntu 22.04 Server 준비
- Apache2 설치
- Docker 설치
- OWASP Juice Shop 컨테이너 실행
- Apache Reverse Proxy 설정
- Apache 로그 파일 생성 확인
- 기본 동작 검증

반면 아래 항목은 이 문서의 직접 범위에서 제외한다.

- MariaDB 테이블 생성 상세
- Python shipper 배포와 서비스 등록 상세
- JSON export 및 LLM 전달 상세
- 공격 탐지 규칙 상세

즉, 이 문서는 **실험 환경을 실제로 띄우는 설치 절차서**다.

---

## 2. 대상 환경

기준 환경은 아래와 같다.

- 운영체제: **Ubuntu 22.04 LTS Server**
- 웹서버: **Apache2**
- 애플리케이션: **OWASP Juice Shop**
- 실행 방식: **Docker 컨테이너**
- 접근 구조: **Apache Reverse Proxy → Juice Shop**
- 기본 접속 주소: `http://서버IP/`
- 내부 애플리케이션 바인딩: `127.0.0.1:3000`

구조는 다음과 같다.

```text
브라우저 / 실험 스크립트 / 점검 도구
                ↓
          Apache2 (:80 또는 :443)
                ↓  Reverse Proxy
      OWASP Juice Shop (127.0.0.1:3000)
```

이 구조를 사용하는 이유는 다음과 같다.

1. 외부 요청이 모두 Apache를 먼저 통과하므로 **로그 수집 지점을 일원화**할 수 있다.
2. Juice Shop은 Docker로 실행하기 쉬워 **재현성과 복구성이 높다**.
3. Apache는 Reverse Proxy, CustomLog, ErrorLogFormat 확장이 쉬워 **후속 로그 수집 설계와 잘 맞는다**.
4. Juice Shop을 서버 외부에 직접 노출하지 않고, Apache 뒤에 두어 **구조를 더 명확하게 분리**할 수 있다.

---

## 3. 사전 준비 사항

### 3.1 권장 가상머신 사양

- CPU: 2코어 이상
- RAM: 4GB 이상
- 디스크: 20GB 이상
- 네트워크: 브리지 또는 NAT + 포트포워딩

### 3.2 설치 이미지

가상머신에 서버를 설치할 목적이라면 다음 이미지를 기준으로 한다.

- `ubuntu-22.04.5-live-server-amd64.iso`

Desktop ISO가 아니라 **Server ISO**를 사용하는 것이 적절하다.

### 3.3 기본 전제

- 서버에 관리자 권한 계정으로 로그인할 수 있어야 한다.
- Ubuntu 패키지 설치를 위해 인터넷 연결이 가능해야 한다.
- Windows 또는 다른 클라이언트 PC에서 서버 IP로 접속할 수 있어야 한다.

---

## 4. 전체 구축 절차

전체 순서는 아래와 같다.

1. Ubuntu 22.04 Server 준비
2. 기본 패키지 업데이트
3. Apache2 설치 및 동작 확인
4. Docker 설치 및 동작 확인
5. OWASP Juice Shop 컨테이너 실행
6. Apache 모듈 활성화
7. Apache 사이트 설정 적용
8. Apache 기본 사이트 비활성화 및 새 사이트 활성화
9. 설정 문법 검사 및 재시작
10. 브라우저 접속 검증
11. 로그 파일 생성 여부 확인

---

## 5. 단계별 설치 절차

### 5.1 시스템 업데이트 및 기본 유틸리티 설치

먼저 패키지 목록과 기본 패키지를 정리한다.

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y curl wget unzip ca-certificates gnupg lsb-release
```

설치 후 시스템을 한 번 점검한다.

```bash
uname -a
lsb_release -a
ip addr
```

---

### 5.2 Apache2 설치

Apache2를 설치한다.

```bash
sudo apt install -y apache2
```

서비스를 활성화하고 시작한다.

```bash
sudo systemctl enable apache2
sudo systemctl start apache2
sudo systemctl status apache2
```

서버 내부에서 HTTP 응답이 오는지 확인한다.

```bash
curl -I http://127.0.0.1
```

다른 PC 브라우저에서는 아래 주소로 접속한다.

```text
http://서버IP/
```

이 시점에서는 Apache 기본 페이지가 보이면 정상이다.

---

### 5.3 Docker 설치

Juice Shop은 Docker 컨테이너로 실행하는 방식이 가장 간단하다.

```bash
sudo apt install -y docker.io
```

Docker 서비스를 활성화한다.

```bash
sudo systemctl enable docker
sudo systemctl start docker
sudo systemctl status docker
```

현재 계정으로 Docker 명령을 사용하고 싶다면 아래를 실행한 뒤 다시 로그인한다.

```bash
sudo usermod -aG docker $USER
```

바로 실습할 때는 `sudo docker ...` 형식으로 실행해도 된다.

Docker 동작을 확인한다.

```bash
sudo docker ps
sudo docker version
```

---

### 5.4 OWASP Juice Shop 실행

이미지를 내려받고 컨테이너를 실행한다.

```bash
sudo docker pull bkimminich/juice-shop:v19.2.1
sudo docker run -d \
  --name juice-shop \
  -p 127.0.0.1:3000:3000 \
  --restart unless-stopped \
  bkimminich/juice-shop:v19.2.1
```

상태를 확인한다.

```bash
sudo docker ps
curl -I http://127.0.0.1:3000
```

이 설정의 의미는 다음과 같다.

- Juice Shop은 **서버 내부 루프백 주소 `127.0.0.1:3000`** 에만 바인딩된다.
- 외부 클라이언트는 Juice Shop 컨테이너에 직접 접속하지 않는다.
- 외부 요청은 Apache가 받고, 내부적으로 Juice Shop으로 전달한다.
- 따라서 외부에서는 `http://서버IP:3000/` 이 아니라 `http://서버IP/` 로 접속해야 한다.

애플리케이션 로그가 필요하면 다음 명령으로 확인할 수 있다.

```bash
sudo docker logs juice-shop
sudo docker logs -f juice-shop
```

---

### 5.5 Apache 모듈 활성화

Apache를 Reverse Proxy와 확장 로그 수집에 맞게 사용하려면 필요한 모듈을 활성화해야 한다.

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
sudo a2enmod logio
sudo a2enmod unique_id
```

필요 시 `rewrite`를 추가로 사용할 수 있지만, 현재 표준 구성의 필수 항목은 아니다.

모듈 활성화 후 Apache를 재시작한다.

```bash
sudo systemctl restart apache2
```

---

### 5.6 Apache 사이트 설정 파일 작성

새 사이트 설정 파일을 만든다.

```bash
sudo nano /etc/apache2/sites-available/juice-shop.conf
```

아래 내용을 기준으로 저장한다.

```apache
<VirtualHost *:80>
    ServerAdmin admin@example.com
    ServerName localhost

    ProxyRequests Off
    ProxyPass        / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/

    # 프록시 또는 로드밸런서가 Apache 앞단에 있을 때만 사용
    # RemoteIPHeader X-Forwarded-For
    # RemoteIPTrustedProxy 127.0.0.1

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
host=\"%{Host}i\" x_forwarded_for=\"%{X-Forwarded-For}i\" \
resp_html_norm_fingerprint=\"%{resp_html_norm_fingerprint}n\" \
resp_html_fingerprint_version=\"%{resp_html_fingerprint_version}n\" \
resp_html_baseline_name=\"%{resp_html_baseline_name}n\" \
resp_html_baseline_match=\"%{resp_html_baseline_match}n\" \
resp_html_baseline_confidence=\"%{resp_html_baseline_confidence}n\" \
resp_html_features_json=\"%{resp_html_features_json}n\"" security_db_aligned

    CustomLog ${APACHE_LOG_DIR}/app_security.log security_db_aligned
</VirtualHost>
```

이 설정의 핵심은 다음과 같다.

- `app_access.log`: 사람이 읽기 쉬운 기본 접근 로그
- `app_security.log`: 탐지·분류용 확장 key=value 로그
- `app_error.log`: 프록시 및 서버 오류 분석용 로그
- 현재 표준에서는 `request_id` 를 security/error 로그에서 우선 사용한다.
- access 로그는 기본 운영 확인용이므로 현재 표준 포맷에는 `request_id` 를 넣지 않는다.
- `UNIQUE_ID`: 요청 상관분석용 기본 식별자
- `%L`: error 로그 연계용 보조 식별자
- `LogIOTrackTTFB ON`: I/O 바이트와 TTFB 수집 활성화
- + **추가한거 resp_html 설명 필요함**

---

### 5.7 사이트 활성화 및 기본 사이트 비활성화

기본 사이트를 비활성화하고, 새 사이트를 활성화한다.

```bash
sudo a2dissite 000-default.conf
sudo a2ensite juice-shop.conf
```

설정 문법을 검사한다.

```bash
sudo apache2ctl configtest
```

정상이라면 Apache를 다시 시작한다.

```bash
sudo systemctl restart apache2
sudo systemctl status apache2
```

---

### 5.8 접속 검증

다음 순서로 점검한다.

1. 서버 내부에서 Apache 프록시 응답 확인

```bash
curl -I http://127.0.0.1/
```

2. 클라이언트 PC 브라우저에서 아래 주소 접속

```text
http://서버IP/
```

3. Apache 기본 페이지가 아니라 **OWASP Juice Shop 화면**이 보이는지 확인

4. 컨테이너와 Apache가 모두 실행 중인지 확인

```bash
sudo docker ps
sudo systemctl status apache2
```

---

### 5.9 로그 파일 생성 확인

Apache 설정이 적용되면 아래 로그 파일이 생성되어야 한다.

```text
/var/log/apache2/app_access.log
/var/log/apache2/app_security.log
/var/log/apache2/app_error.log
```

확인 명령 예시는 다음과 같다.

```bash
ls -l /var/log/apache2/
sudo tail -f /var/log/apache2/app_access.log
sudo tail -f /var/log/apache2/app_security.log
sudo tail -f /var/log/apache2/app_error.log
```

브라우저 새로고침 또는 간단한 요청을 발생시킨 뒤 access/security 로그가 증가하는지 확인한다.

예시:

```bash
curl -I http://127.0.0.1/
```

---

## 6. 설치 후 핵심 체크포인트

설치가 끝난 뒤 아래 항목을 점검한다.

- Ubuntu 22.04 Server가 정상 부팅되는가
- Apache2 서비스가 실행 중인가
- Docker 서비스가 실행 중인가
- `docker ps` 에서 `juice-shop` 컨테이너가 보이는가
- `127.0.0.1:3000` 에서 Juice Shop 응답이 오는가
- `http://서버IP/` 접속 시 Juice Shop 화면이 열리는가
- `apache2ctl configtest` 결과가 `Syntax OK` 인가
- `app_access.log`, `app_security.log`, `app_error.log` 파일이 생성되는가
- 테스트 요청 시 access/security 로그가 실제로 증가하는가

---

## 7. 자주 틀리는 부분

### 7.1 `:3000` 으로 외부 접속하려는 경우

현재 표준 구성은 Juice Shop을 `127.0.0.1:3000` 에만 바인딩한다.
따라서 외부에서는 `http://서버IP:3000/` 로 접속하지 않는다.

정상 접속 주소는 아래와 같다.

```text
http://서버IP/
```

### 7.2 Apache 기본 페이지가 계속 보이는 경우

아래 항목을 확인한다.

- `000-default.conf` 를 비활성화했는가
- `juice-shop.conf` 를 활성화했는가
- `apache2ctl configtest` 를 통과했는가
- Apache를 재시작했는가

### 7.3 `app_security.log` 가 생성되지 않는 경우

주요 확인 항목은 다음과 같다.

- `logio` 모듈이 활성화되었는가
- `CustomLog ${APACHE_LOG_DIR}/app_security.log security_db_aligned` 가 들어갔는가
- Apache 재시작 후 문법 오류가 없는가

### 7.4 로그 파일명이 문서마다 다르게 적힌 경우

과거 문서에는 `juice_shop_access.log`, `juice_shop_security.log`, `juice_shop_error.log` 형식이 보일 수 있다.
현재 통합 기준에서는 아래 파일명으로 통일한다.

- `app_access.log`
- `app_security.log`
- `app_error.log`

이유는 후속 DB 구조 및 shipper 설정과의 정렬성을 높이기 위해서다.

### 7.5 Apache 모듈 목록이 문서마다 다른 경우

현재 설치 표준은 아래 모듈을 기준으로 한다.

- `proxy`
- `proxy_http`
- `headers`
- `logio`
- `unique_id`

`rewrite` 는 필요 시 추가할 수 있지만, 본 실습 환경의 핵심 필수 목록은 아니다.

---

## 8. 이 문서 다음 단계

환경 구축이 끝났다면 다음 순서로 진행한다.

1. Apache 로그 3종 포맷과 DB 컬럼 정렬 기준 확인
2. MariaDB `web_logs` 생성 및 3테이블 생성
3. Python shipper를 이용한 로그 적재
4. JSON export 및 KST 기준 조회
5. LLM 분석용 노이즈 필터링과 요약 전략 적용

즉, 이 문서는 **환경을 띄우는 단계**까지를 다루고, 이후 적재·분석 단계는 다음 문서로 넘긴다.

---

## 9. 요약

이번 실습 환경은 **Ubuntu 22.04 Server + Apache2 + Docker + OWASP Juice Shop** 조합을 기준으로 구축한다.

외부 요청은 Apache가 먼저 받고, 내부적으로 `127.0.0.1:3000` 에서 실행되는 Juice Shop으로 전달한다. 이 구조를 통해 웹 애플리케이션을 직접 외부에 노출하지 않으면서, Apache를 중심으로 access, security, error 로그를 분리 수집할 수 있다.

설치 단계에서 가장 중요한 것은 다음 네 가지다.

1. Juice Shop을 Docker로 내부 바인딩하여 실행할 것
2. Apache Reverse Proxy를 정상 적용할 것
3. `logio`, `unique_id` 를 포함한 필수 모듈을 활성화할 것
4. `app_access.log`, `app_security.log`, `app_error.log` 3종 로그가 실제 생성되는지 확인할 것
