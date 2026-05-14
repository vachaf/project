# 99 Apache 앱 배치별 관측 가능성 비교 계획서

- 문서 상태: 설계 초안
- 작성일: 2026-05-14
- 기준 범위:
  - 웹단에 Apache HTTP Server를 사용하는 애플리케이션 전반
  - 정적 파일 직접 서빙, PHP-FPM/CGI 연계, WAS/앱서버 reverse proxy, WAF 연계 배치 모두 포함
  - reverse proxy는 비교 대상 중 하나이며 필수 전제가 아님
- 관련 문서:
  - `docs/design/99_apache_log_collection_expansion_plan.md`
  - `docs/design/99_apache_log_collection_expansion_scope_correction.md`
  - `lab/observability/scenario_catalog.md`
  - `lab/observability/observation_matrix_template.md`

---

## 1. 목적

이 문서는 Apache를 웹단으로 사용하는 여러 앱 서버 배치에서 동일한 요청 시나리오를 실행하고, 각 배치에서 무엇이 로그로 관찰되는지 비교하기 위한 계획서다.

비교의 목적은 앱 취약성 평가가 아니다. 목적은 다음을 분리하는 것이다.

1. Apache `app_security.log`만으로 관찰 가능한 것
2. Apache `app_error.log`를 붙이면 보강되는 것
3. WAF 로그가 있어야 관찰 가능한 것
4. 앱 런타임 로그가 있어야 관찰 가능한 것
5. DB/app audit 로그 없이는 단정하면 안 되는 것

최종 목표는 LLM 침입 로그 분석 파이프라인에서 사용할 수 있는 증거 계층과 한계선을 데이터로 고정하는 것이다.

---

## 2. 비교 대상 배치

초기 비교 대상은 최소 3종으로 둔다.

| 구분 | 대상 | 목적 |
|---|---|---|
| A | 단순 PHP 샘플 앱 | Apache 직접 처리 baseline |
| B | 실제 PHP 앱, 예: OpenCart/WordPress | 실제 앱 노이즈와 PHP 계층 확인 |
| C | reverse proxy 앱, 예: Juice Shop/Node app | backend proxy 계층과 request ID 전달 확인 |
| D | ModSecurity 적용 앱 | WAF 탐지/차단 로그 optional context 확인 |

D는 선택 확장이다. A~C를 먼저 수행한 뒤 추가한다.

---

## 3. 공통 수집 로그

모든 대상 서버에서 가능한 한 같은 Apache 로그 포맷을 사용한다.

| 로그 | 필수 여부 | 목적 |
|---|---:|---|
| `app_security.log` | 필수 | canonical request evidence |
| `app_access.log` | 권장 | 기존 access log 대조 |
| `app_error.log` | 필수 | Apache 처리 오류/모듈 오류 상관분석 |
| `apache_log_shipper.log` | 권장 | 수집기 동작 상태 확인 |
| PHP-FPM/app log | 선택 | 앱 내부 처리 결과 확인 |
| ModSecurity audit log | 선택 | WAF 룰 매칭/차단 증거 |
| OS/service logs | 선택 | 환경/운영 정황 확인 |

기본 분석은 `app_security.log`를 중심으로 한다. 나머지 로그는 별도 증거 계층으로 연결한다.

---

## 4. 관측 가능성 등급

각 시나리오 결과에는 관측 가능성 등급을 부여한다.

| 등급 | 의미 | 예 |
|---|---|---|
| O0 | 관찰 불가 | 요청 자체가 로그에 없음 |
| O1 | Apache request metadata로 관찰 가능 | method, URI, query, status, bytes |
| O2 | Apache error log까지 붙이면 보강 가능 | 500 원인, proxy timeout, permission error |
| O3 | WAF/app log까지 붙이면 내부 처리 일부 확인 가능 | WAF rule match, app event |
| O4 | DB/app audit까지 있어야 결과 확인 가능 | 로그인 성공, 파일 저장 성공, DB 변경 |

분석 문구는 등급을 반영해야 한다. 예를 들어 O1 수준의 SQLi-like query는 “SQLi-like query가 관찰됨”이라고 표현하고, “SQL injection 성공”으로 표현하지 않는다.

---

## 5. 공통 시나리오 세트

시나리오 정의는 `lab/observability/scenario_catalog.md`를 canonical source로 둔다.

초기 시나리오 범위는 다음이다.

| ID | 이름 | 목적 |
|---|---|---|
| S01 | normal_main | 정상 메인 페이지 요청 |
| S02 | static_css | CSS 정적 파일 요청 |
| S03 | static_js | JS 정적 파일 요청 |
| S04 | query_search | query string 관찰 |
| S05 | not_found | 404 관찰 |
| S06 | forbidden_or_sensitive_path | 403 또는 민감 경로 probe 관찰 |
| S07 | login_get | 로그인 페이지 GET |
| S08 | login_post | 로그인-like POST |
| S09 | upload_like_post | multipart/upload-like 요청 |
| S10 | slow_or_large_request | duration/TTFB/size 관찰 |
| S11 | server_error | 500/error log 연결 |
| S12 | scanner_burst | 반복 요청/스캐너-like 패턴 |
| S13 | sqli_like | SQLi-like query 관찰 |
| S14 | xss_like | XSS-like query 관찰 |
| S15 | traversal_like | path traversal-like query 관찰 |

각 요청에는 `obs_run`과 `scenario` marker를 넣는다.

예:

```bash
curl -H 'User-Agent: obs-test/S04 run=obs_2026_05_14_php_sample' \
  'http://target/search.php?q=test&obs_run=obs_2026_05_14_php_sample&scenario=S04'
```

---

## 6. 실행 단위

각 앱 서버 실험은 run 단위로 기록한다.

필수 메타데이터:

```text
run_id:
target_app:
topology:
apache_version:
os_version:
php_or_app_runtime_version:
apache_modules:
log_format_version:
waf_enabled:
app_log_available:
start_time_kst:
end_time_kst:
scenario_catalog_version:
```

권장 디렉터리 구조:

```text
lab/observability/runs/
  <run_id>/
    raw/
      app_security.log
      app_access.log
      app_error.log
      app_runtime.log
      modsec_audit.log
    exported/
      security.json
      access.json
      error.json
      app_runtime.json
      modsec.json
    notes.md
    observation_matrix.md
```

---

## 7. 비교 질문

각 run은 다음 질문에 답해야 한다.

### 7.1 Apache request evidence

- 요청이 `app_security.log`에 남았는가?
- `method`, `uri`, `query_string`, `protocol`이 기대대로 파싱되었는가?
- `status_code`, `response_body_bytes`, `out_bytes`가 기록되었는가?
- `duration_us`, `ttfb_us`가 기록되었는가?
- `src_ip`, `peer_ip`, `x_forwarded_for`의 의미가 환경과 맞는가?

### 7.2 Apache error context

- `app_error.log`에 관련 오류가 남았는가?
- `request_id` 또는 `error_link_id`로 연결 가능한가?
- 연결 불가능하면 시간/IP/request 근접 매칭이 가능한가?
- error message를 LLM에 원문으로 전달해도 안전한가, 요약해야 하는가?

### 7.3 App/WAF context

- 앱 로그가 존재하는가?
- Apache request ID가 앱 로그와 연결되는가?
- WAF audit log가 존재하는가?
- WAF rule match가 실제 차단인지 탐지만인지 구분되는가?

### 7.4 금지 추론 확인

- `status_code=200`만으로 공격 성공을 말하지 않았는가?
- 응답 크기만으로 파일 노출을 말하지 않았는가?
- 로그인-like POST만으로 로그인 성공을 말하지 않았는가?
- upload-like POST만으로 파일 저장 성공을 말하지 않았는가?
- WAF rule match만으로 침해 성공을 말하지 않았는가?

---

## 8. 앱 배치별 예상 차이

### 8.1 단순 PHP 샘플 앱

예상 특성:

- Apache 직접 처리 baseline으로 가장 해석이 단순하다.
- 정적 파일, PHP endpoint, 404/403/500 관찰이 쉽다.
- 앱 내부 결과는 제한적이다.
- PHP error가 Apache error log 또는 PHP-FPM log에 남을 수 있다.

핵심 확인:

| 항목 | 기대 |
|---|---|
| static resource | O1 |
| query string | O1 |
| PHP error | O2 |
| upload-like POST | O1 |
| upload 저장 성공 | O4 |

### 8.2 실제 PHP 앱

예상 특성:

- 정상 노이즈가 많다.
- 정적 리소스, redirect, session cookie, admin path 요청이 섞인다.
- Apache 로그만으로 로그인 성공/실패를 단정하면 안 된다.
- PHP-FPM/app log가 있으면 내부 처리 결과를 일부 확인할 수 있다.

핵심 확인:

| 항목 | 기대 |
|---|---|
| login page GET | O1 |
| login POST | O1 |
| login success/failure | O4 |
| admin path access | O1 |
| app exception | O2~O3 |

### 8.3 reverse proxy 앱

예상 특성:

- Apache는 웹단 관찰자이고 실제 앱 처리는 backend에서 일어난다.
- backend 연결 실패는 `app_error.log`에서 관찰될 수 있다.
- 앱 내부 결과는 backend app log가 있어야 확인 가능하다.
- `X-Request-ID` 전달이 되면 Apache log와 backend log 조인이 가능하다.

핵심 확인:

| 항목 | 기대 |
|---|---|
| normal proxied request | O1 |
| backend 502/503/504 | O2 |
| login success/failure | O4 |
| app route result | O3~O4 |
| request ID linkage | O3 |

### 8.4 ModSecurity 적용 앱

예상 특성:

- WAF rule ID, anomaly score, block/detect 여부를 관찰할 수 있다.
- WAF 탐지는 공격 성공 증거가 아니다.
- audit log에는 민감정보가 포함될 수 있으므로 LLM 입력은 요약 필드만 사용한다.

핵심 확인:

| 항목 | 기대 |
|---|---|
| SQLi-like query rule match | O3 |
| blocked request | O3 |
| actual compromise | O4 |

---

## 9. 산출물

각 run에서 다음 산출물을 남긴다.

| 산출물 | 위치 | 설명 |
|---|---|---|
| raw logs | `lab/observability/runs/<run_id>/raw/` | 원본 로그 사본 |
| exported JSON | `lab/observability/runs/<run_id>/exported/` | DB/export 결과 |
| notes | `lab/observability/runs/<run_id>/notes.md` | 환경/실행 메모 |
| observation matrix | `lab/observability/runs/<run_id>/observation_matrix.md` | 시나리오별 관측 결과 |
| comparison summary | `lab/observability/runs/<run_id>/summary.md` | 차이점 요약 |

공통 템플릿은 `lab/observability/observation_matrix_template.md`를 사용한다.

---

## 10. 파이프라인 반영 기준

비교 결과는 다음 항목에 반영한다.

1. prepare 단계에서 어떤 context를 추가할지 결정
2. `app_error.log`를 supporting context로 붙일 조건 정의
3. app/WAF 로그를 LLM 입력에 요약 형태로 넣을지 결정
4. Apache-only 한계 문구를 prompt/rubric에 반영
5. Web UI에서 finding과 related context를 분리 표시

반영 시 다음 원칙을 유지한다.

- context-only event를 finding으로 승격하지 않는다.
- Web UI는 read-only를 유지한다.
- status/size/content-type만으로 공격 성공 판단을 하지 않는다.
- 앱 내부 결과는 app/DB audit evidence가 있을 때만 제한적으로 언급한다.

---

## 11. 권장 진행 순서

1. 단순 PHP 샘플 앱에서 S01~S15 수행
2. OpenCart 또는 WordPress에서 동일 시나리오 수행
3. Juice Shop 또는 Node reverse proxy 앱에서 동일 시나리오 수행
4. 필요 시 ModSecurity 적용 후 S13~S15 중심으로 재수행
5. 앱별 observation matrix 작성
6. 배치별 차이점 요약
7. prepare/LLM 입력 확장 후보 선정
8. 별도 구현 계획서 작성

---

## 12. 비범위

이 문서는 다음을 수행하지 않는다.

- 실제 공격 성공 여부 판정
- 취약점 진단 결과 작성
- 운영 서버 설정 변경
- 수집기/DB/파이프라인 코드 수정
- WAF 탐지를 침해 성공으로 승격
- 앱 로그가 없는 상태에서 내부 결과 추정
