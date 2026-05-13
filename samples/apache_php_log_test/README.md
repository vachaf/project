# Apache PHP Log Test Sample

- 문서 상태: 샘플 앱
- 작성일: 2026-05-14
- 목적: Apache를 웹단으로 사용하는 일반 PHP 앱에서 `app_security.log`, `app_access.log`, `app_error.log` 수집을 검증하기 위한 최소 샘플

## 1. 범위

이 샘플은 reverse proxy 전용 검증 앱이 아니다.

검증 대상은 다음이다.

- Apache가 정적 파일을 직접 서빙하는 경우
- Apache가 PHP 앱을 처리하는 경우
- query string, POST, upload-like request, 403, 404, 500, static asset 요청이 로그에 어떻게 남는지 확인하는 경우
- `app_security.log`의 key=value 포맷과 shipper parser 동작을 확인하는 경우

## 2. 파일 구성

```text
samples/apache_php_log_test/
  README.md
  apache-vhost.conf.example
  public/
    index.php
    search.php
    login.php
    upload.php
    forbidden.php
    error.php
    health.php
    static/
      app.js
      style.css
```

## 3. 서버 배치 예

```bash
sudo mkdir -p /var/www/apache-log-test
sudo cp -a samples/apache_php_log_test/public/. /var/www/apache-log-test/
sudo chown -R www-data:www-data /var/www/apache-log-test
```

Apache vhost 예시는 `apache-vhost.conf.example`를 참고한다.

## 4. 검증 요청 예

### 정상 HTML

```bash
curl -i http://localhost/
```

### 정적 파일

```bash
curl -i http://localhost/static/style.css
curl -i http://localhost/static/app.js
```

### query string

```bash
curl -i 'http://localhost/search.php?q=test&page=1'
```

### POST form

```bash
curl -i -X POST http://localhost/login.php \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'username=alice&password=wrong'
```

### upload-like request

```bash
printf 'sample file\n' > /tmp/apache-log-test-upload.txt
curl -i -X POST http://localhost/upload.php \
  -F 'note=sample' \
  -F 'file=@/tmp/apache-log-test-upload.txt'
```

### 403

```bash
curl -i http://localhost/forbidden.php
```

### 404

```bash
curl -i http://localhost/not-found-test
```

### 500

```bash
curl -i http://localhost/error.php
```

## 5. 기대 로그 관찰점

| 요청 | 기대 관찰점 |
|---|---|
| `/` | `status_code=200`, `resp_content_type="text/html..."` |
| `/static/style.css` | CSS 정적 파일 요청, `resp_content_type="text/css..."` |
| `/static/app.js` | JS 정적 파일 요청 |
| `/search.php?q=test&page=1` | `uri="/search.php"`, `query_string="?q=test&page=1"` |
| `POST /login.php` | `method=POST`, `req_content_type`, `req_content_length` |
| `POST /upload.php` | multipart form, larger `in_bytes`, `req_content_length` |
| `/forbidden.php` | `status_code=403` |
| `/not-found-test` | `status_code=404` |
| `/error.php` | `status_code=500`, PHP/Apache error context 가능 |

## 6. 중요한 해석 제한

이 샘플에서도 Apache 로그만으로 다음을 단정하지 않는다.

- 로그인 성공/실패의 실제 인증 의미
- 파일 업로드 저장 성공
- DB 변경 결과
- 서버 침해 성공
- response body 내용
- request body 원문 내용

Apache 로그는 요청/응답 메타데이터 증거로만 사용한다.

## 7. shipper 검증

```bash
python3 src/apache_log_shipper.py --once --reset-state
```

DB 적재 후 예시 조회:

```sql
SELECT log_time, src_ip, method, uri, query_string, status_code, req_content_type, req_content_length, resp_content_type
FROM apache_security_logs
ORDER BY id DESC
LIMIT 20;
```
