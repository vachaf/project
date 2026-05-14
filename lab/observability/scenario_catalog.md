# Apache 앱 관측 가능성 비교 시나리오 카탈로그

- 문서 상태: 실험 카탈로그 초안
- 작성일: 2026-05-14
- 카탈로그 버전: `apache_observability_s01_s15_v1`
- 목적:
  - Apache를 웹단으로 사용하는 앱 배치별 관측 가능성 비교
  - 단순 PHP, 실제 PHP 앱, reverse proxy 앱, WAF 적용 앱에 가능한 한 동일한 요청 세트 적용

---

## 1. 공통 원칙

모든 요청에는 다음 marker를 포함한다.

| marker | 위치 | 목적 | 기준성 |
|---|---|---|---|
| `User-Agent: obs-test/<scenario_id> run=<run_id>` | request header | 서버 로그 필터링 및 시나리오 식별 | canonical |
| `obs_run` | query/body/header | run 식별 보조 | optional/helper |
| `scenario` | query/body/header | 시나리오 식별 보조 | optional/helper |

`User-Agent`를 canonical marker로 둔다.

이유:

- S08 login POST, S09 upload-like POST처럼 `scenario` 값이 request body/form에만 들어갈 수 있다.
- Apache access/security log는 request body를 기록하지 않는다.
- 따라서 query string에서 `scenario=Sxx`만 grep하면 POST body 기반 시나리오를 놓친다.
- 모든 시나리오는 반드시 `User-Agent: obs-test/Sxx run=<run_id>`를 포함해야 한다.

권장 User-Agent 형식:

```text
obs-test/<scenario_id> run=<run_id>
```

예:

```bash
curl -H 'User-Agent: obs-test/S04 run=obs_2026_05_14_php_sample' \
  'http://target/search.php?q=test&obs_run=obs_2026_05_14_php_sample&scenario=S04'
```

서버 로그 필터링 기준:

```bash
grep 'obs-test/.*run=<run_id>' app_security.log
```

시나리오 카운트 기준:

```bash
grep -o 'obs-test/S[0-9][0-9]' app_security.filtered.log \
  | sed 's/obs-test\///' \
  | sort \
  | uniq -c
```

주의:

- 이 카탈로그는 관측 가능성 비교용이다.
- 공격 성공 여부를 검증하는 목적이 아니다.
- SQLi/XSS/traversal-like 시나리오는 페이로드 관찰과 로그 처리 확인 목적이다.
- 운영/외부 시스템에는 실행하지 않는다.

---

## 2. 공통 변수

실행 전 다음 값을 정한다.

```bash
export TARGET_BASE_URL="http://apache-log-test.local"
export OBS_RUN="obs_YYYY_MM_DD_target"
export UA_PREFIX="obs-test"
```

아래 예시는 `${TARGET_BASE_URL}`, `${OBS_RUN}` 변수를 사용한다.

---

## 3. 시나리오 목록

| ID | 이름 | 요청 유형 | 기대 관측 등급 | 목적 |
|---|---|---|---:|---|
| S01 | normal_main | GET | O1 | 정상 메인 요청 baseline |
| S02 | static_css | GET | O1 | CSS 정적 파일 요청 |
| S03 | static_js | GET | O1 | JS 정적 파일 요청 |
| S04 | query_search | GET | O1 | query string 파싱 확인 |
| S05 | not_found | GET | O1 | 404 관찰 |
| S06 | forbidden_or_sensitive_path | GET | O1~O2 | 403/민감 경로 probe 관찰 |
| S07 | login_get | GET | O1 | 로그인 페이지 접근 관찰 |
| S08 | login_post | POST | O1/O4 | 로그인-like POST 관찰, 성공 판정 금지 |
| S09 | upload_like_post | POST multipart | O1/O4 | upload-like 요청 관찰, 저장 성공 판정 금지 |
| S10 | slow_or_large_request | GET/POST | O1 | duration/TTFB/size 관찰 |
| S11 | server_error | GET | O2 | 500 및 error log 연결 확인 |
| S12 | scanner_burst | GET 반복 | O1 | 반복 요청/스캐너-like 패턴 |
| S13 | sqli_like | GET | O1/O3 | SQLi-like query 관찰, WAF optional |
| S14 | xss_like | GET | O1/O3 | XSS-like query 관찰, WAF optional |
| S15 | traversal_like | GET | O1/O3 | traversal-like query 관찰, WAF optional |

---

## 4. 상세 시나리오

## S01 normal_main

### 목적

정상 메인 페이지 요청이 `app_security.log`에 기록되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S01 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/?obs_run=${OBS_RUN}&scenario=S01"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | method=GET, uri=/, status_code=200 계열 |
| `app_error.log` | 일반적으로 없음 |
| app log | optional |

### 금지 추론

- status 200만으로 앱 기능 정상 완료를 단정하지 않는다.

---

## S02 static_css

### 목적

CSS 정적 파일 요청이 정적 리소스로 관찰되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S02 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/static/style.css?obs_run=${OBS_RUN}&scenario=S02"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | uri=/static/style.css, resp_content_type=text/css 계열 |
| `app_error.log` | 일반적으로 없음 |

---

## S03 static_js

### 목적

JS 정적 파일 요청이 정적 리소스로 관찰되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S03 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/static/app.js?obs_run=${OBS_RUN}&scenario=S03"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | uri=/static/app.js, resp_content_type=javascript 계열 |
| `app_error.log` | 일반적으로 없음 |

---

## S04 query_search

### 목적

query string이 `uri`와 `query_string`으로 분리되어 관찰되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S04 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/search.php?q=normal-search&obs_run=${OBS_RUN}&scenario=S04"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | uri=/search.php, query_string에 q/obs_run/scenario 포함 |
| `app_error.log` | 일반적으로 없음 |

---

## S05 not_found

### 목적

존재하지 않는 경로 요청이 404로 관찰되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S05 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/does-not-exist-${OBS_RUN}?scenario=S05&obs_run=${OBS_RUN}"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | status_code=404 |
| `app_error.log` | 설정/LogLevel에 따라 없을 수 있음 |

### 금지 추론

- 404는 파일 부재 관찰일 수 있으나, 애플리케이션 내부 라우팅 구조를 확정하지 않는다.

---

## S06 forbidden_or_sensitive_path

### 목적

금지된 경로 또는 민감 경로 probe가 어떻게 기록되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S06 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/private/secret.txt?scenario=S06&obs_run=${OBS_RUN}"
```

대체 경로:

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S06 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/.env?scenario=S06&obs_run=${OBS_RUN}"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | 403 또는 404 |
| `app_error.log` | 권한/파일 접근 관련 메시지가 있을 수 있음 |

### 금지 추론

- 200/403/404만으로 파일 내용 노출 여부를 단정하지 않는다.
- `response_body_bytes`만으로 민감정보 노출을 단정하지 않는다.

---

## S07 login_get

### 목적

로그인 페이지 접근이 관찰되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S07 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/login.php?obs_run=${OBS_RUN}&scenario=S07"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | method=GET, uri=/login.php |
| app log | optional |

---

## S08 login_post

### 목적

로그인-like POST 요청의 method, content-length, content-type 관찰을 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S08 run=${OBS_RUN}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -X POST \
  --data "username=alice&password=wrong-password&obs_run=${OBS_RUN}&scenario=S08" \
  "${TARGET_BASE_URL}/login.php"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | method=POST, req_content_type, req_content_length, user_agent에 S08 marker |
| app log | 로그인 성공/실패를 판단하려면 필요 |

### 금지 추론

- POST 요청 존재만으로 로그인 성공/실패를 단정하지 않는다.
- Apache access/security log만으로 계정 탈취 성공을 말하지 않는다.

---

## S09 upload_like_post

### 목적

multipart upload-like 요청이 Apache request metadata로 어떻게 관찰되는지 확인한다.

### 예시 요청

```bash
tmp_file="/tmp/obs-upload-${OBS_RUN}.txt"
echo "observability upload sample ${OBS_RUN}" > "${tmp_file}"

curl -i \
  -H "User-Agent: ${UA_PREFIX}/S09 run=${OBS_RUN}" \
  -F "file=@${tmp_file}" \
  -F "obs_run=${OBS_RUN}" \
  -F "scenario=S09" \
  "${TARGET_BASE_URL}/upload.php"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | method=POST, multipart content-type, req_content_length, user_agent에 S09 marker |
| app log | 저장 성공 여부 판단에 필요 |

### 금지 추론

- upload-like POST만으로 실제 파일 저장 성공을 단정하지 않는다.

---

## S10 slow_or_large_request

### 목적

`duration_us`, `ttfb_us`, request/response size 계열 필드를 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S10 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/search.php?q=slow-check&sleep_ms=300&obs_run=${OBS_RUN}&scenario=S10"
```

대체: 큰 query/body 요청은 테스트 환경에서만 사용한다.

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | duration_us, ttfb_us, in_bytes/out_bytes/total_bytes |

### 금지 추론

- 지연만으로 DoS 또는 서버 침해를 단정하지 않는다.

---

## S11 server_error

### 목적

500 응답과 `app_error.log` 연결 가능성을 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S11 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/error.php?obs_run=${OBS_RUN}&scenario=S11"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | status_code=500 계열 |
| `app_error.log` | PHP/app/proxy/module error가 있을 수 있음 |

### 금지 추론

- 500 또는 error message만으로 공격 성공을 단정하지 않는다.

---

## S12 scanner_burst

### 목적

짧은 시간 동안 반복 요청이 IP/UA/시간 기준으로 묶이는지 확인한다.

### 예시 요청

```bash
for path in / /search.php /admin /wp-login.php /.env /server-status /does-not-exist; do
  curl -s -o /dev/null \
    -H "User-Agent: ${UA_PREFIX}/S12 run=${OBS_RUN}" \
    "${TARGET_BASE_URL}${path}?obs_run=${OBS_RUN}&scenario=S12"
done
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | 같은 UA/run/scenario의 반복 요청 |
| `app_error.log` | 일부 경로에서 optional |

### 금지 추론

- scanner-like 패턴은 probe 근거이지 침해 성공 근거가 아니다.

---

## S13 sqli_like

### 목적

SQLi-like query가 URL/query string에 어떻게 기록되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S13 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/search.php?q=1%27%20OR%20%271%27%3D%271&obs_run=${OBS_RUN}&scenario=S13"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | SQLi-like encoded query 관찰 |
| ModSecurity audit | WAF 적용 시 rule match 가능 |

### 금지 추론

- SQLi-like 문자열 관찰만으로 SQL injection 성공을 말하지 않는다.
- DB 결과를 Apache 로그에서 추정하지 않는다.

---

## S14 xss_like

### 목적

XSS-like query가 URL/query string에 어떻게 기록되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S14 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/search.php?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E&obs_run=${OBS_RUN}&scenario=S14"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | XSS-like encoded query 관찰 |
| ModSecurity audit | WAF 적용 시 rule match 가능 |

### 금지 추론

- XSS-like 문자열 관찰만으로 브라우저 실행 또는 XSS 성공을 말하지 않는다.

---

## S15 traversal_like

### 목적

Path traversal-like query/path가 어떻게 기록되는지 확인한다.

### 예시 요청

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S15 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/download.php?file=..%2F..%2F..%2Fetc%2Fpasswd&obs_run=${OBS_RUN}&scenario=S15"
```

대체 경로:

```bash
curl -i \
  -H "User-Agent: ${UA_PREFIX}/S15 run=${OBS_RUN}" \
  "${TARGET_BASE_URL}/..%2F..%2Fetc%2Fpasswd?obs_run=${OBS_RUN}&scenario=S15"
```

### 기대 관찰

| 로그 | 기대 |
|---|---|
| `app_security.log` | traversal-like encoded value 관찰 |
| `app_error.log` | optional |
| ModSecurity audit | WAF 적용 시 rule match 가능 |

### 금지 추론

- traversal-like 요청만으로 파일 읽기 성공을 말하지 않는다.
- status/size/content-type만으로 `/etc/passwd` 노출을 단정하지 않는다.

---

## 5. 실행 후 기록할 공통 항목

각 시나리오별로 다음을 기록한다.

```text
scenario_id:
request_command:
expected_status:
actual_status:
security_log_observed:
error_log_observed:
app_log_observed:
waf_log_observed:
evidence_level:
notes:
```

결과 기록은 `lab/observability/observation_matrix_template.md`를 복사해서 사용한다.
