# OWASP Juice Shop 기준 로그 수집 전략 (수정본)

## 1. 문서 목적
이 문서는 **Ubuntu 22.04 + Apache2(리버스 프록시) + OWASP Juice Shop** 환경에서,
**웹 공격 탐지와 웹 로그 기반 분류 실험**을 위해 어떤 로그를 어떻게 수집할지 정리한 문서이다.

이번 프로젝트의 핵심 목적은 단순한 쇼핑몰 운영이 아니라,
정상 요청과 공격성 요청을 함께 발생시켜 **Apache 중심의 로그를 수집하고**, 그 로그를 바탕으로 공격을 탐지·분류하는 것이다.

따라서 이 문서는 **Juice Shop을 실험 대상 애플리케이션으로 사용하는 경우의 로그 수집 전략**만 다룬다.

---

## 2. 대상 환경
기준 환경은 아래와 같다.

- **운영체제**: Ubuntu 22.04 LTS
- **앞단 웹서버**: Apache2
- **백엔드 애플리케이션**: OWASP Juice Shop
- **실행 방식**: Docker 컨테이너
- **로그 수집의 중심 지점**: Apache

구조는 다음과 같다.

```text
브라우저 / 점검 도구 / 실험 스크립트 / 분류 머신
                ↓
          Apache2 (:80 또는 :443)
                ↓  Reverse Proxy
      OWASP Juice Shop (127.0.0.1:3000)
```

이 구조를 사용하는 이유는 다음과 같다.

1. 외부 요청이 모두 Apache를 먼저 통과하므로 **로그 수집 지점을 일원화**할 수 있다.
2. Juice Shop은 공격 재현성이 높아 **공격성 로그 확보에 유리**하다.
3. Apache는 `CustomLog`, `LogFormat`, `ErrorLogFormat` 등을 통해 **탐지용 로그 형식을 세밀하게 설계**할 수 있다.
4. 나중에 WAF, 포렌식 로그, 추가 보안 로그로 **확장하기 쉽다**.

---

## 3. 왜 기본 combined 로그만으로는 부족한가
Apache의 `combined` 로그는 운영 확인용으로는 유용하다.
보통 아래 정보를 포함한다.

- 클라이언트 주소
- 시간
- 요청 라인
- 상태 코드
- 응답 바이트 수
- Referer
- User-Agent

하지만 공격 탐지와 분류 관점에서는 다음 정보가 부족할 수 있다.

- **모든 요청에 안정적으로 부여되는 고유 ID**
- 가상호스트 정보
- 실제 연결 IP와 원본 IP의 구분
- 요청 처리 시간
- 실제 수신/송신 바이트 수
- 에러 로그와의 연결 키
- 보안 분석용 추가 헤더
- 포렌식/감사 로그와의 연동 정보

즉, `combined`만으로는 “이상한 요청이 있었다” 수준은 볼 수 있어도,
**스캐닝, 인증 시도, XSS, SQL Injection, 경로 탐색, 비정상 대량 요청** 등을 안정적으로 분류하기에는 정보가 부족하다.

---

## 4. 로그 수집의 기본 원칙

### 4.1 로그를 한 종류로 몰아넣지 않는다
실험용 로그는 역할에 따라 분리하는 것이 좋다.

1. **기본 접근 로그**: 전체 요청을 가볍게 남기는 로그
2. **확장 보안 로그**: 탐지·분류에 필요한 필드를 추가한 분석용 로그
3. **에러 로그**: 프록시 오류, 백엔드 연결 문제, 서버 오류를 남기는 로그
4. **애플리케이션 로그**: Juice Shop 자체 실행 로그
5. **선택적 정밀 로그**: 포렌식 로그, WAF audit log 등

이렇게 나누면 운영 점검과 보안 분석을 분리할 수 있고,
수집 비용이 큰 로그는 나중에 필요할 때만 추가할 수 있다.

### 4.2 기본 로그는 유지하고, 분석용 로그를 따로 추가한다
기존의 기본 access log를 버리기보다,
**운영용 로그는 유지하고 탐지용 로그를 별도 파일로 추가**하는 방식이 가장 안전하다.

이 방식의 장점은 다음과 같다.

- 설정 오류 위험이 낮다.
- 기존 실습 흐름을 유지하기 쉽다.
- 운영 점검과 연구용 데이터셋 생성을 분리할 수 있다.
- 나중에 분석 파이프라인을 따로 붙이기 쉽다.

### 4.3 Apache 로그와 Juice Shop 로그는 서로 대체되지 않는다
Apache 로그는 **입구 기록**이고,
Juice Shop 애플리케이션 로그는 **백엔드 내부 실행 기록**이다.

즉, 둘은 같은 로그가 아니라 역할이 다르다.

- Apache access/error log: 누가 어떤 요청을 보냈고, 프록시 계층에서 무슨 일이 있었는가
- Juice Shop log: 애플리케이션 내부에서 어떤 메시지와 오류가 발생했는가

### 4.4 요청 식별자는 두 종류로 구분한다
분석용 로그에서는 **하나의 요청을 식별하는 키**와,
**에러 로그와 연결하는 키**를 분리하는 편이 낫다.

- **주 요청 식별자**: `mod_unique_id` 기반 `UNIQUE_ID`
- **에러 연계 식별자**: `%L`

`%L`은 에러 로그와 access log를 연결할 때 유용하지만,
해당 요청에서 에러 로그가 전혀 없으면 값이 비어 있거나 `-`가 될 수 있다.
따라서 **모든 요청에 안정적으로 남는 주 키**로는 `UNIQUE_ID`를 쓰고,
`%L`은 **error log와의 상호 연계용 보조 키**로 두는 것이 적절하다.

---

## 5. 어떤 로그를 수집해야 하는가

### 5.1 Apache 접근 로그
가장 기본이 되는 로그다.
모든 정상 요청과 공격성 요청이 먼저 여기에 남는다.

이 로그에서 확인할 수 있는 대표 항목은 다음과 같다.

- 요청 시각
- 클라이언트 IP
- 요청 메서드
- 요청 URI
- 쿼리스트링
- 상태 코드
- 응답 크기
- Referer
- User-Agent

공격 탐지 프로젝트에서 Apache 접근 로그는 **핵심 데이터셋의 기반**이 된다.

### 5.2 Apache 에러 로그
프록시 계층과 웹서버 처리 과정의 문제를 남기는 로그다.

예를 들면 다음과 같은 문제가 기록될 수 있다.

- Apache 설정 오류
- 백엔드(Juice Shop) 연결 실패
- 타임아웃
- 권한 문제
- 잘못된 요청 처리 경고
- 프록시 전달 중 발생한 서버 문제

탐지기 학습 외에도, **실험 중 서버가 왜 실패했는지** 확인할 때 중요하다.

### 5.3 Juice Shop 애플리케이션 로그
Juice Shop은 보통 Docker 컨테이너로 실행하므로,
애플리케이션 로그는 일반적으로 컨테이너 표준 출력/표준 오류에 기록된다.

확인 예시는 다음과 같다.

```bash
sudo docker logs -f juice-shop
```

이 로그는 Apache 접근 로그를 대체하지는 않지만,
애플리케이션 내부 동작과 오류를 확인할 때 도움이 된다.

### 5.4 선택적 정밀 로그
필요 시 아래 로그를 추가할 수 있다.

- `mod_log_forensic` 기반 포렌식 로그
- WAF audit log
- 시스템 로그(`journalctl`, `syslog` 등)
- 리버스 프록시 앞단 추가 장비 로그

이 로그는 저장 비용과 민감정보 부담이 커질 수 있으므로,
기본 상시 수집보다는 **선택 수집**이 적절하다.

---

## 6. 권장 로그 구조

### 6.1 1단계: 기본 운영 로그 유지
운영 확인용 기본 access log와 error log는 유지한다.

예시:

```apache
ErrorLog ${APACHE_LOG_DIR}/juice_shop_error.log
CustomLog ${APACHE_LOG_DIR}/juice_shop_access.log combined
```

이 로그는 서비스 동작 확인과 일반적인 운영 점검에 사용한다.

### 6.2 2단계: 보안 분석용 확장 로그 추가
탐지·분류용으로는 별도의 보안 로그를 추가한다.
이 로그는 **사람이 읽을 수 있으면서도 머신 파싱이 쉬운 key=value 형태**를 목표로 한다.

핵심 원칙은 아래와 같다.

- 문자열 필드는 가능한 한 **전부 큰따옴표로 감싼다**.
- 원본 request line과 구조화된 필드를 **둘 다 남긴다**.
- 요청 식별자와 에러 연계 식별자를 **분리한다**.
- 프록시 환경을 고려해 **원본 IP와 실제 peer IP를 같이 남긴다**.

### 6.3 3단계: I/O 정보는 별도 로그보다 본 보안 로그에 합친다
초안에서는 `mod_logio` 값을 별도 `security_io` 로그에 둘 수 있었지만,
실제 실험에서는 **분석용 보안 로그 한 줄 안에 I/O 필드를 같이 넣는 편이 더 실용적**이다.

이유는 다음과 같다.

- 라벨링과 파싱 파이프라인이 단순해진다.
- 같은 요청의 특성이 여러 파일로 나뉘지 않는다.
- 대량 업로드, 데이터 유출 의심, 비정상 응답량 패턴을 한 줄에서 같이 볼 수 있다.

따라서 `in_bytes`, `out_bytes`, `total_bytes`, `ttfb_us`는
기본 보안 로그에 포함하는 방식을 권장한다.

### 6.4 4단계: 에러 로그와의 연계 강화
공격 분석에서는 access log만으로 부족한 경우가 많다.
같은 요청의 access/security log와 error log를 연결할 수 있도록
`UNIQUE_ID`와 `%L`을 함께 남기는 것이 좋다.

- `reqid=%{UNIQUE_ID}e`: 모든 요청에 안정적으로 남는 요청 ID
- `errid=%L`: error log와 연결할 때 사용하는 보조 키

### 6.5 5단계: 포렌식 로그는 상시가 아니라 선택적으로 활성화한다
정밀 분석이 필요할 때만 `mod_log_forensic`을 별도 활성화한다.

예시:

```apache
ForensicLog ${APACHE_LOG_DIR}/juice_shop_forensic.log
```

포렌식 로그는 요청 처리 전후를 엄격하게 남기므로,
침해사고 분석이나 재현 실험에는 유용하지만 상시 운영용으로는 부담이 있을 수 있다.

---

## 7. 권장 수집 항목 우선순위

### 7.1 반드시 수집할 항목
- timestamp
- request_id
- error_link_id
- client_ip
- peer_ip
- method
- raw_request
- path
- query_string
- protocol
- status_code
- response_body_bytes
- processing_time_us
- host
- referer
- user_agent
- vhost

### 7.2 있으면 매우 좋은 항목
- proxy_chain
- x_forwarded_for
- in_bytes
- out_bytes
- total_bytes
- ttfb_us
- request_content_type
- request_content_length
- response_content_type
- keepalive_count
- connection_status
- 세션 존재 여부
- 쿠키 개수 또는 길이
- 업로드 여부

### 7.3 선택 수집 항목
- 요청 본문 원문
- 전체 Cookie 값
- Authorization 헤더
- 응답 본문
- WAF audit body

선택 항목은 민감정보와 저장 용량 문제를 일으킬 수 있으므로,
기본값으로 상시 저장하는 것은 권장하지 않는다.

---

## 8. 공격 유형별로 특히 중요한 특징

### 8.1 스캐닝 / 크롤링 / 취약점 탐색
중요 항목:

- client_ip
- user_agent
- uri
- status_code
- referer
- request frequency
- 404/405/400 비율
- raw_request

대표 징후:

- 짧은 시간 안에 많은 URI 요청
- 존재하지 않는 경로 반복 요청
- 자동화 도구성 User-Agent
- 헤더 조합이 비정상적으로 단순한 요청

### 8.2 인증 시도 / 브루트포스
중요 항목:

- login URI
- method
- status_code
- client_ip
- referer
- 세션 생성 여부
- 시간당 실패 횟수
- 응답 지연

대표 징후:

- 로그인 엔드포인트 반복 POST
- 짧은 간격의 실패 요청 연속 발생
- 동일 IP 또는 동일 User-Agent의 반복 시도

### 8.3 SQL Injection 계열 시도
중요 항목:

- path
- query_string
- raw_request
- request content-type
- processing_time
- ttfb_us
- 상태 코드

대표 징후:

- 비정상적으로 긴 쿼리스트링
- 특수문자 중심 파라미터 조합
- 오류 코드 증가
- 특정 요청만 유난히 오래 걸리는 패턴

### 8.4 XSS 계열 시도
중요 항목:

- query_string
- raw_request
- request content-type
- response_code

대표 징후:

- 스크립트성 문자열이 포함된 파라미터
- 태그, 이벤트 핸들러, 인코딩된 페이로드 형태
- 프런트엔드 입력창 대상 반복 요청

### 8.5 경로 탐색 / 파일 접근 시도
중요 항목:

- uri
- query_string
- raw_request
- status_code
- response_body_bytes

대표 징후:

- `../` 계열 패턴
- 인코딩된 경로 우회 패턴
- 백업 파일, 설정 파일, 숨김 파일 탐색

### 8.6 업로드 악용 / 비정상 대용량 요청
중요 항목:

- method
- request_content_type
- request_content_length
- in_bytes
- out_bytes
- total_bytes
- 상태 코드

대표 징후:

- 큰 POST/PUT 요청
- 비정상 MIME 타입
- 업로드 직후 특정 파일 접근 시도

---

## 9. Juice Shop 환경에서의 로그 위치

### 9.1 Apache 로그
Ubuntu 22.04에서 Apache 로그는 보통 아래 위치를 사용한다.

```text
/var/log/apache2/juice_shop_access.log
/var/log/apache2/juice_shop_security.log
/var/log/apache2/juice_shop_error.log
```

### 9.2 Juice Shop 애플리케이션 로그
Docker 기본 설정에서는 컨테이너의 표준 출력과 표준 오류가 로그의 원천이 된다.
평소 확인은 아래 명령으로 한다.

```bash
sudo docker logs juice-shop
sudo docker logs -f juice-shop
```

즉, Apache처럼 사람이 직접 정한 파일에 바로 쓰는 구조라고 가정하지 말고,
**Juice Shop 실행 방식에 따라 로그 확인 방법이 달라질 수 있음**을 전제로 해야 한다.

---

## 10. 권장 Apache 설정
아래는 Juice Shop 기준의 권장 예시이다.
기본 운영 로그와 실험용 보안 로그를 함께 유지한다.

```apache
<VirtualHost *:80>
    ServerAdmin admin@example.com
    ServerName localhost

    ProxyRequests Off
    ProxyPass        / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/

    # 프록시/LB가 앞단에 있는 경우에만 활성화
    # RemoteIPHeader X-Forwarded-For
    # RemoteIPTrustedProxy 127.0.0.1

    # 사람이 보기 쉬운 에러 로그
    ErrorLogFormat "[%{uc}t] [errid:%L] [reqid:%{UNIQUE_ID}e] [%-m:%-l] [src:%a peer:%{c}a] %M"
    ErrorLog ${APACHE_LOG_DIR}/juice_shop_error.log

    # 사람이 익숙한 표준형
    LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
    CustomLog ${APACHE_LOG_DIR}/juice_shop_access.log combined

    # I/O 및 TTFB 수집
    LogIOTrackTTFB ON

    # 분류/탐지용 key=value 로그
    LogFormat "ts=%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t \
reqid=%{UNIQUE_ID}e errid=%L vhost=%v \
src=%a peer=%{c}a \
method=%m raw_req=\"%r\" uri=\"%U\" qs=\"%q\" proto=%H \
status=%>s resp_body_bytes=%B in_bytes=%I out_bytes=%O total_bytes=%S \
dur_us=%D ttfb_us=%^FB keepalive=%k conn=%X \
req_ct=\"%{Content-Type}i\" req_cl=\"%{Content-Length}i\" resp_ct=\"%{Content-Type}o\" \
referer=\"%{Referer}i\" ua=\"%{User-Agent}i\" host=\"%{Host}i\" xff=\"%{X-Forwarded-For}i\"" security_ext

    CustomLog ${APACHE_LOG_DIR}/juice_shop_security.log security_ext
</VirtualHost>
```

### 10.1 이 설정에서 중요한 수정 포인트

#### `reqid=%{UNIQUE_ID}e`
이 값이 **주 요청 식별자**다.
모든 요청에 안정적으로 붙기 때문에 데이터셋의 기본 키로 사용하기 좋다.

#### `errid=%L`
이 값은 **에러 로그 연결 키**다.
에러 로그와 access/security log를 이어 붙일 때 사용한다.

#### `raw_req="%r"`
정규화된 필드만 남기지 말고,
원본 request line도 같이 남겨야 포렌식 해석과 휴리스틱 분석에 유리하다.

#### `uri="%U"`와 `qs="%q"`
경로와 query string을 분리해 둬야 파싱과 특징 추출이 편해진다.
문자열 필드를 모두 인용부호로 감싸면 파서가 단순해진다.

#### `src=%a`와 `peer=%{c}a`
- `src`: Apache가 인식한 클라이언트 주소
- `peer`: 실제 TCP 연결 상대 주소

프록시/LB를 신뢰하도록 `mod_remoteip`를 설정하면
`src`는 원본 사용자 IP가 되고, `peer`는 실제 연결 상대가 된다.

#### `proxy_chain="%{remoteip-proxy-ip-list}n"`
프록시가 여러 단계를 거치는 환경에서 체인을 확인할 수 있다.
프록시가 없다면 빈 값이어도 무방하다.

#### `in_bytes=%I`, `out_bytes=%O`, `total_bytes=%S`
실제 네트워크 입출력 기준 바이트 수다.
대량 요청, 업로드 시도, 이상한 응답량 편차를 잡는 데 유용하다.

#### `ttfb_us=%^FB`
첫 바이트가 나가기까지 걸린 시간이다.
백엔드 지연, 특정 페이로드에 따른 응답 이상을 볼 때 유용하다.

#### `req_ct`, `req_cl`, `resp_ct`
공격 탐지에서 자주 쓰이는 메타정보다.
요청 본문 원문을 저장하지 않아도 업로드/폼/API 호출의 특성을 파악하기 쉽다.

---

## 11. 필요한 Apache 모듈
최소 권장 모듈 예시는 다음과 같다.

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
sudo a2enmod logio
sudo a2enmod unique_id
```

프록시/LB 뒤에 둘 경우에는 아래도 고려한다.

```bash
sudo a2enmod remoteip
```

설정 확인과 반영:

```bash
sudo apache2ctl configtest
sudo systemctl reload apache2
```

---

## 12. 실험에 추가하면 더 좋은 것

### 12.1 추천 추가 항목
기본 보안 로그 외에 아래 항목을 실험 메타데이터로 따로 남기면 좋다.

- 실험 날짜와 시간
- 실험 이름
- 대상 URL
- 도구 종류
- 정상/공격 여부
- 공격 유형 추정
- 라벨링 기준
- 사용한 스크립트 또는 시나리오 이름

### 12.2 추천 추가 로그 소스
다음은 상시 필수는 아니지만,
실험 품질을 높일 수 있는 보조 소스다.

- Docker 컨테이너 로그
- `journalctl -u apache2`
- WAF audit log
- 시스템 성능 지표(CPU, 메모리, 네트워크)
- 별도 캡처용 패킷 로그(`tcpdump` 등, 허가된 실험망 한정)

### 12.3 쿠키와 세션은 값 전체보다 메타정보를 추천
다음처럼 저장하는 편이 더 낫다.

- 쿠키 존재 여부
- 쿠키 개수
- 쿠키 길이
- 세션 토큰 존재 여부

전체 값을 상시 저장하면 민감정보 부담이 커진다.

---

## 13. 수집 후 운영 절차

### 13.1 정상 트래픽과 공격성 트래픽을 분리해서 수집한다
학습용 데이터셋에는 정상 요청과 공격성 요청이 모두 필요하다.
따라서 아래처럼 구분해 수집하는 것이 좋다.

1. 일반 브라우징, 상품 조회, 검색, 로그인, 장바구니 같은 **정상 시나리오** 먼저 수집
2. 허가된 실험 도구 또는 수동 테스트를 통해 **공격성 시나리오** 별도 수집
3. 수집 시각, 실험 이름, 도구 종류를 메모로 함께 남김

### 13.2 로그와 실험 기록을 함께 남긴다
나중에 라벨링을 쉽게 하려면 로그 파일만 저장하지 말고,
아래 정보를 별도 메모 파일에 남기는 것이 좋다.

- 실험 날짜와 시간
- 실험 대상 URL
- 사용 도구 종류
- 정상/공격 여부
- 공격 유형 추정
- 사용한 테스트 시나리오 이름
- 로그 파일 이름과 해시값

### 13.3 로그 형식을 중간에 자주 바꾸지 않는다
탐지 프로그램을 만들기 시작한 뒤 로그 형식을 자주 바꾸면,
이전 데이터와 이후 데이터가 서로 호환되지 않게 된다.

따라서 초기에 최소 필드를 확정하고,
추가 필드는 새 로그 파일로 분리하는 방식이 더 좋다.

---

## 14. 저장 공간과 보안 주의사항

### 14.1 로그 로테이션을 적용한다
로그는 빠르게 커질 수 있다.
특히 점검 도구나 반복 요청 실험을 하면 access/security log가 짧은 시간에 크게 증가한다.

따라서 `logrotate`를 이용해 회전 정책을 두는 것이 좋다.

예시:

- 일 단위 또는 크기 기준 회전
- 압축 저장
- 최근 N개만 유지
- 오래된 로그 자동 삭제

### 14.2 민감정보를 기본 로그에 직접 넣지 않는다
다음 값은 상시 평문 저장을 피하는 편이 좋다.

- 비밀번호
- 전체 Cookie 값
- Authorization 헤더
- 개인식별정보가 포함된 요청 본문
- 토큰, 세션 식별자 원문

필요하면 아래 방식 중 하나를 택한다.

- 길이만 저장
- 존재 여부만 저장
- 해시/마스킹 처리
- 의심 요청만 별도 감사 로그에 저장

### 14.3 로그 파일을 웹 루트에 두지 않는다
로그 파일은 웹으로 직접 접근 가능한 위치가 아니라,
시스템 로그 디렉터리 같은 **비공개 위치**에 두어야 한다.

---

## 15. 예시 로그 한 줄

### 15.1 사람이 읽기 쉬운 로그
```text
192.168.56.20 - - [26/Mar/2026:13:10:02 +0900] "GET /rest/products/search?q=apple HTTP/1.1" 200 1543 "http://192.168.56.10/" "Mozilla/5.0"
```

### 15.2 머신 파싱용 key=value 로그
```text
ts=2026-03-26T13:10:02.123+0900 reqid=ZrA1x38AAAEAACmK0wAAAAAB errid=- vhost=192.168.56.10 src=192.168.56.20 peer=192.168.56.20 proxy_chain="" method=GET raw_req="GET /rest/products/search?q=apple HTTP/1.1" uri="/rest/products/search" qs="?q=apple" proto=HTTP/1.1 status=200 resp_body_bytes=1543 in_bytes=512 out_bytes=1960 total_bytes=2472 dur_us=8321 ttfb_us=7612 keepalive=0 conn=+ req_ct="-" req_cl="-" resp_ct="application/json; charset=utf-8" referer="http://192.168.56.10/" ua="Mozilla/5.0" host="192.168.56.10" xff=""
```

---

## 16. 추천 최종 전략
이번 프로젝트에서는 아래 조합이 가장 현실적이다.

### 기본 상시 수집
- `juice_shop_access.log`
- `juice_shop_security.log`
- `juice_shop_error.log`
- `docker logs juice-shop` 기반 애플리케이션 로그 확인

### 필요 시 추가
- `juice_shop_forensic.log`
- WAF audit log
- `journalctl -u apache2`
- 프록시/LB 메타로그

이 전략의 장점은 다음과 같다.

- 운영 확인과 분석용 데이터셋 수집을 분리할 수 있다.
- Juice Shop 환경에서 공격 재현 로그를 안정적으로 모을 수 있다.
- Apache 중심 분석 구조를 유지할 수 있다.
- 나중에 탐지 모델, 경보 시스템, 대시보드로 확장하기 쉽다.

---

## 17. 결론
Juice Shop 환경에서의 로그 수집 전략은 단순히 access log 하나를 남기는 수준으로 끝나면 안 된다.
이번 프로젝트처럼 **공격 탐지와 웹 로그 분류**가 목적이라면,
기본 운영 로그 위에 **분석용 확장 로그**, **에러 로그 연계**, **애플리케이션 로그 확인**, **선택적 정밀 로그**를 계층적으로 구성하는 것이 적절하다.

정리하면 다음과 같다.

1. Apache를 수집 중심 지점으로 삼는다.
2. 기본 access log는 유지한다.
3. 탐지용 key=value 확장 로그를 별도 파일로 둔다.
4. `UNIQUE_ID`를 주 요청 식별자로 쓰고 `%L`은 에러 연계용으로 둔다.
5. `mod_logio`와 헤더 메타정보를 함께 넣어 분류용 특징을 강화한다.
6. Juice Shop 애플리케이션 로그는 Docker 로그로 보조 확인한다.
7. 포렌식/WAF 로그는 필요할 때만 추가한다.

이 방식이 현재 프로젝트 목적에 가장 잘 맞는 **Juice Shop 기준 로그 수집 전략**이다.
