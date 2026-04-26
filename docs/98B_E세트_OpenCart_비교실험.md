# 98B_E세트_OpenCart_비교실험

- 작성 기준일: 2026-04-26
- 문서 역할: `docs/98_비교_실험_요청_세트_표준.md` 계열을 따르는 E세트 비교 실험 초안
- 적용 범위: OpenCart / PHP / route parameter / PHP wrapper / admin probing / config exposure / POST body visibility
- 기준 데이터: Apache `security` 로그 표면 지표
- 대상 서비스: OpenCart
- 기본 URL: `http://192.168.56.111`
- UA prefix: `lab-e-set`

> 주의: 이 문서는 승인된 로컬 실험 환경에서만 사용한다. Apache 로그만으로는 PHP wrapper 실행 성공, config 파일 내용 노출, SQLi 성공, 로그인/권한 상승 성공, POST body 내부 처리 결과를 확정하지 않는다.

---

## 1. 실험 목적

E세트는 Juice Shop 중심 A/B/C/D세트 이후 OpenCart/PHP 기반 환경에서 다음을 확인하기 위한 실험이다.

1. OpenCart의 `index.php?route=...` 구조에서 route parameter probing을 식별하는가.
2. PHP 기반 환경에서 `php://filter` 같은 wrapper/file disclosure intent를 인식하는가.
3. `/admin`, `/admin/index.php`, `/admin/config.php`, `/config.php` 같은 OpenCart/PHP 경로 탐색을 directory probing 또는 sensitive file intent로 해석하는가.
4. product/search/category 계열 query에서 SQLi/XSS payload가 Apache 로그에 남을 때 기존 B/C세트 탐지 로직이 일반화되는가.
5. POST login/register/admin form에서 raw POST body visibility 한계를 재확인하는가.
6. D세트 R3에서 추가한 `probing_sequence_summaries`가 OpenCart 경로에서도 실험환경 특화 없이 동작하는가.

---

## 2. 기본 변수 및 환경

```bash
export OPENCART_URL="http://192.168.56.111"
export UA_PREFIX="lab-e-set"
```

사전 확인:

```bash
curl -i "$OPENCART_URL/"
curl -i "$OPENCART_URL/index.php"
curl -i "$OPENCART_URL/admin/"
```

Apache 로그 확인:

```bash
sudo tail -n 10 /var/log/apache2/app_security.log
```

확인할 것:

- `host="192.168.56.111"` 또는 OpenCart vhost로 남는지
- `uri`, `query_string`, `raw_request`가 정상 기록되는지
- Juice Shop fallback으로 잘못 들어가지 않는지
- OpenCart와 Juice Shop이 같은 Apache vhost/proxy 설정을 공유하는 경우 host/vhost 구분이 가능한지

---

## 3. Round 1 — OpenCart route / admin probing

Round 1은 OpenCart 특유의 route 구조와 관리자 경로 탐색을 확인한다.

### E-01 Basic OpenCart Home

목적:

- OpenCart 정상 기준 요청을 확보한다.

```bash
curl -i \
  -A "${UA_PREFIX}-base-home-1" \
  "$OPENCART_URL/"
```

기대 관찰:

- 정상 baseline 요청
- candidate로 과승격하지 않는 것이 적절
- 이후 fallback/response size 비교 기준으로 활용 가능

### E-02 Route Parameter Baseline

목적:

- 정상 route parameter 요청이 어떻게 기록되는지 확인한다.

```bash
curl -i -G \
  -A "${UA_PREFIX}-route-base-1" \
  --data-urlencode "route=product/category" \
  "$OPENCART_URL/index.php"
```

기대 관찰:

- `uri=/index.php`
- `query_string=?route=product%2Fcategory` 또는 동등 형태
- 정상 route parameter는 candidate로 과승격하지 않음
  
실제:
- route=product/category가 404라서 “정상 route와 공격 route의 차이”를 비교하는 힘은 약함. 따라서 실제 브라우저에서 200으로 확인된 상품/카테고리 URL을 baseline으로 써야 함. 그 예시가 밑임.
  
```bash
curl -i -G \
  -A "lab-e-set-route-base-2" \
  --data-urlencode "route=product/product" \
  --data-urlencode "product_id=43" \
  "$OPENCART_URL/index.php"
```

### E-03 Route Probing — Unknown Route

목적:

- 존재하지 않는 route 접근을 route probing으로 식별하는지 확인한다.

```bash
curl -i -G \
  -A "${UA_PREFIX}-route-unknown-1" \
  --data-urlencode "route=../../../../etc/passwd" \
  "$OPENCART_URL/index.php"
```

기대 관찰:

- route parameter 내부 traversal intent가 query_string에 남는지 확인
- 파일 읽기 성공은 단정하지 않음
- route parameter abuse 또는 traversal intent로 해석 가능

### E-04 Admin Path Probe

목적:

- OpenCart 관리자 경로 접근을 탐지하되, 단발 요청을 과도하게 high severity로 올리지 않는지 확인한다.

```bash
curl -i --path-as-is \
  -A "${UA_PREFIX}-admin-path-1" \
  "$OPENCART_URL/admin/"

curl -i --path-as-is \
  -A "${UA_PREFIX}-admin-index-1" \
  "$OPENCART_URL/admin/index.php"
```

기대 관찰:

- admin path probing으로 context 보존
- 실제 관리자 로그인 성공 또는 권한 획득은 단정하지 않음

---

## 4. Round 2 — PHP wrapper / config exposure intent

Round 2는 PHP 기반 file disclosure intent를 확인한다.

### E-11 PHP Wrapper via Route Parameter

목적:

- `php://filter` wrapper payload를 OpenCart/PHP 환경에서 file disclosure intent로 식별하는지 확인한다.

```bash
curl -i -G \
  -A "${UA_PREFIX}-php-wrapper-route-1" \
  --data-urlencode "route=php://filter/convert.base64-encode/resource=index.php" \
  "$OPENCART_URL/index.php"
```

기대 관찰:

- query_string에 `php%3A%2F%2Ffilter...` 형태가 남음
- decoded view에서 `php://filter/convert.base64-encode/resource=index.php` 의미 복원
- `route=php://filter...index.php` 요청이 candidate로 올라감
- verdict 또는 hint에 PHP wrapper 기반 file disclosure intent가 명시됨
- 404면 route 미인식 또는 실패 가능성까지만 서술
- 실제 base64 소스 노출 여부는 response body 원문 없이는 확정하지 않음

### E-12 PHP Wrapper via Path-like Parameter

목적:

- 일반 file/path parameter에 wrapper를 넣었을 때도 intent를 인식하는지 확인한다.

```bash
curl -i -G \
  -A "${UA_PREFIX}-php-wrapper-path-1" \
  --data-urlencode "path=php://filter/convert.base64-encode/resource=config.php" \
  "$OPENCART_URL/index.php"
```

기대 관찰:

- `path=` parameter 내 PHP wrapper intent 식별
- `path=php://filter...config.php` 요청도 candidate로 올라감
- config.php 접근 의도와 file disclosure intent를 함께 식별
- status 200이어도 실제 config 노출 성공은 단정하지 않음
- 실제 config 노출 성공 단정 금지

### E-13 Direct Config Path Probe

목적:

- OpenCart/PHP config 파일 접근 시도 식별.

```bash
curl -i --path-as-is \
  -A "${UA_PREFIX}-config-root-1" \
  "$OPENCART_URL/config.php"

curl -i --path-as-is \
  -A "${UA_PREFIX}-config-admin-1" \
  "$OPENCART_URL/admin/config.php"
```

기대 관찰:

- `/config.php`, `/admin/config.php` 접근 시도 식별
- direct sensitive config path probe로 context-only 보존
- 단발 요청이면 candidate 과승격보다 `low_signal_dir_probe` 또는 context-only 해석이 적절
- `response_body_bytes=0`이면 파일 노출 성공이 아니라 본문 노출 증거 없음으로 기록
- 실제 파일 내용 노출은 response body 원문 없이는 확정하지 않음

---

## 5. Round 3 — OpenCart SQLi / XSS query 재검증

Round 3은 B/C세트 탐지 로직이 OpenCart URL 구조에도 일반화되는지 확인한다.

### E-21 Product Search SQLi

목적:

- OpenCart product/search 계열 query에서 SQLi payload가 query_string에 남을 때 탐지되는지 확인한다.

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-sqli-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=x')) OR 1=1 --" \
  "$OPENCART_URL/index.php"
```

기대 관찰:

- `route=product/search`, `search=` parameter 보존
- SQLi payload가 B세트와 유사하게 탐지되는지 확인
- response size anomaly가 있어도 실제 SQLi 성공 단정 금지

### E-22 Product Search XSS

목적:

- OpenCart product/search 계열 query에서 XSS payload가 query_string에 남을 때 탐지되는지 확인한다.

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-xss-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=<script>alert(1)</script>" \
  "$OPENCART_URL/index.php"
```

기대 관찰:

- XSS payload 탐지
- 브라우저 실행 성공은 단정하지 않음
- response body 반영 여부는 Apache 로그만으로 확정하지 않음

### E-23 Encoded XSS / Entity XSS

목적:

- C세트의 URL/entity decode 개선이 OpenCart query에서도 유지되는지 확인한다.

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-xss-entity-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=&#x3C;script&#x3E;alert(1)&#x3C;/script&#x3E;" \
  "$OPENCART_URL/index.php"
```

기대 관찰:

- HTML entity payload 식별
- `xss:html_entity_decoded_script` 계열 hint 유지
- SQL comment `#` 오탐 재발 방지

---

## 6. Round 4 — POST body visibility 재확인

Round 4는 OpenCart login/admin form에서 POST body visibility 한계를 다시 확인한다.

### E-31 Admin Login POST Baseline

목적:

- POST 요청이 Apache 로그 표면에서 어떻게 보이는지 확인한다.

```bash
curl -i \
  -A "${UA_PREFIX}-post-login-base-1" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=admin&password=test" \
  "$OPENCART_URL/admin/index.php"
```

기대 관찰:

- method=POST
- req_content_type / req_content_length 기록
- raw POST body 원문은 baseline에서 보이지 않음
- 로그인 성공/실패 또는 계정 존재 여부는 Apache 로그만으로 확정하지 않음

### E-32 Admin Login SQLi POST

목적:

- POST body SQLi payload가 현재 baseline에서 직접 보이지 않는다는 점을 확인한다.

```bash
curl -i \
  -A "${UA_PREFIX}-post-login-sqli-1" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=admin' OR '1'='1&password=x" \
  "$OPENCART_URL/admin/index.php"
```

기대 관찰:

- Apache 로그에는 method, URI, content-type, content-length 중심으로 남음
- body 내부 SQLi payload는 직접 보이지 않음
- Stage2는 POST body visibility 한계를 명시해야 함
- SQLi 성공 단정 금지

---

## 7. Round 5 — Directory probing sequence 일반성 확인

Round 5는 D세트 R3에서 개선한 `probing_sequence_summaries`가 OpenCart/PHP 경로에서도 동작하는지 확인한다.

```bash
for path in \
  "/admin/" \
  "/admin/index.php" \
  "/config.php" \
  "/admin/config.php" \
  "/backup.zip" \
  "/backup.sql" \
  "/phpmyadmin" \
  "/vendor/" \
  "/storage/"; do
  curl -i --path-as-is \
    -A "${UA_PREFIX}-probe-burst-1" \
    "$OPENCART_URL${path}"
  sleep 1
done
```

기대 관찰:

- 개별 요청을 candidate로 과승격하지 않음
- 같은 src_ip/window 내 3개 이상 민감/관리/백업 경로 접근을 `probing_sequence_summaries`로 보존
- 200/403/404 status 분포와 content-type/response size 반복성을 context로 전달
- 실제 config/admin/backup 노출 성공은 단정하지 않음

---

## 8. 실행 순서 권장

OpenCart E세트는 처음부터 전부 실행하지 말고 round별로 분리한다.

권장 순서:

1. E Round 0: URL/vhost/log 확인
2. E Round 1: route/admin probing
3. export + prepare + Stage1/Stage2 + 비교 문서
4. E Round 2: PHP wrapper/config exposure intent
5. export + 분석
6. E Round 3: SQLi/XSS query 재검증
7. export + 분석
8. E Round 4: POST body visibility
9. export + 분석
10. E Round 5: directory probing sequence 일반성 확인
11. E세트 통합 비교 문서 작성

한 export window에 모든 round를 섞지 않는 것이 좋다. OpenCart는 route, PHP wrapper, probing, POST body visibility의 평가 축이 다르기 때문이다.

---

## 9. 평가 기준

| 평가 축 | 성공 기준 | 보수적 해석 |
|---|---|---|
| Route parameter visibility | `route=`가 query_string에 보존됨 | route 처리 성공은 단정하지 않음 |
| PHP wrapper intent | `php://filter` decoded view가 확인됨 | source disclosure 성공은 body 없이는 미확정 |
| Config exposure intent | `/config.php`, `/admin/config.php` 접근 확인 | 파일 내용 노출 단정 금지 |
| SQLi query | `search=` 등 query parameter에 SQLi payload 보존 | DB 결과 변경/유출 단정 금지 |
| XSS query | query parameter에 XSS payload 보존 | 브라우저 실행/DOM 반영 단정 금지 |
| POST body | content-type/length 확인 | body payload는 직접 보이지 않음 |
| Probing sequence | `probing_sequence_summaries` 생성 | context-only, incident 과승격 금지 |

---

## 10. Provider 비교 포인트

| 비교 항목 | 확인 내용 |
|---|---|
| OpenCart route 이해 | `route=product/search`, `route=product/category`를 일반 query parameter로만 볼지, route abuse로 볼지 |
| PHP wrapper 보수성 | `php://filter`를 file disclosure intent로 보되 성공 단정은 피하는지 |
| Config file intent | config.php 접근을 sensitive file probe로 설명하는지 |
| POST body 한계 | raw body가 없을 때 SQLi/login 성공을 단정하지 않는지 |
| probing sequence | D세트 R3 개선 구조를 활용해 burst를 context-only로 설명하는지 |
| known asset 고려 | 내부 테스트/실험 가능성을 병기하는지 |

---

## 11. 산출물 관리

public repo 공개 권장:

- E세트 비교 Markdown
- 최종 Stage2 Markdown
- 통합 요약 문서

public repo 공개 비권장:

- raw export
- LLM input JSON
- Stage2 report input JSON
- analysis_candidates JSON
- noise_summary JSON
- stage1_errors JSON

OpenCart에서는 admin path, config path, route query, host/vhost 정보가 포함될 수 있으므로 raw/LLM input 공개에 더 주의한다.

---

## 12. 후속 코드 개선 후보

E세트 결과에 따라 다음을 검토한다.

1. PHP wrapper hint 세분화
   - `file_disclosure:php_filter_wrapper`
   - `file_disclosure:base64_source_intent`

2. OpenCart route parameter context
   - `opencart:route_parameter`
   - 단, OpenCart 전용 조건을 일반 탐지 score에 과하게 넣지 않음

3. config file probing hint
   - `file_probe:config_php`
   - `file_probe:admin_config_php`

4. POST body visibility 정책 유지/확장
   - raw POST body를 넣지 않는 현재 정책 유지가 기본
   - 실험 전용 body capture는 별도 보안 정책 필요

5. probing sequence generality
   - D세트 R3 개선 로직이 OpenCart에서도 불필요하게 과탐하지 않는지 확인

---

## 13. 최종 주의

E세트는 OpenCart/PHP라는 특정 앱을 대상으로 하지만, 코드 개선은 실험환경 특화가 되면 안 된다.

금지:

- `lab-e-set-*` UA를 탐지 조건으로 사용
- `192.168.56.111`을 탐지 조건으로 사용
- 특정 OpenCart 응답 크기를 hard-code
- `/admin/config.php` 등 특정 경로 하나만 보고 high severity 자동 승격
- 200 응답을 source/config 노출 성공으로 단정

허용:

- 일반적인 PHP wrapper 패턴 인식
- 일반적인 config/admin/backup path probing 인식
- route/query parameter에 남은 공격 payload 인식
- same src_ip/time window 기반 probing sequence context 보존

---

## 14. 발표용 한 줄 정리

E세트는 OpenCart/PHP 환경에서 route parameter, PHP wrapper, config/admin path probing, SQLi/XSS query, POST body visibility를 검증하는 실험이다. 핵심은 PHP/OpenCart 특성을 활용하되, 실제 파일 노출·로그인 성공·SQLi 성공·XSS 실행은 Apache 로그만으로 단정하지 않는 것이다.
